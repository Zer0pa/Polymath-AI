# H11-A Falsifier Report

- hidden ADB iteration driver: pass, the queue is phone-local and one daemon invocation runs all iterations.
- process restart per step: pass for the runner process; OpenCL internal context reuse remains explicitly unclaimed until H11-C/H11-D timing.
- missing heartbeat: pass.
- overwritten artifacts: pass, iteration output dirs are unique and state resumes from checkpoint boundaries.
- host-side minibatch serving: pass, token caches are phone-local paths.
- stale checkpoint input: pass.
- active/wall gate: pass.
- disconnect survival gate: pass.
