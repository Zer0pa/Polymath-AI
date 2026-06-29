# GPD Reconciliation

Active phone GPD state lives under `GPD/STATE.md`, `GPD/ROADMAP.md`, and `GPD/state.json`.

Observed during handoff prep:

- `.gpd/STATE.md`: missing in this Termux workspace.
- `.gpd/ROADMAP.md`: missing in this Termux workspace.
- `GPD/STATE.md`: current focus records Phase 2-C handoff/drift quarantine after terminal `phase2c_real_corpus_required`.
- `GPD/ROADMAP.md`: Phase 03 has four completed plans through handoff and drift quarantine.
- `GPD/phases/03-phase-2-c-maximal-binary-packetization-guardrail-execution/.continue-here.md`: canonical resume surface.
- `GPD/DERIVATION-STATE.md`: appended session state.

This is not Mac/phone reconciliation. It is a phone-side statement that `.gpd` is absent here and `GPD` is the active state surface. This handoff is not Phase 3 closure.

## Validation

```json
{
  "valid": true,
  "issues": [],
  "warnings": [],
  "integrity_mode": "standard",
  "integrity_status": "healthy",
  "state_source": "state.json",
  "project_contract_load_info": {
    "status": "loaded",
    "source_path": "GPD/state.json",
    "provenance": "raw",
    "raw_project_contract_classified": true,
    "errors": [],
    "warnings": []
  },
  "project_contract_validation": {
    "valid": true,
    "errors": [],
    "warnings": [],
    "question": "Can the Phase 2-C high-diversity continuation clear the 50k distinct-token performance floor while preserving the PJP1 contract and avoiding Phase 2-C maximal-pass or Phase 3 handoff overclaims?",
    "decisive_target_count": 12,
    "guidance_signal_count": 6,
    "reference_count": 5,
    "mode": "approved"
  },
  "project_contract_gate": {
    "status": "loaded",
    "visible": true,
    "blocked": false,
    "load_blocked": false,
    "approval_blocked": false,
    "authoritative": true,
    "repair_required": false,
    "raw_project_contract_classified": true,
    "provenance": "raw",
    "source_path": "GPD/state.json"
  }
}
```
