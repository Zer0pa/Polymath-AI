# Conventions

## Runtime Roles

- Mac: control plane only.
- RunPod: build server and PyTorch reference oracle only.
- REDMAGIC: authority runtime.

## Tensor And Comparator Conventions

- Forward parity gates use FP64 cosine over non-pad tokens unless a validated
  numerical-analysis amendment changes the comparator.
- G1/G3 default pass threshold: p50 cosine >= `0.99` and failed non-pad tokens
  below threshold = `0`.
- CPU fallback must be explicit and cannot satisfy Adreno/OpenCL/Vulkan gates.

## Artifact Conventions

- Git may contain source, schemas, runbooks, text reports, manifests, checksums,
  and redacted command logs.
- Git must not contain model weights, raw tensor outputs, `.safetensors`,
  binary model/output payloads, SDK binaries, build directories, caches,
  `.venv`, `venv`, `node_modules`, `.env`, `.env.local`, tokens, or keys.

## Phone Safety

- Preserve existing phone runner/pack checksums before destructive overwrite.
- Stop rather than mutate phone state destructively without rollback.
