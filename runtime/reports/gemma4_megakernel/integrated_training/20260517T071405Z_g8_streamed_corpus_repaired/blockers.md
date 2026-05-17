# Blockers

None for the repaired G8 gate.

Notes:
- RunPod workspace artifact quota blocked storing the full exported embedding asset under `/workspace/artifacts`; assets were exported under `/tmp/g8_assets_071405`, transferred to the Mac control plane, then pushed to the phone as immutable hashed assets.
- This is not a runtime boundary issue because the phone training path consumed only phone token cache files and immutable Gemma assets.
