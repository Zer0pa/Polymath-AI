# D003 GPU Backend Policy

Decision: keep Vulkan and OpenCL alive until REDMAGIC benchmark evidence exists.

## Evidence

- LiteRT-LM Android docs explicitly mention OpenCL native libraries for GPU backend setup.
- Android Vulkan support is widespread and attractive for explicit memory/synchronization control.
- Adreno driver behavior is device-specific enough that Mac-side ideology is not evidence.

## Policy

- Implement equivalent RMSNorm and matmul skeletons for OpenCL and Vulkan.
- Use identical golden vectors and JSON telemetry for both.
- Choose only after REDMAGIC runs include correctness, latency, battery, thermals, and sustained-run stability.
