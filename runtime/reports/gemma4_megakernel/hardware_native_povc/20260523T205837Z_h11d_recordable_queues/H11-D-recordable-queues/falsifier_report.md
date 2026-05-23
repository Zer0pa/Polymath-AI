# H11-D Falsifier Report

- authority runtime was REDMAGIC phone via ADB: pass.
- native probe binary path: `/data/local/tmp/polymath_gemma4_gate/phase11/opencl_recordable_queue_probe`.
- phone gate artifact directory: `/data/local/tmp/polymath_gemma4_gate/phase11/runs/20260523T205837Z_h11d_recordable_queues/H11-D-recordable-queues`.
- requested iterations per microbenchmark: 100.
- recordable queues enabled for later gates: True.
- CPU fallback excluded: probe uses libOpenCL platform/device extension strings and OpenCL command queues.
- mutable update ABI source checked against MNN's vendored `cl_ext_qcom.h` and wrapper signatures before rerun.
- promotion requires mutable-arg correctness and measured benefit; skipped or failed mutable evidence blocks promotion.
