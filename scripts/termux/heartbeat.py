#!/usr/bin/env python3
"""Phone-side heartbeat for long-horizon runs.

Runs in a tmux session alongside the training loop. Every N seconds,
reads the latest train_step from the audit log, queries phone state via
termux-battery-status, builds a heartbeat envelope, and pushes it to a
private HF dataset under Architect-Prime. Output is a small JSONL file
(one row per heartbeat) so a viewer can see the run is alive without
cloning the repo.

Usage:
    python heartbeat.py \
        --run-dir ~/polymath/runs/<run_id> \
        --interval 300 \
        --hf-repo Architect-Prime/polymath-telemetry \
        --hf-path heartbeats/<run_id>.jsonl

If HF push fails, queue a pending-upload row locally and keep running.
The training loop is not interrupted.

The ``run-dir/audit.jsonl`` is read-only from this process; never writes.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


def read_audit_tail(audit_path: Path) -> dict:
    """Return the latest audit row plus event-type counts. Tolerant of
    a partial / locked file (the trainer is writing to it).
    """
    if not audit_path.exists():
        return {"audit_present": False}
    try:
        rows = []
        with open(audit_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
        if not rows:
            return {"audit_present": True, "row_count": 0}
        last = rows[-1]
        train_steps = [r for r in rows if r.get("event_type") == "train_step"]
        last_train = train_steps[-1] if train_steps else None
        return {
            "audit_present": True,
            "row_count": len(rows),
            "last_event_type": last.get("event_type"),
            "last_recorded_at": last.get("recorded_at"),
            "last_event_hash": last.get("event_hash"),
            "train_step_count": len(train_steps),
            "last_train_step": last_train["payload"]["step"] if last_train else None,
            "last_train_loss": last_train["payload"]["loss"] if last_train else None,
            "last_grad_norm": last_train["payload"].get("grad_norm") if last_train else None,
            "frozen_drift_observed": any(
                ts["payload"].get("frozen_changed") for ts in train_steps
            ),
        }
    except Exception as e:
        return {"audit_present": True, "read_error": str(e)}


def battery_status() -> dict:
    try:
        out = subprocess.run(
            ["termux-battery-status"], capture_output=True, text=True, timeout=10
        ).stdout
        return json.loads(out)
    except Exception as e:
        return {"error": repr(e)}


def thermal_zones_quick() -> dict:
    """Read CPU + battery temps via /sys/class/thermal/. Sub-second."""
    out = {}
    base = Path("/sys/class/thermal/")
    if not base.exists():
        return {"error": "no /sys/class/thermal"}
    for d in sorted(base.glob("thermal_zone*")):
        try:
            ttype = (d / "type").read_text().strip()
            tval = int((d / "temp").read_text().strip()) / 1000.0
            if any(k in ttype for k in ("cpu", "skin", "battery", "aoss")):
                out[ttype] = tval
        except Exception:
            continue
    return out


def disk_free_gb() -> float | None:
    try:
        s = os.statvfs(os.path.expanduser("~"))
        return s.f_bavail * s.f_frsize / 1e9
    except Exception:
        return None


def hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def utc_now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def push_to_hf(repo_id: str, path_in_repo: str, content: str, repo_type: str = "dataset") -> tuple[bool, str]:
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return False, "huggingface_hub not installed"
    try:
        import io
        api = HfApi()
        api.upload_file(
            path_or_fileobj=io.BytesIO(content.encode("utf-8")),
            path_in_repo=path_in_repo,
            repo_id=repo_id,
            repo_type=repo_type,
            commit_message=f"heartbeat {path_in_repo}",
        )
        return True, "ok"
    except Exception as e:
        return False, repr(e)[:200]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--interval", type=int, default=300, help="seconds between heartbeats; default 300 (5 min)")
    p.add_argument("--hf-repo", default="Architect-Prime/polymath-telemetry")
    p.add_argument("--hf-path-prefix", default="heartbeats")
    p.add_argument("--max-iters", type=int, default=0, help="0 = forever")
    args = p.parse_args()

    run_dir = Path(args.run_dir)
    run_id = run_dir.name
    audit_path = run_dir / "audit.jsonl"

    local_hb_path = run_dir / "heartbeats.jsonl"
    pending_path = run_dir / "pending_uploads.jsonl"

    print(f"[heartbeat] starting; run_dir={run_dir}; interval={args.interval}s; hf_repo={args.hf_repo}")

    iter_count = 0
    while True:
        iter_count += 1
        rec = {
            "schema_version": "1.0.0",
            "ts": utc_now_iso(),
            "run_id": run_id,
            "host": hostname(),
            "iter": iter_count,
            "audit": read_audit_tail(audit_path),
            "battery": battery_status(),
            "thermal_c": thermal_zones_quick(),
            "disk_free_gb": disk_free_gb(),
        }
        line = json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n"

        # Always append to local file
        with open(local_hb_path, "a", encoding="utf-8") as f:
            f.write(line)

        # Upload the *full* heartbeats.jsonl as a single replace each
        # interval - simple and idempotent. (Could differential-upload
        # later if size matters.)
        path_in_repo = f"{args.hf_path_prefix}/{run_id}.jsonl"
        ok, detail = push_to_hf(args.hf_repo, path_in_repo, local_hb_path.read_text())
        if ok:
            print(f"[heartbeat {iter_count}] hf push ok -> {args.hf_repo}/{path_in_repo}")
        else:
            print(f"[heartbeat {iter_count}] hf push FAIL: {detail}; queued pending")
            with open(pending_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": rec["ts"], "iter": iter_count, "err": detail}) + "\n")

        if args.max_iters and iter_count >= args.max_iters:
            print(f"[heartbeat] reached max_iters={args.max_iters}; exiting")
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
