# Wave-2 Research: The Authority-Metric Measurement Protocol

**Date:** 2026-05-16
**Wave:** 2 (orchestrator-spawned single-question agent)
**Question this artifact answers:**
"`useful learning per energy/thermal envelope` has been used repeatedly as the authority metric but never operationalized. What is the protocol — units, instruments, sampling cadence, statistical treatment, gates, falsifiers — that turns that phrase into a number computable from a real training run on the RedMagic 10 Pro Plus?"
**Governing discipline:** Resistance V2.
**Forbidden in this artifact:** `fp-scopeevaporation` (collapse to tokens/sec), `fp-benchmarkproxy` (substitute a quality-blind proxy), `fp-interimossification` (treating this protocol as a measurement instead of the input to one), `fp-toolbusy` (specifying a protocol that cannot be run).
**Status:** research note. This artifact does NOT yet measure anything. It specifies what must be measured, with what instruments, at what cadence, with what statistical treatment, and what counts as a violated gate.

---

## 0. Framing — why the existing language is rhetoric, not measurement

Every iteration of the dialogue uses the phrase "useful learning per energy/thermal envelope without general regression" as the authority metric (`HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md` lines 94, 211–215, 645–646, 759–767; `heterogeneous-training-loop-shape.md` falsifier #8 line 351; `blueprint Part IX line 720`; `blind-spots-frontier-scan.md` line 9). None of these mentions specifies:

- the units of "useful learning"
- the units of "energy" on a phone (joules at which boundary — battery terminals, SoC rails, USB inlet?)
- the units of "thermal envelope" (junction temp, skin temp, GPU clock ratio, throttle-event count?)
- how to compute the ratio without divide-by-near-zero pathologies in early training
- how many independent runs are required for an A-vs-B claim to be defensible
- what statistical test compares run A to run B
- what counts as a disqualifying gate violation that voids a run entirely

The only concrete artifact in the codebase that touches this question is `polymath_ai/falsifiers/registry.py` `_check_energy_budget_exceeded` (lines 180–191), which compares a single scalar `joules_per_token` to a `joules_per_token_baseline`. That falsifier does not specify how `joules_per_token` was computed, what battery-current sampling cadence produced it, what the uncertainty bound is, or how it interacts with model quality. As written it is a placeholder for the gate, not the gate.

This is the gap. The rest of this document closes it.

Resistance V2 invariant: a measurement protocol that produces a number divorced from quality (`fp-benchmarkproxy`) or that cannot be executed on the actual phone (`fp-toolbusy`) is theater. The protocol below is constrained at both ends: it must produce a number that an A-vs-B claim would actually depend on, and it must be runnable on an unrooted RedMagic 10 Pro Plus over ADB plus Termux.

---

## 1. Candidate authority-metric formalizations

A metric is a function from a training-run trace `T` to a real number `M(T)`, where `T` includes the model checkpoint stream, the held-out probe set, an energy trace, a thermal trace, and a sample of timing data. Below are the candidates surfaced in the dialogue, the literature, and adjacent benchmark work (MLPerf Power, ML.ENERGY, Hoffmann/Chinchilla, MosaicML).

Notation:

- `θ_t` = model parameters at training step `t`
- `D_probe` = held-out evaluation corpus (size `N_probe` tokens, sequences of length `L_probe`)
- `NLL(θ; D_probe) = -(1 / N_probe) Σ_x log p_θ(x_t | x_<t)` — nats per token on the held-out probe; equivalently `log(PPL)`
- `E([t_a, t_b])` = energy in joules consumed by a defined boundary (battery terminals, SoC rails, USB inlet) over wall-clock window `[t_a, t_b]`
- `t_steady` = end of warm-up window where the system reaches thermal+memory steady state
- `t_eval(i)` = wall-clock time at which the `i`-th held-out evaluation is taken

### Candidate A — Mean NLL reduction per joule over the steady-state window

```
M_A(T) = ( NLL(θ_{t_steady}; D_probe) - NLL(θ_{t_end}; D_probe) ) / E([t_steady, t_end])
```

Units: `nats · token^-1 · J^-1`. Higher is better.

Strengths: directly couples a quality-improvement number to a power-consumption number; both numerator and denominator are integrated over the same window; immune to first-microbatch transients because the window starts after `t_steady`.

Weaknesses: a single scalar over a long window hides whether learning was concentrated in the first hour and the next five hours bought nothing but heat. Treats the run as monotone, which it may not be when the curriculum changes. Sensitive to `D_probe` choice; if the probe is too small, `NLL` confidence intervals dominate the ratio.

### Candidate B — Tokens-to-target-NLL under a hard thermal gate

```
Define a target T_NLL such that NLL(θ_0; D_probe) - T_NLL = Δ_target  (chosen ex ante)
M_B(T) = N_tokens_consumed such that NLL(θ_τ; D_probe) ≤ T_NLL
        subject to: thermal_gate_violations(T, [0, τ]) == 0
```

Units: tokens. Lower is better. If `T_NLL` is never reached, `M_B = ∞` and the run fails.

Strengths: matches Chinchilla / Hoffmann tokens-to-loss tradition. Disqualifies thermally-cheated runs by construction. Defines failure cleanly (target not reached). Easy to compare A-vs-B (fewer tokens to the same NLL wins).

Weaknesses: pre-committing `T_NLL` before knowing run dynamics is a calibration problem; pick too low and every run fails, pick too high and every run trivially passes. Does not directly score energy — it scores token-budget under a thermal constraint that proxies energy. Insensitive to whether method A consumed 3 J/token and method B consumed 5 J/token to reach the same target. Use B alongside A, not as a substitute.

### Candidate C — Validation-perplexity reduction per device-watt-hour at sustained thermal state

```
M_C(T) = ( PPL(θ_{t_steady}; D_probe) - PPL(θ_{t_end}; D_probe) ) / Wh([t_steady, t_end])
```

Where `Wh = E / 3600` and `E` is in joules. Identical structure to A but reports `Wh` because operators read battery dashboards in `mAh @ V`. Numerically equivalent to A up to the unit conversion and the `exp(NLL)` vs `NLL` swap. Use A in primary reporting; compute C only as a derived secondary number for cross-comparison with cloud-energy reporting conventions.

Weakness: working in PPL means non-linear in NLL; small NLL deltas produce non-additive PPL deltas, which breaks variance-of-the-ratio arithmetic and corrupts confidence-interval propagation. A is the rigorous form, C is the legible form.

### Candidate D — Information density per joule (nats added to held-out compression)

```
Define a fixed reference distribution p_ref (e.g. base-model logprob on the same probe).
M_D(T) = ( ΔLogLikelihood(θ_{t_end} - θ_0; D_probe) ) / E([t_0, t_end])
       = ( N_probe · ( NLL(θ_0; D_probe) - NLL(θ_{t_end}; D_probe) ) ) / E([t_0, t_end])
```

Units: `nats · J^-1`. This is A multiplied by `N_probe`, expressing total nats compressed out of the held-out probe per joule, rather than per-token.

Strengths: aligns with information-theoretic literature ("nats per joule" is the physical quantity if you think of training as a compression process). The `N_probe` factor makes the metric scale with probe size, which is useful when comparing across probes of different sizes. Equivalent to Candidate A up to a scaling factor when `N_probe` is fixed.

Weaknesses: identical to A's. The choice between A and D is presentational. Use A internally; report D when communicating with the information-theoretic / scaling-laws literature.

### Candidate E — Multi-domain Pareto frontier under thermal constraint

```
For domains d in D_set (e.g. math, code, multilingual, retention):
   ΔNLL_d = NLL_d(θ_0) - NLL_d(θ_end)
Compute the vector (ΔNLL_d for d in D_set) / E([t_0, t_end]).
Compare runs by Pareto dominance, not scalar product.
```

Strengths: keeps the "useful" half honest. A scalar `M_A` can hide that method A learned the target language at the cost of catastrophic forgetting on the retention probe (`fp-benchmarkproxy` of the worst kind). A Pareto-vector metric makes this regression structural, not invisible.

Weaknesses: not a single number. A-vs-B comparisons may produce "neither dominates." This is correct, not a defect. The pricing of failure is asymmetric; a catastrophic-forgetting regression on the retention probe should be a hard gate (Candidate F below), not a softening of A.

### Candidate F — Constrained version of A with hard retention gate

```
M_F(T) = M_A(T)
         if NLL_retention(θ_end; D_retention) - NLL_retention(θ_0; D_retention) < δ_retention
         else FAIL (catastrophic forgetting)
```

`δ_retention` is the maximum permitted regression on a general-domain probe (default 0.01 nats/token, or +1% PPL — matches the `catastrophic_forgetting` falsifier's 1pp English anchor drop threshold in `polymath_ai/falsifiers/registry.py` line 199). Below the threshold, score with A. Above the threshold, the run is disqualified regardless of how good `M_A` looks. This is the structural protection against `fp-benchmarkproxy`.

### Working stance

The four-element metric tuple this project should report for every run is:

```
M = ( M_A, M_B, ΔNLL_d-vector across domains, retention_gate_pass: bool )
```

`M_A` is the primary scalar. `M_B` is the secondary check that the run actually reached an a-priori-defined target. The vector `ΔNLL_d` per domain guards against scalar averaging hiding regressions. The retention gate is the hard disqualifier.

**No scalar metric is sovereign.** A run that reports only `M_A` without the retention gate or the per-domain vector is `fp-benchmarkproxy` by construction.

---

## 2. What is measurable on SM8750 Android — instruments, sysfs paths, sampling cadences, uncertainty

The RedMagic 10 Pro+ runs Android 15 on Snapdragon 8 Elite (SM8750). Most measurement happens via ADB or Termux. The phone is NOT a Pixel, so ODPM (On-Device Power Rail Monitors) — the only Android API that exposes per-subsystem energy with sub-second resolution — is NOT available. This is the single biggest measurement constraint on the project.

### 2.1 Energy / power — the load-bearing measurement

| Source | Path / API | What it reports | Sampling cadence | Unit | Notes |
|---|---|---|---|---|---|
| Battery instantaneous current | `adb shell dumpsys battery` field `current now` (Android API); `/sys/class/power_supply/battery/current_now` if readable | Instantaneous current at battery terminals | Hardware fuel-gauge update rate is 1–10 Hz typically; ADB poll adds ~50–100 ms latency per call | µA (microamps); positive = discharge, negative = charge depending on sign convention | The most direct power reading available without ODPM. Voltage and current together give power. |
| Battery instantaneous voltage | `/sys/class/power_supply/battery/voltage_now` | Battery terminal voltage | Same as current | µV (microvolts) | Multiply by current to get terminal power. |
| Battery cumulative charge | `/sys/class/power_supply/battery/charge_counter` (if present) | Coulombs accumulated since boot or wrap | Hardware fuel-gauge update | µAh | Differencing this across a window gives accumulated charge; multiplying by mean voltage gives accumulated energy. Lower variance than integrating instantaneous current, at the cost of cadence. |
| Battery energy counter | `BATTERY_PROPERTY_ENERGY_COUNTER` via Android BatteryManager (Termux Java bridge) | Remaining energy in nWh | Slow (1 Hz typical) | nWh | When available, this is the cleanest single-number energy reading. Not all SoCs expose it. Must be probed on SM8750 to confirm. |
| Battery temperature | `dumpsys battery` field `temperature` | Battery temperature | 1 Hz typical | tenths of °C (e.g. 280 = 28.0 °C; matches our probe in `runtime/probes/phone/2026-05-16T100713Z/battery.txt`) | Already verified readable on this RedMagic. |
| Charging policy / AC powered flag | `dumpsys battery` fields `Charging state`, `Charging policy`, `AC powered` | Whether USB / AC is delivering power | 1 Hz typical | bool / enum | Critical for distinguishing tare runs (battery-only) from plugged-in runs. |
| External USB power meter | Inline hardware (e.g. Plugable USBC-VAMETER3, ChargerLAB POWER-Z KT002/AK001) | USB-inlet voltage and current | 100–1000 Hz; built-in averaging | mV / mA / mW | The ONLY way to measure SoC power independent of battery buffering and charging current under bypass-charging. Operator-procurable, <$100. Required for any joule claim that intends to be defensible across plugged/unplugged regimes. |

**The fundamental joule-measurement problem (treated in section 3 in detail):**
Under bypass charging, USB current goes through the phone to the SoC. Battery instantaneous current still reflects only the battery's tiny self-balancing trickle. Battery current is NOT SoC current in this regime. Without an external USB meter or ODPM, there is no way to measure SoC energy directly during a plugged-in run.

**Without ODPM, per-subsystem energy attribution (CPU vs GPU vs NPU vs DRAM) is not measurable on this phone.** Battery counters give whole-device power only. Any per-substrate energy claim (e.g. "Adreno consumed X joules of this training step") requires either (a) ODPM access via root + custom kernel, (b) a power-model fit calibrated against ODPM-equipped Pixel 9 Pro or similar as a proxy, or (c) outright disqualification of per-substrate energy claims. Resistance V2 says (c).

### 2.2 Memory pressure — `/proc/PID/smaps_rollup`

| Source | Path / API | What it reports | Sampling cadence | Unit | Notes |
|---|---|---|---|---|---|
| Process PSS (Proportional Set Size) | `/proc/<pid>/smaps_rollup` field `Pss:` | Proportional resident memory; counts shared pages divided by sharer count | Each read costs O(VMA count) ms; smaps_rollup is ~12× faster than reading full smaps per Android engineering note. Safe at 1 Hz; 10 Hz is feasible for a single process | kB | Cheap, reliable on rooted or self-readable processes. Android's system_server samples PSS every ~10 min on system processes; we will need finer cadence on the training process. |
| Process RSS | `/proc/<pid>/status` field `VmRSS:` | Resident pages (not adjusted for sharing) | Each read is cheap | kB | Faster than PSS but less interpretable across processes that share pages with the training process. |
| Process major / minor page faults | `/proc/<pid>/stat` fields 12 (minflt), 14 (majflt) | Cumulative fault counters | 1 Hz cheap | counts | The leading signal of UFS / page-cache thrashing. Differential between two samples gives faults per window. Hot-path major faults during compute = the LMK or storage subsystem is breaking the run. |
| System memory state | `/proc/meminfo` | MemTotal, MemAvailable, Cached, SwapFree, Mlocked, etc. | 1 Hz cheap | kB | Already captured in our probe (`runtime/probes/phone/2026-05-16T100713Z/meminfo.txt`). MemTotal = 23.6 GB confirmed. |
| Low-memory killer events | `logcat -b system,events -s lowmemorykiller:* ActivityManager:* OOM:*` | LMK kills | event-driven | log entries | A single LMK kill of the training process disqualifies the run. Must be parsed live and surfaced as a falsifier. |

Sampling cadence target: 1 Hz for `smaps_rollup`, `meminfo`, `current_now`, `voltage_now`. Logcat consumed as a stream, not a poll. Higher rates (10 Hz) are feasible for any single sysfs file but introduce CPU load on the measurement thread that pollutes the very thing being measured. **The measurement rig must run on Phoenix M efficiency cores affinity-pinned away from training cores**, otherwise the rig itself becomes a heat source.

### 2.3 GPU clock and utilization — partial visibility

| Source | Path / API | What it reports | Cadence | Notes |
|---|---|---|---|---|
| Adreno cur_freq | `/sys/class/devfreq/*kgsl*/cur_freq` | Current GPU clock in Hz | If readable | DECISIONS.md note D-?: this path requires root on the RedMagic — our probe (`runtime/probes/phone/2026-05-16T100713Z/gpu-clock.txt` is empty) confirms it is NOT readable without root. |
| Adreno max_freq | `/sys/class/devfreq/*kgsl*/max_freq` | Maximum permitted GPU clock | If readable | Same. |
| Game Space GPU clock path | `/sys/class/kgsl/kgsl-3d0/gpuclk`, `/sys/class/kgsl/kgsl-3d0/max_gpuclk` | RedMagic-specific path; reported in `getprop.txt` under `ro.vendor.feature.zte_feature_game_controlpanel_performance_gpu_path` | If readable | RedMagic exposes these through its Game Space app to the user; whether ADB can read without root is unconfirmed and must be probed. |
| gfxinfo (per-app) | `adb shell dumpsys gfxinfo <package>` | Frame-time histogram, draw call counts | On-demand | Indirect proxy for GPU load; not a clock; not useful for compute workloads. |
| Android GPU Inspector | Host tool talking to instrumented GPU driver | Per-frame and per-counter GPU traces | Trace-based, low overhead | Requires a debuggable build of the training process or system-trace permission. Useful for one-off characterization runs; not the steady-state cadence instrument. |
| Snapdragon Profiler | Host tool | GPU counters, kernel timing | On-demand | Same caveat. |

**Working assumption:** on an unrooted RedMagic, GPU clock is NOT directly readable at high cadence. The throughput-based proxy "tokens-per-second moving average" is the cheap reading. Direct GPU-clock monitoring requires either rooting (out of scope for the operator's regime) or piggy-backing on a one-shot Snapdragon Profiler trace at a fixed schedule. **Decision D-006 / D-007 from `DECISIONS.md` should be re-opened with this finding.**

### 2.4 Thermal sensors — broad and noisy

The probe at `runtime/probes/phone/2026-05-16T100713Z/thermal.txt` shows 76+ named thermal zones, including:

- `cpu-0-*` through `cpu-1-*` (Oryon CPU clusters; Phoenix L on cluster 1, Phoenix M on cluster 0)
- `gpuss-0` through `gpuss-7` (GPU subsystem zones)
- `nsphvx-0..2`, `nsphmx-0..3` (Hexagon HVX and HMX subunits; the NPU temperatures)
- `ddr` (DRAM)
- `aoss-0..3` (always-on subsystem)
- `skin-msm-therm`, `xo-therm`, `usb-therm`, `wls-therm`, `battery` (skin and external)
- many PMIC and battery-current-limit zones (`pmih010x-*`, `pm8550-*`)

Cadence: 1 Hz read from `cat /sys/class/thermal/thermal_zone*/temp` is cheap and verified working in our probe.

**Selection for the training authority gate (default subset):**
- `cpu-1-*` for Phoenix L (optimizer step)
- `cpu-0-*` for Phoenix M (data pipeline)
- `gpuss-*` mean for Adreno
- `nsphvx-*` and `nsphmx-*` mean for Hexagon
- `ddr` for memory subsystem
- `skin-msm-therm` for the operator-relevant skin reading
- `battery` for the battery-safety reading

**Disqualifying thresholds (operator-set, treat as inputs):**
- `battery >= 42 °C` for 60 s = run abort (matches existing `battery_heat_risk` falsifier)
- `skin-msm-therm >= 45 °C` sustained = thermal-safety abort
- any of `cpu-0-*`, `cpu-1-*`, `gpuss-*` reading missing or pinned at -40960 (sensor failure) = re-probe

The negative readings in the probe (lines 146, 147, 151, 152, 165, 166, 167) are sensor-disabled or fault states and must be filtered, not averaged.

### 2.5 CPU clock and utilization per core

| Source | Path | What it reports | Cadence |
|---|---|---|---|
| Per-core current frequency | `/sys/devices/system/cpu/cpu<N>/cpufreq/scaling_cur_freq` | Hz | 1 Hz cheap |
| Per-core utilization | `/proc/stat` lines `cpu<N> ...` | jiffies | 1 Hz; rate-of-change |
| Per-core load average | `top -n 1 -d 0.5 -m 5` parsed | percent | second-scale |

CPU clock readings ARE typically readable on Android without root (this is one of the few sysfs paths Android leaves open). Verify on SM8750 during probe.

### 2.6 Logcat — LMK, thermal, charging events

```
adb shell logcat -b system,events -s lowmemorykiller:* ActivityManager:* OOM:* thermal:* battery:* charger:* -d -T '<start_time>'
```

Must run as a streaming consumer for the duration of the run. Events of interest:
- LMK kills targeting the training PID
- thermal-zone trip events from kernel
- charging-mode transitions
- ActivityManager kills (Android may kill the training process if it deems it a foreground-service violation)

### 2.7 What CANNOT be measured on this phone

This list IS the protocol's honesty constraint:

1. **Per-substrate energy attribution** (CPU vs GPU vs NPU vs DRAM joules). No ODPM. No alternative without root + custom kernel + on-die rail sensing.
2. **Sub-second GPU clock** on an unrooted device, except via one-shot GPU Inspector traces.
3. **NPU clock and utilization** at any cadence. QNN does not expose Hexagon clock to userspace. Inferred only through wall-clock latency of a Hexagon kernel.
4. **DRAM bandwidth utilization** as a primary signal. Available only indirectly via Snapdragon Profiler one-shot traces, not as a sampled time-series.
5. **SoC die temperature distinct from package skin** beyond what the named thermal zones expose. Junction temp of the GPU shader array is not directly readable.
6. **Joules consumed by the SoC during plugged-in operation** without an external USB power meter or a calibrated battery-discharge tare procedure.

Any A-vs-B claim that depends on a quantity in this list is unfalsifiable on this hardware as currently provisioned. The protocol below avoids depending on any of these.

---

## 3. The joule-measurement problem and the best obtainable protocol

The single hardest measurement in the protocol is energy in joules. The phone is a buffered system: the charger feeds the battery (or, under bypass charging, the SoC directly with some buffering); the battery feeds the SoC. Reading "battery current" does not give SoC current except under one very specific regime — pure battery discharge with the charger disconnected.

### 3.1 The four operating regimes

| Regime | USB connected | Charge Separation | Battery state | What "battery current" measures | What "USB current" measures (if external meter) |
|---|---|---|---|---|---|
| (1) Pure battery | no | n/a | discharging | SoC + display + radios | n/a |
| (2) Plugged-in, no bypass | yes | OFF | charging | (charger current) − (SoC current); near zero or charging-direction | total: SoC + battery charging |
| (3) Bypass charging, battery cap reached | yes | ON | trickle | small balancing current ≈ 0 | ≈ SoC + display + radios (the load) |
| (4) Bypass charging, battery below cap | yes | ON | slow charge | small charging current | SoC + slow battery top-up |

The fridge-mode operator regime (Phase 1A and beyond) is regime (3): Charge Separation ON, battery cap 70–80 %, run starts at cap. This is the cleanest plugged-in regime for energy attribution because the battery's contribution is approximately zero.

### 3.2 The three energy-measurement protocols, ordered by fidelity

#### Protocol J-1: External USB power meter (REQUIRED for plugged-in regimes)

Hardware: inline USB-C power meter logging at 100–1000 Hz to a host (USB pass-through or Bluetooth). Examples: ChargerLAB POWER-Z KT002 / AK001 (~$30–$60), Plugable USBC-VAMETER3 (~$50, USB-A serial logging), or a Joulescope JS220 if budget allows (~$1000, 1 MHz, 9-decade dynamic range, professional metrology).

```
E_USB([t_a, t_b]) = ∫_{t_a}^{t_b} V_USB(t) · I_USB(t) dt
```

Where `V_USB` and `I_USB` are the meter readings, sampled at meter cadence. Under regime (3) with battery cap reached, `E_USB ≈ E_SoC + E_display + E_radios`. Subtracting `E_display + E_radios` (measured during an idle tare) gives `E_SoC` to within ~5–10 % accuracy on a $50 meter, ~1 % on Joulescope-class.

**Required calibration runs (tare):**
- T-A: phone idle, screen off, all radios on, Game Space inactive, 10 min. Records baseline SoC load.
- T-B: phone idle, screen min brightness, all radios on, Game Space active (fan running), 10 min. Records fan + Game Space overhead.
- T-C: as T-B but Termux foreground with `while true; do sleep 1; done` — records the runner-thread overhead before any training.

Subtract the median of T-B from training-run `E_USB` to get `E_training`.

**Uncertainty bound:** ~5–10 % at the $50 meter level. The dominant uncertainty is not the meter — it is whether the tare correctly captures the time-varying baseline (the fan duty cycle is itself thermally driven). Report `E_training ± uncertainty(E_training)` where uncertainty includes meter spec + tare variance.

**This is the only plugged-in joule measurement Resistance V2 will accept as the energy denominator.** Without it, any plugged-in `M_A` is rhetoric.

#### Protocol J-2: Battery-discharge tare (REQUIRED for battery-only regimes; SUFFICIENT alone if plugged-in regimes are not needed)

Hardware: none beyond the phone. Method: start the run with the charger disconnected, battery freshly charged to a known level, and integrate battery current over the run window.

```
E_battery([t_a, t_b]) = ∫_{t_a}^{t_b} V_battery(t) · I_battery(t) dt
                      ≈ Σ_k V_battery(t_k) · I_battery(t_k) · (t_{k+1} - t_k)
```

Where samples are at 1 Hz from `/sys/class/power_supply/battery/voltage_now` and `current_now`.

Alternative form using `charge_counter` (preferred when available, lower variance):

```
E_battery([t_a, t_b]) = (charge_counter(t_a) - charge_counter(t_b)) · V_battery_mean
```

Where `V_battery_mean` is the median voltage over the window. The `charge_counter` form averages out the fuel-gauge sampling noise.

**Uncertainty bound:** ~10–20 %. Battery internal resistance loss is not captured (the battery is itself dissipating energy as heat as it discharges; this heat does NOT reach the SoC). For a fresh, well-conditioned RedMagic battery at room temperature, internal-resistance loss is ~3–5 % of throughput; rises with low SOC. Run with battery between 80 % and 20 % SOC to minimize.

**Constraints on the run:**
- Phone screen off, all unnecessary radios disabled, Game Space active with fan only on what's needed.
- Battery temperature stays within 5 °C of ambient — runs that thermally cycle the battery during the measurement break the assumption.
- Run must terminate before SOC drops below 20 % or fuel-gauge nonlinearity dominates.
- Maximum reasonable single-run window: ~2–3 hours (battery capacity 5000 mAh × 8 V ≈ 40 Wh; training load ~5–8 W; so 5–8 h of training is feasible, but 2–3 h is the high-confidence window).

**This is the only joule measurement that requires no hardware beyond the phone.** It is the right starting point for Phase 0E small experiments. It is NOT sufficient for the multi-day plugged-in regime that the PRD targets.

#### Protocol J-3: Differential plugged-vs-tare (DEPRECATED — do not use)

Estimate SoC energy by measuring the plugged-in run's electric charge into the battery, plus the discharge that would have occurred at the same load on battery-only. This requires assuming the SoC consumes the same power in both regimes, which is wrong (the charging circuit itself consumes power; the battery charging current is non-linear in SOC; the bypass logic adds overhead). Listed here only so the protocol-author resists the temptation to substitute it for J-1.

### 3.3 Decision rule

| Regime | Required protocol |
|---|---|
| Phase 0E pilot (small probe, 10 min – 2 h, no fridge) | J-2 (battery discharge tare) |
| Phase 0E E0.4 sustained 2 h, plugged in | J-1 (external USB meter) — operator must procure meter before this step |
| Phase 1A 100M-token run, fridge mode, plugged | J-1 mandatory |
| Any A-vs-B claim that crosses plugged/unplugged regimes | J-1 + J-2 (one of each) |

Any phase that needs a joule denominator without a J-1 reading should NOT be reported with `M_A` as a primary metric. It can report `M_B` (tokens-to-target-NLL under thermal gate), which does not depend on joules. This is the structural protection against `fp-toolbusy` (specifying a protocol that cannot be run).

### 3.4 Operator hardware ask

Procure ONE of:
- ChargerLAB POWER-Z KT002 (~$60, 1000 Hz internal, USB-A serial export to host via PD-tester firmware)
- Plugable USBC-VAMETER3 (~$50, lower cadence, simpler firmware)
- Joulescope JS220 (~$1000, 1 MHz, the right tool if the metric is going to be defended in publication)

Without this, the energy-half of the authority metric is approximate (±15–20 %) at best, and the plugged-in regime is unmeasurable. The recommendation is the cheaper meter first to unblock the protocol; the Joulescope only if the project later needs cross-cited energy numbers.

---

## 4. The thermal-constraint operationalization — what "sustained" means

"Sustained 6-hour run" is currently unspecified language. The four formal questions:

### 4.1 When does the steady-state window begin?

`t_steady` = earliest `t > 0` such that ALL of the following have held for 5 consecutive minutes:
- `skin-msm-therm` time-derivative (1-min EWMA) below 0.5 °C/min
- `battery` temperature time-derivative below 0.5 °C/min
- token-throughput time-derivative (1-min EWMA) below 5 %/min
- `MemAvailable` time-derivative below 100 MB/min
- no LMK or major-fault event in the last 5 min

This is the definition of "thermal + memory + throughput equilibrium." It typically occurs 5–15 minutes into a run on this hardware class. Steady-state windows shorter than 5 min are too noisy for the variance-of-the-ratio arithmetic in section 6.

### 4.2 When does a run get disqualified by thermal violation?

Hard gates (run aborts; metric is NOT reported):
- `battery >= 42 °C` for 60 s (matches `battery_heat_risk` falsifier)
- `skin-msm-therm >= 45 °C` for 5 min (safety)
- any GPU-clock proxy below 600 MHz for >10 % of any 1-hour window (matches `thermal_throttle` falsifier; requires GPU-clock readable, see §2.3 caveat)

Soft gates (run continues; flag in the report; metric is annotated):
- any of the named thermal zones reads > 80 °C for >1 min
- skin > 40 °C
- battery > 38 °C

Soft-gate annotations are aggregated as `thermal_excursion_count` and `thermal_excursion_seconds`. Two otherwise-identical runs with different thermal excursion totals are not directly comparable on `M_A`; they may be comparable on `M_B` if both reached target.

### 4.3 When does cooling (RedMagic fan, fridge ambient, bypass charging) enter the measurement?

The cooling regime is a categorical variable that pre-conditions the measurement, not part of the metric. The protocol reports:

- `cooling_regime` ∈ {`ambient_no_fan`, `ambient_fan`, `fridge_fan`, `ambient_bypass`, `fridge_bypass_fan`, ...}
- `ambient_temperature_c` (room or fridge interior, operator-measured)
- `charge_separation` ∈ {`on`, `off`}
- `battery_cap_pct` (70, 80, 100)
- `performance_mode` ∈ {`stable`, `extreme`} (RedMagic OS modes)

A-vs-B comparisons are only valid within the same `cooling_regime` / `ambient_temperature_c` / `charge_separation` / `battery_cap_pct` / `performance_mode` tuple. Cross-regime comparison is a different research question (the "thermal-policy elasticity" question).

### 4.4 The "tokens-to-target-NLL under sustained thermal" formalization (Candidate B)

```
M_B(T) = {
    "tokens_to_target": min { N : NLL(θ at N tokens; D_probe) ≤ T_NLL },
    "thermal_status": "sustained" if no hard gate violated in [0, t at N tokens]
                      "violated"  otherwise
}
```

A run with `thermal_status == "violated"` is DISQUALIFIED. `M_B = ∞`. The thermal gate is not soft; it is the entire reason for thermal constraint to enter the metric.

This is the only candidate metric that operationalizes "sustained" rigorously. `M_A` reports the ratio over a window that the protocol asserts WAS sustained (because the run was not aborted), but `M_B` directly tests that the model reached a target under sustained thermal — which is the system-level question.

---

## 5. The "useful learning" definition gap

The other half of the metric — "useful learning" — depends on `D_probe`. This document cannot define `D_probe` because the corpus does not yet exist. This is the dependency on the corpus-characterization agent's deliverable.

What CAN be specified now:

### 5.1 The probe structure (independent of corpus content)

Every metric run requires THREE held-out probes, evaluated at the same checkpoint cadence:

| Probe | Purpose | Size | Construction |
|---|---|---|---|
| `D_target` | "useful learning" on the target distribution | 100K–500K tokens | Held-out from the same source as the training corpus. Same domain, same language mix. The numerator of `M_A`'s NLL improvement. |
| `D_retention` | catastrophic-forgetting guard | 100K–500K tokens | Generic English (Wikipedia + cleaned Common Crawl) NOT overlapping the training corpus. The retention gate of `M_F`. |
| `D_general` | cross-domain transfer | 100K–500K tokens | A small set of well-known benchmarks (translated/native) — for example MMLU-multilingual, ARC, a coding probe (HumanEval), a math probe (GSM8K). The per-domain vector of Candidate E. |

The exact corpora are inputs from the corpus-characterization agent's deliverable. This protocol assumes those probes exist as named, deduplicated-from-training, hashed artifacts before any A-vs-B claim is made.

### 5.2 Evaluation cadence

Held-out NLL is evaluated at:
- `t = 0` (base-model anchor)
- `t = t_steady` (start of measurement window)
- every 10 % of planned wall-clock window thereafter (e.g. for a 6-hour run, every 36 min)
- `t = t_end`

Each evaluation requires a forward pass over the full probe (no training, no gradient). On the RedMagic, evaluating 500K tokens with Qwen2.5-1.5B at the projected ~700 tokens/sec inference rate costs ~12 min — non-trivial. The evaluation cadence is a tunable; finer cadence gives smoother NLL trajectory but eats into training wall-clock.

Trade-off:
- 10 evaluations per run × 12 min = 2 hours of eval overhead in a 6-hour window.
- Reduce probe to 100K tokens: 10 evaluations × 2.4 min = 24 min overhead, but probe variance is 5× larger (variance ~ 1/N).

The right cadence is a hyper-parameter of the protocol, not a free choice. Lock it once and reuse across A-vs-B runs.

### 5.3 The "useful" half is corpus-dependent — flag for the corpus agent

This protocol asserts that `D_target`, `D_retention`, `D_general` exist as named hashed artifacts. The corpus-characterization agent must deliver them with:
- token count
- sequence-length distribution
- domain / language tag distribution
- deduplication audit against any candidate training corpus
- a sha256 manifest

Until those probes exist, NO `M_A`, `M_B`, `M_F` reading is meaningful. This is the upstream dependency that the orchestrator's Wave-2 dispatch implicitly relies on.

---

## 6. End-to-end measurement protocol — sampling cadences, run lengths, statistical treatment, A-vs-B comparison

This section is the executable protocol. Run this and you get a number. Skip a step and the number is theater.

### 6.1 Pre-run

1. Generate `run_id` (UUID). All files in `runtime/runs/<run_id>/`.
2. Capture full device probe (already implemented: `scripts/host/phone_probe.sh`). Verify SoC target SM8750, confidence 1.0.
3. Verify `D_target`, `D_retention`, `D_general` exist as hashed artifacts. Verify they are disjoint from the training corpus by hash check.
4. Verify cooling regime: Game Space active, Charge Separation ON if plugged, battery temp < 30 °C at start, fan on.
5. Verify external USB power meter logging at >= 100 Hz to host file (J-1) OR battery cap >= 80 % and starting battery state at level >= 90 % (J-2).
6. Run tare T-A, T-B, T-C (each 10 min) and log to `runtime/runs/<run_id>/tare-{A,B,C}.jsonl`.
7. Evaluate base-model NLL on all three probes (record `NLL_*(θ_0)`).

### 6.2 Sampling cadences during the run

| Channel | Cadence | Sink |
|---|---|---|
| Token throughput (tokens trained / sec) | 1 Hz | `audit.jsonl` |
| Train-step loss | per step | `audit.jsonl` |
| `current_now`, `voltage_now`, `charge_counter`, `temperature` | 1 Hz | `power.jsonl` |
| Thermal zone temps (selected subset) | 1 Hz | `thermal.jsonl` |
| `/proc/<pid>/smaps_rollup` (training PID) | 1 Hz | `memory.jsonl` |
| `/proc/<pid>/stat` major+minor faults | 1 Hz | `memory.jsonl` |
| `/proc/meminfo` | 0.1 Hz (every 10 s) | `memory.jsonl` |
| CPU per-core freq + utilization | 1 Hz | `cpu.jsonl` |
| USB power meter (if J-1) | 100 Hz (meter native) | `usb_power.csv` (host-side) |
| Logcat (LMK, thermal, charger, ActivityManager) | event-driven stream | `logcat.txt` |
| Held-out NLL evaluation (all 3 probes) | every 10 % of planned window | `eval.jsonl` |

All `*.jsonl` files are append-only with a leading `recorded_at_iso` field. The measurement rig runs as a single Python process pinned to Phoenix M cores 4–5 (not the training cores). Total measurement overhead must be < 2 % of CPU load — verified by a tare run with the measurement rig active but no training.

### 6.3 Run length

- Pilot (Phase 0E E0.1–E0.3): 10 min – 30 min sustained training after `t_steady`.
- Phase 0E E0.4 thermal+energy gate: 2 hours sustained training after `t_steady`.
- Phase 1A 100M-token run: ~40 hours wall clock (per source-brief throughput model); measurement window is everything after `t_steady` until OOM, thermal abort, or end-of-corpus.

A run is too short for a defensible `M_A` if the measurement window is less than 30 min after `t_steady`, because NLL trajectory noise dominates the ratio. Pilot runs are for protocol validation, not metric claims.

### 6.4 Statistical treatment

#### NLL evaluation variance

For a probe of `N` tokens, `NLL` is a mean over `N` per-token cross-entropies. Per-token cross-entropy has empirical standard deviation `σ_NLL` (depends on probe; measure it from the base-model evaluation). Standard error of the NLL estimate:

```
SE(NLL) ≈ σ_NLL / sqrt(N)
```

For Qwen2.5-1.5B on a typical multilingual probe, `σ_NLL` is order 5–10 nats/token; with `N = 500K`, `SE(NLL) ≈ 0.01 nats/token`. To detect a `ΔNLL` of 0.05 nats/token at p < 0.05 requires ~3 SE separation — feasible at the 500K probe size, tight at 100K.

#### Energy variance

`E([t_steady, t_end])` from J-1 is a sum of high-rate meter samples; meter spec gives ~1 % at the $50 level, ~0.1 % at Joulescope. Time-base noise dominates: a 60-min window with sample noise of 1 % gives `SE(E) ≈ 0.01 E`. From J-2, `SE(E) ≈ 0.05 E` due to fuel-gauge nonlinearity and internal-resistance loss.

#### Ratio variance (delta method)

```
M_A = ΔNLL / E
Var(M_A) ≈ (1 / E^2) Var(ΔNLL) + (ΔNLL^2 / E^4) Var(E)
SE(M_A) ≈ sqrt(Var(M_A))
```

For a 6-hour run with `ΔNLL = 0.2 nats/token`, `E = 100 kJ`, `SE(NLL) = 0.01`, `SE(E) = 1 kJ`:

```
Var(ΔNLL) ≈ 2 × (0.01)^2 = 2e-4 (the factor 2 because ΔNLL is a difference of two independent NLL evaluations)
SE(ΔNLL) ≈ 0.014
SE(M_A) / M_A ≈ sqrt( (0.014 / 0.2)^2 + (1 / 100)^2 ) ≈ 0.07
```

So `M_A` is determined to ~7 % under these conditions. Tighter probes or longer windows reduce this. The variance budget is dominated by the NLL evaluation, not by the energy measurement, so long as J-1 is used.

#### Number of independent runs

A single run gives `M_A ± 7 %`. An A-vs-B claim that A is better than B by a factor < 1.07 is NOT defensible from a single A-run and single B-run. The minimum required for a defensible A-vs-B claim:

- 3 runs per arm (A and B both run 3 times with independent random seeds and freshly-charged thermal state)
- difference of arm means tested with a paired (matched-seed) bootstrap or Welch's t-test
- effect size ≥ 1.2× ratio (i.e. M_A_arm_A / M_A_arm_B ≥ 1.2)
- p < 0.05 with multiple-comparisons correction for the four-metric tuple

3 runs per arm is the minimum. 5 is preferred. Less than 3 runs per arm is single-anecdote evidence; report it as a probe, not a claim.

### 6.5 A-vs-B comparison test

```
For each of 3+ matched seeds:
    run_A(seed) -> (M_A_A, M_B_A, vector_E_A, retention_pass_A)
    run_B(seed) -> (M_A_B, M_B_B, vector_E_B, retention_pass_B)

If any retention_pass_A is False OR any retention_pass_B is False:
    that seed's run is DISQUALIFIED, not analyzed.

Across surviving seeds:
    paired diff Δ_A = M_A_A - M_A_B
    bootstrap 95% CI on mean(Δ_A) across seeds
    if CI excludes 0 with sign favoring one arm AND |mean(Δ_A) / mean(M_A_B)| >= 0.2:
        DEFENSIBLE: that arm is better on M_A by the observed effect size
    else:
        NOT DEFENSIBLE: more runs needed, or the difference is real but smaller than the gate, or both
```

Same procedure for `M_B`, applied to the per-domain `vector_E` Pareto check (use a vector Wilcoxon signed-rank test or report per-domain p-values with Holm correction).

**A claim of the form "method A beats method B on this SoC" requires:**
1. ≥3 surviving (non-disqualified) seeds per arm
2. retention gate passed on every surviving seed
3. paired bootstrap CI on `ΔM_A` excludes 0 in the favored direction
4. effect size on the favored metric ≥ 20 %
5. all per-domain `ΔNLL_d` either favor A or are within noise (no statistically significant regression on any domain)

Anything less is `fp-overclaim` and the falsifier `overclaim` in the registry fires.

### 6.6 What constitutes a violated gate that disqualifies a run

| Gate | Trigger | Effect |
|---|---|---|
| OOM | training process killed by OOM or peak PSS > 22 GB | RUN DISQUALIFIED |
| LMK kill | LMK targets training PID | RUN DISQUALIFIED |
| ActivityManager kill | ActivityManager forcibly stops training PID | RUN DISQUALIFIED |
| Battery thermal | battery ≥ 42 °C for 60 s | RUN DISQUALIFIED (abort) |
| Skin thermal | skin-msm-therm ≥ 45 °C for 5 min | RUN DISQUALIFIED (abort, safety) |
| Charge bypass invalid | battery SOC drift > 2 pp/h under bypass test | RUN DISQUALIFIED (Charge Separation not actually bypassing) |
| GPU thermal throttle | GPU clock proxy below 600 MHz for >10 % of 1-h window | RUN DISQUALIFIED |
| Frozen-weight drift | any frozen parameter SHA changes during training | RUN DISQUALIFIED (ELO/LoRA violation) |
| Probe-corpus overlap detected | sha overlap > 0 between training corpus and any probe | RUN DISQUALIFIED |
| Measurement rig overhead | rig CPU > 4 % of training cores' time | RUN DISQUALIFIED (measurement pollution) |
| Retention regression | `ΔNLL_retention > δ_retention` (default 0.01 nats/token) | METRIC DISQUALIFIED (run completes, M_A NOT reportable, M_F is "FAIL") |

A run that finishes but violates any disqualification gate has no `M_A`, no `M_B`, and contributes nothing to an A-vs-B claim except a "this configuration is not viable" datapoint.

---

## 7. What is NOT measurable on this phone without additional hardware

Restated explicitly so this section is grep-able:

1. **Per-substrate energy** (CPU vs GPU vs NPU vs DRAM joules). Requires ODPM hardware not present on this SoC, OR a calibrated power model from a Pixel 9 Pro reference rig (not in scope), OR root + custom kernel + on-die rail tapping (not safe in operator regime).
2. **Sub-second GPU clock** without root. Available only via one-shot Snapdragon Profiler / Android GPU Inspector trace, not as a steady-state stream.
3. **NPU clock and utilization**. Not exposed by QNN to userspace at any rate.
4. **DRAM bandwidth utilization** as a time-series. Only available as one-shot traces.
5. **SoC die / GPU shader-array junction temperatures** beyond the named thermal zones.
6. **Plugged-in SoC energy without external USB meter**. Battery-counter readings under bypass charging do NOT represent SoC power.

Any deliverable that claims to A-vs-B on a quantity in this list, on this phone as currently provisioned, is unfalsifiable. The protocol above is structured to avoid depending on any of these.

---

## 8. Open tensions — places the metric formalization remains ambiguous

### 8.1 Curriculum-dependent NLL trajectory

`M_A` assumes the NLL trajectory is monotone decreasing during the measurement window. Curriculum schedulers that introduce harder material late in the run can cause `NLL` to rise. Under this regime `ΔNLL = NLL(t_end) - NLL(t_steady)` may be negative — the metric becomes negative even for a training run that learned things, because the late-curriculum material was harder than the early material.

Mitigation: evaluate against `D_target` not against the current training distribution. `D_target` is fixed; if the model learned, `NLL(D_target)` decreases monotonically (in expectation, modulo SGD noise). The trajectory on the training-loss telemetry is a different signal and should not be confused with the metric.

Open question: when the corpus IS a curriculum (Polymath staged language schedule), should `D_target` be the final-stage distribution, the union of all stages, or a multi-stage vector? This is a question for the corpus-characterization agent, not this protocol.

### 8.2 Probe evaluation cost as a metric input

Held-out evaluation consumes joules and consumes wall-clock that is otherwise training. The protocol exempts evaluation from the metric (joules of evaluation are NOT counted in `E`, and training-only tokens are counted as `N_tokens`). But this means a method that requires very frequent evaluation looks artificially good on `M_A`. Address by also reporting "joules per token including evaluation overhead" as a secondary number.

### 8.3 Method-dependent definition of "tokens"

For LoRA / ELO, `N_tokens` is unambiguous (input sequence tokens). For zeroth-order (MeZO, MobiZO), each "step" involves multiple forward passes over the same tokens — does each forward pass count? Under Resistance V2, the right answer is YES: `N_tokens` is forward-pass token-throughput, because the metric is wall-clock-and-energy efficiency, not gradient-step efficiency. This penalizes ZO methods by a 2–3× factor, which is fair: they really do spend that much energy per useful update.

### 8.4 The `t_steady` definition is a hyper-parameter

The 5-minute holding window in §4.1 is an operator-chosen threshold. Too short → noisy steady state declared too early. Too long → small runs never report `M_A`. Lock the threshold in a run-config and don't tune it post-hoc per arm; tuning post-hoc is researcher-degrees-of-freedom that invalidates A-vs-B claims.

### 8.5 Bypass-charging "active" verification depends on phone OS state

The `charge_bypass_unproven` falsifier uses SOC drift over 10 min as the test. This assumes the OS does not change charging policy mid-run (e.g. for thermal reasons). RedMagic OS Game Space mode may switch charging policy under thermal load. The protocol must include a charging-policy poll at 1 Hz and abort if `Charging policy` changes during a measurement window.

### 8.6 The retention probe vs the catastrophic-forgetting falsifier

`catastrophic_forgetting` falsifier uses "English anchor drop > 1 pp" (`polymath_ai/falsifiers/registry.py` line 199). This is a percent-points measure on what is presumably an English benchmark accuracy. The metric protocol in §1 (F gate) uses a nats/token threshold on a held-out NLL probe. These are different operationalizations of the same concept. The protocol above defaults to the NLL-based form (it is the natural unit of `M_A`) but the project must decide which is sovereign and which is derived. Recommendation: NLL-based as sovereign (it ports across tasks); accuracy-based as a secondary check on a fixed benchmark.

### 8.7 Cross-regime claims

The protocol forbids A-vs-B across different `(cooling_regime, ambient_T, charge_sep, battery_cap, performance_mode)` tuples. This is correct but limits the project. A separate "thermal-policy sensitivity" sub-protocol would compare the SAME method under different regimes to characterize how `M_A` varies with cooling. This is a different research question and should not be smuggled into the A-vs-B claim space.

---

## 9. Open questions for the operator

1. **Will the operator procure an inline USB-C power meter?** The choice between Plugable USBC-VAMETER3 (~$50, simpler), ChargerLAB POWER-Z KT002 (~$60, higher-cadence), or Joulescope JS220 (~$1000, metrology-grade) determines whether plugged-in joule numbers are approximate or publishable. Without ANY of these, the protocol can only report `M_B` for plugged-in runs.

2. **Can `/sys/class/power_supply/battery/current_now`, `voltage_now`, `charge_counter`, and `energy_now` be read over ADB without root on the RedMagic?** Our 2026-05-16 probe captured `dumpsys battery` but did not directly probe these sysfs paths. Required as a Phase 0E pre-flight.

3. **Can `/sys/class/kgsl/kgsl-3d0/gpuclk` be read over ADB without root?** RedMagic Game Space hints it might be exposed. Required as a Phase 0E pre-flight; if no, the `thermal_throttle` falsifier and Candidate B's thermal-gate operational definition need to fall back to GPU thermal-zone proxies (`gpuss-*`) rather than direct clock readings.

4. **Is `BATTERY_PROPERTY_ENERGY_COUNTER` available via Android BatteryManager on SM8750 (Termux Java bridge required to query)?** If yes, this is a lower-variance energy source than integrating `current_now * voltage_now`. Required as a Phase 0E pre-flight.

5. **What is the operator-chosen `cooling_regime` matrix for the formal experiment program?** The protocol works inside any one regime; the program must commit to which combinations of {fridge/ambient × fan/no-fan × bypass/no-bypass × performance-mode} will be run, so that comparisons are within-regime.

6. **What is the operator's tolerance for run wall-clock budget?** The protocol's "≥3 surviving seeds per arm × N arms × 6 h per run" implies tens of hours of phone time per defensible A-vs-B claim. If the operator wants faster turn, the protocol can shrink to 30 min steady-state windows (with proportionally wider CIs) — but the shrinkage must be a config commitment, not a per-run tuning knob.

7. **Who hashes and ratifies the three probes (`D_target`, `D_retention`, `D_general`)?** The corpus-characterization agent owns the construction; the operator owns the ratification (license attestation, dedup audit sign-off). Until they exist with manifests in `corpus/manifests/probes/`, this protocol's `M_A` is not computable.

8. **Should the `δ_retention` threshold be 0.01 nats/token (the protocol default), or harder (0.005)?** Operator call. Tighter threshold = more runs disqualified; looser = more `fp-benchmarkproxy` slip through.

---

## 10. Sources

### Android measurement infrastructure

- Linux kernel `power_supply` sysfs interface — units, semantics: https://www.kernel.org/doc/Documentation/ABI/testing/sysfs-class-power
- Android Health 2.1 HAL — what the framework exposes from the underlying sysfs: https://source.android.com/docs/core/perf/health/implementation-2-1
- Android `IPowerStats` HAL — power-rail interface (Pixel-only in practice): https://source.android.com/docs/core/power/power-stats-hal
- Android `BatteryProperty` API and `BATTERY_PROPERTY_ENERGY_COUNTER` (nWh): Android `BatteryManager` reference (developer.android.com/reference/android/os/BatteryManager)
- Perfetto power data sources documentation (battery counters and ODPM): https://perfetto.dev/docs/data-sources/battery-counters
- Android `smaps_rollup` patch history (PSS sampling overhead and cadence): https://patchwork.kernel.org/comment/20801969/
- Android GPU Inspector (Adreno counters): https://gpuinspector.dev/
- Qualcomm Vulkan Adreno Layer and Snapdragon Profiler: https://docs.qualcomm.com/

### Energy benchmarking literature

- MLPerf Power benchmark methodology and minimum 60-s measurement windows: https://arxiv.org/abs/2410.12032 (Tschand et al., HPCA 2025)
- MLCommons Power Working Group at HPCA 2025: https://mlcommons.org/2025/03/ml-commons-power-hpca/
- MLPerf training power measurement policy (the source-of-truth document for the `Σ V·I·dt` formulation): https://github.com/mlcommons/training_policies/blob/master/power_measurement.adoc
- ML.ENERGY Benchmark — automated inference energy with joules per token as the primary unit: https://arxiv.org/abs/2505.06371
- TokenPowerBench: https://arxiv.org/abs/2512.03024
- "Tokens per Joule" applied to clinical LLM inference (John Snow Labs): https://www.johnsnowlabs.com/tokens-per-joule-how-to-quantify-and-reduce-the-energy-footprint-of-clinical-llm-inference/
- "Benchmarking Energy Efficiency of LLMs Using vLLM": https://arxiv.org/abs/2509.08867

### Scaling laws and the "tokens-to-loss" frame

- Hoffmann et al., "Training Compute-Optimal Large Language Models" (Chinchilla): https://arxiv.org/abs/2203.15556
- Besiroglu et al., "Chinchilla Scaling: A replication attempt": https://arxiv.org/abs/2404.10102

### On-device training and energy reporting (state of practice)

- MeBP — memory-efficient backprop on mobile (memory-focused, no energy protocol): https://arxiv.org/abs/2510.03425
- MobileFineTuner (Gemma 3 / Qwen 2.5 mobile fine-tuning, "energy-aware scheduling" claim): https://arxiv.org/abs/2512.08211
- ZeroQAT — forward-only QAT on phone: https://arxiv.org/abs/2509.00031
- MobiZO / mobile fine-tuning via inference engines: https://arxiv.org/abs/2409.15520
- AndroWatts — Android power consumption modeling: https://hal.science/hal-04928609v1/document

### Hardware power-meter options for the joule-measurement protocol

- ChargerLAB POWER-Z KT002: https://www.chargerlab.com/
- Plugable USBC-VAMETER3 (USB-C inline, 240 W, serial export): https://plugable.com/products/usbc-vameter3
- Joulescope JS220 (metrology-grade, 1 MHz): https://www.joulescope.com/products/js220-precision-energy-analyzer

### Project-internal prior research

- `/Users/Zer0pa/Polymat AI/Polymath-AI/RESISTANCE-V2.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/research/soc-architecture-2026-05-16/heterogeneous-training-loop-shape.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/research/soc-architecture-2026-05-16/blind-spots-frontier-scan.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/source-briefs/01-on-device-training-blueprint.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/PHONE-ATTACH-RUNBOOK.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/GAME-SPACE-FRIDGE-RUNBOOK.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/FALSIFIERS.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/polymath_ai/falsifiers/registry.py` (existing `_check_energy_budget_exceeded` placeholder)
- `/Users/Zer0pa/Polymat AI/Polymath-AI/polymath_ai/experiments/phase0e.py` (existing telemetry plumbing)
- `/Users/Zer0pa/Polymat AI/Polymath-AI/scripts/host/phone_probe.sh` (existing probe collector)
- `/Users/Zer0pa/Polymat AI/Polymath-AI/scripts/termux/heartbeat.py` (existing phone-side telemetry pusher)
- `/Users/Zer0pa/Polymat AI/Polymath-AI/runtime/probes/phone/2026-05-16T100713Z/` (the actual SM8750 probe artifacts informing what is and is not readable)

---

## 11. Resistance V2 self-check

| Forbidden pattern | Did this artifact slip? |
|---|---|
| `fp-scopeevaporation` | No. The protocol explicitly rejects tokens/sec as the authority gate. `M_A` is `nats · token^-1 · J^-1` with a per-domain Pareto guard. |
| `fp-benchmarkproxy` | No. The retention gate (Candidate F) is a hard disqualifier that prevents `M_A` from being optimized while general capability regresses. |
| `fp-interimossification` | No. This artifact is explicitly a protocol specification, not a measurement. Section 0 and the open-questions section state that without (a) the operator's USB meter procurement, (b) the corpus agent's probes, and (c) Phase-0E pre-flight sysfs verification, no `M_A` is computable. |
| `fp-toolbusy` | Partial-risk. Some parts of the protocol require hardware (USB meter) or sysfs access (battery/sysfs paths) that has not been pre-verified on the RedMagic. Section 9 (open questions for operator) lists those gates explicitly so they cannot be skipped. |
| `fp-localgreen` | No. The protocol's "RUN DISQUALIFIED" list is structured so that a run that "completes" but violates a gate produces NO `M_A`. There is no path by which a thermally-cheated or memory-cheated run gets credited as a pass. |
| `fp-softrefusal` | No. The protocol does not weaken the metric; it specifies it precisely enough that a `M_A` reading from method A and method B can be directly compared under the specified conditions. |
| `fp-overclaim` | The minimum-3-seeds-per-arm rule plus the explicit 20 % effect-size threshold plus the multiple-comparisons correction is the structural protection. The protocol forbids a single-run number from being called a result. |
| `fp-demogravity` | No. The protocol does not describe a demo. It describes a measurement that defines whether a configuration even qualifies for the project's authority gate. |

The protocol is built to be deliberately costly to satisfy. That cost is the price of the authority metric meaning something.
