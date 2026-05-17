# Vulkan Backend Skeleton

The Vulkan backend is intentionally not part of the passing gate yet. The CPU reference kernels and JSON golden vectors are the authority for future Vulkan implementation work.

Before enabling this backend:

1. Implement shader modules for RMSNorm forward/backward and matmul forward/backward.
2. Add host-side descriptor, dispatch, and readback code that emits the same case/output schema as `native_kernel_tests`.
3. Run the same golden comparison gate used by `tools/run_kernel_tests.py`.
