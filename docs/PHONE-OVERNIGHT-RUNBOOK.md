# Phase 1A overnight chain — runbook for fridge mode

**Audience:** zero-coder operator with a REDMAGIC 10 Pro / SM8750. You connect the phone over USB, type one command, disconnect, put it in the fridge.

**What runs:** an inference loop on the phone's Hexagon NPU using the Phase 0G AOT artifacts (D-030 / D-031). Each iteration runs either a single Qwen2.5-1.5B transformer block (fast) or all 26 layers of the ELO frozen middle (slow). Telemetry — battery, thermal, memory, disk, per-inference timing — is appended to a hash-chained JSONL audit log on `/sdcard/Polymath/phase1a/`. Every 10 iterations the audit log is pushed to a private HF dataset so you can monitor live from any browser without reconnecting the phone.

## What the operator sees during execution

**Live monitoring (any browser, any device):**

```
https://huggingface.co/datasets/Architect-Prime/polymath-telemetry/blob/main/phase1a/<run_id>/audit.jsonl
```

The `<run_id>` is printed at startup (format `YYYYMMDDTHHmmSSZ_phase1a_overnight`). HF auto-renders JSONL — you'll see one row per inference batch with timing + battery + thermal data. Files refresh every ~2 minutes (every 10 iterations).

## Pre-conditions (already in place from this session)

- `/data/local/tmp/qairt-2.44/` — QAIRT 2.44.0.260225 aarch64-android (579 MB)
- `/data/local/tmp/phase1a/qwen_block.qnn.bin` (90 MB) and `qwen_frozen_subgraph.qnn.bin` (2.3 GB)
- `/data/local/tmp/phase1a/input.bin` + `input_list.txt` (synthetic FP32 zeros — 1×16×1536)
- `/sdcard/Polymath/.hf-token` (HF token for live telemetry push)
- `/sdcard/Polymath/phase1a/overnight_inference.sh` (the runner)

## Start the chain

From the host (Mac, with `adb` connected):

```bash
adb shell '
  rm -f /sdcard/Polymath/phase1a/STOP /sdcard/Polymath/phase1a/audit.jsonl /sdcard/Polymath/phase1a/hf_push.log
  nohup setsid sh /sdcard/Polymath/phase1a/overnight_inference.sh \
    > /sdcard/Polymath/phase1a/runner.log 2>&1 &
  echo "PID=$!"
  sleep 3
  svc power stayon ac
'
```

Verify it's running and detached:

```bash
adb shell 'ps -ef | grep overnight_inference | grep -v grep'
# PPID column should be 1 (init) — that means adb disconnect won't kill it
```

## Disconnect + put in fridge

Once `ps -ef` shows PPID=1, **you can unplug the USB cable**. The loop keeps running:
- The phone stays awake because `svc power stayon ac` is set (keeps CPU running while AC powered).
- The Hexagon NPU is reachable via `qnn-net-run` from adb-shell context, even with the screen off and ADB disconnected.

For fridge mode:
- Put the phone in **REDMAGIC Game Zone** before unplugging if available — Game Zone disables Doze for foreground processes.
- Plug the phone into a power outlet IN the fridge (charge bypass mode if the phone supports it; otherwise battery will charge to full and then trickle-charge).
- Close the fridge.

## Live monitoring (no reconnection needed)

**Quick status check** — visit this URL in any browser:
```
https://huggingface.co/datasets/Architect-Prime/polymath-telemetry/tree/main/phase1a
```

The newest directory matches your current run. Click into `audit.jsonl` to see per-iteration rows. Each row carries:
- `iter` — iteration number
- `scope` — `qwen_block` (1 layer) or `qwen_frozen_subgraph` (26 layers)
- `wall_ms` + `per_inf_ms` — wall-clock for the batch + per-inference latency
- `rc` — exit code from `qnn-net-run` (0 = ok)
- `out_size` — output bytes (98304 = 1×16×1536 FP32; anything else = problem)
- `battery.{level,temp_dC,ac_powered}` — phone health
- `thermal.{cpu-N-N-N,battery,skin-msm-therm}` — every available thermal zone
- `memory.{avail_kb,total_kb}` — RAM headroom
- `disk.{data_free_kb,sdcard_free_kb}` — storage headroom
- `prev_event_hash` — sha256 of the previous row, for tamper-detection

If the row count stops growing for >5 minutes, something stalled. If it hasn't pushed to HF in >10 minutes, network or HF API is down.

## Auto-stop conditions (graceful)

The loop monitors itself and halts on any of:
- **`/sdcard/Polymath/phase1a/STOP` file exists** (your kill switch)
- **Battery temperature > 45.0°C** (records `thermal_halt` event then exits)
- **Battery level < 15%** (records `low_battery_halt` event then exits)
- **Required QNN binary missing** (records `fatal_missing_artifact` event then exits)

A graceful halt always writes a `phase1a_overnight_end` event as the last row, so you can tell apart "still running but slow" vs "stopped on its own".

## Stopping it manually (kill switch)

From the host (after re-connecting USB):
```bash
adb shell 'touch /sdcard/Polymath/phase1a/STOP'
```

The loop checks for `STOP` once per iteration (~12 s cycle). It will halt within one cycle, write the `stop_signal_received` event, and exit.

## Reconnecting in the morning

```bash
adb shell 'tail -3 /sdcard/Polymath/phase1a/audit.jsonl | tr "," "\n" | grep -E "ts|event_type|iter|wall_ms|per_inf|level|temp_dC"'
adb pull /sdcard/Polymath/phase1a/audit.jsonl /tmp/overnight_audit.jsonl
adb pull /sdcard/Polymath/phase1a/runner.log /tmp/overnight_runner.log
```

Then summarise locally with:
```bash
wc -l /tmp/overnight_audit.jsonl                      # total events
grep -c inference_batch /tmp/overnight_audit.jsonl    # inference iterations
grep -E "thermal_halt|low_battery_halt|stop_signal"  /tmp/overnight_audit.jsonl
```

## What this run actually proves overnight

- **Steady-state per-inference latency** on Hexagon for both qwen_block and qwen_frozen_subgraph (the 10x wall-clock from the smoke test was dominated by 2.3 GB mmap; thousands of iterations factor that out).
- **Thermal sustainability** of continuous Hexagon-NPU inference — does the SM8750 throttle under sustained load, especially in cool fridge ambient?
- **Battery / charge-bypass behavior** — if the phone is plugged in inside the fridge, does the AC supply keep the battery at full without thermal stress, or does it cycle?
- **Reliability of the inference primitive** — across thousands of inferences, do we ever see `rc != 0` or `out_size != 98304` (i.e. silent corruption)?
- **End-to-end auditable record** — the hash-chained JSONL gives a tamper-evident log of every inference call we made through the night.

These four data points are the foundation for the Phase 1A.A ELO experiment that's queued next.

## Known constraints / caveats

- **No real tokens yet.** The input is FP32 zeros. So the outputs are `f(0)` for the random-init weights of each scope; numerically they're the layer-norm bias / projection patterns of the network. They DON'T mean anything semantically. The point of this overnight run is the system-level proof, not language modelling.
- **Termux is unused.** The original blueprint relied on Termux for telemetry, but Termux SSH was unresponsive in this session (suspected aggressive power-management of the Termux app process). The pure adb-shell + curl path is more reliable.
- **No Android NDK / LiteRT app.** Running the QNN context binary directly via `qnn-net-run --retrieve_context` works for our case because every op in our compiled subgraphs is QNN-delegated by construction. A model with mixed delegate coverage would need a different runtime.
