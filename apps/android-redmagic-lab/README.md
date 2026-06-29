# Polymath Lab Android REDMAGIC Phase 1 App

This directory is the Phase 1 Android package-authority lane for Polymath Lab.
It is a Kotlin + Jetpack Compose + NDK/CMake app for package
`ai.zer0pa.polymath.lab` with `android:appCategory="game"`.

Current state: canonical Phase 1 is integrated through the app runtime. CMake
builds the imported Zig source into `polymath_lab_native`, renames the Zig
entrypoint, and the APK can also package the exact delivered Phase 1 PIE as
`libphase1_qa_stream_exec.so` when `POLYMATH_PHASE1_EXECUTABLE` is supplied.
The JNI bridge calls the canonical Phase 1 path without tokenizer substitution.

The remaining APK-vs-Termux performance gap was diagnosed as a REDMAGIC /
Nubia performance-profile DVFS ceiling, not Phase 1 artifact drift. The active
authority lane now enforces the high-performance Nubia profile; the lower
standard APK profile is debug history, not a selectable product mode.

- Historical standard APK child-exec path: 53-54M token IDs/sec class after
  warm-up.
- Termux nice0 exact closure: 62M+ token IDs/sec class and up to 68M transient.
- APK child-exec with enforced Nubia high-performance profile: 60-61M token
  IDs/sec class in repeated no-sampler authority runs.
- The earlier reversible whitelist probe remains useful attribution evidence
  only; authority scripts no longer restore the device to the lower standard
  profile after a Phase 1 run.

Do not promote the 53-54M standard-profile behavior as an acceptable mode. The
real Phase 1 artifact works inside the Android app architecture; the device
must stay in the OEM high-performance profile class for this lane.

## Toolchain Prerequisites

No Gradle wrapper is checked in yet. Use command-line Gradle or add an approved
wrapper in a later slice.

Required local tooling:

- JDK 17 or 21.
- Gradle 9.4.1 or newer in the Gradle 9 line.
- Android SDK platform `android-37`.
- Android SDK Build Tools `36.0.0`.
- Android NDK `28.2.13676358`.
- Android SDK CMake `3.22.1`.
- Zig 0.16.0 for the current canonical imported Zig source path, supplied with
  `POLYMATH_ZIG_EXECUTABLE` when needed.
- Android platform-tools with `adb` for install, launch, report pull, and
  authority probes.

Do not install dependencies globally from this repo. Use the Android SDK
manager and the project-local Gradle files.

## Build

From the repository root:

```bash
export JAVA_HOME="$(brew --prefix openjdk@17)/libexec/openjdk.jdk/Contents/Home"
export PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_HOME=/usr/local/share/android-commandlinetools
export ANDROID_SDK_ROOT=/usr/local/share/android-commandlinetools
export GRADLE_BIN=/tmp/polymath-gradle/gradle-9.6.1/bin/gradle
export POLYMATH_PHASE1_EXECUTABLE=/tmp/polymath_android_lab_phase1_exact_closure_material_export/android_lab_phase1_exact_closure_material_export/bin/phase1_qa_stream
export POLYMATH_ZIG_EXECUTABLE=/tmp/polymath_zig_0_16_0_test/zig-aarch64-macos-0.16.0/zig
bash scripts/android_lab/build_install_phase1_app.sh build
```

Or directly from this directory:

```bash
gradle :app:assembleDebug
```

Expected debug APK:

```text
apps/android-redmagic-lab/app/build/outputs/apk/debug/app-debug.apk
```

## Install And Authority Run

With exactly one authorized REDMAGIC attached, or `SERIAL=<device>` set:

```bash
bash scripts/android_lab/build_install_phase1_app.sh build-install
adb shell am start -n ai.zer0pa.polymath.lab/.MainActivity
```

Run the high-performance authority lane from the host:

```bash
SERIAL=<device> python3 scripts/android_lab/run_phase1_nubia_whitelist_probe.py \
  --trial 1m \
  --staging external \
  --timeout-sec 1800
```

The script stages exact Phase 1 closure material, applies the Nubia
high-performance target before the native run, runs the APK child-exec warm
sequence without the sampler, re-applies the high-performance target after the
run, and pulls JSON/Markdown reports only. The generated app-side report root
is:

```text
/sdcard/Android/data/ai.zer0pa.polymath.lab/files/reports/phase1/<UTC>/
```

The active UI reads the latest report evidence and displays artifact identity,
material/parity state, native run phase, warmups/trials, cpuset and
`Cpus_allowed`, frequency/profile evidence when available, throughput, forbidden
payload scan state, and whether the high-performance OEM profile is active.

## Host Authority Skeletons

Pull reports:

```bash
python3 scripts/android_lab/pull_phase1_app_reports.py
```

Capture package/game/thermal evidence skeleton:

```bash
python3 scripts/android_lab/run_phase1_game_authority_ab.py
```

Comet dry run after pulling reports:

```bash
python3 scripts/android_lab/log_phase1_android_game_authority_to_comet.py <report_dir> --dry-run
```

Actual Comet upload requires `COMET_API_KEY` in the host environment only. Set
`COMET_WORKSPACE` and `COMET_PROJECT_NAME` when logging to a white-label
project. The scripts never print the key and refuse forbidden payload suffixes.

## Current Diagnostic Checkpoint

The app has crossed the material integration checkpoint:

- APK exact parity passes on the real Phase 1 artifact.
- Manifest game category is preserved.
- Native runs assert benchmark-active `GameState` and keep-screen-on state.
- The app remains alive after native runs; GameState/window cleanup is marshaled
  onto the UI thread.
- Native reports capture cpuset and CPU allowance before/after the call.
- Child-exec diagnostics prove PIE-vs-shared/JNI linkage is not the primary
  throughput gap.
- Process-residency diagnostics prove the APK child has `/top-app`, CPUs `0-7`,
  policy `0`, nice `0`, and uclamp max `1024`; the recovered class comes from
  the OEM high-frequency profile.

No Game Mode, Game Space, Rise, Diablo, ADPF, or Comet success should be
claimed without direct report evidence. Any production path that depends on
Nubia performance settings must keep those settings explicit, verified, and
non-optional in the authority lane.
