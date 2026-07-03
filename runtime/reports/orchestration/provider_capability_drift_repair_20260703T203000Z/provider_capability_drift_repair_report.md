# Provider Capability Drift Repair

Created UTC: `2026-07-03T20:30:00Z`

Status: `process_drift_repaired_unstaged`

## Root Cause

The context-load diet and narrowed Gate C watchdog prompts preserved the live
handoff edge but dropped the global provider-role invariant that existed in
earlier orchestration state. Local/phone QAIRT source scans were then treated as
sufficient to route user source custody before the authorized RunPod surface was
checked.

## Correct Operational Map

- RunPod: QAIRT/QNN SDK source/tool host for outside-git export/build metadata.
- RedMagic phone over ADB/Termux/SSH: authority execution target for
  model/training gates.
- Hugging Face: corpus/model revision source and metadata-only provenance.
- GitHub: Repo Custodian-owned freeze/PR surface.
- Comet: authority-linked numeric metrics/logging, never dashboard-as-evidence.

## New Rule

Provider capability is not optional lane memory. Every provider/source/logging
or custody-affected route must carry a secret-free
`provider_capability_capsule`.

`user_action_required: true` is invalid for provider/source-custody gaps until
the handoff records the relevant provider matrix entry and exact safe-check
result, or explains why no provider surface owns the artifact class.

## Current Live Edge

Owner: Phase Engineering / Gate C QNN Export Authority
`019f27dd-3879-79d0-9235-2a068349a706`

Gate: `gate_c_layer1_export_package_runpod_qairt_source_root_integration_pending`

RunPod source root validated by Pipeline:
`/workspace/qairt-2.44/qairt/2.44.0.260225`

Execution remains asleep until Pipeline validates the repaired package.

## Nonclaims

- no Gate C authority acceptance.
- no full Gate C execution.
- no layer1 QNN/HTP context authority proof.
- no multi-layer QNN/HTP authority evidence.
- no heldout before/after evidence.
- no model-quality claim.
- no raw payloads in git.
- no secrets printed.
