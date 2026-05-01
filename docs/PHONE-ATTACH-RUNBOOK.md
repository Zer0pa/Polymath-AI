# Phone Attach Runbook — REDMAGIC 10 Pro+

**Boundary:** Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

This runbook is the config-flag-shaped continuation (Decision D-005) when the REDMAGIC 10 Pro+ is physically attached to the host.

## Pre-attach checklist (host)

1. ADB / platform-tools installed:
   ```sh
   brew install --cask android-platform-tools     # macOS
   # or:
   sudo apt install android-tools-adb adb         # Linux
   adb version
   ```
2. HF auth working (token at `~/.cache/huggingface/token`).
3. Repo cloned, venv built, tests green:
   ```sh
   cd Polymath-AI
   .venv/bin/python -m pytest tests/ -q
   ```
4. The Qwen ELO smoke report under `runtime/reports/qwen_elo_smoke/<latest>/report.json` says `result: pass` with zero `frozen_changes_observed`.

## Step 1 — Physical attach

1. Plug REDMAGIC 10 Pro+ into the host with USB-C.
2. On the phone: enable Developer Options (Settings -> About -> Tap "Build number" 7x).
3. Enable USB Debugging in Developer Options.
4. Plug in and accept the USB debugging fingerprint dialog. Tick "Always allow from this computer."
5. Confirm:
   ```sh
   adb devices -l
   ```
   Expect a single line with state `device` (not `unauthorized`, not `offline`).

## Step 2 — Probe SoC + battery + thermal

```sh
scripts/host/phone_probe.sh runtime/probes/phone
```

This writes a probe directory at `runtime/probes/phone/<timestamp>/` with:
* `adb-devices.txt`
* `getprop.txt`
* `meminfo.txt`
* `df.txt`
* `thermal.txt`
* `battery.txt`
* `kernel.txt`, `cpuinfo.txt`, `gpu-clock.txt`
* `summary.json`

Then resolve the SoC target:

```sh
.venv/bin/python -c "
from polymath_ai.device.probe import parse_getprop, soc_target_from_reported
text = open('runtime/probes/phone/<timestamp>/getprop.txt').read()
props = parse_getprop(text)
reported = props.get('ro.soc.model') or props.get('ro.product.cpu.abi')
target, conf = soc_target_from_reported(reported)
print('reported:', reported, 'target:', target, 'confidence:', conf)
"
```

**Gate D-006**: do NOT proceed to QNN compile until `confidence >= 1.0` OR until you have re-probed by attempting a tiny-block AOT compile against each candidate target and chosen the one that succeeds. The `device_soc_mismatch` falsifier blocks the run otherwise.

Record the result:

```sh
echo "phone:soc_target=<target>" >> docs/DECISIONS.md   # plus a D-row entry per the schema
```

## Step 3 — Charge Separation / bypass charging

RedMagic OS supports Charge Separation in Settings -> Battery -> Charging. Verify:

1. Plug in.
2. Battery -> Charging -> "Charge Separation" toggle ON.
3. Set battery cap 70-80% if the option is present.
4. Run a 10-minute idle test:
   ```sh
   adb shell dumpsys battery > /tmp/before.txt
   sleep 600
   adb shell dumpsys battery > /tmp/after.txt
   ```
5. Compute SoC drift:
   ```sh
   diff <(grep 'level' /tmp/before.txt) <(grep 'level' /tmp/after.txt)
   ```
6. If drift > 2pp / 10 min (i.e. > 12pp / hour), the falsifier `charge_bypass_unproven` fires; either Charge Separation is not actually active or the bypass test is invalid. Try setting battery cap to 70% and retest.

## Step 4 — Termux bootstrap

```sh
adb push scripts/termux/bootstrap.sh /sdcard/Download/polymath-bootstrap.sh
# On the phone in Termux:
#   cp /sdcard/Download/polymath-bootstrap.sh ~/
#   bash ~/polymath-bootstrap.sh
adb shell input keyevent KEYCODE_HOME    # then user opens Termux manually
```

After bootstrap, pull the verdict:
```sh
adb pull /data/data/com.termux/files/home/polymath/termux-verdict.json runtime/probes/phone/termux-verdict.json
```

If `torch_install_result` is `working`, on-device training is viable. Otherwise the host runs the model and Termux is control plane (Decision D-010).

## Step 5 — Phase 0E: Experiment 0 — micro-run ladder

Configs at `configs/experiments/E0/`:

| Step | Tokens | Seq | Batch | Purpose |
|---|---:|---:|---:|---|
| E0.1 | 10K | 128 | 1 | end-to-end smoke + checkpoint sync |
| E0.2 | 100K | 256 | 1-2 | first thermal + memory signal |
| E0.3 | 1M | 512 | 2-4 | throughput estimate |
| E0.4 | 2h sustained | 512 | max stable | thermal + energy gate |

Trigger from host:

```sh
.venv/bin/python -m polymath_ai.experiments.runner \
    --phase phase0e_experiment0 \
    --config configs/experiments/E0/E0.1.yaml \
    --device-mode termux_or_host
```

Falsifier gate at end: `oom_or_memory_pressure`, `thermal_throttle`, `throughput_floor_fail`, `battery_heat_risk`, `charge_bypass_unproven` all `pass`.

## Step 6 — Phase 0F: Tokenizer fertility audit

```sh
.venv/bin/python -m polymath_ai.experiments.fertility \
    --tokenizer Qwen/Qwen2.5-1.5B \
    --samples data/fixtures/fertility/ \
    --out runtime/reports/fertility/
```

Falsifier gate: `tokenizer_fertility_high`. If any core language above 2.5x English, write a Decision row deciding vocabulary extension, sampling adjustment, or model swap before Phase 1A.

## Step 7 — Phase 0G: SmolLM3 QNN export verdict

Only meaningful if Step 2 produced a high-confidence SoC target.

```sh
.venv/bin/python -m polymath_ai.experiments.smollm3_export_probe \
    --soc-target <SM8650|SM8750|SM8850> \
    --scope tiny_block,real_block,frozen_subgraph \
    --out runtime/reports/export/
```

Falsifier gate: `smollm3_export_unproven`. If any scope fails to compile, the failing op + graph pattern must be recorded. Decision: `accelerated_candidate_b`, `gpu_cpu_eval_only`, or `deferred`.

## Step 8 — Phase 0H: Cutover readiness review

Before Phase 1A:

1. Audit chain validates: `polymath_ai.audit.validate_audit_chain(runtime/runs/<latest>/audit.jsonl)`.
2. Every Phase 0 falsifier reports `pass` (or explicit `blocked` with documented mitigation).
3. Corpus manifest for the 100M slice exists at `corpus/manifests/phase1a-100m.json`, has manifest_sha256, and every source has license_class `A` or `B`.
4. Reflex Scheduler micro-calibration recorded.
5. QLoRA / LoRA baseline ran on a 10M pilot.

The Phase 1A cutover is then `phase: phase1a_qwen_elo_100m` in the runner config. No code changes.

## Energy regime

Default operating profile (PRD §Energy Regime):

* Charge Separation ON.
* Battery cap 70-80% if RedMagic OS supports it.
* Fan ON.
* "Stable" performance mode unless measured better.
* Case removed.
* Ambient < 25C.
* Screen off / minimum brightness.
* No fast-charge during sustained training.

## Failure recovery

* ADB drops: re-run Step 1; the runner watchdog auto-retries up to 10 times (`scripts/termux/training_runner.sh`).
* Process killed by OOM: `oom_or_memory_pressure` fires; reduce batch / sequence in config and retry.
* Battery temp >= 42C for 60s: `battery_heat_risk` fires; runner stops; cool the device; resume.
* Hash chain breaks: do not proceed. The chain is your one record of state. Diagnose with `validate_audit_chain` and roll back to the prior tail.

## Open questions surfaced when phone arrives

The following are deferred until probe data exists; record answers in `docs/DECISIONS.md`:

1. Actual `ro.soc.model` string and confidence-1.0 SoC target.
2. Charge Separation: present? toggleable from `adb shell settings`?
3. Termux Python torch wheel availability and matmul correctness.
4. Sustained Adreno 830 clock with fan ON (probe `gpu-clock.txt`).
5. Vulkan version reported (probe `host-vulkan-summary.txt` from host vulkaninfo, plus on-device `vulkaninfo` if installed in Termux).
6. QNN / QAIRT runtime libraries in `/system/lib64/` (probe via `adb shell ls /system/lib64/ | grep -iE "qnn|qairt|hexagon"`).
