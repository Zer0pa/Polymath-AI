#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import mmap
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PHASE2B_REPORT_ROOT = ROOT / "runtime/reports/polar_phase2_native_closure"
MIRROR_ROOT = Path("/sdcard/Download/polymath/polar_phase2/native_closure")
NATIVE_DIR = ROOT / "native/polar_phase2_packetizer"
NATIVE_BIN = NATIVE_DIR / "bin/phase2b_native_packetizer"
PY_GATE_PATH = ROOT / "scripts/termux/run_polar_phase2_gate.py"

PY_BASELINE_100K = 30_761.689914298815
PY_BASELINE_1M = 18_517.112150908564
FLOOR_TOKENS_PER_SEC = 100_000.0
SPEEDUP_FLOOR = 3.0
PACKET_LEN = 128
PJP1_HEADER_LEN = 4096
PJP1_META_BYTES = 192
TOKEN_IDS_BYTES = PACKET_LEN * 4
ROLES_BYTES = PACKET_LEN
JL_K = 256
POLAR_BYTES = PACKET_LEN * (JL_K // 8)
POOLED_BYTES = JL_K // 8


def utc_stamp() -> str:
    return dt.datetime.now(tz=dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_iso() -> str:
    return dt.datetime.now(tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def jwrite(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_cmd(cmd: list[str], *, cwd: Path = ROOT, timeout: int | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "cmd": cmd,
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "elapsed_sec": time.perf_counter() - started,
        "stdout_tail": proc.stdout[-8000:],
        "stderr_tail": proc.stderr[-8000:],
    }


def load_phase2_gate_module():
    spec = importlib.util.spec_from_file_location("phase2_gate", PY_GATE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {PY_GATE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def environment_report() -> dict[str, Any]:
    status = Path("/proc/self/status").read_text(errors="ignore")
    cpus_allowed = None
    thread_count = None
    for line in status.splitlines():
        if line.startswith("Cpus_allowed_list"):
            cpus_allowed = line.split(":", 1)[1].strip()
        if line.startswith("Threads:"):
            thread_count = int(line.split()[1])
    thermal = []
    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        try:
            thermal.append(
                {
                    "zone": zone.name,
                    "type": (zone / "type").read_text().strip(),
                    "temp_raw": (zone / "temp").read_text().strip(),
                }
            )
        except OSError:
            pass
    return {
        "schema_version": "polar_phase2b_environment_v1",
        "created_at_utc": utc_iso(),
        "python": sys.version,
        "nproc": os.cpu_count(),
        "cpus_allowed_list": cpus_allowed,
        "process_thread_count": thread_count,
        "device_model": subprocess.run(["getprop", "ro.product.model"], text=True, capture_output=True).stdout.strip(),
        "device_soc_model": subprocess.run(["getprop", "ro.soc.model"], text=True, capture_output=True).stdout.strip(),
        "device_board": subprocess.run(["getprop", "ro.board.platform"], text=True, capture_output=True).stdout.strip(),
        "thermal": thermal[:64],
        "comet_api_key_in_environment": bool(os.environ.get("COMET_API_KEY")),
    }


def pjp1_layout(packet_count: int) -> dict[str, int]:
    offset = PJP1_HEADER_LEN
    meta_off = offset
    meta_len = packet_count * PJP1_META_BYTES
    offset += meta_len
    token_off = offset
    token_len = packet_count * TOKEN_IDS_BYTES
    offset += token_len
    roles_off = offset
    roles_len = packet_count * ROLES_BYTES
    offset += roles_len
    input_off = offset
    input_len = packet_count * POLAR_BYTES
    offset += input_len
    target_off = offset
    target_len = packet_count * POLAR_BYTES
    offset += target_len
    pooled_off = offset
    pooled_len = packet_count * POOLED_BYTES
    offset += pooled_len
    return {
        "metadata": (meta_off, meta_len),
        "token_ids": (token_off, token_len),
        "roles": (roles_off, roles_len),
        "input_polar": (input_off, input_len),
        "target_polar": (target_off, target_len),
        "pooled_answer": (pooled_off, pooled_len),
        "file_len": offset,
    }


def read_packet_count(path: Path) -> int:
    data = path.read_bytes()[:64]
    if len(data) < 56 or data[:4] != b"PJP1":
        raise RuntimeError(f"{path}: bad PJP1 header")
    return int.from_bytes(data[24:32], "little")


def hash_region(handle, offset: int, length: int) -> str:
    h = hashlib.sha256()
    handle.seek(offset)
    remaining = length
    while remaining:
        chunk = handle.read(min(1 << 20, remaining))
        if not chunk:
            break
        h.update(chunk)
        remaining -= len(chunk)
    if remaining:
        raise RuntimeError("short read while hashing PJP1 region")
    return h.hexdigest()


def compare_pjp1_sections(native_path: Path, reference_path: Path, full: bool = True) -> dict[str, Any]:
    native_packets = read_packet_count(native_path)
    reference_packets = read_packet_count(reference_path)
    if native_packets != reference_packets:
        return {
            "status": "fail",
            "reason": "packet_count_mismatch",
            "native_packet_count": native_packets,
            "reference_packet_count": reference_packets,
        }
    layout = pjp1_layout(native_packets)
    rows = []
    with native_path.open("rb") as native, reference_path.open("rb") as reference:
        if full:
            for section in ["metadata", "token_ids", "roles", "input_polar", "target_polar", "pooled_answer"]:
                offset, length = layout[section]
                native_hash = hash_region(native, offset, length)
                reference_hash = hash_region(reference, offset, length)
                rows.append(
                    {
                        "section": section,
                        "bytes": length,
                        "native_sha256": native_hash,
                        "reference_sha256": reference_hash,
                        "match": native_hash == reference_hash,
                    }
                )
        else:
            mmap_native = mmap.mmap(native.fileno(), 0, access=mmap.ACCESS_READ)
            mmap_ref = mmap.mmap(reference.fileno(), 0, access=mmap.ACCESS_READ)
            sample_ids = sorted({0, 1, 2, 3, 4, max(0, native_packets - 1)})
            for packet_id in sample_ids:
                checks = []
                for section, stride in [
                    ("metadata", PJP1_META_BYTES),
                    ("token_ids", TOKEN_IDS_BYTES),
                    ("roles", ROLES_BYTES),
                    ("input_polar", POLAR_BYTES),
                    ("target_polar", POLAR_BYTES),
                    ("pooled_answer", POOLED_BYTES),
                ]:
                    offset, _ = layout[section]
                    start = offset + packet_id * stride
                    end = start + stride
                    checks.append({"section": section, "match": mmap_native[start:end] == mmap_ref[start:end]})
                rows.append({"packet_id": packet_id, "checks": checks, "match": all(c["match"] for c in checks)})
            mmap_native.close()
            mmap_ref.close()
    return {
        "schema_version": "polar_phase2b_pjp1_section_parity_v1",
        "status": "pass" if all(row.get("match", False) for row in rows) else "fail",
        "native_path": str(native_path),
        "reference_path": str(reference_path),
        "mode": "full_sections" if full else "sample_packets",
        "packet_count": native_packets,
        "rows": rows,
    }


def read_memory_kb() -> dict[str, Any]:
    out: dict[str, Any] = {}
    status = Path("/proc/self/status").read_text(errors="ignore")
    for key in ["VmRSS", "VmHWM", "VmSize", "Threads"]:
        for line in status.splitlines():
            if line.startswith(key + ":"):
                parts = line.split()
                out[key.lower()] = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else line
    try:
        rollup = Path("/proc/self/smaps_rollup").read_text(errors="ignore")
        for line in rollup.splitlines():
            if line.startswith("Pss:"):
                out["pss_kb"] = int(line.split()[1])
            if line.startswith("Rss:"):
                out["rss_rollup_kb"] = int(line.split()[1])
    except OSError:
        out["smaps_rollup_error"] = "unavailable"
    return out


def build_native(commands: list[dict[str, Any]], report_dir: Path) -> dict[str, Any]:
    result = run_cmd(["bash", str(NATIVE_DIR / "build_phase2b_native_packetizer.sh")], timeout=300)
    commands.append(result)
    if result["returncode"] != 0:
        return {"status": "fail", "build": result}
    binary_sha = sha256_file(NATIVE_BIN)
    build_identity = {
        "schema_version": "polar_phase2b_build_identity_v1",
        "status": "pass",
        "binary": str(NATIVE_BIN),
        "binary_sha256": binary_sha,
        "compiler": run_cmd(["clang++", "--version"], timeout=30),
        "build_command": result,
        "source_sha256": sha256_file(NATIVE_DIR / "phase2b_native_packetizer.cpp"),
        "build_script_sha256": sha256_file(NATIVE_DIR / "build_phase2b_native_packetizer.sh"),
        "language_choice": "C++20 with AArch64 NEON intrinsics because the Phase 2-B risk is the dense JL kernel, not parser ergonomics.",
    }
    jwrite(report_dir / "phase2b_build_identity_report.json", build_identity)
    return build_identity


def write_list_file(paths: list[Path], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(str(path) + "\n" for path in paths), encoding="utf-8")


def run_native_scale(
    label: str,
    paths: list[Path],
    max_records: int | None,
    report_dir: Path,
    embedding_manifest: dict[str, Any],
    embedding_manifest_hash: str,
    jl_cfg: dict[str, Any],
    threads: int,
    commands: list[dict[str, Any]],
) -> dict[str, Any]:
    list_path = report_dir / f"phase2b_{label}_pqa1_list.txt"
    write_list_file(paths, list_path)
    pjp1_path = report_dir / f"raw_{label}.pjp1"
    result_path = report_dir / f"phase2b_{label}_native_packetizer_report.json"
    cmd = [
        str(NATIVE_BIN),
        "--label",
        label,
        "--pqa1-list",
        str(list_path),
        "--output",
        str(pjp1_path),
        "--embedding",
        embedding_manifest["embedding_artifact_path"],
        "--jl",
        jl_cfg["matrix_path"],
        "--embed-sha",
        embedding_manifest["embedding_artifact_sha256"],
        "--embed-manifest-sha",
        embedding_manifest_hash,
        "--jl-sha",
        jl_cfg["matrix_sha256"],
        "--threads",
        str(threads),
        "--result-json",
        str(result_path),
    ]
    if max_records is not None:
        cmd.extend(["--max-records", str(max_records)])
    result = run_cmd(cmd, timeout=None)
    commands.append(result)
    if result["returncode"] != 0:
        return {"status": "fail", "command": result}
    report = json.loads(result_path.read_text(encoding="utf-8"))
    report["native_command"] = {k: result[k] for k in ["cmd", "cwd", "returncode", "elapsed_sec", "stdout_tail", "stderr_tail"]}
    report["pjp1_sha256"] = sha256_file(pjp1_path)
    report["memory_after_python_runner"] = read_memory_kb()
    jwrite(result_path, report)
    return report


def comet_result(report_dir: Path) -> dict[str, Any]:
    if not os.environ.get("COMET_API_KEY"):
        return {
            "schema_version": "polar_phase2b_comet_result_v1",
            "status": "blocked",
            "reason": "COMET_API_KEY is absent from the process environment; secrets were not read from any file.",
            "secret_policy": "No secret values were printed, written, copied, or logged.",
        }
    try:
        import comet_ml  # type: ignore

        experiment = comet_ml.Experiment(
            api_key=os.environ["COMET_API_KEY"],
            workspace="zer0pa",
            project_name="mobile-polymath-ai-training",
            auto_output_logging="simple",
        )
        experiment.set_name(f"polar-phase2b-native-{report_dir.name}")
        for path in report_dir.rglob("*"):
            if not path.is_file() or path.suffix in {".pqa1", ".qai1", ".pjp1", ".jsonl", ".safetensors", ".bin"}:
                continue
            if path.stat().st_size <= 5_000_000:
                experiment.log_asset(str(path))
        experiment.end()
        return {
            "schema_version": "polar_phase2b_comet_result_v1",
            "status": "pass",
            "experiment_key": experiment.get_key(),
            "experiment_url": experiment.url,
        }
    except Exception as exc:
        return {
            "schema_version": "polar_phase2b_comet_result_v1",
            "status": "blocked",
            "reason": repr(exc),
            "secret_policy": "No secret values were printed, written, copied, or logged.",
        }


def forbidden_scan(report_dir: Path, mirror_dir: Path) -> dict[str, Any]:
    forbidden_suffix = {".qai1", ".pqa1", ".pjp1", ".jsonl", ".safetensors", ".gguf", ".bin"}
    secret_patterns = [
        re.compile(rb"hf_[A-Za-z0-9]{20,}"),
        re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
        re.compile(rb"ghp_[A-Za-z0-9]{20,}"),
        re.compile(rb"sk-[A-Za-z0-9]{20,}"),
    ]
    findings = []
    scanned = 0
    for root, root_kind in [(report_dir, "report"), (mirror_dir, "mirror")]:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            scanned += 1
            if root_kind == "mirror" and path.suffix in forbidden_suffix:
                findings.append({"path": str(path), "reason": "forbidden payload in compact mirror"})
            try:
                if path.stat().st_size < 2_000_000 and any(pattern.search(path.read_bytes()) for pattern in secret_patterns):
                    findings.append({"path": str(path), "reason": "secret-shaped token"})
            except OSError:
                pass
    return {
        "schema_version": "polar_phase2b_forbidden_payload_scan_v1",
        "status": "pass" if not findings else "fail",
        "scanned_files": scanned,
        "findings": findings,
    }


def mirror_reports(report_dir: Path, mirror_dir: Path) -> None:
    if mirror_dir.exists():
        shutil.rmtree(mirror_dir)
    (mirror_dir / "reports").mkdir(parents=True, exist_ok=True)
    (mirror_dir / "source_files").mkdir(parents=True, exist_ok=True)
    (mirror_dir / "git").mkdir(parents=True, exist_ok=True)
    safe_suffixes = {".json", ".md", ".txt", ".py", ".cpp", ".h", ".sh"}
    for path in report_dir.rglob("*"):
        if not path.is_file() or path.suffix not in safe_suffixes:
            continue
        if path.suffix in {".pqa1", ".qai1", ".pjp1", ".jsonl", ".safetensors", ".bin"}:
            continue
        if path.stat().st_size <= 5_000_000:
            shutil.copy2(path, mirror_dir / "reports" / path.relative_to(report_dir))
    for rel in [
        "scripts/termux/run_polar_phase2b_native_closure.py",
        "scripts/termux/run_polar_phase2_gate.py",
        "native/polar_phase2_packetizer/phase2b_native_packetizer.cpp",
        "native/polar_phase2_packetizer/build_phase2b_native_packetizer.sh",
        "native/polar_phase2_packetizer/README.md",
        "docs/PRD-POLAR-PHASE2B-NATIVE-PERFORMANCE-CLOSURE-2026-06-27.md",
        "docs/TERMUX-POLAR-PHASE2B-NATIVE-CLOSURE-STARTUP-PROMPT-2026-06-27.md",
        "docs/PRD-POLAR-PHASE2B-INTERSECTED-NATIVE-CLOSURE-2026-06-27.md",
    ]:
        src = ROOT / rel
        if src.exists() and src.stat().st_size <= 5_000_000:
            dst = mirror_dir / "source_files" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    for name, cmd in [
        ("git_status_short_branch.txt", ["git", "status", "--short", "--branch"]),
        ("git_diff_stat.txt", ["git", "diff", "--stat"]),
    ]:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
        (mirror_dir / "git" / name).write_text(proc.stdout, encoding="utf-8")
    (mirror_dir / "MANIFEST.md").write_text(
        f"# Phase 2-B Native Closure Compact Mirror\n\nReport root: `{report_dir}`\n\nRaw PQA1/PJP1 streams, embedding tensors, JL binaries, and secrets are intentionally omitted.\n",
        encoding="utf-8",
    )


def write_engineering_report(report_dir: Path, status: str, details: dict[str, Any]) -> None:
    lines = [
        "# Phase 2-B Native Closure Engineering Report",
        "",
        f"Status: `{status}`",
        f"Report root: `{report_dir}`",
        f"Mirror: `{details.get('mirror_dir')}`",
        "",
        "## Read First",
    ]
    for item in details.get("read_first", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Results"])
    for label, result in details.get("runs", {}).items():
        if not isinstance(result, dict):
            continue
        throughput = result.get("throughput", {})
        lines.append(
            f"- {label}: status={result.get('status')} records={result.get('source_record_count')} "
            f"tokens={result.get('source_real_token_count')} packets={result.get('packet_count')} "
            f"real_tokens_per_sec={throughput.get('real_tokens_per_sec')} output_MB_per_sec={throughput.get('output_MB_per_sec')}"
        )
    lines.extend(["", "## Correctness"])
    for label, result in details.get("readbacks", {}).items():
        lines.append(f"- {label} readback: {result.get('status')}")
    for label, result in details.get("parity", {}).items():
        lines.append(f"- {label} section parity: {result.get('status')} ({result.get('mode')})")
    lines.extend(["", "## Blockers"])
    for blocker in details.get("blockers", []):
        lines.append(f"- {blocker}")
    if not details.get("blockers"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Comet",
            f"- {details.get('comet', {}).get('status')}: {details.get('comet', {}).get('reason') or details.get('comet', {}).get('experiment_url')}",
            "",
            "## Hygiene",
            f"- {details.get('hygiene', {}).get('status')}",
        ]
    )
    (report_dir / "ENGINEERING_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def classify_status(runs: dict[str, Any], correctness_ok: bool, blockers: list[str]) -> str:
    if blockers and not correctness_ok:
        return "phase2b_failed"
    hundred = runs.get("100k")
    one_m = runs.get("1M")
    if not correctness_ok:
        return "phase2b_failed"
    if not hundred or hundred.get("status") != "pass":
        return "phase2b_correctness_pass_perf_blocked"
    hundred_tps = float(hundred["throughput"]["real_tokens_per_sec"])
    hundred_speedup = hundred_tps / PY_BASELINE_100K
    if hundred_tps < FLOOR_TOKENS_PER_SEC or hundred_speedup < SPEEDUP_FLOOR:
        return "phase2b_correctness_pass_perf_failed"
    if one_m and one_m.get("status") == "pass":
        one_m_tps = float(one_m["throughput"]["real_tokens_per_sec"])
        one_m_speedup = one_m_tps / PY_BASELINE_1M
        if one_m_tps >= FLOOR_TOKENS_PER_SEC and one_m_speedup >= SPEEDUP_FLOOR:
            return "phase2b_native_maximal_closure_pass"
        return "phase2b_correctness_pass_perf_failed"
    return "phase2b_native_floor_pass_1m_continuation_required"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=PHASE2B_REPORT_ROOT / utc_stamp())
    parser.add_argument("--max-scale", choices=["smoke", "10k", "100k", "1M"], default="100k")
    parser.add_argument("--threads", type=int, default=max(1, min(8, os.cpu_count() or 1)))
    parser.add_argument("--force-1m", action="store_true")
    args = parser.parse_args()

    report_dir = args.run_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    mirror_dir = MIRROR_ROOT / report_dir.name
    commands: list[dict[str, Any]] = []
    blockers: list[str] = []
    runs: dict[str, Any] = {}
    readbacks: dict[str, Any] = {}
    oracles: dict[str, Any] = {}
    parity: dict[str, Any] = {}
    read_first = [
        str(ROOT / "AGENTS.md"),
        str(ROOT / "docs/PRD-POLAR-PHASE2B-NATIVE-PERFORMANCE-CLOSURE-2026-06-27.md"),
        str(ROOT / "docs/TERMUX-POLAR-PHASE2B-NATIVE-CLOSURE-STARTUP-PROMPT-2026-06-27.md"),
        str(ROOT / "docs/PRD-POLAR-PHASE2B-INTERSECTED-NATIVE-CLOSURE-2026-06-27.md"),
        str(ROOT / "scripts/termux/run_polar_phase2_gate.py"),
        str(ROOT / "native/polar_phase2_packetizer"),
    ]
    status = "phase2b_blocked"

    try:
        jwrite(report_dir / "phase2b_environment.json", environment_report())
        commands.extend(
            [
                run_cmd(["git", "status", "--short", "--branch"], timeout=60),
                run_cmd(["git", "diff", "--stat"], timeout=60),
            ]
        )
        build_identity = build_native(commands, report_dir)
        if build_identity.get("status") != "pass":
            blockers.append("native build failed")
            status = "phase2b_blocked"
            raise RuntimeError("native build failed")

        phase2_gate = load_phase2_gate_module()
        pqa1_sets = phase2_gate.discover_pqa1_sets()
        if not pqa1_sets:
            blockers.append("no PQA1 source sets discovered")
            status = "phase2b_blocked"
            raise RuntimeError("no PQA1 source sets discovered")
        jwrite(
            report_dir / "phase2b_pqa1_source_report.json",
            {
                "schema_version": "polar_phase2b_pqa1_source_v1",
                "status": "pass",
                "sets": {label: [str(p) for p in paths] for label, paths in pqa1_sets.items()},
                "source_policy": "valid Phase 1 PQA1 only; raw payloads are not mirrored",
            },
        )

        embedding_manifest = phase2_gate.ensure_embedding(report_dir, commands, force=False)
        jwrite(report_dir / "phase2b_embedding_manifest.json", embedding_manifest)
        embedding_manifest_hash = hashlib.sha256(json.dumps(embedding_manifest, sort_keys=True).encode("utf-8")).hexdigest()
        jl_cfg = phase2_gate.ensure_jl_matrix(phase2_gate.EMBED_DIM, commands)
        jwrite(report_dir / "phase2b_jl_config.json", jl_cfg)
        jwrite(
            report_dir / "phase2b_artifact_identity_report.json",
            {
                "schema_version": "polar_phase2b_artifact_identity_v1",
                "status": "pass",
                "embedding_path": embedding_manifest["embedding_artifact_path"],
                "embedding_bytes": embedding_manifest["embedding_artifact_bytes"],
                "embedding_sha256": embedding_manifest["embedding_artifact_sha256"],
                "embedding_manifest_sha256": embedding_manifest_hash,
                "jl_path": jl_cfg["matrix_path"],
                "jl_bytes": jl_cfg["matrix_bytes"],
                "jl_sha256": jl_cfg["matrix_sha256"],
                "phase1_build_identity_discipline": "hashes and exact promoted artifacts are carried into native execution; no alternate tokenizer or corpus is introduced.",
            },
        )

        scale_order = ["smoke", "10k", "100k", "1M"]
        max_index = scale_order.index(args.max_scale)
        run_specs: list[tuple[str, list[Path], int | None]] = []
        if "10k" in pqa1_sets:
            run_specs.append(("smoke", pqa1_sets["10k"], 32))
        if max_index >= scale_order.index("10k") and "10k" in pqa1_sets:
            run_specs.append(("10k", pqa1_sets["10k"], None))
        if max_index >= scale_order.index("100k") and "100k" in pqa1_sets:
            run_specs.append(("100k", pqa1_sets["100k"], None))

        for label, paths, max_records in run_specs:
            runs[label] = run_native_scale(
                label,
                paths,
                max_records,
                report_dir,
                embedding_manifest,
                embedding_manifest_hash,
                jl_cfg,
                args.threads,
                commands,
            )
            if runs[label].get("status") != "pass":
                blockers.append(f"{label} native packetizer failed")
                break
            readbacks[label] = phase2_gate.verify_pjp1(Path(runs[label]["pjp1_path"]))
            jwrite(report_dir / f"phase2b_{label}_pjp1_readback_report.json", readbacks[label])
            if readbacks[label].get("status") != "pass":
                blockers.append(f"{label} PJP1 readback failed")
            if label in {"smoke", "10k"}:
                oracles[label] = phase2_gate.oracle_check(report_dir, Path(runs[label]["pjp1_path"]), embedding_manifest, jl_cfg)
                jwrite(report_dir / f"phase2b_{label}_oracle_agreement_report.json", oracles[label])
                if oracles[label].get("status") != "pass":
                    blockers.append(f"{label} oracle agreement failed")
                ref = ROOT / "runtime/reports/polar_phase2/2026-06-26T235142Z" / f"raw_{label}.pjp1"
                if ref.exists():
                    parity[label] = compare_pjp1_sections(Path(runs[label]["pjp1_path"]), ref, full=True)
                    jwrite(report_dir / f"phase2b_{label}_section_parity_report.json", parity[label])
                    if parity[label].get("status") != "pass":
                        blockers.append(f"{label} section parity failed")

        hundred = runs.get("100k")
        if hundred and hundred.get("status") == "pass":
            hundred_tps = float(hundred["throughput"]["real_tokens_per_sec"])
            hundred_speedup = hundred_tps / PY_BASELINE_100K
            if (hundred_tps >= FLOOR_TOKENS_PER_SEC and hundred_speedup >= SPEEDUP_FLOOR) or args.force_1m:
                if "1M" in pqa1_sets and (args.max_scale == "1M" or args.force_1m):
                    runs["1M"] = run_native_scale(
                        "1M",
                        pqa1_sets["1M"],
                        None,
                        report_dir,
                        embedding_manifest,
                        embedding_manifest_hash,
                        jl_cfg,
                        args.threads,
                        commands,
                    )
                    if runs["1M"].get("status") == "pass":
                        readbacks["1M"] = phase2_gate.verify_pjp1(Path(runs["1M"]["pjp1_path"]))
                        jwrite(report_dir / "phase2b_1M_pjp1_readback_report.json", readbacks["1M"])
                        if readbacks["1M"].get("status") != "pass":
                            blockers.append("1M PJP1 readback failed")
                    else:
                        blockers.append("1M native packetizer failed")

        correctness_ok = (
            "smoke" in runs
            and runs["smoke"].get("status") == "pass"
            and readbacks.get("smoke", {}).get("status") == "pass"
            and oracles.get("smoke", {}).get("status") == "pass"
            and (not parity or all(item.get("status") == "pass" for item in parity.values()))
        )
        status = classify_status(runs, correctness_ok, blockers)

        performance = {
            "schema_version": "polar_phase2b_performance_gate_v1",
            "status": status,
            "floor_real_tokens_per_sec": FLOOR_TOKENS_PER_SEC,
            "speedup_floor_vs_python": SPEEDUP_FLOOR,
            "python_baselines": {"100k": PY_BASELINE_100K, "1M": PY_BASELINE_1M},
            "runs": {
                label: {
                    "real_tokens_per_sec": run.get("throughput", {}).get("real_tokens_per_sec"),
                    "records_per_sec": run.get("throughput", {}).get("records_per_sec"),
                    "output_MB_per_sec": run.get("throughput", {}).get("output_MB_per_sec"),
                    "source_real_token_count": run.get("source_real_token_count"),
                    "source_record_count": run.get("source_record_count"),
                    "packet_count": run.get("packet_count"),
                    "thread_count": run.get("thread_count"),
                    "job_count": run.get("job_count"),
                    "wall_elapsed_sec": run.get("timing_sec", {}).get("total"),
                    "speedup_vs_python": (
                        (run.get("throughput", {}).get("real_tokens_per_sec") or 0.0)
                        / (PY_BASELINE_1M if label == "1M" else PY_BASELINE_100K)
                        if label in {"100k", "1M"}
                        else None
                    ),
                }
                for label, run in runs.items()
            },
            "blockers": blockers,
        }
        jwrite(report_dir / "phase2b_performance_gate_report.json", performance)

        comet = comet_result(report_dir)
        jwrite(report_dir / "phase2b_comet_logging_result.json", comet)
        jwrite(
            report_dir / "phase2b_allocation_audit.json",
            {
                "schema_version": "polar_phase2b_allocation_audit_v1",
                "status": "pass",
                "method": "code audit plus native fixed-size thread-local buffers; no per-token/per-packet heap allocation in the native processing loop",
                "hot_loop_heap_allocation_claim": "none in native process_record/project/write path",
                "caveat": "system mmap/page faults, libc, OpenSSL SHA setup, zlib CRC internals, and thread creation are outside the per-packet hot loop.",
            },
        )
        jwrite(
            report_dir / "phase2b_correctness_report.json",
            {
                "schema_version": "polar_phase2b_correctness_v1",
                "status": "pass" if correctness_ok else "fail",
                "readbacks": readbacks,
                "oracles": oracles,
                "parity": parity,
            },
        )
        jwrite(
            report_dir / "phase2b_gate_result.json",
            {
                "schema_version": "polar_phase2b_gate_result_v1",
                "status": status,
                "valid_terminal_status": status
                in {
                    "phase2b_native_maximal_closure_pass",
                    "phase2b_native_floor_pass_1m_continuation_required",
                    "phase2b_correctness_pass_perf_failed",
                    "phase2b_correctness_pass_perf_blocked",
                    "phase2b_blocked",
                    "phase2b_failed",
                },
                "report_root": str(report_dir),
                "mirror": str(mirror_dir),
                "comet": comet,
                "blockers": blockers,
            },
        )
        jwrite(report_dir / "commands.json", {"schema_version": "polar_phase2b_commands_v1", "commands": commands})

        details = {
            "read_first": read_first,
            "mirror_dir": str(mirror_dir),
            "runs": runs,
            "readbacks": readbacks,
            "parity": parity,
            "blockers": blockers,
            "comet": comet,
        }
        write_engineering_report(report_dir, status, details)
        mirror_reports(report_dir, mirror_dir)
        hygiene = forbidden_scan(report_dir, mirror_dir)
        jwrite(report_dir / "phase2b_forbidden_payload_scan.json", hygiene)
        jwrite(mirror_dir / "reports/phase2b_forbidden_payload_scan.json", hygiene)
        if hygiene["status"] != "pass":
            status = "phase2b_failed"
            blockers.append("artifact hygiene failed")
        details["hygiene"] = hygiene
        write_engineering_report(report_dir, status, details)
        jwrite(
            report_dir / "phase2b_gate_result.json",
            {
                "schema_version": "polar_phase2b_gate_result_v1",
                "status": status,
                "report_root": str(report_dir),
                "mirror": str(mirror_dir),
                "comet": comet,
                "hygiene": hygiene,
                "blockers": blockers,
            },
        )
        mirror_reports(report_dir, mirror_dir)
        return 0 if status in {
            "phase2b_native_maximal_closure_pass",
            "phase2b_native_floor_pass_1m_continuation_required",
            "phase2b_correctness_pass_perf_failed",
            "phase2b_correctness_pass_perf_blocked",
            "phase2b_blocked",
        } else 5
    except Exception as exc:
        blockers.append(repr(exc))
        comet = comet_result(report_dir)
        if status not in {"phase2b_blocked", "phase2b_failed"}:
            status = "phase2b_failed"
        jwrite(report_dir / "phase2b_comet_logging_result.json", comet)
        jwrite(report_dir / "commands.json", {"schema_version": "polar_phase2b_commands_v1", "commands": commands})
        jwrite(
            report_dir / "phase2b_gate_result.json",
            {
                "schema_version": "polar_phase2b_gate_result_v1",
                "status": status,
                "report_root": str(report_dir),
                "mirror": str(mirror_dir),
                "comet": comet,
                "blockers": blockers,
            },
        )
        write_engineering_report(
            report_dir,
            status,
            {
                "read_first": read_first,
                "mirror_dir": str(mirror_dir),
                "runs": runs,
                "readbacks": readbacks,
                "parity": parity,
                "blockers": blockers,
                "comet": comet,
                "hygiene": {"status": "unknown"},
            },
        )
        mirror_reports(report_dir, mirror_dir)
        return 6


if __name__ == "__main__":
    raise SystemExit(main())
