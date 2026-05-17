# Android Skeleton

This directory is the REDMAGIC-facing Android shell for the native kernel lab.

Current status:

- `app/`: placeholder for a future Gradle/NDK app that pushes kernel fixtures, executes OpenCL/Vulkan parity tests, and streams telemetry.
- `native/`: placeholder for Android NDK C++ bindings around the same CPU reference and GPU backend interfaces used by the host lab.

The first Android execution gate is not full training. It is REDMAGIC-attached RMSNorm and matmul parity with battery and thermal telemetry.
