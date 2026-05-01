# Game Space + Fridge Mode — Long-Horizon Autonomous Training

**Boundary:** Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

**Status:** Operator-proposed strategy 2026-05-01 — phone runs unplugged-from-host, plugged-into-power, inside a refrigerator, in REDMAGIC Game Space mode, autonomous training via Termux. Documented here so the setup is reproducible and the safety risks are explicit before each run.

**Audience:** Operator + future overnight executor. The agent does **not** automate the physical setup — the operator places the phone, plugs the charger, closes the fridge. The agent automates everything that runs *on* the phone.

## TL;DR

1. Bootstrap Termux + venv + Python deps.
2. Add Termux to **Game Space** (operator-driven; agent cannot drive Settings).
3. Confirm Charge Separation / battery cap, fan ON, performance mode.
4. Place phone on a thermal-compatible base; plug into a quality charger.
5. Run `scripts/termux/long_horizon_runner.sh` inside Termux.
6. Operator closes fridge. Phone runs autonomously.
7. WiFi-reachable: monitor via SSH or HF telemetry pulls. Otherwise: pull artifacts from HF when the run completes.

## Why this strategy

REDMAGIC 10 Pro+ has an integrated active fan. Its Adreno 830 sustains higher clocks the cooler the SoC stays. A fridge at 3-7 °C is a much larger thermal sink than ambient air, so sustained training under Game Space ("Extreme") performance mode keeps the GPU at max clock for the entire run rather than throttling after 10-30 minutes.

This is operator-led thermal engineering. The PRD §Energy Regime allows "ambient < 25 °C" — fridge mode hits that hard.

## Hard safety rules

| Rule | Why |
|---|---|
| **Never put the phone in the freezer (sub-zero).** | Lithium batteries operate at 0-45 °C. Charging below 0 °C plates lithium on the anode, permanently damaging capacity. Discharging below -20 °C is also harmful. Fridges are 3-7 °C. Freezers are -18 to -25 °C. |
| **Don't open the fridge mid-run.** | Each opening cycles temperature 10-15 °C, which causes condensation cycles inside the phone. Repeated condensation kills the screen and the SoC. |
| **Equilibrate inside a sealed bag before removing.** | When the cold phone meets warm room air, water condenses on every internal surface. Procedure: at end of run, place phone (still ON, draining heat) inside a *sealed* zip-lock bag; remove from fridge; let temperature equilibrate (45-90 min) before opening the bag. |
| **Use a quality USB-C cable with a quality charger.** | Cable jackets stiffen at low temp; bargain cables can crack. Use the OEM cable. Use the OEM charger (REDMAGIC 80W); it negotiates safely. |
| **Charge Separation MUST be ON.** | "Charge Separation" / "Bypass Charging" routes USB power directly to the system, bypassing the battery. Without it, multi-day training cycles the battery thousands of times -> dead in a month. With it, the battery sits at the configured cap (70-80 %) and is barely used. |
| **Battery cap 70-80 %, not 100 %.** | Lithium batteries last longer at partial charge. RedMagic OS supports the cap. |
| **WiFi range check before closing the fridge.** | Fridges are partially Faraday cages. 5 GHz WiFi often dies; 2.4 GHz usually survives. Test: with door closed, phone at run-position, can the host SSH in? If no, plan for HF-pull-only monitoring. |
| **Confirm phone-side `huggingface_hub` push works** before sealing. | If WiFi is too weak, the phone can still buffer telemetry locally and HF-push when WiFi comes back, but the buffer is bounded. |
| **No condensation on the charger plug.** | The cable goes through the door seal of the fridge. Use the cable channel of a fridge that supports it, or a thin-cable port mod. The seal must still close. |

## Pre-flight checklist (every run)

- [ ] Phone fully booted, USB Debugging on, Termux installed (F-Droid build, not Play Store), Termux:API installed (F-Droid).
- [ ] `bash ~/polymath/bootstrap.sh` ran successfully today; `~/polymath/termux-verdict.json` says torch=`working` OR control_plane mode is acceptable.
- [ ] **Game Space toggle ON** (the physical red switch on the side of the REDMAGIC). The phone announces "Game Space ON" with a screen flash.
- [ ] Termux is registered in Game Space app list (Operator step — see "Add Termux to Game Space" below).
- [ ] Settings → Battery → Charge Separation **ON**.
- [ ] Settings → Battery → Battery Cap **70 %** (or 80 % — operator's call; lower is gentler on battery).
- [ ] Settings → Battery → Performance Mode = **Stable** (not Extreme yet — start conservative; promote to Extreme after thermal margin is measured by Phase 0E E0.4).
- [ ] Settings → Display → Screen Timeout = max (or "Always On" if available; the wakelock holds anyway, but redundant safety).
- [ ] Settings → Display → Brightness = minimum (saves heat).
- [ ] Phone lying flat on a clean dry surface (paper towel sheet to absorb the inevitable post-run condensation drip).
- [ ] OEM USB-C cable + OEM 80 W charger, plugged into a wall outlet (not the host).
- [ ] WiFi connected, signal strength tested with the door closed: `adb shell ping -c 3 8.8.8.8` from the host (when host can still see the phone via wireless ADB) **OR** `ssh phone 'ping -c 3 8.8.8.8'`.
- [ ] Battery temperature reading at idle: `adb shell dumpsys battery | grep temperature` returns < 30 °C.
- [ ] Audit chain validates clean for the prior phase: `python -m polymath_ai.audit.chain validate runtime/runs/<latest>/audit.jsonl` (or scripted equivalent).
- [ ] Run config explicitly says `phone_attached: true`, model is the one we verified (Qwen2.5-1.5B / SmolLM3-3B), corpus_slice points to a license-attested HF dataset path.
- [ ] **Fridge temperature is between 3 °C and 7 °C** (a few degrees above freezing; double-check with a thermometer if uncertain — most household fridges are 3-5 °C).
- [ ] **Fridge is door-closed-stable** during the run window (operator should not be cooking while running).

## Add Termux to Game Space (operator-driven)

The agent cannot drive the Settings UI safely. This is operator-only.

1. Install **Termux** from F-Droid (`https://f-droid.org/packages/com.termux/`). The Play Store version is deprecated and stale.
2. Install **Termux:API** from F-Droid (`https://f-droid.org/packages/com.termux.api/`). This unlocks `termux-wake-lock`, `termux-battery-status`, `termux-sensor`, etc.
3. Open **Game Space** (REDMAGIC's gaming hub; usually accessible from the side switch or as an app titled "Game Space" or "Game Studio").
4. Tap **+** / "Add app" / "Add games" — terminology varies by RedMagic OS version.
5. Select **Termux** from the app list. Confirm.
6. From now on, launching Termux from inside Game Space invokes Performance / Extreme mode and starts the active fan.

If Game Space doesn't list Termux: try toggling Settings → Apps → Termux → "Allow in Game Space" or similar. Some RedMagic OS versions hide Game Space behind hardware-switch-only activation.

## Inside Termux, on the phone

```bash
# One-time
bash ~/polymath/bootstrap.sh
pkg install termux-api tmux

# Each run
tmux -L polymath ls 2>/dev/null    # list existing sessions
bash ~/polymath/long_horizon_runner.sh \
    --phase phase0e_experiment0 \
    --config ~/polymath/configs/E0.1.yaml

# Detach implicitly (the tmux session stays alive even when Termux is closed).
# Re-attach later:
tmux -L polymath attach -t polymath-phase0e_experiment0
```

The runner:
- Acquires `termux-wake-lock` so the screen-off does not pause the process.
- Spawns a tmux detached session so the runner survives Termux being killed by the OOM-killer or by Game Space app cycling.
- Watchdog loop: up to 20 retries with 60-600 s backoff per crash.
- Per-step audit row + per-N-steps checkpoint -> HF push (or pending manifest if WiFi flaky).

## Monitoring during the run

| Channel | Pros | Cons |
|---|---|---|
| Wireless ADB (USB unplugged) | Live shell, file pulls. | Requires WiFi reach; phone IP changes; ADB pairing must be set up first via Settings → Developer options → Wireless debugging. |
| SSH to Termux | Live shell, low overhead. | Requires SSH server running in Termux (`pkg install openssh; sshd`), public-key set up. |
| HF dataset polls | Survives WiFi outages; durable. | Latency = the runner's HF push cadence. |
| HF run page (model card auto-updates) | Web UI; no client setup. | Same latency as above. |
| GitHub commits via `gh` from Termux | Authoritative; survives device loss. | Slow; only suitable for milestones, not per-step. |

For the **fridge mode** specifically: WiFi is the chokepoint. If 2.4 GHz reaches the fridge, prefer SSH for live monitoring + HF for durable. If not, plan for HF-only monitoring with a 5 min push cadence and accept a 5 min visibility lag.

## End-of-run procedure

1. Inside the tmux session, you should see `[long-horizon] complete at <ts>`.
2. Verify: the audit log validates clean; the latest checkpoint is on HF (or queued in a pending manifest); the per-language eval report is generated.
3. Post-run cooldown: stop the workload but **leave the phone on** so it self-heats to fridge ambient slowly. Do not pull immediately.
4. Bag-and-equilibrate procedure (above).
5. Once dry, plug back into host, ADB-pull any remaining artifacts, run the host-side validator: `python -m polymath_ai.experiments.runner --phase phase0h_cutover_review`.

## Decisions that need operator engagement before we can run

The agent will pause and ask you for any of these:

1. **First fridge-mode run? Confirm fridge temp + door schedule.** I will refuse to start a multi-hour run without operator confirmation that the fridge stays closed for the run window.
2. **Charge Separation unverified.** If `dumpsys battery` shows the battery level rising during plugged-in idle (i.e. Charge Separation is *not* active), I will refuse to start a multi-day run.
3. **WiFi monitoring missing.** If neither SSH nor wireless ADB reaches the phone in the run position, I will warn but proceed if the operator approves the HF-pull-only mode explicitly.
4. **Battery temp at start > 30 °C.** I will wait until the phone cools, OR refuse if the fridge isn't cold enough to pull it down.
5. **Performance mode set to Extreme on the first run.** I will recommend Stable for the first run; promote to Extreme only after E0.4 confirms thermal margin.

## Falsifiers extended for fridge mode

In addition to the existing falsifier registry:

- `condensation_risk` — battery temperature has crossed the dewpoint (~5 °C of ambient external) in the past 5 minutes. Triggers if the operator opened the fridge or the run finished and the phone is warming. Required response: stop and bag.
- `wifi_silent` — no successful HF push in the last 30 min. Pause the run; rely on local pending-upload buffer; resume when WiFi recovers.
- `fan_silent` — fan speed reads zero / low for sustained training. Game Space mode might have been turned off accidentally. Stop and notify operator.

These will be wired into `polymath_ai.falsifiers.registry` in a follow-up commit (separate from tonight's substrate work).

## Risk summary (one paragraph)

A REDMAGIC 10 Pro+ in a 4 °C fridge under Game Space + active fan is a research-grade thermal management trick. It is safe **if and only if** the operator (a) keeps the fridge closed during the run, (b) lets the phone equilibrate inside a sealed bag before removing, and (c) has Charge Separation active so the battery isn't cycled. The chief failure modes are condensation and battery cycling; both are addressed by the rules above. The agent enforces what it can in software (wakelock, watchdog, charge-bypass falsifier); the operator owns the physical safety steps.
