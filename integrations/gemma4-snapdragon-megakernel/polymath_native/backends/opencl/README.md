# OpenCL Backend Skeleton

The OpenCL backend is intentionally not part of the passing gate yet. The CPU reference kernels and JSON golden vectors are the authority for future OpenCL implementation work.

Before enabling this backend:

1. Implement kernels for RMSNorm forward/backward and matmul forward/backward.
2. Add host-side launch code that reports JSON in the same case/output schema as `native_kernel_tests`.
3. Run the same golden comparison gate used by `tools/run_kernel_tests.py`.
