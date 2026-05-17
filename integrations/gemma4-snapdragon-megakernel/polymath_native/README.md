# Polymath Native Kernel Lab

This directory contains a small native kernel correctness lab. The CPU kernels are the authority implementation for early backend work; OpenCL and Vulkan files are skeletons only and are not wired into the passing gate.

Run the full gate from this directory or the repository root:

```bash
python3.11 polymath_native/tools/run_kernel_tests.py
```

The runner generates fresh golden vectors, builds the CMake target, runs the native executable, compares all output arrays, writes JSON results under `polymath_native/build/native_kernel_lab/`, and exits non-zero on any regression.
