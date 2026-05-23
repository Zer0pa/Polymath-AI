# Agent Instructions

For the Gemma 4 hardware-native training lane, read these first:

1. docs/PRD-HARDWARE-NATIVE-TRAINING-POVC.md
2. docs/PRD-GEMMA4-SNAPDRAGON-MEGAKERNEL-HETEROGENEOUS-TRAINING.md
3. RESISTANCE-V2.md
4. .gpd/STATE.md

Phone is the authority runtime. Mac is control plane only. RunPod is
build/reference oracle only. Do not let Mac or RunPod drive every iteration,
serve runtime minibatches, compute gradients, or perform optimizer updates for
an authority phone-training claim.

Phase 11 is a sequential experiment campaign, H11-A through H11-H. Do not skip
the phone-resident daemon and bottleneck autopsy to chase a narratable HTP,
scope, or benchmark win.

For long-horizon execution, do not stop at a single defensible result. After
each gate, record evidence, update GPD state/runlog, preserve the strongest
valid config or fallback, and continue unless a PRD boundary blocker or safety
stop applies.

Allowed in git: source, small schemas, text reports, JSON gate results,
manifests, checksums, summaries, and sanitized command logs.

Forbidden in git: model weights, raw large tensor binaries, SDK binaries,
env files, HF tokens, phone token files, SSH keys, .venv, node_modules, build
caches, and raw phone output payloads.
