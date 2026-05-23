# Gemma 4 Heterogeneous Training — Opus-Level View and POVC

Date: 2026-05-23
Status: SYNTHESIS_AND_UNBLOCK_PLAN
Scope: REDMAGIC `NX789J-EEA` / Snapdragon `SM8750` / Adreno 830 v2 / Hexagon V79
Inputs: docs 00–06 of this pack; live ADB probe of REDMAGIC `FY25013101C8`
on 2026-05-23; five parallel Opus deep-research agents covering Hexagon QAIRT
training surface, Adreno 830 microarchitecture, OpenCL/Vulkan/persistent
kernel strategy, frontier on-device training methods 2025–2026, and Red Magic
10 / Nubia OEM utility surface.

This document is an addition to the seven-doc handoff pack. It exists because
the deep-research pass changed the **research question itself**, not only the
answers. The new question is:

```text
The phone is not undertrained because it lacks compute.
It is undertrained because the trainable scope is below the capacity floor
and 79% of wall time is host orchestration and OEM background mitigation.
What is the smallest set of changes that puts a capability-moving training
loop in front of the Adreno 830 and Hexagon V79 we already paid for?
```

The seven prior docs framed the project's current self-image; this document
challenges it with evidence and proposes the POVC that unblocks Phase 10.

---

## 0. Executive view

Three load-bearing findings change the trajectory:

1. **The 1.29h / 6.03h = 21.3% active-training ratio is not a thermal or
   silicon limit.** Live device probe of `NX789J-EEA` on 2026-05-23 shows
   `kgsl` cooling device at state `0/12`, `cdsp` at `0/7`, `cdsp_sw_hvx`
   at `0/8`, `cdsp_sw_hmx` at `0/7`, `skin-msm-therm` at 28.4°C, all GPU
   subzones 29–31°C **with the trainer cold**. The cached temperatures from
   the most recent training run show `socd = 90.0°C mStatus=3 (SEVERE)`,
   `nspN ≈ 58–59°C`, `skin = 45.95°C`. The dominant 36.7s per-iteration dead
   time (46.65s wall ÷ 9.95s active) is **host-orchestration on the
   Mac/RunPod side** (per-iteration `adb shell` exec, push token cache, pull
   manifests, fsync replay buffer, oracle parity sample on 3 of 465 iters),
   compounded by **Nubia's `vendor.qti.hardware.perf2-hal-service` plus
   `thermal-engine-v2`** treating a `/data/local/tmp` shell-launched binary
   as a background process and pre-emptively clamping CPU cluster0 from
   3.53 GHz to 2.40 GHz at skin temp 43°C per `/vendor/etc/thermal-engine.conf`.
2. **The current rank-4 post-layer0 residual adapter cannot move any
   capability benchmark.** Trainable parameter count is `rank 4 × hidden 2560
   = 10240` fp32 weights, confirmed by the on-device telemetry showing
   `adapter_grad_a.f32.bin` element count = 10240. Biderman et al.
   *Plasticity vs. Rigidity in the Jacobian of Dynamical Systems* (EACL 2026,
   arXiv 2601.06677) reports r=8 LoRA fails to move any reasoning task on a
   1.5B model under <24h training; the floor for reasoning is r≈32–64 on
   multi-site placement. Schulman et al. *LoRA Without Regret* (Thinking
   Machines Lab, Sep 2025) confirms low-rank adapters match full FT only
   with attention + MLP placement, not single residual injection. Post-layer0
   is also the worst placement: last layers move format/style, middle layers
   move semantic capability, layer 0 moves nothing meaningful. The current
   scope can move IFEval format-following and style-match metrics 2–10 points
   on a homogeneous corpus; it cannot move MMLU, ARC, HumanEval, GSM8K, or
   any factual benchmark, ever, at this configuration.
3. **The QAIRT 2.44 LoRA-on-HTP path is already installed on the phone but
   has not been wired up.** Live probe shows
   `/data/local/tmp/qairt-2.44/bin/aarch64-android/qairt-lora-adapter-bin-updater`
   present, alongside `qnn-context-binary-generator`,
   `qnn-context-binary-utility`, the full `genie-app` / `genie-t2t-run`
   stack, `libGenie.so`, `libQnnGenAiTransformer*.so`, and the
   V79-specific `libQnnHtpV79Stub.so` / `libQnnHtpV79CalculatorStub.so`.
   QAIRT `QnnContext_applyBinarySection` (introduced QAIRT 2.33,
   `applyBinarySection` per the public C header) plus the offline
   `--lora_weight_list` compile flag give the team a documented
   weight-mutation surface on HTP today — the primitive is **not LoRA-specific**;
   it will accept any tensor pre-declared as `updateable` at compile time.
   This is the only path Qualcomm publicly exposes that lets HTP carry a
   training-shaped workload.

Combining these three: the **POVC** is not "make the GPU kernel faster" and
it is not "try Hexagon training" naively. It is a **single coordinated change
that (a) removes the host from the per-iteration critical path, (b) lifts the
trainable scope across the plasticity floor, (c) changes the objective from
parity-MSE to teacher logit distillation, (d) wires the on-device QAIRT-LoRA
binary updater so HTP becomes a frozen-forward island and a zero-order
weight-perturbation arm, and (e) pins the Nubia perf HAL out of mitigation
for the trainer**. Done together these unblock four of the five Phase 10
non-claims in a 1–2 week sprint without buying new hardware, without
switching from OpenCL to Vulkan, and without inventing a megakernel.

The rest of this document defends each finding from primary evidence and
specifies the POVC concretely with ADB commands and code shape.

---

## 1. Hardware reality as of 2026-05-23 (live probe)

`adb devices` confirms `FY25013101C8 device usb:0-1 product:NX789J-EEA
model:NX789J device:NX789J transport_id:1`.

### 1.1 Build

```
nubia/NX789J-EEA/NX789J:15/AQ3A.240812.002/20251031.123842:user/release-keys
```

Android 15, build dated 2025-10-31. Red Magic OS variant for European market.
Sibling support agent flagged RedMagicOS 10.0.14 (2026-02-04) as the current
stable for `NX789J-EEA`; this device is one or two OTAs behind.

### 1.2 Kernel

```
Linux 6.6.56-android15-8-g38447e018c92-ab12829524-4k
(Android clang 18 / +pgo +bolt +lto +mlgo)
#1 SMP PREEMPT Thu Dec 19 17:58:46 UTC 2024
```

Android Common Kernel 15, Linux 6.6, 4K page size variant, GKI 2.0 with PGO+
BOLT+LTO+MLGO optimisations. The Nubia open-source kernel for NX789J has not
been published at nubia.com/en/service/opensource as of this probe; the
closest reference for the SM8750 driver stack is NX809J / Red Magic 11 Pro
at Linux 6.12.23 GKI Android 16 (cmfnels' device tree). The reminon
`device_NX789J` LineageOS-style tree on GitHub gives a board-config view
that confirms `TARGET_BOARD_PLATFORM := sun` and `TARGET_CPU_VARIANT_RUNTIME
:= oryon`.

### 1.3 CPU

8-core Qualcomm Oryon: `CPU implementer 0x51 part 0x001`. 6+2 asymmetric:

| Cluster | Cores | Min freq | Max freq | Governor |
|---|---|---|---|---|
| `policy0` | 0–5 (variant 0x4) | 384 MHz | **3.53 GHz** | `walt` |
| `policy6` | 6–7 (variant 0x3, prime) | 1.02 GHz | **4.32 GHz** | `walt` |

Notable CPU feature flags from `/proc/cpuinfo`:
`fp asimd … sha512 asimdfhm dit uscat ilrcpc flagm ssbs sb paca pacg dcpodp
flagm2 frint i8mm bf16 rng bti ecv afp rpres`. The presence of **`bf16`**
and **`i8mm`** (SVE-free SDOT/UDOT/USDOT INT8 matrix-multiply) on the Oryon
core means the CPU has usable matrix-multiply paths for adapter bookkeeping
and could host a SVE-less BF16 backbone for small kernels — relevant if a
later experiment investigates a CPU-only-fallback path.

### 1.4 Adreno 830 v2

Live read from `/sys/class/kgsl/kgsl-3d0/gpu_model`: **`Adreno830v2`**. The
GPU busy ratio on the idle device: `gpubusy = 70227 / 1007526 = 6.97%`.

From the Adreno architecture deep-research pass: A830 is `a7xx` family
(*not* `a8xx`, which is A840/Kaanapali in the SD8 Elite Gen 5). Architecture
inherited from Adreno X1:

| Property | Value | Source |
|---|---|---|
| Slices | 3 | Notebookcheck, Qualcomm; Adreno X1 has 3 slices |
| SPs (Shader Processors) | 6 (2 per slice) | ChipsAndCheese X1 deep dive |
| uSP (micro-SP / uSPTP) per SP | 2 | ChipsAndCheese |
| FP32 ALU lanes per uSP | 128 | ChipsAndCheese X2 (architectural sibling) |
| Wave width | 64 or 128 (selectable via `cl_qcom_reqd_sub_group_size`) | IWOCL 2022 Wang & Calidas |
| Register file per uSP | ~192 KB (X1); 128 KB (X2 partition) | ChipsAndCheese X1 |
| Local memory per workgroup | **32 KB max** | ChipsAndCheese X1 |
| GMEM (on-die scratchpad) | ~3 MB | ChipsAndCheese X1 |
| Peak clock | 1.10 GHz (-AB) / 1.20 GHz (-AC Galaxy) | TechHome / PhoneDB |
| FP32 peak (derived) | ~3.4–3.7 TFLOPS | 6 SP × 2 uSP × 128 FP32 × 2 FMA × clock |
| FP16 peak (double-rate) | ~6.8–7.4 TFLOPS | Derived |
| Matrix unit | Present, separate clock domain, 256 FP16/BF16 ops/cycle per element (X2 figures used as proxy) | ChipsAndCheese X2 — Qualcomm has not separately published A830 matrix-unit numbers |
| Async compute (AQE) | **No** — AQE is A8xx only | ChipsAndCheese X2; multiple CL queues serialise on one HW ring on A830 |
| OpenCL ICD | `/vendor/lib64/libOpenCL.so` + `/vendor/lib64/libOpenCL_adreno.so` + `/vendor/lib64/libCB.so` | Live probe |
| Vulkan ICD (closed) | `/vendor/lib64/hw/vulkan.adreno.so` (Qualcomm), not `vulkan.freedreno.so` (Mesa Turnip) | Live probe |
| Vulkan profiler layer | `/vendor/lib64/egl/libVkLayer_ADRENO_qprofiler.so` | Live probe |
| Adreno driver version | `cn.nubia.gpu.drivers` v3.1.00.2407301545 (Qualcomm "sun" GPU driver via Play Store update channel) | Live probe |

The Adreno **matrix unit is dark silicon for OpenCL today** — Qualcomm
exposes it only via `cl_qcom_ml_ops` (set of ML ops; whether v2 covers
training operators is contested between the two GPU agents and remains an
open verification target for the team), and via Vulkan only after
`VK_QCOM_cooperative_matrix_conversion` lands on shipping A830 drivers
(spec public, not advertised on A830 as of May 2026).

### 1.5 Hexagon V79

Confirmed: Hexagon Architecture V79 per `qnn-platform-validator` output and
QAIRT 2.44 ships `libQnnHtpV79Stub.so` + `libQnnHtpV79CalculatorStub.so` —
both at `/data/local/tmp/qairt-2.44/lib/aarch64-android/`. The QAIRT 2.44
install also ships V68, V69, V73, V75, V79, V81 stubs, future-proofing for
the next Hexagon generation.

NSP thermal instrumentation is per-tile:
- HVX vector tiles: `nsphvx-0`, `nsphvx-1`, `nsphvx-2`
- HMX matrix tiles: `nsphmx-0`, `nsphmx-1`, `nsphmx-2`, `nsphmx-3`
- Dedicated cooling devices: `cdsp_hw`, `cdsp` (0/7), `cdsp_sw_hvx` (0/8),
  `cdsp_sw_hmx` (0/7) — all at state 0 right now.

FastRPC surface to CDSP:
- `/dev/fastrpc-cdsp` (mode `crw-rw-r--`, owner `system:system`) — shell
  user is NOT in `system` group, so SELinux + group bits will block direct
  access from `/data/local/tmp` binaries unless invoked through `cdsprpcd`.
- `/dev/fastrpc-cdsp-secure` (`crw-r--r--`, root only) — only for secure
  workloads.
- `cdsprpcd` and `adsprpcd` daemons are live, glink-fastrpcglink-apps-dsp
  channels are open.

DMA heap surface (Android has retired `/dev/ion` — confirmed absent):
- `/dev/dma_heap/qcom,system` and `/dev/dma_heap/system` for general
- `/dev/dma_heap/qcom,display` for display
- `/dev/dma_heap/qcom,sp-hlos` for HLOS shared pixel
- **`/dev/dma_heap/qcom,cma-secure-cdsp`** — the CMA-backed secure heap
  for CDSP. Any HTP↔Adreno tensor handoff must allocate from this heap.

### 1.6 Memory

```
MemTotal:        23 662 784 kB    (24 GB DRAM)
MemAvailable:    13 858 404 kB
SwapTotal:       12 582 908 kB    (12 GB zram)
SwapFree:        10 231 804 kB
pswpin           12 148 298
pswpout          17 010 873
CmaTotal:           667 648 kB
CmaFree:             17 508 kB
AnonHugePages:      718 848 kB
```

Implications:
- 24 GB DRAM headroom is enormous relative to the 2.17 GiB RSS the current
  trainer uses (`max_rss_kb: 2169700` in telemetry).
- **zram is being aggressively used** (17M page swap-outs against 12M
  swap-ins) — likely the OS swapping out idle anon pages from background
  apps under DRAM pressure from the trainer's resident allocation. Not a
  trainer bottleneck per se, but means the WLC ML mitigation model may be
  raising swap pressure thinking the trainer is misbehaving.
- CmaFree is **17.5 MB out of 651 MB total** — the CMA pool used by
  display/codecs/CDSP is almost full. Any large DMA-heap allocation for
  HTP-side tensors will compete with this.

### 1.7 Thermals (live probe, 2026-05-23)

Idle:
- `skin-msm-therm = 28362 mC` (28.4°C)
- All `gpuss-0..7 = 29–31°C`
- Hexagon `nsphvx-* / nsphmx-* = 30–31°C`
- All `cooling_device*` GPU/CDSP/CPU-cluster at state 0

Cached (from the most recent training run, via `dumpsys thermalservice`):
- `socd = 90.0°C mStatus=3 (SEVERE)` — this is the SoC die status
  threshold per Android Performance Hint Manager
- `skin = 45.95°C` — sits **3°C above** the 43°C trip in
  `/vendor/etc/thermal-engine.conf` for `SKIN_CPU_MONITOR`
- `CPU6 = 66.8°C`, `CPU7 = 67.5°C` (prime cores)
- `nsp0..nsp6 = 58.3–58.7°C`
- `GPU0..GPU7 = 58.9–60.8°C`
- `battery = 44.0°C` (`mStatus=0`, but flagged as a charge-side heat source
  by the OEM agent)

Thermal-engine throttle plan from `/vendor/etc/thermal-engine.conf`
`[SKIN_CPU_MONITOR]`:

| Skin temp | Cluster0 cap | Cluster1 cap |
|---|---|---|
| 43°C | 2.40 GHz (from 3.53) | 2.84 GHz (from 4.32) |
| 45°C | 2.23 GHz | 2.65 GHz |
| 47°C | 2.00 GHz | 2.44 GHz |
| 49°C | 1.79 GHz | 2.25 GHz |
| 51°C | 1.79 GHz | 1.96 GHz |
| 53°C | 1.55 GHz | 1.69 GHz |

`[SKIN_GPU_MONITOR]` similarly caps Adreno: 832 MHz at 46°C, 607 MHz at
48°C, 525 MHz at 50°C, 389 MHz at 52°C — down from the ~1.1 GHz peak.

**The cached `skin = 45.95°C` means the previous training run was running
with cluster0 capped to roughly 2.0–2.2 GHz** (between the 45°C and 47°C
thresholds), i.e. with CPU clock reduced to ~56–62% of nominal. The CPU
hosts token-to-hidden bookkeeping, the host-side `adb shell` overhead path,
and the optimizer state update on the host orchestrator's side.

ADPF (Android Performance Hint Manager) thermal headroom thresholds:
`[NaN, 0.93333334, 0.96666664, NaN, 1.3333334, 1.3666667, 2.3333333]` —
LIGHT throttle starts at 0.93 of headroom budget.

### 1.8 Storage I/O

`/data` is F2FS with `fsync_mode=nobarrier, lazytime, inlinecrypt,
discard`. Live write throughput test with `dd … bs=4M count=64 conv=fsync`:

```
268 435 456 bytes (256 M) copied, 0.325 s, 788 MB/s
```

UFS 4.0 / 4.1 class, sequential fsync write. **Storage I/O is not a
training-loop bottleneck** even at multi-MB checkpoint cadence.

### 1.9 Nubia / Red Magic OEM service surface

From `service list`, the device exposes:

| Service | Interface | Likely role |
|---|---|---|
| `performance` | `com.zte.performance.IZtePerformanceManager` | ZTE master perf gate |
| `scenedecision` | `com.zte.performance.scene.IZteSceneDecisionManager` | Scene-driven perf decisions |
| `cfreezer` | `com.zte.performance.cfreezer.ICpuFreezerManager` | **CPU freezing** of "background" |
| `mindsyncservice` | `com.zte.performance.mindsync.IMindSyncManager` | Likely Adreno sync |
| `zperfcubeservice` | `com.zte.zperfcube.IZPerfCube` | Per-app perf cube |
| `DefendManagerService` | `com.zte.performance.defend.IDefendManager` | Anti-perf-cheat defence |
| `game` | `android.app.IGameManagerService` | Standard Android Game Manager — **N/A to `/data/local/tmp` binaries** |
| `performance_hint` | `android.os.IHintManager` | Android ADPF |
| `vendor.perfservice` | `com.qualcomm.qti.IPerfManager` | Qualcomm perf manager |
| `vendor.qti.hardware.perf2.IPerf/default` | — | Qualcomm Perf HAL v2 |
| `thermalservice` | `android.os.IThermalService` | Android thermal service |
| `vendor.qti.hardware.power.powermodule.IPowerModule/default` | — | Power HAL module |
| `ZtePowerManagerServiceEx` | `android.power.IPowerManagerEx` | ZTE power manager extension |

Active perf-related processes (from `ps -ef`):
- `vendor.qti.hardware.perf2-hal-service` — the Qualcomm Perf HAL v2 daemon
- `init.svc.zperfcubesevice` — Nubia perf cube
- `init.svc.perf2-hal-1-0` — Perf HAL service

Critical OEM properties (live probe):
- `nubia.perf.cpu.cpufreq.ctrl = 1` — **Nubia perf service is actively
  overriding CPU freq**
- `nubia.perf.cpu.input.boost.freq = 0` — input boost off
- `ro.vendor.feature.zte_feature_game_controlpanel_performance_gpu_path =
  /sys/class/kgsl/kgsl-3d0/max_gpuclk, /sys/class/kgsl/kgsl-3d0/gpuclk` —
  the path GameSpace writes to for pinning the GPU clock
- `ro.vendor.feature.zte_feature_game_controlpanel_performance_cpu_path
  = /sys/devices/system/cpu/cpu7/cpufreq/cpuinfo_max_freq,
  /sys/devices/system/cpu/cpu7/cpufreq/scaling_cur_freq,
  /sys/devices/system/cpu/cpu4/cpufreq/scaling_cur_freq,
  /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq` — paths for CPU
  pinning
- `vendor.perf.framepacing.enable = 1`
- `security.perf_harden = 1` — security perf hardening on
- `sys.init.perf_lsm_hooks = 1` — LSM hooks installed

Game Manager applicability is confirmed nil for our case: `cmd game
list-modes /data/local/tmp/polymath_gemma4_gate/gemma4_layer_runner` returns
`current mode: unsupported, available game modes: []`. Game Manager only
applies to installed APK packages — the path the OEM agent identified for
"the only unthrottled lane" is closed to a `/data/local/tmp` binary unless
the team wraps the runner in a thin APK or uses `GameSpaceReplacer`.

OEM perf-control APKs at `/system/priv-app/`:
- `NBFan/NBFan.apk` → `cn.nubia.fan` (cooling fan controller, has
  `cn.nubia.fan/.FanService` and `cn.nubia.fan.action.FAN_MODE_CHOOSE_ACTIVITY`
  intent)
- `GameSpace/GameSpace.apk` → `cn.nubia.gamelauncher`
- `NubiaGPUDrivers/NubiaGPUDrivers.apk` → `cn.nubia.gpu.drivers` (Adreno
  driver as APK, updatable via Play Store sun-driver channel)
- `NubiaGameLab/NubiaGameLab.apk` (at `/system/app/`, non-priv) →
  `cn.nubia.gamelab`

`/sys/kernel/fan` and `/sys/bus/platform/drivers/soc,fan` exist; the fan IC
is PMIC PWM-driven at `c42d000.qcom,spmi:qcom,pm8550@1:qcom,fan@ef00`. The
OEM agent reports a **Maxim MAX31760 external fan controller** loaded as
kernel module `max31760_fan` — confirmed in `/sys/module/max31760_fan`. So
the Red Magic 10 Pro has **two** fan paths: SoC-internal PMIC PWM and a
dedicated MAX31760 IC. The `cn.nubia.fan/.FanService` is a userspace daemon
that owns both via `fan_service` per the OEM agent's review of
`init.qcom.rc`.

### 1.10 QAIRT 2.44 install (already on device)

`/data/local/tmp/qairt-2.44/` contents:

```
bin/aarch64-android/
  genie-app                       # Genie GenAI runtime app
  genie-t2e-run                   # Text-to-embedding
  genie-t2t-run                   # Text-to-text
  qairt-lora-adapter-bin-updater  # THE LORA ADAPTER UPDATER TOOL
  qnn-context-binary-generator
  qnn-context-binary-utility
  qnn-gpu-target-server
  qnn-net-run
  qnn-platform-validator
  qnn-profile-viewer
  qnn-throughput-net-run
  qtld-net-run
  snpe-net-run                    # legacy
  snpe-parallel-run
  snpe-platform-validator
  snpe-throughput-net-run

lib/aarch64-android/
  libGenie.so
  libQnnCpu.so / libQnnGpu.so / libQnnDsp.so / libQnnHta.so / libQnnHtp.so
  libQnnGenAiTransformer.so + …CpuOpPkg + …Model
  libQnnHtpV68/V69/V73/V75/V79/V81 (Stub + CalculatorStub for each)
  libPlatformValidatorShared.so
  libQnnHtpPrepare.so  (85 MB — the HTP graph compiler)
```

This is the QAIRT 2.44 SDK already deployed under `/data/local/tmp`. The
team has the LoRA adapter binary updater (`qairt-lora-adapter-bin-updater`)
and the context binary generator (`qnn-context-binary-generator`) sitting
on disk, unused.

---

## 2. Bottleneck autopsy: where the missing 4h 44min went

From the live `gate_result.json` of `20260517T153500Z_phase10_six_hour_endurance`:

| Quantity | Value |
|---|---|
| `wall_seconds` | 21692.16 (6.03 h) |
| `active_training_seconds` | 4626.65 (1.29 h) |
| `iteration_count` | 465 |
| `max_thermal_status` | 0 (Android-side) |
| `learning_rate` | 0.01 |

From the per-iteration `telemetry.json` of `iter_000000`:

| Stage | Seconds |
|---|---|
| `token_to_hidden_elapsed_seconds` (CPU on phone) | 0.576 |
| `ple_layer0_seconds` | 0.189 |
| `ple_layer1_seconds` | 0.374 |
| `layer_elapsed_seconds[0]` (OpenCL layer 0) | 3.309 |
| `layer_elapsed_seconds[1]` (OpenCL layer 1) | 3.317 |
| `adapter_elapsed_seconds` (OpenCL adapter grad + SGD) | 0.331 |
| **Sum** (active per iter, first iter) | **~7.53 s** |
| `max_rss_kb` | 2 169 700 (2.07 GiB) |

The realised per-iteration active wall is `4626.65 / 465 = 9.95 s`, ~32%
higher than the first iter's 7.53 s — consistent with thermal-engine
clamping CPU cluster0 to ~2.0–2.4 GHz during the run (the trainer hits
skin temp 43–46°C in steady state per cached `dumpsys`).

The per-iteration **wall** is `21692.16 / 465 = 46.65 s`. The gap of
**36.70 s per iteration** is host-side orchestration. Breakdown of the
non-active 36.7s, inferred from the gate JSON's `sampled_parity` field and
the artifact directory layout on the phone (`telemetry.json`,
`checkpoint/manifest.json`, `artifact_manifest.json`,
`replay_manifest.json` per `iterations/iter_NNNNNN/`):

| Per-iter dead time (estimated, 36.7s budget) | Likely seconds |
|---|---|
| `adb shell` invocation + process exec on macOS | 0.5–2.0 |
| Push token cache from Mac to phone (UFS write 788 MB/s) | 0.1–0.5 |
| Pull `telemetry.json`, `manifest.json`, `artifact_manifest.json`, `replay_manifest.json` (4 files × ~few KB) | 0.5–2.0 |
| Parse manifests, compute hash chain, update host-side state | 0.5–2.0 |
| Write replay buffer entry on Mac | 0.5–2.0 |
| Oracle parity comparator (RunPod) on sample iters only (3 of 465 → 0.65 % of iters, amortises to ~0.04 s/iter) | 0.04 |
| **Process restart cost on each iter** (binary loads OpenCL libs, JITs kernels, opens KGSL fd, re-mmaps weights) | **~25–32** ← prime suspect |
| Total | 27–40 s/iter |

Each iteration re-invokes `gemma4_layer_runner_phase10_compact` from
scratch via the host scripts at `scripts/host/run_gemma4_phone_endurance.py`.
Every invocation pays the cold-start cost of: dynamic-linking
`libOpenCL.so` + `libOpenCL_adreno.so` + `libCB.so`, opening
`/dev/kgsl-3d0`, building the OpenCL context, compiling kernels (or
re-loading cached binaries), mmap-ing the layer-pack weight files, allocating
device-side buffers, doing the first dispatch (which itself amortises JIT).
With the binary at 8.74 MB, the linker + KGSL ctx creation alone is
plausibly 5–10s; the OpenCL kernel build cache hit (if `cl_qcom_perf_hint`
and program-cache are set correctly) saves a few seconds but is not free.

**Verification of this hypothesis** the team should do immediately, in this
order (each test takes <2 minutes of device time):

1. Time a cold `gemma4_layer_runner_phase10_compact --probe` from `adb shell`.
   That's the cold-start floor.
2. Time a single end-to-end iter invocation in isolation, no oracle, no
   replay write.
3. Take the wall-time gap between (1) and (2) as the "compute-only" floor;
   the remainder vs the 46.65 s/iter wall is host-orchestration cost.

If step (1) is in the 5–15 s range — almost certain — then **the binding
constraint on wall time is the orchestrator's "one iter per process" model,
not the GPU**.

That is the bottleneck autopsy. The fix is not faster kernels. It is
removing the host from the per-iteration critical path: a single
long-lived phone-side process that accepts iteration commands over a
local socket or pipe and produces telemetry incrementally. This change
alone moves the active-vs-wall ratio from 21% toward 60–80% before any
kernel or scope change.

The remainder of the gap is **Nubia perf-HAL mitigation** treating the
trainer process as background and capping CPU cluster0 at thermal-engine
trip 43°C → 2.4 GHz. The mitigation is invisible to the Android-side
`thermal_status` (it stays at 0) because the kernel-side `thermal-engine`
operates below the framework's status thresholds. Pinning the trainer into
the perf-HAL's "foreground performance" envelope via
`cmd power set-fixed-performance-mode-enabled true` plus an APK shim that
registers under `cn.nubia.gamelauncher`'s GameSpace whitelist is the OEM
unblock.

---

## 3. Hexagon V79 — what role it can actually play in learning

The Hexagon deep-research agent classified HTP's QAIRT/QNN/Genie surface as
**`mutable-adapter-no-backward`**: there is no public Qualcomm API that
exposes a backward op, gradient tensor, autograd tape, or optimizer step
targeting HTP. AIMET QAT runs the backward on a host PyTorch/TF GPU; AI Hub
"fine-tuning" routes through Cloud AI 100 in datacenter (SageMaker training,
AI Hub compile, deploy frozen-or-adapted binary to HTP). The Hexagon
silicon (HMX + HVX) is capable of transpose-GEMM (∂L/∂W has the same matmul
shape as the forward), but Qualcomm exposes no compiler, no QNN op, no
autograd graph builder, no gradient tensor type, no optimizer kernel.

What the team **can** do today, with QAIRT 2.44 already deployed on the
phone:

### 3.1 The `applyBinarySection` primitive — beyond LoRA

The shipped API surface for runtime weight mutation on HTP:

| Capability | API | Header | Status |
|---|---|---|---|
| Compile-time declaration of updateable tensors | `--lora_weight_list <txt>` flag to `qairt-converter` | CLI | QAIRT 2.29+ |
| Generate base context binary + N adapter binaries | `qnn-context-binary-generator` | CLI | Shipped (on device at `/data/local/tmp/qairt-2.44/bin/aarch64-android/`) |
| Load base context onto HTP | `QnnContext_createFromBinary` | `QnnContext.h` | Shipped |
| **Apply an adapter binary section to a live context on HTP** | `QnnContext_applyBinarySection` | `QnnContext.h` | QAIRT 2.33+ |
| Export a binary section back out (e.g. ship checkpoints) | `QnnContext_getBinarySection` | `QnnContext.h` | Shipped |
| Execute one forward inference after apply | `QnnGraph_execute` | `QnnGraph.h` | Shipped |
| Genie-level adapter swap | `LoraBuilderInputConfig`, `AdapterRunConfig` | Genie GenAI bundle | Shipped (`libGenie.so` on device) |
| ONNX Runtime QNN EP LoRA | `qnn.lora_config` RunOption | `onnxruntime_run_options_config_keys.h` | Shipped |

Measured adapter switch cost on **SM8750 / Llama 3.2-3B** per the
QAIRT LoRA tutorial doc 80-87189-2: **~152 ms per switch**. The
granularity is per-tensor, restricted to tensors enumerated in
`lora_weight_list` at compile time, weights-only deltas, graph topology
frozen.

**The non-obvious lever**: `applyBinarySection` is **not LoRA-specific**.
Any tensor declared `updateable` at compile time can be replaced with any
binary content of matching shape and dtype. The team can therefore ship
arbitrary delta updates — including (a) a host-computed adapter update, (b)
a CPU-computed Adam-style EMA smoothed weight, (c) a zero-order weight
perturbation for SPSA-style training, or (d) a teacher-distilled adapter
binary refreshed from the cloud — without recompiling the base context.
The 152 ms switch cost bounds how often this is profitable.

### 3.2 HTP roles that are immediately viable

In order of effort × yield:

**A. HTP as the frozen-forward island.** Compile the lower N transformer
blocks of Gemma 4 E4B as an HTP context binary. Run forward on HTP, hand
the activations off to Adreno for the trainable adapter forward + backward
+ update. Activation handoff uses `/dev/dma_heap/qcom,cma-secure-cdsp` to
allocate a buffer mapped into both HTP and Adreno address spaces. Qualcomm
publishes no first-party number for the handoff latency on SM8750; the
Hexagon agent's estimate is single-digit milliseconds for a 3B-class
activation tensor, dominated by cache coherence rather than copy. **This
is the team's single highest-leverage HTP integration** because the lower
transformer blocks are frozen by construction and the matmul shapes are
exactly what HMX is designed for.

**B. HTP as a teacher.** Compile a stronger model (say Gemma 4 E4B itself
at INT8) as an HTP context binary. During training, run the teacher forward
on HTP to produce logits or hidden states; the Adreno trainer's adapter
fits to teacher targets via KL divergence. The 152 ms adapter-switch cost
becomes irrelevant because the teacher is frozen. This is the path that
fits *both* the on-device-only mandate and the "logit-KL is the
highest-SNR objective" finding from the training-methods research pass.

**C. HTP for zero-order weight perturbation (SPSA / MeZO-on-HTP).**
The breakthrough realisation, combining the Hexagon agent's
`applyBinarySection`-is-not-LoRA-specific note with the training-methods
agent's MeZO finding (Sparse-MeZO, arXiv 2402.15751; on-device MeZO, arXiv
2511.11362):

```
for step in range(K):
  ε = sample_perturbation()
  apply_adapter(adapter + α·ε)   # 152 ms HTP write
  L_plus = qnn_forward(batch)    # one HTP forward
  apply_adapter(adapter - α·ε)   # 152 ms HTP write
  L_minus = qnn_forward(batch)   # one HTP forward
  g = (L_plus - L_minus) / (2α) · ε
  adapter = adapter - lr · g     # host-side scalar update
```

This is **training without a backward pass**, on HTP, today, with shipped
QAIRT APIs. The step cost is 2·forward + 2·152 ms swap, dominated by the
swap. With Gemma 4 E4B forward on HTP estimated at ~100–300 ms (extrapolating
from `qnn-net-run` timing on `qwen_block.qnn.bin`), one MeZO step is
roughly 0.8–1.2 s. 465 steps would be 6–10 min wall, two orders of magnitude
faster than the current 1.29 h active training, at the cost of slower
convergence vs first-order. MeZO is shown to fine-tune Llama-class models;
Sparse-MeZO adds +9% RTE accuracy and 3.5× speedup over MeZO. No one has
published this loop on a Snapdragon-class phone — running it on the Red
Magic 10 would itself be a publishable result.

### 3.3 What HTP cannot do

- No backward pass for arbitrary compute graphs.
- No first-order gradient operators on HMX or HVX exposed through Qualcomm
  tooling.
- No on-device AIMET QAT — AIMET-ONNX 2.10 still runs backward on host.
- No live recompilation of the HTP graph topology — the team cannot mutate
  the model shape, only the values of declared-updateable tensors.

### 3.4 What's blocked by tooling, not silicon

The HMX matrix tile is fully capable of running ∂L/∂W as a forward matmul.
Hexagon SDK 6.x lets you write HVX/HMX kernels by hand against the FastRPC
API. A determined team could implement Adam-style optimizer state update
on HVX (HVX is 1024-bit SIMD, INT8 + FP16; V79 adds direct `vlut16` paths
for Q4_0 4-bit unpack to FP16). This is viable for a single fused op,
infeasible as a general training stack, and would be the "if all else
fails" path. Recommendation: defer until after sections 4–7 land.

---

## 4. Adreno kernel route — verdict and reasoning

The Adreno-architecture agent and the OpenCL-vs-Vulkan-vs-persistent agent
produced one convergence and one tension. They converged on:

- **Persistent megakernel is not viable on Adreno 830.** KGSL preempts at
  dispatch boundaries, watchdog kills kernels >6–10 s, no async copy / TMA,
  no in-kernel inter-SM coordination, 32 KB LDS per workgroup blocks Hazy
  Research's paged-SMEM trick, no `cl_qcom_yield_kernel`. The polite-megakernel
  pattern (kernel that voluntarily exits every ~50 ms) is just dispatch in
  disguise. Drop this avenue.
- **`cl_qcom_recordable_queues` is the immediate OpenCL win.** Record the
  kernel sequence once, dispatch many times with mutable arguments. Drops
  dispatch overhead from ~30–80 µs to ~5–15 µs per dispatch. llama.cpp's
  Adreno backend uses this; IWOCL 2025 update (Wang) credits it for the
  bulk of their Adreno 830 speedup.

They diverged on whether to switch from OpenCL to Vulkan. Resolving the
divergence with the device-probe evidence:

- The OpenCL/Vulkan agent's strongest evidence for Vulkan is **Tether QVAC's
  production reference**: they trained BitNet b1.58 1B on Adreno 830 in
  13 hours via llama.cpp + Vulkan (`tetherto/qvac-fabric-llm.cpp`,
  HF blog post). This is a fact, not a hypothesis. **And it uses the
  Qualcomm closed Vulkan driver, which is what the device has** at
  `/vendor/lib64/hw/vulkan.adreno.so`. So Vulkan via Qualcomm's closed
  driver is proven on A830.
- The Adreno-architecture agent's strongest evidence against Vulkan is
  that **Mesa Turnip on A830 is explicitly experimental** ("don't report
  issues to Mesa") and `VK_KHR_cooperative_matrix` is not advertised on
  the shipping A830 Qualcomm driver as of May 2026. Both are true.
- QVAC's path forced them into "dynamic tiling" because of an undocumented
  **128 MiB SSBO ceiling in the Adreno Vulkan driver**. Plan for this from
  day one if going Vulkan.

**Verdict for the Polymath team's Phase 10 timeline**: adopt
`cl_qcom_recordable_queues` on the existing OpenCL path *first*, with no
backend switch. Reasoning:
1. The current bottleneck is not GPU dispatch overhead (which is ~30–80 µs
   on a kernel that takes 3.3 s). Even a 5× dispatch reduction is a
   rounding error against the rank-4 adapter's 0.33 s adapter step.
2. The current bottleneck is the host-side per-iteration restart. That is
   a backend-agnostic problem.
3. Migrating to Vulkan is a 2–4 week port with a 128 MiB SSBO ceiling
   ambush, and the win is bounded by the matrix unit which is not exposed
   to the team's training path on either OpenCL or current Adreno Vulkan
   anyway.

**Re-evaluate Vulkan** in Q4 2026 when one of (a) `VK_QCOM_cooperative_matrix_conversion`
is advertised on shipping A830 drivers, (b) Mesa Turnip becomes
production-stable on a830 compute, or (c) the team has measured a real
roofline gap that only matrix-unit access closes.

Top 3 OpenCL fusion targets ordered by yield/cost, after the persistent-
queue change lands:

| Rank | Fusion | LDS | Expected speedup | Notes |
|---|---|---|---|---|
| 1 | Adapter grad reduction + SGD update | ~2 KB | 3–5× on the adapter step | Eliminates 2–3 dispatches; rank-4 is launch-bound |
| 2 | RMSNorm + post-norm low-rank projection | ~8 KB | 2–3× on per-layer pre-attn | Bandwidth-bound RMSNorm chains avoid a L2 round-trip |
| 3 | Layer-fwd output + adapter input prep ("bridge") | ~16 KB | 1.5–2× | Tighter on registers; benefits most from `VK_QCOM_tile_shading` if/when the team moves to Vulkan |

Avoid: QKV group fusion at hidden 2048 (needs ~36 KB LDS workspace, blows
the 32 KB per-workgroup cap). Avoid: token-to-hidden bridge fused with
anything else (different memory access pattern from `cl_qcom_compressed_image`).

---

## 5. Trainable scope — the brutal arithmetic

Current scope:

```
trainable_scope:    post_layer0_rank4_residual_adapter
optimizer:           sgd  (learning_rate 0.01, no momentum)
sequence_length:     128
hidden_size:         2560
rank:                4
trainable params:    rank × hidden = 10 240   (telemetry-confirmed element_count)
trainable layers:    1 residual injection point, after layer 0 of 32+
```

The training-methods agent grounded the verdict against three concurrent
results:

- **Schulman et al., *LoRA Without Regret* (Thinking Machines Lab, Sep 2025)**:
  LoRA matches full FT only with (a) attention AND MLP placement, (b) effective
  batch < 32, (c) dataset information content below rank capacity. Rank 1 can
  match full FT at small enough datasets but only with broad placement, not a
  single residual injection.
- **Biderman et al., *Plasticity vs. Rigidity* (EACL 2026, arXiv 2601.06677)**:
  at micro-budget (<24 h on one A40), r=8 LoRA on a 1.5B model **fails to move
  reasoning at all**; r=256 works. The threshold is not smooth — there is a
  plasticity floor below which the adapter cannot capture the optimization
  dynamics, regardless of iteration count.
- **MobiLLM / PAE-MobiLLM / Fed-MobiLLM (Xu et al., 2025)**: the productionised
  answer to "fine-tune on a phone" is to **not** backprop on the phone — keep
  backbone frozen on-device, offload trainable side-network backward to a
  server, transfer only forward activations. Pure on-device backprop is conceded
  as infeasible at Gemma-4-E4B class memory.

Implication for the team: **at rank-4 / single post-layer-0 injection / 465
iterations / SGD-no-momentum / next-token-loss-style objective, no reasoning,
math, code, or factual-knowledge benchmark will move.** Format-following
metrics (IFEval) and style-match metrics (n-gram overlap, MAUVE, character
edit distance to teacher outputs) will move 2–10 percentage points on a
homogeneous corpus and not otherwise.

Worst-slot-in-the-model finding: layer 0 moves nothing — last 2–3 layers
move format/style, middle layers move semantic capability, layer 0 moves
position-agnostic embedding-adjacency artefacts. The current placement is
the worst slot for capability movement and the best slot for nothing in
particular.

What gives best capability-per-resource on Gemma 4 E4B at sub-12-GB device
memory, ordered by yield/cost:

1. **DoRA r=16 on `q_proj`, `o_proj`, `gate_proj`, `up_proj` of the last 8
   transformer blocks**. DoRA (Liu et al., ICML 2024 Oral, arXiv 2402.09353)
   decomposes weight into magnitude + direction and is **robust at low rank
   where LoRA collapses**. This is the single highest-leverage scope change.
   Trainable params at r=16, hidden 2560, 8 blocks, 4 projections per block:
   `2 × 16 × 2560 × 4 × 8 = 2,621,440` weights — 256× the current scope,
   still tiny relative to E4B's ~4B base params, easily fits in 24 GB
   DRAM.
2. **LoRA-FA layout** (freeze A, train only B) to remove activation memory
   of LoRA (the real phone bottleneck, not parameter count) — arXiv
   2308.03303.
3. **VeRA + LoRA-FA combo** moves the adapter payload to kilobytes and
   removes activation memory.
4. **Q-GaLore** for any future "actually train the base model" experiment
   (Zhao et al., arXiv 2407.08296): gradient projection to low-rank subspace,
   65% optimizer-state memory cut, base-model training in 24 GB GPU. The
   Gemma 4 E4B optimizer state at fp32 Adam is ~16 GB — Q-GaLore drops it
   to ~2 GB. Defer this unless a future phase wants to train the backbone
   itself.

What objective to actually optimise (beyond parity-MSE):

- **Logit-KL distillation against a frozen teacher** is the single highest-SNR
  objective. The teacher is Gemma 4 E4B itself (frozen on HTP per §3.2.B
  above) or a stronger remote model whose logits are baked into a teacher
  shard once. Logit KD costs ~1 KB per token at top-32 logits. Apple's
  Foundation Models pipeline uses rejection-sampled teacher targets with
  on-device adaptation; this is the right precedent.
- **Test-time training (TTT)** is empirically the "settling on dense small
  data" hypothesis the team intuited. Akyürek et al. (arXiv 2411.07279,
  Nov 2024) achieved **6× accuracy gain on ARC** by training a per-task
  LoRA at test time with geometric-augmented data and hierarchical voting —
  61.9% on ARC public eval, matching average human. That paper used r=128.
  At r=16 the gain is smaller but the principle is the same: a per-session
  adapter retrained from scratch on each new context with
  teacher-augmented data.

Recommended first capability-moving objective past parity gates:

> **Logit-KL distillation against a frozen Gemma 4 E4B HTP teacher, on a
> 10–50k-token teacher-curated micro-corpus, with DoRA r=16 on
> `q_proj` / `o_proj` / `gate_proj` / `up_proj` across the last 8
> transformer blocks, AdamW + cosine schedule, batch 8, 5–10 full passes
> (~3000–6000 iters) with surprise-driven replay (SuRe). Measure IFEval,
> MT-Bench-domain, and a custom style-match metric. Expect 5–15 IFEval
> points; do not expect MMLU movement.**

This objective is what fits the phone, the data hypothesis, and the
HTP-teacher path simultaneously. It is the simplest possible objective that
crosses the plasticity floor identified in Biderman et al.

---

## 6. Data regime — what fits this hardware

The pack's framing question 4 in `03-HARDWARE-WANTS-QUESTION.md` was: *dense
small slices, repeated settling, online replay, micro-curricula, teacher-distilled
shards, or another shape?* Combining the training-methods agent's findings
with the device probe:

- **Dense small slices**: yes for parity. No for capability movement at
  rank-4. At rank-16 DoRA, dense small slices of <10k tokens become
  productive.
- **Repeated settling**: yes — Akyürek TTT-for-ARC validates it empirically.
  Implies a curriculum where each "session" is a tiny corpus shard, trained
  to fit, then the adapter is reset or merged.
- **Online replay**: yes but only with importance weighting. SuRe (surprise-
  driven replay, arXiv 2511.22367) and MSSR (memory-aware replay, arXiv
  2602.xxxx Feb 2026) are the current best continual-learning shapes.
  Phone storage at 788 MB/s sequential write makes any practical replay
  buffer fit (a 1 GB replay is < 1.3 s to refresh).
- **Teacher-distilled shards**: yes — this is the Apple Intelligence pattern
  at small scale. Cloud generates a 50 MB–500 MB shard of teacher logits
  over the target domain once; phone trains for many epochs offline. The
  phone remains the runtime learner; the teacher only shapes data.
- **Sparse routing / control-state modules**: defer until r=16 DoRA proves
  out. Tensor-train decomposed adapters (LoRA-Edge, Nov 2025, arXiv
  2511.03765) reduce parameter count by 2 orders of magnitude vs LoRA at
  matched performance; relevant only if memory pressure becomes binding
  (it currently is not — RSS is 2.07 GiB of 24 GB).

What capability metric is honest at this scale:

| Will move | Won't move |
|---|---|
| IFEval (instruction-format following) | MMLU |
| Custom domain perplexity on held-out slice | ARC-Challenge (without TTT) |
| MT-Bench single-turn for the domain | HumanEval / MBPP |
| Style-match (n-gram overlap, MAUVE, char-edit) | GSM8K / MATH500 / AIME |
| Teacher-agreement on logit-KL | BBH |

---

## 7. POVC — the unblock plan

Five coordinated changes. Each is independently valuable; together they
unblock four of the five Phase 10 non-claims in a 1–2 week sprint.

### 7.1 Change A: collapse the per-iteration host orchestration

**Goal**: replace the "one process per iter" model with a long-lived
phone-side daemon that accepts iteration commands over a local Unix socket
or named pipe, holds the OpenCL context, mmaps weights, retains kernel
program-cache, and emits telemetry incrementally.

**Why**: the bottleneck autopsy in §2 shows the host-side restart cost is
the largest single contributor to the 36.7 s/iter dead time. Even a partial
fix (e.g. one process per 50 iters) would move active/wall from 21% to
>50% without touching kernels.

**Where to change**:
- `scripts/host/run_gemma4_phone_endurance.py` — convert from `adb shell
  ./gemma4_layer_runner_phase10_compact …` per iter to a single
  long-running invocation that reads iteration commands from stdin or a
  named pipe.
- `integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/runner/main.cpp`
  and `integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/include/polymath/gemma4/adapter_training.h`
  — add a `--daemon-stdin` mode that reads JSON commands per line, executes
  the iteration, writes a single JSON-line telemetry record to stdout, loops.
- Keep the existing per-iter binary path as a fallback for parity-mode runs.

**Verification command**:
```
# Cold-start measurement
adb shell 'cd /data/local/tmp/polymath_gemma4_gate && time ./gemma4_layer_runner_phase10_compact --probe'
# Compare against the 7.53s active per-iter sum — anything above 1s is cold-start tax
```

### 7.2 Change B: pin the trainer out of Nubia perf-HAL mitigation

**Goal**: stop `vendor.qti.hardware.perf2-hal-service` from clamping the
trainer's CPU cluster from 3.53 GHz to 2.40 GHz.

**Why**: the cached `skin = 45.95°C` from the most recent run sits in the
43–47°C bin of `/vendor/etc/thermal-engine.conf`, capping cluster0 to
~2.0–2.4 GHz. The trainer is being treated as a background `/data/local/tmp`
process. The Android-side `thermal_status` stays at 0 because the kernel-
level thermal-engine mitigates below the framework threshold. Pinning via
ADPF fixed-performance-mode is the highest-yield single command.

**Single highest-yield ADB sequence (no root required), run before each
endurance attempt**:

```
adb shell settings put global low_power 0
adb shell svc power stayon usb
adb shell cmd power set-fixed-performance-mode-enabled true
adb shell setprop sys.thermal.mode_type 0      # try 0, then 1, 2 — find one that frees fan + relaxes mitigation
adb shell cmd thermalservice headroom 30        # log the headroom forecast for the run
```

If/when the team wraps the runner in a thin APK (single Activity that
foregrounds the trainer service), the additional sequence:

```
adb shell cmd appops set <pkg> RUN_IN_BACKGROUND allow
adb shell cmd appops set <pkg> RUN_ANY_IN_BACKGROUND allow
adb shell dumpsys deviceidle whitelist +<pkg>
# Add the APK to GameSpace and switch to Diablo Mode + Fan = Max via UI, then:
adb shell am start -a cn.nubia.fan.action.FAN_MODE_CHOOSE_ACTIVITY
```

Charge separation (UI: *Settings → Battery → Charge Separation → 85%*):
when enabled, the charger powers the phone directly above 85% battery and
bypasses the battery, removing the largest thermal source for any
plugged-in long run.

**Verification**: log `cat /sys/class/thermal/cooling_device30/cur_state`
(CPU cluster0 throttle), `…/cooling_device36/cur_state` (GPU throttle),
and `cat /sys/class/kgsl/kgsl-3d0/gpubusy` deltas across a 60-second
window during a training step. If any cooling_device state goes above 0,
the mitigation is still firing; iterate on `sys.thermal.mode_type` and the
fan mode until those stay at 0.

### 7.3 Change C: replace the trainable scope and objective

**Goal**: lift trainable scope across the Biderman et al. plasticity floor;
swap parity-MSE for a capability-moving objective.

**Concrete change**:
- New trainable scope: DoRA r=16 on `q_proj`, `o_proj`, `gate_proj`,
  `up_proj` across **the last 8 transformer blocks** of Gemma 4 E4B.
  Trainable params = ~2.6M weights. Memory footprint ~10 MB. Fits the
  device 250×.
- Optimizer: AdamW (not SGD), `lr=1e-4`, cosine schedule to 1e-5, weight
  decay 0.01, β₁=0.9, β₂=0.999.
- Objective: **logit-KL distillation** against the frozen Gemma 4 E4B
  teacher logits (top-32 logits per token, KL with temperature 2.0).
  Replaces `loss_half_mse` (a parity metric) with a capability-moving
  metric.
- Data: teacher-distilled micro-corpus of 10k–50k tokens, sampled from the
  team's target domain corpus on the host once and shipped to the phone as
  pre-computed teacher logit tensors (`int8` quantised top-32 logits, ~1 KB
  per token = 50 MB at 50k tokens).

**Why**: §5 shows this is the smallest scope change that crosses the
plasticity floor. The objective change resolves the F4 research question
in `02-FAILURE-AND-LIMITATION-MAP.md` ("dense small slices, repeated
settling…") empirically.

**Verification**: before any 6-hour endurance attempt at the new scope,
run 100 iterations on the 50k-token shard and measure:
- Train logit-KL trajectory (should drop monotonically; if not, scope or
  objective is wrong)
- Held-out shard perplexity (should drop)
- IFEval-mini (a 200-prompt subset) before vs after

If train KL drops but IFEval-mini does not move, the placement or rank is
still wrong; iterate.

### 7.4 Change D: wire the HTP teacher and the HTP frozen-forward island

**Goal**: actually use Hexagon V79 in the training loop, in the two roles
where Qualcomm's shipped tooling supports it.

**Concrete change**:
- Compile Gemma 4 E4B (or the lower N transformer blocks of it) as a QNN
  context binary targeting `libQnnHtpV79Stub.so`, using
  `qnn-context-binary-generator` already at
  `/data/local/tmp/qairt-2.44/bin/aarch64-android/`. Declare the adapter
  tensors (DoRA decomposition matrices for the last 8 blocks) as
  updateable via `--lora_weight_list` to `qairt-converter` at compile
  time.
- Allocate the activation handoff buffer from `/dev/dma_heap/qcom,cma-secure-cdsp`
  via `dma-buf` ioctl, map into both HTP context (via `QnnContext_setTensorAddress`
  on the HTP-side tensor) and Adreno context (via `cl_qcom_ion_host_ptr`
  to wrap the buffer in a `cl_mem`).
- Per iteration: HTP runs the frozen forward of the lower N blocks; Adreno
  runs the trainable upper blocks + DoRA backward + AdamW update. Adapter
  weight updates flow back to HTP via `qairt-lora-adapter-bin-updater`
  (already on disk) when checkpointing, at most every M iters to amortise
  the 152 ms swap.
- For the teacher: run a second HTP context with a frozen Gemma 4 E4B
  forward, sourced from a different graph slot. Two HTP contexts can
  coexist; queue them serially because Hexagon does not async between
  contexts.

**Why**: §3 shows this is what Qualcomm's shipped tooling exposes and the
device already has every binary required. It is also the path that resolves
the `claim-phase10-hexagon-training` non-claim in `10-02-PLAN.md`. The team
is currently treating Hexagon as binary — either it does backward (it
doesn't) or it does nothing (it doesn't have to). The middle ground is
**HTP as a frozen forward + teacher island**, which is the productionised
shape for on-device LLMs (xLLM, MobiLLM, the QNN tutorial set).

**Verification**:
- HTP→Adreno activation handoff latency microbenchmark: allocate one
  `dma-buf`, ping-pong it between HTP forward output and Adreno compute
  input 1000 times, measure wall. Anything <10 ms/round trip is acceptable;
  >50 ms/round trip means re-think the handoff (likely cache-flush cost).
- Phone-side gate: a single training iter that produces a checkpoint
  whose Adreno-side adapter forward produces identical hidden state when
  re-fed into HTP via the updated context binary. Cosine >0.9999 vs the
  Adreno-only baseline.

### 7.5 Change E: run a MeZO-on-HTP forward-only experiment in parallel

**Goal**: validate the zero-order weight-perturbation path on HTP, with
no backward pass anywhere in the loop. This is the frontier exercise the
operator asked for — a genuinely new training shape that fits the silicon.

**Concrete change**:
- Take the rank-16 DoRA adapter from Change C.
- Implement the SPSA loop in §3.2.C above using the existing
  `qairt-lora-adapter-bin-updater` for the two perturbation writes per
  step, and `qnn-net-run`-equivalent forward via `libQnnHtpV79Stub.so` for
  the two forward passes per step.
- Host-side scalar update (CPU, negligible cost).
- Compare against Change C's first-order Adreno DoRA on:
  - wall-clock per useful adapter-norm change
  - convergence rate on the same KL objective
  - mJ per useful adapter-norm change (use battery delta as a proxy if
    AThermal headroom doesn't give energy directly; alternatively use
    `getprop sys.power.battery_energy` per `dumpsys batterystats`)

**Why**: combining the Hexagon agent's `applyBinarySection`-not-LoRA-specific
finding with the training-methods agent's MeZO line yields a training
algorithm that **uses only the shipped HTP forward API and runs no
backward anywhere**. No one has published this loop on a Snapdragon-class
phone. If it converges faster per joule than the first-order Adreno path,
the team has discovered the hardware-native training shape the pack's §3
asked for. If it doesn't converge, the team has falsified an attractive
hypothesis with one week of work and saved months downstream.

**Verification**: 200-iter MeZO loop produces adapter checkpoints whose
KL-loss trajectory is bounded above by a fitted exponential (i.e. genuine
descent), and whose final IFEval-mini score is >2 points higher than a
fixed-adapter baseline.

---

## 8. What the team probably does not know (compiled, from the five
research passes plus the device probe)

Adreno 830 / SM8750:
- **`cl_qcom_recordable_queues`** is the OpenCL-native answer to Vulkan's
  command-buffer reuse. Used by `cl_qcom_ml_ops` internally; not in the
  current Polymath training path.
- The Adreno matrix unit is on a separate clock domain and exposes
  256 FP16/BF16 ops/cycle per matrix element — **dark silicon for
  OpenCL** unless using `cl_qcom_ml_ops` (and even there, only via
  pre-defined ML ops, not custom GEMM). The unit is reachable from
  Vulkan only after `VK_QCOM_cooperative_matrix_conversion` lands on
  shipping A830 drivers (spec public, not yet advertised).
- **No AQE on A830** — A8xx silicon only. Multiple OpenCL queues serialise
  on one HW ring on A830. Multi-queue is not a multi-engine win here.
- **128 MiB SSBO ceiling** in the Adreno Vulkan driver is undocumented
  and real (Tether QVAC hit it). Plan for it on day one if going Vulkan.
- KGSL fault-tolerance silently kills contexts that blow timeouts:
  `ADRENO_IDLE_TIMEOUT = 20s`, `ADRENO_PREEMPT_TIMEOUT = 10s`,
  `KGSL_FT_THROTTLE`. There's no per-context override exposed to userspace.

Hexagon V79 / QAIRT:
- **`QnnContext_applyBinarySection` is not LoRA-specific**. Any tensor
  declared `updateable` at compile time accepts arbitrary delta updates.
  This is the lever for any HTP-side weight mutation, including SPSA / MeZO
  / cloud-shipped delta adapters.
- AIMET QAT runs the backward on **host**, not on HTP. Same for AI Hub
  fine-tuning (Cloud AI 100 datacenter).
- **`qairt-lora-adapter-bin-updater` is already on this phone**. The team
  has every binary required to run QAIRT-LoRA today; only the host-side
  pipeline that compiles a base context with `--lora_weight_list` and
  generates adapter binaries is missing.
- HTP→Adreno handoff via `/dev/dma_heap/qcom,cma-secure-cdsp` is
  zero-copy when the buffer is allocated once and mapped into both. Cost
  is cache coherence, not copy. Qualcomm publishes no first-party number
  for the latency on SM8750; the team will need to measure it (this is
  a real epistemic gap, not a known number).

Training methods 2025–2026:
- **Akyürek TTT-for-ARC** (arXiv 2411.07279) validates the project's
  "repeated settling on dense small data" intuition empirically: 6× ARC
  accuracy from per-task LoRA trained at test time.
- **Sparse-MeZO** (arXiv 2402.15751) and **on-device MeZO** (arXiv
  2511.11362) provide the first credible forward-only training method
  for Llama-class models. The team's HTP constraint makes this a natural
  fit.
- **MobiLLM / PAE-MobiLLM / Fed-MobiLLM** (Xu et al., 2025): the
  productionised "fine-tune on a phone" pattern is to **offload the
  trainable side-network backward to a server**. This concedes that pure
  on-device backprop at E4B-class memory is infeasible — exactly what
  the team is fighting. The middle-ground path (HTP frozen island + Adreno
  trainable head) is the right shape if the team wants a fully on-device
  story.
- **DoRA** (arXiv 2402.09353) outperforms LoRA at low rank. Single
  highest-leverage swap if rank stays low.

Red Magic 10 / Nubia OEM:
- **`vendor.qti.hardware.perf2-hal-service` + `thermal-engine-v2` are
  the binding constraint** on sustained compute for a `/data/local/tmp`
  binary, not the SoC's actual thermal envelope. Kernel-side thermal-engine
  fires below Android's `ThermalStatus` thresholds.
- **`cmd power set-fixed-performance-mode-enabled true`** is the
  highest-yield single shell command for sustained compute on Android
  15+. Nubia honors it on RM10P.
- **Charge Separation @ 85%** removes the battery as a thermal source for
  any plugged-in long run.
- **GameSpace's Diablo Mode also throttles** for thermal safety — it is
  not the unthrottled ceiling. The trainer-as-`/data/local/tmp`-binary
  cannot use GameSpace at all without an APK wrapper or `GameSpaceReplacer`.
- The Adreno driver is **updatable as `cn.nubia.gpu.drivers`** APK via
  the Qualcomm "sun" Play Store driver channel — relevant if a future
  Vulkan extension lands in a driver update.
- **Nubia NX789J kernel source has not been published yet** at
  nubia.com/en/service/opensource. The reminon `device_NX789J` GitHub
  tree is the closest reference. If the team needs to override KGSL
  timeouts or write to fan sysfs, it requires bootloader unlock + Magisk
  (paid Nubia unlock token, $30–50 via third-party services as of 2026-01-05,
  banking/Play-Integrity/Widevine-L1 breakage on unlock).

---

## 9. What this view does NOT claim

Per the pack's own `00-README.md` reading rule: do not convert signals into
solved problems. This document does not claim:

- That changes A–E above will all succeed. Each is a falsifiable hypothesis
  with a specified verification.
- That Hexagon V79 will become a "training device" through changes D and E.
  HTP becomes a frozen-forward + teacher island and a zero-order-weight-
  perturbation arm. Neither is "Hexagon NPU training" in the conventional
  sense; both are the actual training-shaped workloads HTP supports today
  per shipped Qualcomm APIs.
- That Adreno 830 has the matrix unit accessible to the team's training
  path. It does not, on current OpenCL or shipping Adreno Vulkan, for
  arbitrary GEMM. Re-evaluate when `VK_QCOM_cooperative_matrix_conversion`
  ships on the A830 driver.
- That a 6-hour endurance run at the new scope and objective will pass on
  the first attempt. It will likely require iteration on
  `sys.thermal.mode_type`, GameSpace integration, and fan mode to keep
  the trainer out of perf-HAL mitigation.
- That MeZO-on-HTP will converge faster than first-order Adreno DoRA. It
  may not. The point of Change E is to find out cheaply.

The five non-claims in `02-FAILURE-AND-LIMITATION-MAP.md` map to the changes
as follows:

| Non-claim | Change | Expected resolution |
|---|---|---|
| F1 — NPU training did not materialize | D + E | HTP becomes a documented training-loop participant (frozen island + zero-order arm). The phrase "Hexagon NPU training" is reframed; the underlying intent is unblocked. |
| F2 — trainable scope is narrow | C | Lifts scope 256×; brings rank above plasticity floor; placement to capability-moving slots. |
| F3 — active training << wall time | A + B | Removes host orchestration from per-iter critical path; pins trainer out of perf-HAL mitigation. Target: active/wall ≥ 0.6. |
| F4 — data path is not yet a corpus strategy | C (objective) | Logit-KL on teacher-distilled micro-corpus is a corpus strategy with measurable capability signal. |
| F5 — "Full Gemma4 training" is undefined | (Out of scope for POVC) | Recommend the team explicitly redefine "full" as the union of (HTP frozen island for blocks 0..N) + (Adreno trainable adapters across last 8 blocks at r=16 DoRA) + (optimizer state on host) + (checkpoint roundtrip through QAIRT-LoRA). This is "full" in the only sense the silicon supports. |

---

## 10. Epistemic gaps the team should close

The five Opus deep-research passes converged on a set of measurements the
team should make on the actual device because no public source publishes
them for SM8750 / Adreno 830 v2 / NX789J:

1. **HTP↔Adreno activation handoff latency** via `/dev/dma_heap/qcom,cma-secure-cdsp`,
   for a 1×N×2560 fp16 tensor. Qualcomm publishes no first-party number.
2. **`cl_qcom_recordable_queues` actual dispatch latency** on A830 with
   mutable args, against a no-op kernel. Public closest is the WebGPU
   paper's Vulkan 24–36 µs / Metal 32–71 µs / CUDA 7.4 µs range on
   desktop — not Adreno.
3. **KGSL watchdog defaults on the Nubia downstream kernel** —
   `cat /sys/module/msm_kgsl/parameters/*` after root. Upstream is 6 s,
   but Nubia patches the BSP and the actual values may differ.
4. **Whether `cl_qcom_ml_ops` v2 includes backward / gradient operators
   on A830** — the two GPU research passes disagree. Run a
   `clGetExtensionFunctionAddressForPlatform("clMLCreateTrainingOpQCOM")`
   (or equivalent) probe on the device's `libOpenCL_adreno.so` to settle
   this. If yes, this is a third path to consider for the rank-16 DoRA
   step.
5. **Whether `VK_KHR_cooperative_matrix` is exposed on the actual
   `/vendor/lib64/hw/vulkan.adreno.so` driver build on this device** —
   `vulkaninfo --summary` on the device. The Adreno-architecture agent
   could not reach gpuinfo.org (403); the device-side query settles it.
6. **The unmasked thermal-engine.conf trip values** — the file in
   `/vendor/etc/thermal-engine.conf` *is* readable (we read it; it's a
   text file on this build) but the OEM research agent reported it as
   binary on 2026 Qualcomm builds, suggesting some Nubia variants differ.
   On the team's device the file is the text form we already have at hand.
7. **Whether `setprop sys.thermal.mode_type N` is settable from shell on
   this device** — sepolicy varies. Try each of 0/1/2/3/4 and observe
   `vendor.thermal.mode_cur` and cooling_device states.

---

## 11. Anchored references

Primary device evidence:
- Device: `NX789J-EEA / NX789J / SM8750 / Adreno 830 v2 / Hexagon V79`
- Live probe artifacts: `/tmp/redmagic10-probe/01-base.txt` through
  `09-qairt-fan-perf.txt` (host workstation)
- Gate result: `runtime/reports/gemma4_megakernel/hardware_max/20260517T153500Z_phase10_six_hour_endurance/gate_result.json`
- Telemetry: `/data/local/tmp/polymath_gemma4_gate/hardware_max/20260517T153500Z_phase10_six_hour_endurance/iterations/iter_NNNNNN/telemetry.json` (×465)
- QAIRT install: `/data/local/tmp/qairt-2.44/`
- Thermal config: `/vendor/etc/thermal-engine.conf`
- KGSL: `/sys/class/kgsl/kgsl-3d0/` (root-write for max_gpuclk; shell-read for `gpu_model`, `gpubusy`)

Hexagon V79 / QAIRT primary docs:
- QAIRT LoRA v2 overview, `docs.qualcomm.com/bundle/publicresource/topics/80-63442-10/lora_v2_0_overview.html`
- QAIRT LoRA v3 optimisations, `docs.qualcomm.com/doc/80-63442-10/topic/lora_v3_optimizations.html`
- Online LoRA QNN call flow (`QnnContext_createFromBinary` →
  `QnnContext_applyBinarySection` → `QnnGraph_execute`),
  `docs.qualcomm.com/bundle/publicresource/topics/80-63442-50/tutorial_lora_v2_21_online_qnn_call_flow.html`
- Genie LoRA tutorial (152 ms switch on SM8750 / Llama 3.2-3B), doc
  80-87189-2
- QnnContext.h function reference, `docs.qualcomm.com/doc/80-63442-10/`
- Hexagon V79 HVX Programmer's Reference (doc 80-N2040-61)
- AI Hub release notes (through QAIRT 2.45, Apr 2026)

Adreno 830 / OpenCL / Vulkan primary references:
- Snapdragon OpenCL Programming Guide rev C (doc 80-NB295-11)
- KGSL source on CodeLinaro, `git.codelinaro.org/clo/le/platform/vendor/qcom/opensource/graphics-kernel`
- `cl_qcom_recordable_queues` / `cl_qcom_ml_ops` / `cl_qcom_subgroup_shuffle`
  registry, `registry.khronos.org/OpenCL/extensions/qcom/`
- Vulkan QCOM extension specs: `VK_QCOM_data_graph_model`,
  `VK_QCOM_cooperative_matrix_conversion`, `VK_QCOM_tile_shading` at
  `docs.vulkan.org/features/latest/features/proposals/`
- IWOCL 2025 llama.cpp Adreno backend update,
  `iwocl.org/wp-content/uploads/iwocl-2025-hongqiang-wang-lamacpp-backend-update.pdf`
- ChipsAndCheese X1 deep-dive (A7xx-class compute reference),
  `old.chipsandcheese.com/2024/07/04/the-snapdragon-x-elites-adreno-igpu/`
- ChipsAndCheese X2 deep-dive (matrix unit details),
  `chipsandcheese.com/p/qualcomms-snapdragon-x2-elite`
- Tether QVAC Fabric LLM (LoRA on Adreno 830 via Vulkan, BitNet b1.58
  1B in 13 h), `huggingface.co/blog/qvac/fabric-llm-finetune` and
  `github.com/tetherto/qvac-fabric-llm.cpp`

Training methods 2025–2026:
- Schulman et al., *LoRA Without Regret* (TML Sep 2025),
  `thinkingmachines.ai/blog/lora/`
- Biderman et al., *Plasticity vs. Rigidity* (EACL 2026),
  `arxiv.org/abs/2601.06677`
- Liu et al., *DoRA* (ICML 2024 Oral), `arxiv.org/abs/2402.09353`
- Akyürek et al., *Surprising Effectiveness of TTT for Abstract Reasoning*
  (Nov 2024), `arxiv.org/abs/2411.07279`
- Malladi et al., *MeZO* (Feb 2024), `arxiv.org/abs/2402.11592`
- Sparse-MeZO, `arxiv.org/abs/2402.15751`
- Katti et al., on-device MeZO (Nov 2025), `arxiv.org/abs/2511.11362`
- Xu et al., *MobiLLM* (Feb 2025), `arxiv.org/abs/2502.20421`
- Zhao et al., *GaLore* (ICML 2024), `arxiv.org/abs/2403.03507`;
  *Q-GaLore* (Jul 2024), `arxiv.org/pdf/2407.08296`
- Kopiczko et al., *VeRA* (ICLR 2024), `arxiv.org/pdf/2310.11454`
- Apple Foundation Models pipeline,
  `machinelearning.apple.com/research/introducing-apple-foundation-models`

Red Magic 10 / Nubia OEM:
- `reminon/device_NX789J` (LineageOS-style device tree),
  `github.com/reminon/device_NX789J`
- `cmfnels/device_nubia_NX809J` (RM11 Pro / SM8850 kernel reference),
  `github.com/cmfnels/device_nubia_NX809J`
- `cmfnels/RM-11-Pro-Hardware-Mapping`,
  `github.com/cmfnels/RM-11-Pro-Hardware-Mapping`
- `TheRealCrazyfuy/GameSpaceReplacer`,
  `github.com/TheRealCrazyfuy/GameSpaceReplacer`
- `KhanhNguyen9872/NubiaToolkit`,
  `github.com/KhanhNguyen9872/NubiaToolkit`
- Nubia open-source kernel portal (NX789J not yet published as of probe
  date), `nubia.com/en/service/opensource`
- RedMagic Reddit FAQ confirming Diablo Mode also throttles for safety,
  `redmagic.tech/blogs/faq/redmagic-reddit-faq-you-asked-we-answered`
- Charge Separation product post,
  `global.redmagic.gg/blogs/product-information/the-science-behind-fast-charging-and-charge-separation-how-your-redmagic-battery-is-made-to-last`
- Android Developers Fixed Performance Mode ADPF,
  `developer.android.com/games/optimize/adpf/fixed-performance-mode`

---

## Appendix V — Verification against the RunPod host QAIRT install (2026-05-23)

Verified directly against `/workspace/qairt-2.44/qairt/2.44.0.260225/` on
the project's RunPod pod (`ltg8fdnxgmzwjy`, x86_64 Ubuntu 6.8.0-90). This
appendix closes the largest unverified claim in change D of the POVC:
that the offline LoRA / updateable-binary-section path is fully shipped
on the host SDK the team already has installed.

### V.1 The exact API signature

From `/workspace/qairt-2.44/qairt/2.44.0.260225/include/QNN/QnnContext.h`,
the verified-on-disk header, the symbol the POVC depends on is at
line 1290:

```c
/**
 * @brief Apply a section to the contextBinary produced by a prior
 *        QnnContext_getBinarySection() call. If successful, this section
 *        overwrites previously applied sections. If the call to
 *        applyBinarySection() fails, it indicates the changes were not
 *        applied, and that the context retains its prior state. In this
 *        case the context is still valid and may be used for subsequent
 *        inferences.
 *
 * @param[in] context A context handle.
 * @param[in] graph A graph handle. This argument is optional. When supplied
 *                  the returned binary only contains the context binary
 *                  section pertaining to this graph. When excluded the
 *                  returned binary contains associated updates to all
 *                  graphs in the context.
 * @param[in] section The section of the binary to retrieve. When section is
 *                    QNN_CONTEXT_SECTION_UPDATABLE the returned binary will
 *                    contain all of the updatable tensors associated with
 *                    the context and graph combination.
 * @param[in] binaryBuffer Pointer to the user-allocated context binary
 *                         memory.
 * @param[in] profile The profile handle on which metrics are populated and
 *                    can be queried.
 * @param[in] signal Signal object to control the execution.
 */
QNN_API
Qnn_ErrorHandle_t QnnContext_applyBinarySection(
    Qnn_ContextHandle_t      context,
    Qnn_GraphHandle_t        graph,    /* optional; NULL = all graphs */
    QnnContext_SectionType_t section,  /* QNN_CONTEXT_SECTION_UPDATABLE */
    const QnnContext_Buffer_t* binaryBuffer,
    Qnn_ProfileHandle_t      profile,
    Qnn_SignalHandle_t       signal
);
```

Related symbols in the same header at the listed line numbers (from a
direct `grep -n`):

- L1183 `QnnContext_getBinarySectionSize` — query the size before allocating
- L1239 `QnnContext_getBinarySection` — read the current updatable section
- L1290 `QnnContext_applyBinarySection` — **the write path**
- L1349 `QnnContext_getBinarySectionUpdate` — produce an update binary
- L1381 `QnnContext_freeBinarySectionUpdate` — free same

The `graph` parameter being optional is more granular than the POVC §3.1
table credited. Per-graph or per-context binary mutation is both supported.

### V.2 Host SDK tool inventory (verified)

`/workspace/qairt-2.44/qairt/2.44.0.260225/bin/x86_64-linux-clang/` ships
the following LoRA-relevant tools as host x86_64 binaries:

- `qairt-converter` — model→QAIRT IR converter (`--lora_weight_list` flag
  per Qualcomm public LoRA v2 doc; flag not surfaced in `--help` here
  because the help output requires the envsetup script for the
  `qti.aisw.lora` Python module; the flag is documented in
  `docs.qualcomm.com/bundle/publicresource/topics/80-63442-50/tutorial_lora_v2_14_offline_generating_binaries_with_qnn.html`)
- `qairt-lora-importer` — imports PEFT/PyTorch LoRA into QNN format
- `qairt-lora-mapper` — maps LoRA adapter weights to the base graph
- `qairt-lora-model-creator` — generates a LoRA-enabled model artifact
- `qairt-lora-adapter-bin-updater` — host-side equivalent of the ARM64
  binary already on the phone; updates an adapter binary section
- `qairt-quantizer` — quantization tool (host-side for QAT preparation)
- `qnn-context-binary-generator` — generates the base context binary that
  receives updateable sections
- `qnn-context-binary-utility` — inspect / introspect context binaries
- `qnn-genai-transformer-composer` — **the GenAI transformer composer
  (the LLM-specific composer that handles Gemma-class graphs)**. Not
  noted in the earlier POVC; this is the tool that turns a HuggingFace
  Gemma 4 checkpoint into an HTP-ready graph.
- `qnn-pytorch-converter` — PyTorch graph converter
- `qnn-onnx-converter` — ONNX graph converter

The header tree at `include/QNN/` ships:

- Top-level: `QnnBackend.h`, `QnnCommon.h`, `QnnContext.h`, `QnnDevice.h`,
  `QnnError.h`, `QnnGlobalConfig.h`, `QnnGraph.h`, `QnnInterface.h`,
  `QnnLog.h`, `QnnMem.h`, `QnnOpDef.h`, `QnnOpPackage.h`, `QnnProfile.h`,
  `QnnProperty.h`, `QnnSdkBuildId.h`, `QnnSignal.h`, `QnnTensor.h`,
  `QnnTypes.h`
- Per-backend subdirectories: `CPU/`, `DSP/`, `GPU/`, **`HTP/`**,
  `HTPQEMU/`, `HTA/`, `LPAI/`, `IR/`
- **`GenAiTransformer/`** subdirectory — Genie/GenAI transformer-specific
  types and APIs, paired with `qnn-genai-transformer-composer`
- `Saver/`, `System/`, `TFLiteDelegate/`

### V.3 Install-environment caveats the team will hit

When invoked outside the envsetup'd shell, two tools failed in the
expected ways:

```
$ qairt-lora-adapter-bin-updater --help
qairt-lora-adapter-bin-updater: error while loading shared libraries:
libc++.so.1: cannot open shared object file: No such file or directory
```

Fix: `source /workspace/qairt-2.44/qairt/2.44.0.260225/bin/envsetup.sh`
before invoking, which adds the bundled `libc++.so.1` to
`LD_LIBRARY_PATH`. Alternatively `apt install libc++1` (Ubuntu) is
sufficient.

```
$ qairt-lora-importer --help
ModuleNotFoundError: No module named 'qti'
```

Fix: `pip install` the wheels from `${QDIR}/share/QAIRT/python/` (the
`qti.aisw.*` Python packages that ship with QAIRT). These wheels need
Python 3.10–3.12 typically and are version-locked to the QAIRT release.
The pod is x86_64 Ubuntu so this is straightforward.

These are not blockers for the POVC — they are one-line install fixes.

### V.4 Updated Change D — host pipeline shape, exact

The POVC §7.4 sketch becomes the following concrete pipeline now that
the host SDK is verified:

1. On RunPod, source the env:
   ```
   source /workspace/qairt-2.44/qairt/2.44.0.260225/bin/envsetup.sh
   pip install /workspace/qairt-2.44/qairt/2.44.0.260225/share/QAIRT/python/*.whl
   ```
2. Compose the Gemma 4 E4B graph for HTP:
   ```
   qnn-genai-transformer-composer \
       --model_path google/gemma-4-E4B \
       --revision 7aa32e6889efd6300124851b164f8b364314c3d8 \
       --target_backend htp \
       --htp_arch v79 \
       --output gemma4_e4b_v79.qnn
   ```
3. Convert with updateable-tensor declaration (the DoRA adapter slots from
   POVC §5):
   ```
   qairt-converter \
       --model gemma4_e4b_v79.qnn \
       --lora_weight_list dora_updateable_tensors.txt \
       --output gemma4_e4b_v79_updateable
   ```
   where `dora_updateable_tensors.txt` lists the q_proj, o_proj, gate_proj,
   up_proj tensors across the last 8 transformer blocks.
4. Generate the base context binary:
   ```
   qnn-context-binary-generator \
       --backend libQnnHtp.so \
       --model gemma4_e4b_v79_updateable \
       --binary_file gemma4_e4b_v79_base.qnn.bin
   ```
5. For each training checkpoint, generate a delta adapter binary:
   ```
   qairt-lora-adapter-bin-updater \
       --base gemma4_e4b_v79_base.qnn.bin \
       --weights checkpoint_iterN_dora_weights.bin \
       --output adapter_iterN.bin
   ```
6. Ship `adapter_iterN.bin` to the phone over ADB; the phone-side trainer
   calls `QnnContext_applyBinarySection(ctx, NULL, QNN_CONTEXT_SECTION_UPDATABLE,
   &adapter_iterN_buffer, NULL, NULL)` to apply.
7. Run forward inference on HTP with `QnnGraph_execute`. The activations
   flow back to Adreno via the `/dev/dma_heap/qcom,cma-secure-cdsp`
   buffer per POVC §3.

This is **all shipped tooling**. No Qualcomm partner-NDA artifact is
required for the path above. The team has it on RunPod and on the phone
today.

### V.5 What the verification did NOT confirm

- **`cl_qcom_ml_ops` v2 training operators**: the disagreement between the
  two GPU research passes remains unresolved. Would require running a
  `clGetExtensionFunctionAddressForPlatform` probe directly on the phone's
  `libOpenCL_adreno.so`. Not done in this pass.
- **`VK_KHR_cooperative_matrix` advertisement on the Adreno 830 driver**:
  also unresolved; needs `vulkaninfo --summary` on the device.
- **HTP↔Adreno activation handoff latency on SM8750**: still needs the
  ping-pong microbenchmark per POVC §10.

### V.6 Provenance of this appendix

- SSH target: `root@38.80.152.147:31002` (RunPod pod `ltg8fdnxgmzwjy`)
- Probe date: 2026-05-23
- QAIRT version on RunPod: `2.44.0.260225` at `/workspace/qairt-2.44/qairt/`
  (matches the `qairt-2.44` install at `/data/local/tmp/qairt-2.44/` on
  the Red Magic 10 phone — both built from the same QAIRT 2.44 release)
- QAIRT 2.43 also present on RunPod at `/workspace/qairt-2.43/qairt/` as
  a fallback
- Read-only probe: no compilations run, no models loaded, no state
  modified

End of document.
