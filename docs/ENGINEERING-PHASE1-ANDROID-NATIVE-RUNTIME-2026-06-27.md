# Engineering: Phase 1 Android Native Runtime

**Date:** 2026-06-27
**Scope:** Android app backend/native-runtime integration for the Phase 1 tokenizer pipeline segment
**App package:** `ai.zer0pa.polymath.lab`
**Device lane:** REDMAGIC Android app authority lane, with Termux as the exact-artifact performance reference
**Status:** Backend/native-runtime waypoint reached; frontend/process UI hardening remains open

## 1. Executive Summary

The Phase 1 tokenizer pipeline segment is now integrated into the Android app
architecture with the real artifact. The app can run the canonical Phase 1 path
through the NDK/JNI bridge and can launch the exact delivered Phase 1 PIE from
the APK native library area. Correctness and material parity are not the
remaining blocker.

The original problem was a large performance split:

| Runtime | Warmed 1M class | Notes |
| --- | ---: | --- |
| Termux exact closure | 62M+ token IDs/sec | Promoted reference class |
| APK standard path | 53-54M token IDs/sec | After native warm-up |
| APK with reversible Nubia performance whitelist probe | 60.4-60.6M token IDs/sec best observed | Same artifact, high-frequency profile recovered |

The root cause of the 8-10M token IDs/sec APK gap is a REDMAGIC/Nubia
performance-profile and DVFS ceiling, not tokenizer drift, JNI overhead,
shared-vs-PIE linkage, simple cpuset starvation, or Linux nice value alone.

Standard APK child-exec runs show the same visible scheduler surface as Termux:
`/top-app`, CPUs `0-7`, policy `0`, nice `0`, prio `120`, PCY `ta`, and
effective uclamp max `1024`. Despite that, the standard APK path is held to
CPU0-5 `2.7456GHz` and CPU6-7 `2.4384GHz`. Termux and the reversible Nubia
whitelist APK probe reach CPU0-5 `3.5328GHz` and CPU6-7 `4.32GHz`.

The practical engineering conclusion is:

1. The Phase 1 backend/native segment works inside the Android app.
2. The remaining large gap is platform policy, not artifact implementation.
3. The app must preserve exact-artifact execution and expose true process state
   in the UI.
4. Any production use of the high-frequency profile must be handled as an
   explicit device/operator policy, not hidden as a code optimization.

## 2. Acceptance Gate And Claim Boundary

This document records a backend/native-runtime waypoint, not a final Phase 1
product completion claim.

Accepted:

- The real Phase 1 artifact runs from the Android app architecture.
- APK parity/material diagnostics pass on the exact artifact path.
- The primary APK-vs-Termux shortfall has been attributed to REDMAGIC/Nubia
  DVFS policy.
- Reversible diagnostics can recover the high-frequency profile and reduce the
  performance gap to about 2M token IDs/sec versus the promoted Termux baseline.

Not accepted yet:

- Final APK authority promotion.
- UI/product completeness.
- Any claim that Android Game Mode alone fixes the issue.
- Any claim that the app can always obtain the Nubia high-frequency profile
  without explicit device/operator support.
- Any Phase 2 claim.

The user intent after this waypoint is to harden the system, delete drift, and
connect the UI authentically to the native process. The remaining roughly 2M
token IDs/sec delta is not the main strategic concern.

## 3. Artifact Identity

The authority path remains the exact Phase 1 artifact. No tokenizer
substitution, synthetic probe, or partial implementation can replace it.

| Artifact | SHA-256 |
| --- | --- |
| Export manifest | `4f1720f804b28c56493769ffcfe80ad824c18c5fc95a7fd143d9d7165a19ae71` |
| Canonical Phase 1 source | `829da5e89cf2c787dd6e1e2f984e3f604216633900d6d5896c27260e8711adcb` |
| GBT1 tokenizer table | `5887e29db2618b21fd9db1358c7f6db5bb7efffab54c16ba0643b46d7f3714ae` |
| Delivered executable PIE | `855c8392d627e1510a02b3bef43fe28dfc05c01837961d0451c27885d258a9fe` |

Important paths:

- Local exact closure export:
  `/tmp/polymath_android_lab_phase1_exact_closure_material_export/android_lab_phase1_exact_closure_material_export`
- Original device export path:
  `/sdcard/Download/polymath/android_lab_phase1_exact_closure_material_export/`
- Android app:
  `apps/android-redmagic-lab/`
- Imported canonical Zig source:
  `apps/android-redmagic-lab/native_import/phase1_qa_stream_zig/phase1_qa_stream.zig`

## 4. Architecture

### 4.1 Android App Package

The Android app path is `apps/android-redmagic-lab/`. It uses:

- Kotlin and Jetpack Compose for the app/UI shell.
- NDK/CMake for the native bridge.
- Package `ai.zer0pa.polymath.lab`.
- `android:appCategory="game"` preserved in the manifest.
- Benchmark-active GameState and keep-screen-on state during native runs.

### 4.2 Native Bridge

The current native design has two important execution forms:

1. Shared-object/JNI path:
   - CMake builds the imported canonical Zig source into the Android native
     library path.
   - The Zig `main` symbol is renamed to `phase1_qa_stream_main`.
   - `polymath_lab_native` calls the canonical Phase 1 entrypoint through a
     narrow ABI.

2. Exact PIE child-exec path:
   - `POLYMATH_PHASE1_EXECUTABLE` packages the delivered PIE as
     `libphase1_qa_stream_exec.so`.
   - `useLegacyPackaging=true` and `keepDebugSymbols` keep the packaged binary
     extractable and exact.
   - The APK launches this exact PIE as a child process.

The child-exec path is important because it proves the performance gap is not
primarily caused by JNI, shared-library linkage, or the 64MiB pthread wrapper.

### 4.3 App Lifecycle Hardening

`AndroidGameAuthorityController.kt` now marshals GameState and window flag
mutations onto the UI thread. This fixed the post-run
`CalledFromWrongThreadException` that occurred when clearing
`FLAG_KEEP_SCREEN_ON` from a benchmark worker thread.

This is a real hardening change. It prevents diagnostics and benchmark runs
from leaving the app in a crashed post-native state.

## 5. Build Procedure

The verified benchmark build command is:

```bash
cd "/Users/Zer0pa/Polymat AI/Polymath-AI/apps/android-redmagic-lab"

POLYMATH_PHASE1_EXECUTABLE=/tmp/polymath_android_lab_phase1_exact_closure_material_export/android_lab_phase1_exact_closure_material_export/bin/phase1_qa_stream \
POLYMATH_ZIG_EXECUTABLE=/tmp/polymath_zig_0_16_0_test/zig-aarch64-macos-0.16.0/zig \
JAVA_HOME=/tmp/polymath_jdk21 \
ANDROID_HOME=/usr/local/share/android-commandlinetools \
ANDROID_SDK_ROOT=/usr/local/share/android-commandlinetools \
/tmp/polymath_gradle_9_6_1/gradle-9.6.1/bin/gradle --no-daemon :app:assembleBenchmark
```

Build verification after cleanup succeeded with this command.

Generated artifacts such as `.gradle`, `.kotlin`, `build`, `app/build`,
`app/.cxx`, APKs, AABs, CMake caches, and Gradle binary caches must not be
committed.

## 6. Performance Evidence

### 6.1 Promoted Termux Baselines

| Scale | Token IDs/sec |
| --- | ---: |
| 10k | `16,402,897.6177` |
| 100k | `49,068,772.5901` |
| 1M | `62,634,625.4288` |

### 6.2 Standard APK Path

The old APK path before warm-up could land in a 32-42M class. Warm-up changed
the diagnosis.

Observed standard APK results after native warm-up:

| Path | Best observed token IDs/sec | Ratio vs promoted Termux |
| --- | ---: | ---: |
| Shared-object large-stack wrapper | `53,936,097.8023` | `0.8611` |
| Direct-entry diagnostic | `54,544,086.4224` | `0.8708` |
| Installed exact PIE child exec | `53,183,471.5114` | `0.8491` |
| Post UI-thread fix child exec | `54,458,665.3173` | `0.8695` |

Direct entry is diagnostic only. It passed exact parity and was about 1.1%
above the wrapper, but it later became stack-fragile with extracted native lib
packaging. It should not be retained as the production path.

### 6.3 Termux Collaboration Runs

Termux-side collaboration showed that warm-up and frequency residency matter:

| Run | Token IDs/sec | Notes |
| --- | ---: | --- |
| Cold single | `33,116,120.9911` | Cold regime can look APK-like |
| nice -10 warmup0 transient | `64,808,756.0411` | High-frequency transient |
| nice -10 best post-warm trial | `61,048,534.1079` | Termux remains high class |
| nice 0 baseline hot | `66,498,010.3023` | Nice alone does not explain gap |
| nice 0 best measured trial | `61,727,214.2781` | Same conclusion |

Fresh Termux APK-gap probe with nice0 wrapper:

| Label | Token IDs/sec |
| --- | ---: |
| baseline_no_sampler | `62,993,517.9299` |
| warmup0_no_sampler | `68,360,839.1242` |
| trial0_no_sampler | `65,457,341.0522` |
| trial1_sampled | `59,481,607.9517` |

The sampled Termux child had `/top-app`, CPUs `0-7`, policy `0`, nice `0`,
prio `120`, uclamp max `1024`, CPU0-5 at `3.5328GHz`, and CPU6/7 scaling max
`4.32GHz`.

### 6.4 Standard APK Process Residency

APK child-process sampling showed:

- UID `10563`
- PCY `ta`
- policy `0`
- nice `0`
- prio `120`
- `/top-app` cpuset and cpu groups
- cgroup v2 `/uid_10563/pid_<app_pid>`
- `Cpus_allowed_list: 0-7`
- effective uclamp max `1024`

Despite those visible scheduler conditions, detected child samples were pinned
to:

- CPU0-5: `2.7456GHz`
- CPU6-7: `2.4384GHz`

This closed the hypothesis that the gap was caused by ordinary Linux scheduler
class, cpuset starvation, nice value, or uclamp visibility.

### 6.5 Reversible Nubia Performance Whitelist Probe

A reversible diagnostic temporarily added `ai.zer0pa.polymath.lab` to Nubia
performance/strengthen settings:

```text
NubiaperformanceMode=ai.zer0pa.polymath.lab+300,com.primatelabs.geekbench6+300,
db_game_strengthen_mode_list=null,ai.zer0pa.polymath.lab+6,com.primatelabs.geekbench6+6
db_game_strengthen_packagename=ai.zer0pa.polymath.lab
game_strengthen_mode_value=6
performance_mode_package=ai.zer0pa.polymath.lab
performance_mode_value=2
```

The script restored the original settings after the run.

With these diagnostic settings:

- CPU0-5 max moved to `3.5328GHz`.
- CPU6-7 max moved to `4.32GHz`.
- Native-sampler derived best trial: `60,283,151.4986` token IDs/sec.
- No-sampler best trial: `60,640,010.8813` token IDs/sec.
- No-sampler repeat best trial: `60,472,837.6189` token IDs/sec.

Original restored values:

```text
NubiaperformanceMode=com.primatelabs.geekbench6+300,
db_game_strengthen_mode_list=null,com.primatelabs.geekbench6+6
db_game_strengthen_packagename=com.primatelabs.geekbench6
game_strengthen_mode_value=0
performance_mode_package=ai.zer0pa.polymath.lab
performance_mode_value=2
```

This is the decisive evidence that the exact APK path is capable of the
Termux-class frequency envelope when the OEM performance profile allows it.

## 7. Diagnostic Timeline

1. Exact-artifact app integration was verified.
2. APK remained below Termux, initially in a 32-42M cold class.
3. Native warm-up moved APK into the 53-54M class.
4. Direct-entry diagnostic showed only about 1.1% uplift over the wrapper, so
   wrapper/pthread stack was not primary.
5. Exact delivered PIE child exec from the APK still landed around 53M, so
   PIE-vs-shared/JNI linkage was not primary.
6. Runtime samplers showed APK had `/top-app`, CPUs `0-7`, and uclamp max
   `1024`; no simple cpuset starvation.
7. Termux collaboration showed nice0 still reaches high class, so nice alone
   was not primary.
8. Fast child-process sampling captured the APK child in the hot window and
   proved visible scheduler parity with Termux but lower frequency.
9. Thermal service showed status `0` and cooling devices at `0`, so Android
   thermal throttling was not the immediate explanation.
10. Nubia settings showed Geekbench in performance strengthen lists, not
    Polymath.
11. Reversible Nubia whitelist probe lifted APK frequency and throughput into
    the 60M class.
12. Generated build artifacts were removed and the app-local README was updated
    to remove stale placeholder claims.

## 8. Warm-Up Lessons

Warm-up is necessary for interpreting this pipeline segment.

Observed behavior:

- Cold single runs can land in the 32-39M class on APK and around 33M in Termux.
- One or more native 1M warmups can move the workload into a higher-frequency
  transient.
- Warm-up explains much of the cold APK shortfall but does not explain the full
  standard APK vs Termux gap.
- The high-frequency profile is separate from warm-up. Without the Nubia
  whitelist/profile effect, standard APK still settles around 53-54M after
  warm-up.

Operational implication:

- Do not compare cold APK against warmed Termux.
- Do not compare warmed APK standard mode against Termux without capturing CPU
  frequency.
- Any authority run must include warm-up sequence details and frequency/profile
  evidence.

## 9. Root Cause Analysis

### 9.1 Primary Cause

The primary APK-vs-Termux gap is an OEM performance-profile/DVFS policy
difference.

The key finding is that the Android scheduler fields visible from `/proc` are
not sufficient to explain or guarantee performance. The APK child can be in the
same visible scheduler class as Termux and still receive a lower frequency
ceiling.

### 9.2 Closed Hypotheses

The following are closed as primary explanations:

- correctness/material parity failure;
- tokenizer substitution or semantic drift;
- JNI overhead;
- pthread wrapper stack overhead;
- direct shared-object linkage vs exact PIE;
- simple background cpuset starvation;
- missing CPUs in `Cpus_allowed_list`;
- Linux nice value alone;
- Android GameManager standard/custom mode alone;
- immediate Android thermal throttling;
- raw app UI/Compose thread count as direct hot-loop contention.

### 9.3 Remaining Gap

The best observed APK no-sampler whitelist run is about 2M token IDs/sec below
the promoted Termux 1M baseline:

- Termux promoted 1M: `62,634,625.4288`
- APK whitelist no-sampler best: `60,640,010.8813`
- Difference: about `1,994,614.5475` token IDs/sec

This residual is not the main Phase 1 backend blocker. It may be normal run
variance, remaining APK launch/context difference, measurement path difference,
or residual process/runtime overhead. It should not distract from UI and
hardening work unless future repeated authority runs show it is stable and
important.

## 10. Do And Do Not Rules

### 10.1 Do

- Keep the exact Phase 1 artifact as the authority path.
- Preserve `android:appCategory="game"` unless testing a bounded diagnostic.
- Use native warm-up before interpreting 1M performance.
- Capture frequency evidence during the hot window, not only pre/post.
- Capture cpuset, `Cpus_allowed_list`, cgroup, policy, priority, uclamp, and
  process state for diagnostic runs.
- Enforce the Nubia high-performance profile before and after authority APK
  runs. The high profile is the default lane configuration for
  `ai.zer0pa.polymath.lab`.
- Treat historical standard APK behavior as a debug/attribution baseline, not
  an accessible product fallback.
- Keep UI state tied to real native run state.
- Keep generated build artifacts and raw payloads out of git.
- Record exact commands, run IDs, and report paths for benchmark claims.

### 10.2 Do Not

- Do not substitute a tokenizer or synthetic probe for the real artifact.
- Do not promote direct-entry as production; it is diagnostic and stack-fragile.
- Do not reintroduce APK thread-priority nice `-8` as a win path. It regressed
  throughput to about `24,003,100` token IDs/sec.
- Do not claim Game Mode success from standard/custom mode alone. Custom mode
  did not close the gap.
- Do not claim `top-app` plus uclamp max `1024` guarantees peak frequency.
- Do not compare cold APK to warmed Termux.
- Do not treat sampler-depressed throughput as authority throughput.
- Do not restore the authority device to the lower standard APK profile after a
  Phase 1 run. Reapplying the high-performance target is the current default.
- Do not expose a UI or script affordance that makes the 53-54M standard APK
  profile look like an acceptable runtime mode.
- Do not commit `.gradle`, `.kotlin`, `build`, `app/build`, `app/.cxx`, APKs,
  AABs, `.qai1`, `.pqa1`, `.jsonl`, model binaries, or device payloads.
- Do not edit root `README.md` as part of this phase.
- Do not use GPD for this Android app consolidation lane.

## 11. Frontend/UI Engineering Contract

The current UI is not the completed Phase 1 product surface. The frontend work
must make the app reflective of the real native process rather than decorative.

The UI should expose:

- artifact identity:
  - source SHA-256;
  - GBT1 SHA-256;
  - delivered PIE SHA-256 when packaged;
  - APK hash when available;
- run mode:
  - shared-object wrapper;
  - exact PIE child exec;
  - diagnostic direct-entry only if intentionally enabled;
- run phase:
  - idle;
  - staging;
  - warmup `n`;
  - trial `n`;
  - parity/material check;
  - report write;
  - complete/error;
- performance:
  - token IDs/sec;
  - records/sec;
  - worker elapsed times;
  - best, mean, latest;
- process residency:
  - cpuset;
  - `Cpus_allowed_list`;
  - cgroup summary;
  - sched policy/nice/uclamp excerpt where available;
- frequency/profile:
  - standard APK frequency class;
  - high-frequency/OEM-profile diagnostic state when available;
  - explicit warning when frequency evidence is missing;
- safety and hygiene:
  - forbidden-payload scan status;
  - high-performance profile enforcement status after any host authority run;
  - nonclaim labels for diagnostic-only runs.

The UI should not hide the OEM profile state. For this lane, high-performance
profile enforcement is the default authority configuration; standard APK
profile evidence is historical/debug context only.

## 12. Phase 2 Interface

Phase 2 should build on this engineering truth:

- The Phase 1 Android backend/native segment is integrated and performance
  behavior is understood.
- The Phase 2 packetization/native closure work should not reopen tokenizer
  identity or APK-vs-Termux root-cause questions unless new evidence invalidates
  this document.
- Phase 2 must preserve artifact identity and frequency/profile observability.
- Phase 2 should inherit the same payload hygiene and run-evidence rules.

Open Phase 1 items before declaring product completion:

- UI/process-state hardening.
- Repeat best-known APK performance run from a clean app workflow.
- Decide how the product will handle REDMAGIC/Nubia high-performance profile
  activation.
- Commit/push a scoped Android app/source/report set without unrelated dirty
  work.

## 13. Operational Runbook

### 13.1 Standard Diagnostic APK Run

Use the exact packaged PIE and Zig override:

```bash
cd "/Users/Zer0pa/Polymat AI/Polymath-AI/apps/android-redmagic-lab"

POLYMATH_PHASE1_EXECUTABLE=/tmp/polymath_android_lab_phase1_exact_closure_material_export/android_lab_phase1_exact_closure_material_export/bin/phase1_qa_stream \
POLYMATH_ZIG_EXECUTABLE=/tmp/polymath_zig_0_16_0_test/zig-aarch64-macos-0.16.0/zig \
JAVA_HOME=/tmp/polymath_jdk21 \
ANDROID_HOME=/usr/local/share/android-commandlinetools \
ANDROID_SDK_ROOT=/usr/local/share/android-commandlinetools \
/tmp/polymath_gradle_9_6_1/gradle-9.6.1/bin/gradle --no-daemon :app:assembleBenchmark
```

Then install/run with the existing Android benchmark scripts. Do not pull raw
payloads into the repo.

### 13.2 High-Performance Authority Profile

Current authority runs use the high-performance Nubia profile by default:

```bash
SERIAL=<device> \
python3 scripts/android_lab/run_phase1_nubia_whitelist_probe.py \
  --trial 1m \
  --staging external \
  --timeout-sec 1800
```

The script must:

1. Record the previous settings for audit only.
2. Apply the high-performance target for `ai.zer0pa.polymath.lab`.
3. Run the exact artifact path.
4. Pull safe JSON/text reports only.
5. Re-apply the high-performance target in a `finally` path.
6. Verify final settings match the target.

Historical reversible diagnostics remain useful attribution evidence:

- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T180322Z_phase1_apk_nubia_whitelist_probe/run_nubia_whitelist_probe.py`
- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T180553Z_phase1_apk_nubia_whitelist_no_sampler_probe/`
- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T180651Z_phase1_apk_nubia_whitelist_no_sampler_repeat/`

### 13.3 Cleanup

After builds:

```bash
rm -rf \
  apps/android-redmagic-lab/.gradle \
  apps/android-redmagic-lab/.kotlin \
  apps/android-redmagic-lab/build \
  apps/android-redmagic-lab/app/build \
  apps/android-redmagic-lab/app/.cxx
```

Then scan:

```bash
find apps/android-redmagic-lab runtime/reports/polar_phase1_android_game_authority scripts/android_lab \
  -type f \( \
    -name '*.apk' -o -name '*.aab' -o -name '*.qai1' -o -name '*.pqa1' \
    -o -name '*.jsonl' -o -name '*.bin' -o -name '*.safetensors' \
    -o -name '*.pt' -o -name '*.pth' -o -name '*.onnx' -o -name '*.tflite' \
  \) -print
```

The expected output for a commit-ready source/report scope is empty.

## 14. Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| OEM high-frequency profile cannot be activated by production app flow | APK remains 53-54M class | Treat as operator/device policy; expose state in UI; do not hide it |
| Stale docs keep saying placeholder/NOT_CONNECTED | Agents rebuild old drift | Keep this document and app README as current truth |
| Generated artifacts enter git | Repo becomes polluted and unsafe to push | Use `.gitignore`, cleanup, and forbidden suffix scan |
| UI reports success without process evidence | Product becomes misleading | UI must show artifact, run mode, frequency/profile, and nonclaim state |
| Direct-entry diagnostic is mistaken for production | Stack fragility/crashes | Keep direct-entry diagnostic-only |
| Sampler depresses performance but is treated as authority | False regression | Separate sampler diagnostics from no-sampler authority-like runs |
| Future agents optimize a different tokenizer | Authority metric invalidated | Enforce artifact SHA and exact-path checks |

## 15. Source Evidence

Primary attribution:

- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T180804Z_phase1_apk_gap_attribution_summary/phase1_apk_gap_attribution_summary.json`

Process residency:

- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T180008Z_phase1_apk_fast_child_proc_sampler/fast_child_proc_sampler_summary.json`

Nubia whitelist diagnostics:

- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T180322Z_phase1_apk_nubia_whitelist_probe/nubia_whitelist_probe_summary.json`
- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T180553Z_phase1_apk_nubia_whitelist_no_sampler_probe/nubia_whitelist_no_sampler_probe_summary.json`
- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T180651Z_phase1_apk_nubia_whitelist_no_sampler_repeat/nubia_whitelist_no_sampler_repeat_summary.json`

Termux collaboration:

- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T_termux_apk_gap_probe/termux_apk_gap_probe_2026-06-27T174943Z/SUMMARY.json`

Earlier child-exec comparison:

- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T_phase1_apk_child_exec_diagnostics/PHASE1_APK_CHILD_EXEC_DIAGNOSTIC_COMPARISON.md`

## 16. Document Continuation Rules

This is the single engineering document for the Phase 1 Android backend/native
runtime segment. The next agent should extend it rather than start a competing
Phase 1 engineering narrative.

Recommended future sections:

- `17. Frontend/UI Completion`
- `18. Product Runbook`
- `19. Phase 1 Final Acceptance`
- `20. Phase 2 Handoff`

Do not rewrite this document into a victory narrative. Keep claim boundaries,
evidence paths, and nonclaims intact.

## 17. Frontend/UI Completion

### 17.1 Fresh Best-Known APK Reproduction

Before frontend hardening, the app system was rebuilt, installed, and rerun
from the Android path with the exact packaged Phase 1 PIE:

```bash
cd "/Users/Zer0pa/Polymat AI/Polymath-AI/apps/android-redmagic-lab"

POLYMATH_PHASE1_EXECUTABLE=/tmp/polymath_android_lab_phase1_exact_closure_material_export/android_lab_phase1_exact_closure_material_export/bin/phase1_qa_stream \
POLYMATH_ZIG_EXECUTABLE=/tmp/polymath_zig_0_16_0_test/zig-aarch64-macos-0.16.0/zig \
JAVA_HOME=/tmp/polymath_jdk21 \
ANDROID_HOME=/usr/local/share/android-commandlinetools \
ANDROID_SDK_ROOT=/usr/local/share/android-commandlinetools \
/tmp/polymath_gradle_9_6_1/gradle-9.6.1/bin/gradle --no-daemon :app:assembleBenchmark
```

Installed APK identity:

- device APK path:
  `/data/app/~~FajaXUkv26SIn1gcm0B2gg==/ai.zer0pa.polymath.lab-hDzJcWXV3KHGvzrDrP3TKw==/base.apk`
- device APK SHA-256:
  `966f498f44f70aa23d4a3c11c258513f72c2d4597ad8c4580cf977dce53dbab1`

A reusable host profile/authority runner was added:

- `scripts/android_lab/run_phase1_nubia_whitelist_probe.py`

It stages the exact 1M closure material on device, applies the Nubia
high-performance target, runs the APK child-exec path, re-applies the
high-performance target in a `finally` path, and pulls only JSON/Markdown
report evidence. Previous settings are retained for audit only; they are not
the target state.

Fresh no-sampler reproduction:

- report root:
  `runtime/reports/polar_phase1_android_game_authority/2026-06-27T182522Z_phase1_apk_nubia_whitelist_no_sampler_repro`
- app run ID: `2026-06-27T182529Z`
- exact material parity: `pass`
- child exec: `enabled`, `child_exec_errno=0`
- cpuset: `/top-app`
- `Cpus_allowed_list`: `0-7`
- best derived trial: `61,755,471.2386` token IDs/sec
- mean derived trial: `60,519,383.2345` token IDs/sec
- ratio vs promoted Termux 1M: `0.98596`
- forbidden payload scan: `pass`
- settings restored match original: `true`

The original settings for this fresh run were different from the earlier
handoff run because the device was currently pointed at Termux:

```text
NubiaperformanceMode=com.primatelabs.geekbench6+300,
db_game_strengthen_mode_list=null,com.primatelabs.geekbench6+6
db_game_strengthen_packagename=com.primatelabs.geekbench6
game_strengthen_mode_value=0
performance_mode_package=com.termux
performance_mode_value=0
```

This first fresh reproduction still followed the earlier reversible protocol.
That protocol has now been superseded for active authority runs by the
high-performance default described in section 17.4.

### 17.2 UI/Process-State Hardening

The Compose UI was updated to read app-owned Phase 1 report files and render a
real runtime snapshot instead of static placeholder claims.

New/updated app pieces:

- `Phase1RuntimeSnapshot` and `Phase1ReportReader` in `Contracts.kt`
- `LocalPhase1ReportReader.kt`
- `ApkIdentityReader.kt` now includes packaged
  `libphase1_qa_stream_exec.so` path and SHA-256 when available
- `LabController.kt` projects latest report evidence into the metric rail,
  phase pipeline, and bottom evidence strip
- `LabConsoleScreen.kt` now displays artifact identity, run mode, warmups,
  trials, throughput, cpuset, `Cpus_allowed_list`, scheduler/uclamp fields when
  present, frequency/profile evidence, forbidden-payload state, and diagnostic
  nonclaims
- `LabComponents.kt` now uses responsive metric/phase/evidence layouts and
  system-bar padding so portrait UI does not draw under Android status bars

The UI intentionally distinguishes:

- `HIGH-FREQUENCY EVIDENCED` when sampler evidence captures the frequency
  profile;
- `HIGH RATE` / `frequency evidence missing` for no-sampler high-rate runs;
- `STANDARD APK` class when rates are in the warmed standard range;
- unknown profile when neither rate nor frequency evidence is present.

This preserves the claim boundary: a high no-sampler rate is not presented as
proof of the Nubia high-frequency profile unless frequency evidence was
captured.

### 17.3 Report Semantics Cleanup

The app report factory was updated so generated reports no longer say the
native path is merely a placeholder when a real run was executed. Correctness
summaries now record whether the staged output material matches one of the
known exact closure baselines. Gate results remain `probe` and
`promotion_eligible=false` until host authority evidence includes matched exact
material, enforced high-performance profile state, frequency/profile evidence,
and a clean forbidden-payload scan.

No root `README.md` edits were made. Generated Gradle/CMake/APK outputs remain
disposable and must be removed before commit.

### 17.4 High-Performance Default Enforcement

The lower standard APK profile is now treated as drift for this authority lane.
It remains useful as historical root-cause evidence, but it is not an acceptable
runtime target and should not be exposed as a product fallback.

The active host runner now enforces this policy:

- record previous settings for audit;
- apply the high-performance target before the run;
- run exact 1M child exec with warmups/trials and no sampler for authority-like
  throughput;
- re-apply the high-performance target after the run;
- verify final settings match the target.

Fresh high-profile authority runs after this change:

| Report | Best derived trial | Mean derived trial | Exact material | Final settings |
| --- | ---: | ---: | --- | --- |
| `2026-06-27T185310Z_phase1_apk_high_profile_no_sampler_authority` | `61,122,162.5233` | `60,155,131.8051` | `pass` | target match |
| `2026-06-27T185358Z_phase1_apk_high_profile_no_sampler_authority` | `60,857,026.2525` | `59,054,959.4533` | `pass` | target match |

Direct ADB verification after the second run:

```text
NubiaperformanceMode=ai.zer0pa.polymath.lab+300,com.primatelabs.geekbench6+300,
db_game_strengthen_mode_list=null,ai.zer0pa.polymath.lab+6,com.primatelabs.geekbench6+6
db_game_strengthen_packagename=ai.zer0pa.polymath.lab
performance_mode_package=ai.zer0pa.polymath.lab
performance_mode_value=2
game_strengthen_mode_value=6
```

UI drift deletion performed in the same slice:

- removed the visible smoke-report button that could trigger an unstaged app
  probe from the frontend;
- left the UI as an evidence surface with `refresh evidence`;
- changed user-facing profile copy from restore/diagnostic language to
  high-performance profile enforcement;
- kept Game Mode/Rise/Diablo/Comet as nonclaims.

The APK itself still cannot be assumed to own privileged Nubia global-setting
writes. Therefore the enforced default lives in the host authority harness and
must remain part of the product runbook for this REDMAGIC lane.
