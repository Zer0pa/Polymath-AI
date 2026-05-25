# Agent Instructions

For the Gemma 4 hardware-native training lane, read these first:

1. docs/PRD-PHASE13-GEMMA4-ONLY-HETEROGENEOUS-CORPUS-SCALE.md
2. docs/HANDOFF-PHASE13-GEMMA4-ONLY-HETEROGENEOUS-EXECUTOR.md
3. docs/PRD-HARDWARE-NATIVE-TRAINING-POVC.md
4. docs/PRD-GEMMA4-SNAPDRAGON-MEGAKERNEL-HETEROGENEOUS-TRAINING.md
5. RESISTANCE-V2.md
6. .gpd/STATE.md

Phone is the authority runtime. Mac is control plane only. RunPod is
build/reference oracle only. Do not let Mac or RunPod drive every iteration,
serve runtime minibatches, compute gradients, or perform optimizer updates for
an authority phone-training claim.

Phase 13 is a Gemma4-only correction campaign. Non-Gemma artifacts are
forbidden inside promoted Gemma gates. Qwen, SmolLM, random-init, hidden-size
mismatched, or shape-bridged artifacts may be used only as isolated negative
tool-surface probes and cannot advance Gemma training or heterogeneous claims.

Do not use `megakernel` language unless the run actually uses a fused/static
kernel path and measures the dispatch/traffic benefit. Existing two-layer
OpenCL runner and residual adapter paths must be named exactly.

Do not promote 16-sequence cache movement as corpus-scale learning. Phase 13
learning promotion requires a material phone-native HF-streamed corpus cache or
a true boundary blocker.

For long-horizon execution, do not stop at a single defensible result. After
each gate, record evidence, update GPD state/runlog, preserve the strongest
valid config or fallback, and continue unless a PRD boundary blocker or safety
stop applies.

Allowed in git: source, small schemas, text reports, JSON gate results,
manifests, checksums, summaries, and sanitized command logs.

Forbidden in git: model weights, raw large tensor binaries, SDK binaries,
env files, HF tokens, phone token files, SSH keys, .venv, node_modules, build
caches, and raw phone output payloads.
