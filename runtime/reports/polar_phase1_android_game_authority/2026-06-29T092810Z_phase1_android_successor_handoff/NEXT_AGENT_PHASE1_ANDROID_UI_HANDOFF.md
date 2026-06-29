# Next Agent Handoff: Phase 1 Android App UI And Authority Runtime

**Created:** 2026-06-29T09:28:10Z
**Repo:** `/Users/Zer0pa/Polymat AI/Polymath-AI`
**Branch at handoff:** `gemma4-megakernel-native-training`
**Do not create a new worktree. Do not use GPD. Do not edit root `README.md`.**

## Read First

Read these before changing code:

1. `AGENTS.md`
2. `docs/ENGINEERING-PHASE1-ANDROID-NATIVE-RUNTIME-2026-06-27.md`
3. `runtime/reports/polar_phase1_android_game_authority/2026-06-27T180804Z_phase1_apk_gap_attribution_summary/phase1_apk_gap_attribution_summary.json`
4. `runtime/reports/polar_phase1_android_game_authority/2026-06-27T180804Z_phase1_apk_gap_attribution_summary/NEXT_AGENT_PHASE1_ANDROID_APP_HANDOFF.md`
5. `apps/android-redmagic-lab/README.md`
6. `apps/android-redmagic-lab/app/src/main/java/ai/zer0pa/polymath/lab/data/AndroidGameAuthorityController.kt`
7. `apps/android-redmagic-lab/app/src/main/java/ai/zer0pa/polymath/lab/data/LocalPhase1ReportReader.kt`
8. `apps/android-redmagic-lab/app/src/main/java/ai/zer0pa/polymath/lab/ui/LabController.kt`
9. `apps/android-redmagic-lab/app/src/main/java/ai/zer0pa/polymath/lab/ui/screens/LabConsoleScreen.kt`

The canonical engineering document is the source of truth for backend/native
runtime engineering. Extend it as frontend work completes; do not replace it
with competing narrative docs.

## Current Truth

Phase 1 is a working Android app path, not a toy tokenizer. The real Phase 1
tokenizer path is integrated into the Android architecture:

- Android app path: `apps/android-redmagic-lab/`
- Package: `ai.zer0pa.polymath.lab`
- Manifest keeps `android:appCategory="game"`.
- CMake builds the imported canonical Zig source into `polymath_lab_native`.
- When `POLYMATH_PHASE1_EXECUTABLE` is supplied, the APK packages the exact
  delivered Phase 1 PIE as `libphase1_qa_stream_exec.so`.
- The JNI bridge calls the canonical Phase 1 path without tokenizer
  substitution.
- Correctness and material parity are not the remaining blocker.

The major remaining performance fact is REDMAGIC/Nubia DVFS policy:

- Historical standard APK child-exec class: 53-54M token IDs/sec after warm-up.
- Enforced Nubia high-performance APK child-exec class: 60-61M token IDs/sec.
- Termux promoted 1M baseline in the reports: about 62.63M token IDs/sec.
- The 53-54M standard profile is now drift for the active product lane. Do not
  expose it as a UI mode, script option, or acceptable fallback.

## Best Evidence To Preserve

Use these report directories as the short evidence chain:

- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T182522Z_phase1_apk_nubia_whitelist_no_sampler_repro`
  - Earlier reversible attribution run.
  - Run ID: `2026-06-27T182529Z`
  - Best derived trial: `61,755,471.2386` token IDs/sec.
  - Mean derived trial: `60,519,383.2345` token IDs/sec.
  - Exact material parity: pass.
  - Child exec: enabled, errno `0`.
  - Cpuset: `/top-app`; CPUs allowed: `0-7`.
  - Forbidden payload scan: pass.
  - Historical note: this run restored previous settings. That restore policy
    is now considered drift for the active lane.
- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T185310Z_phase1_apk_high_profile_no_sampler_authority`
  - Active high-performance no-restore lane.
  - Run ID: `2026-06-27T185317Z`
  - Best derived trial: `61,122,162.5233` token IDs/sec.
  - Mean derived trial: `60,155,131.8051` token IDs/sec.
  - Settings policy: `high_performance_profile_is_authority_default_no_restore`.
  - Final settings match target: `true`.
- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T185358Z_phase1_apk_high_profile_no_sampler_authority`
  - Repeat active high-performance no-restore lane.
  - Run ID: `2026-06-27T185405Z`
  - Best derived trial: `60,857,026.2525` token IDs/sec.
  - Mean derived trial: `59,054,959.4533` token IDs/sec.
  - Settings policy: `high_performance_profile_is_authority_default_no_restore`.
  - Final settings match target: `true`.

## High-Performance Authority Configuration

The active host runner is:

```bash
SERIAL=FY25013101C8 python3 scripts/android_lab/run_phase1_nubia_whitelist_probe.py \
  --trial 1m \
  --staging external \
  --timeout-sec 1800
```

The script stages exact Phase 1 closure material, applies the Nubia
high-performance target before the native run, runs the APK child-exec path
with native warm sequence and extended warm sequence flags, avoids the runtime
sampler for the headline run, pulls JSON/Markdown only, and re-applies/verifies
the high-performance target after the run.

Target settings:

```text
NubiaperformanceMode=ai.zer0pa.polymath.lab+300,com.primatelabs.geekbench6+300,
db_game_strengthen_mode_list=null,ai.zer0pa.polymath.lab+6,com.primatelabs.geekbench6+6
db_game_strengthen_packagename=ai.zer0pa.polymath.lab
performance_mode_package=ai.zer0pa.polymath.lab
performance_mode_value=2
game_strengthen_mode_value=6
```

If app launch or Nubia services mutate `performance_mode_value` or
`game_strengthen_mode_value`, re-run the host authority script or re-apply the
target settings. Do not interpret that mutation as permission to restore the
lower standard profile.

## Build Command

The last verified benchmark build used:

```bash
cd "/Users/Zer0pa/Polymat AI/Polymath-AI/apps/android-redmagic-lab"

POLYMATH_PHASE1_EXECUTABLE=/tmp/polymath_android_lab_phase1_exact_closure_material_export/android_lab_phase1_exact_closure_material_export/bin/phase1_qa_stream \
POLYMATH_ZIG_EXECUTABLE=/tmp/polymath_zig_0_16_0_test/zig-aarch64-macos-0.16.0/zig \
JAVA_HOME=/tmp/polymath_jdk21 \
ANDROID_HOME=/usr/local/share/android-commandlinetools \
ANDROID_SDK_ROOT=/usr/local/share/android-commandlinetools \
/tmp/polymath_gradle_9_6_1/gradle-9.6.1/bin/gradle --no-daemon :app:assembleBenchmark
```

Build outputs were removed after install/verification. Do not commit Gradle,
CMake, APK, AAB, cache, or raw-material outputs.

## Current UI State

The UI is no longer a pure placeholder, but it is not product-complete.

Implemented frontend/process connection:

- `Phase1RuntimeSnapshot` and `Phase1ReportReader` were added in
  `domain/Contracts.kt`.
- `LocalPhase1ReportReader.kt` reads the latest app-owned report under
  `/sdcard/Android/data/ai.zer0pa.polymath.lab/files/reports/phase1/<run_id>/`.
- `LabAppContainer.kt` wires `phase1ReportReader`.
- `PolymathLabApp.kt` calls `refreshLatestReport()` on launch.
- `LabController.kt` projects the latest runtime snapshot into metric tiles and
  the phase pipeline.
- `LabConsoleScreen.kt` surfaces artifact identity, source/GBT1/PIE/APK hashes,
  material/parity state, native run phase, warmups/trials, cpuset,
  `Cpus_allowed`, uclamp/scheduler evidence, profile/frequency evidence,
  throughput, forbidden scan state, and high-performance policy.
- `LabComponents.kt` was adjusted for responsive metric rail, phase pipeline,
  evidence strip, and system bar padding.

Important nuance:

- `LabController.writeProbeReport()` still exists because the engine can write
  a package-owned report, but the visible UI no longer exposes a smoke/probe
  button. The active product lane should use host authority evidence and the
  high-performance profile, not an in-app low-gear fallback.
- `LocalPhase1ReportReader` labels high-rate no-sampler runs as rate evidence
  without claiming direct frequency unless sampler evidence exists.
- The UI should keep moving toward a real operator surface. Do not add in-app
  text that explains implementation details or shortcuts; make controls and
  evidence states self-evident.

Next UI work should make the screen more product-real while preserving evidence
truth:

- Keep artifact identity first-class.
- Show current run state and latest report state without stale placeholders.
- Make profile state explicit: high-performance authority lane active, standard
  APK not a product mode.
- Add run progress only if it is sourced from real process/report state.
- Continue visual testing on the REDMAGIC screen after each UI pass.

## Comet And White-Label Prep

The Comet logger was made white-label friendly:

- Script: `scripts/android_lab/log_phase1_android_game_authority_to_comet.py`
- `COMET_API_KEY` remains host-env only and is never printed.
- `COMET_WORKSPACE` defaults to `zer0pa`.
- `COMET_PROJECT_NAME` defaults to `mobile-polymath-ai-training`; set it to a
  separate Hyperspeed project when needed.
- The logger rejects forbidden payload suffixes before upload.

A separate white-label seed was prepared at:

```text
/Users/Zer0pa/Hyperspeed Mobile Tokenizer
```

That folder contains app source, scripts, the canonical engineering doc, safe
report evidence, an export manifest, and its own `NEXT_AGENT_HANDOFF.md`. It
does not contain raw payloads, APK/AAB, model weights, `.gpd`, credentials, or
build output.

## Git And Worktree State

The worktree is dirty. Do not assume everything dirty belongs to this task.

Scoped Phase 1 Android work to consider for staging later:

- `apps/android-redmagic-lab/`
- `scripts/android_lab/`
- `docs/ENGINEERING-PHASE1-ANDROID-NATIVE-RUNTIME-2026-06-27.md`
- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T182522Z_phase1_apk_nubia_whitelist_no_sampler_repro/`
- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T185310Z_phase1_apk_high_profile_no_sampler_authority/`
- `runtime/reports/polar_phase1_android_game_authority/2026-06-27T185358Z_phase1_apk_high_profile_no_sampler_authority/`
- This handoff directory:
  `runtime/reports/polar_phase1_android_game_authority/2026-06-29T092810Z_phase1_android_successor_handoff/`

Known unrelated or dangerous worktree areas to avoid unless the user explicitly
redirects:

- `.gpd/`
- `integrations/gemma4-snapdragon-megakernel/...`
- unrelated Phase 15 docs and scripts
- unrelated Phase 2 / Phase 2C docs and reports
- `native/`
- `polymath_ai/schtm/`
- generated build outputs, APKs, AABs, caches, raw payloads, and model binaries

Before any commit:

```bash
git status --short
find apps/android-redmagic-lab scripts/android_lab runtime/reports/polar_phase1_android_game_authority \
  -type f \( -name '*.apk' -o -name '*.aab' -o -name '*.qai1' -o -name '*.pqa1' \
  -o -name '*.jsonl' -o -name '*.safetensors' -o -name '*.bin' -o -name '*.pt' \
  -o -name '*.pth' -o -name '*.onnx' -o -name '*.tflite' \) -print
```

If replacing GitHub main is requested, ask whether to push this branch or open
and merge a PR. Do not force-push over main from ambiguity.

## Successor First Actions

1. Read the files listed above.
2. Inspect `git status --short` and isolate Phase 1 Android files from
   unrelated dirty work.
3. Run or re-run the high-performance authority script on the REDMAGIC if the
   user wants fresh performance evidence.
4. Continue frontend integration from the current report-backed UI, not from a
   new placeholder.
5. Extend
   `docs/ENGINEERING-PHASE1-ANDROID-NATIVE-RUNTIME-2026-06-27.md` after
   frontend work is materially improved and verified.
6. Keep the authority metric sovereign: exact artifact, exact parity, child
   exec, high-performance profile, safe reports, and 60M token IDs/sec class.
