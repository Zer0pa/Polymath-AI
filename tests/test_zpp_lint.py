from __future__ import annotations

from polymath_ai.zpp import lint_orchestration_state


APEX_PRD_SHA256 = "a3606c186109c1597e43a793647cd7b7f3bd63c653d3986c25e1db09bf224a93"


def base_state() -> dict:
    return {
        "active_edge": "edge_a",
        "status_classification": "PENDING_ACTION_EXECUTION",
        "first_missing_green_field": "runtime_probe_pending",
        "next_concrete_action": "Execution runs one bounded probe.",
        "research_escalation": "none",
        "nonclaims": ["no authority pass"],
    }


def codes(findings) -> set[str]:
    return {finding.code for finding in findings}


def complete_handoff(**overrides) -> dict:
    handoff = {
        "schema_version": "zpp_next_handoff_v1",
        "to": "Repo Custodian 019f2059-ef2c-7762-ba42-963b58f3af90",
        "status": "phase_complete",
        "reasoning_level": "xhigh",
        "artifacts": ["runtime/reports/example.json sha256:" + "a" * 64],
        "authority_metric": "authority metric under test",
        "first_missing_green_field": "custody_commit_missing",
        "next_action": "Freeze the pathset.",
        "prompt_to_send": "Custodian: freeze the pathset.",
        "handoff_dispatch_status": "SENT_TO_NEXT_OWNER",
        "context_load": {
            "tier": "targeted_reference",
            "files_loaded": ["references/next-handoff.md"],
            "extraction_mode": "targeted",
            "rationale": "handoff validation only",
            "omitted_heavy_sources": ["EXECUTIVE_DELIVERY_STATE.json"],
        },
        "provider_access_state": "PENDING_ACTION_PROVIDER_NOT_NEEDED_FOR_CURRENT_EDGE",
        "raw_boundary_state": "metadata_only_no_raw_payloads",
        "drift_action": "none",
        "research_escalation": "none",
        "nonclaims": ["no C5 pass"],
    }
    handoff.update(overrides)
    return handoff


def provider_capability_capsule() -> dict:
    return {
        "matrix_artifact": "runtime/reports/orchestration/SYSTEM_PROVIDER_ACCESS_CAPABILITY_MATRIX_20260702T201330Z.json sha256:" + "a" * 64,
        "providers": {
            "runpod": {
                "role": "QAIRT/QNN SDK source/tool host for outside-git export/build metadata",
                "safe_check": "metadata-only SSH check",
                "current_classification": "PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES",
            },
            "phone_adb_termux": {
                "role": "RedMagic 10 Pro authority execution target for model/training gates",
                "safe_check": "ADB/Termux metadata-only check",
                "current_classification": "PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES",
            },
            "hugging_face": {
                "role": "corpus/model revision source and metadata-only provenance",
                "safe_check": "hf auth whoami after approved env sourcing",
                "current_classification": "PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES",
            },
            "github": {
                "role": "Repo Custodian-owned freeze/PR surface",
                "safe_check": "gh auth status with token redaction",
                "current_classification": "PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES",
            },
            "comet": {
                "role": "authority-linked numeric metrics/logging",
                "safe_check": "SDK init/auth check without printing API key",
                "current_classification": "PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES",
            },
        },
        "false_stop_prevention": [
            "Do not mark user_action_required before checking provider matrix.",
        ],
        "secret_policy": "Never print, copy, summarize, commit, or include token/key values.",
    }


def gate_c_readiness_node(**overrides) -> dict:
    node = {
        "status": "backend_observation_source_package_ready_for_pipeline_validation",
        "first_missing_green_field": "gate_c_active_run_measurement_backend_observation_source_artifacts_absent",
        "package_readiness_only": True,
        "backend_observation_source_artifacts_produced": False,
        "measurement_evidence_produced": False,
        "authority_report_emitted": False,
        "next_action": "Pipeline validates backend-observation source package readiness.",
        "nonclaims": [
            "no Gate C authority acceptance",
            "no backend observation source artifacts produced or accepted",
            "no finite metrics accepted",
            "no authority report emitted or accepted",
        ],
    }
    node.update(overrides)
    return node


def readiness_guard(**overrides) -> dict:
    guard = {
        "readiness_only_count": 1,
        "after_backend_observation_package": True,
        "exit_condition": "real_artifact_production",
        "required_next_output": "backend observations, command manifests, rows, metrics, measurement evidence, or exact blocker",
        "forbid_execution_wake_from_readiness": True,
        "comet_metrics_route_preserved": True,
    }
    guard.update(overrides)
    return guard


def whole_source_input_contract() -> dict:
    return {
        "target_material": "exact target material producer and hash ledger",
        "backend_observations": "backend observation artifacts and producer",
        "command_manifests": "before/after command manifests and owner",
        "theta_pre_post": "theta pre/post canonical snapshots or exact blocker",
        "rows": "active-run before/after rows and row-source owner",
        "finite_metrics": "finite metric producer and Comet route preservation",
        "measurement_evidence": "measurement evidence artifact producer",
        "authority_report": "metadata-only authority report producer",
        "producer_by_surface": {
            "target_material": "Phase Engineering",
            "backend_observations": "Phase Engineering",
            "metrics": "Pipeline/Execution when authorized",
        },
        "stop_conditions": ["missing artifact owner", "nonfinite metric", "raw payload boundary violation"],
    }


def test_valid_minimal_pending_state_has_no_findings() -> None:
    assert lint_orchestration_state(base_state()) == []


def test_missing_required_top_level_field_is_error() -> None:
    state = base_state()
    del state["next_concrete_action"]

    findings = lint_orchestration_state(state)

    assert "zpp.state.required_missing" in codes(findings)
    assert any(finding.severity == "error" for finding in findings)


def test_blocker_requires_failure_evidence() -> None:
    state = base_state()
    state["status_classification"] = "BLOCKER_TERMUX_COMMAND_CHANNEL_UNAVAILABLE"

    findings = lint_orchestration_state(state)

    assert "zpp.blocker.evidence_missing" in codes(findings)


def test_blocker_with_probe_evidence_is_accepted() -> None:
    state = base_state()
    state["status_classification"] = "BLOCKER_TERMUX_COMMAND_CHANNEL_UNAVAILABLE"
    state["probe_stderr_sha256"] = "a" * 64

    assert "zpp.blocker.evidence_missing" not in codes(lint_orchestration_state(state))


def test_access_channel_failure_requires_recovery_attempt_or_authority_boundary() -> None:
    state = base_state()
    state["status_classification"] = "BLOCKER_SSH_DROPPED"
    state["probe_stderr_sha256"] = "a" * 64

    findings = lint_orchestration_state(state)

    assert "zpp.recovery.attempt_missing" in codes(findings)


def test_access_channel_failure_with_recovery_packet_is_accepted() -> None:
    state = base_state()
    state["status_classification"] = "BLOCKER_SSH_DROPPED"
    state["probe_stderr_sha256"] = "a" * 64
    state["recovery_attempt_packet"] = {
        "schema_version": "zpp_recovery_attempt_v1",
        "attempted_actions": ["ssh reconnect check"],
        "restored": False,
    }

    assert "zpp.recovery.attempt_missing" not in codes(lint_orchestration_state(state))


def test_stale_watchdog_mirror_is_flagged() -> None:
    state = base_state()
    state["active_watchdog_state"] = {
        "active_edge": "old_edge",
        "status_classification": "PENDING_ACTION_OLD",
        "first_missing_green_field": "old_missing_field",
    }

    findings = lint_orchestration_state(state)

    assert "zpp.state.stale_mirror" in codes(findings)


def test_research_escalation_packet_requires_decision_fields() -> None:
    state = base_state()
    state["research_escalation"] = {
        "trigger": "repeated_field",
        "why_execution_cannot_decide": "same kernel field repeated",
    }

    findings = lint_orchestration_state(state)

    assert "zpp.research.packet_field_missing" in codes(findings)


def test_textual_research_sprint_without_packet_is_warning() -> None:
    state = base_state()
    state["research_escalation"] = "bounded_sprint_required: repeated kernel field"

    findings = lint_orchestration_state(state)

    assert "zpp.research.packet_missing" in codes(findings)
    assert all(finding.severity != "error" for finding in findings)


def test_completed_lane_requires_explicit_handoff_under_strict_mode() -> None:
    state = base_state()
    state["lane"] = {
        "status": "phase_complete",
        "next_action": "Repo Custodian freezes pathset.",
    }

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.handoff.next_handoff_missing" in codes(findings)
    assert any(finding.severity == "error" for finding in findings)


def test_completed_lane_with_handoff_passes_strict_mode() -> None:
    state = base_state()
    state["lane"] = {
        "status": "phase_complete",
        "next_handoff": complete_handoff(),
    }

    assert lint_orchestration_state(state, strict_handoff=True, include_historical=True) == []


def test_handoff_packet_requires_wavec_fields() -> None:
    state = base_state()
    state["lane"] = {
        "status": "phase_complete",
        "NEXT_HANDOFF": {
            "to": "Repo Custodian",
            "status": "phase_complete",
        },
    }

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.handoff.packet_field_missing" in codes(findings)


def test_handoff_packet_requires_dispatch_status() -> None:
    state = base_state()
    handoff = complete_handoff()
    del handoff["handoff_dispatch_status"]
    state["lane"] = {
        "status": "phase_complete",
        "NEXT_HANDOFF": handoff,
    }

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.handoff.packet_field_missing" in codes(findings)


def test_handoff_packet_rejects_invalid_dispatch_status() -> None:
    state = base_state()
    state["lane"] = {
        "status": "phase_complete",
        "NEXT_HANDOFF": complete_handoff(handoff_dispatch_status="DESCRIBED_NOT_SENT"),
    }

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.handoff.dispatch_status_invalid" in codes(findings)


def test_provider_source_custody_route_requires_capability_capsule() -> None:
    state = base_state()
    state["lane"] = {
        "status": "route_green",
        "next_handoff": complete_handoff(
            provider_access_state="PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES",
            first_missing_green_field="qairt_wrapper_source_unavailable",
            next_action="Route QAIRT source custody after RunPod/phone provider checks.",
            prompt_to_send="Check RunPod QAIRT source root and phone ADB/Termux source contract.",
        ),
    }

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.provider_capability_capsule.missing" in codes(findings)


def test_provider_source_custody_route_with_capsule_passes_provider_guard() -> None:
    state = base_state()
    state["lane"] = {
        "status": "route_green",
        "next_handoff": complete_handoff(
            provider_access_state="PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES",
            provider_capability_capsule=provider_capability_capsule(),
            first_missing_green_field="qairt_wrapper_source_unavailable",
            next_action="Route QAIRT source custody after RunPod/phone provider checks.",
            prompt_to_send="Check RunPod QAIRT source root and phone ADB/Termux source contract.",
        ),
    }

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.provider_capability_capsule.missing" not in codes(findings)
    assert "zpp.provider_capability_capsule.provider_missing" not in codes(findings)


def test_provider_capability_capsule_requires_all_major_surfaces() -> None:
    capsule = provider_capability_capsule()
    del capsule["providers"]["comet"]
    state = base_state()
    state["lane"] = {
        "status": "route_green",
        "next_handoff": complete_handoff(
            provider_access_state="PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES",
            provider_capability_capsule=capsule,
            next_action="Route QAIRT source custody with RunPod.",
            prompt_to_send="Check RunPod QAIRT source root.",
        ),
    }

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.provider_capability_capsule.provider_missing" in codes(findings)


def test_gate_c_readiness_only_requires_recursion_guard() -> None:
    state = base_state()
    state["lane"] = gate_c_readiness_node()

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.readiness_recursion.guard_missing" in codes(findings)


def test_second_gate_c_readiness_green_requires_whole_source_input_contract() -> None:
    state = base_state()
    state["lane"] = gate_c_readiness_node(
        readiness_recursion_guard=readiness_guard(
            readiness_only_count=2,
            exit_condition="whole_source_input_contract",
        )
    )

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.readiness_recursion.whole_contract_missing" in codes(findings)


def test_gate_c_readiness_whole_source_input_contract_satisfies_recursion_guard() -> None:
    state = base_state()
    state["lane"] = gate_c_readiness_node(
        readiness_recursion_guard=readiness_guard(
            readiness_only_count=2,
            exit_condition="whole_source_input_contract",
            whole_source_input_contract=whole_source_input_contract(),
        )
    )

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert not any(finding.code.startswith("zpp.readiness_recursion") for finding in findings)


def test_execution_wake_from_gate_c_package_readiness_requires_bounded_authorization() -> None:
    state = base_state()
    state["lane"] = gate_c_readiness_node(
        next_action="Wake Execution from package readiness after Pipeline green.",
        readiness_recursion_guard=readiness_guard(),
    )

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.readiness_recursion.execution_wake_from_readiness" in codes(findings)


def test_text_handoff_packet_requires_prompt_to_send() -> None:
    state = base_state()
    state["lane"] = {
        "status": "phase_complete",
        "NEXT_HANDOFF": "NEXT_HANDOFF:\n- to: Repo Custodian\n- status: phase_complete\n",
    }

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.handoff.packet_field_missing" in codes(findings)


def test_default_mode_ignores_unrelated_historical_completed_lane() -> None:
    state = base_state()
    state["old_lane"] = {"status": "phase_complete"}

    assert lint_orchestration_state(state, strict_handoff=True) == []


def test_default_mode_checks_active_candidate_lane() -> None:
    state = base_state()
    state["active_edge"] = "WaveB_final_hidden_shape_repair"
    state["final_hidden_shape_report"] = {
        "status": "phase_complete",
    }

    findings = lint_orchestration_state(state, strict_handoff=True)

    assert "zpp.handoff.next_handoff_missing" in codes(findings)


def test_route_changing_handoff_requires_xhigh_reasoning() -> None:
    state = base_state()
    state["lane"] = {
        "status": "route_green",
        "next_handoff": complete_handoff(reasoning_level="high"),
    }

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.reasoning.xhigh_required" in codes(findings)


def test_xhigh_unavailable_reason_is_accepted() -> None:
    state = base_state()
    state["lane"] = {
        "status": "route_green",
        "next_handoff": complete_handoff(
            reasoning_level="xhigh_unavailable_with_reason",
            reasoning_unavailable_reason="tool surface exposes no xhigh override",
        ),
    }

    assert lint_orchestration_state(state, strict_handoff=True, include_historical=True) == []


def test_complete_state_requires_authority_fields() -> None:
    state = base_state()
    state["lane"] = {
        "status": "phase_complete",
        "next_handoff": {
            "to": "Pipeline Integrator",
            "status": "phase_complete",
            "reasoning_level": "xhigh",
            "artifacts": ["none: protocol-only"],
            "first_missing_green_field": "apex_command_package_missing",
            "next_action": "Validate command package.",
            "prompt_to_send": "Validate.",
            "research_escalation": "none",
            "nonclaims": ["no authority pass"],
        },
    }

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.completion.field_missing" in codes(findings)
    assert "zpp.handoff.packet_field_missing" in codes(findings)


def test_route_changing_work_requires_context_load_contract() -> None:
    state = base_state()
    state["lane"] = {
        "status": "route_green",
        "next_handoff": complete_handoff(),
    }
    del state["lane"]["next_handoff"]["context_load"]

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.context_load.missing" in codes(findings)
    assert "zpp.handoff.packet_field_missing" in codes(findings)


def test_context_load_rejects_invalid_tier() -> None:
    state = base_state()
    state["lane"] = {
        "status": "route_green",
        "next_handoff": complete_handoff(
            context_load={
                "tier": "read_everything",
                "files_loaded": ["runtime/reports/orchestration/EXECUTIVE_DELIVERY_STATE.json"],
                "extraction_mode": "full",
                "rationale": "debugging",
                "omitted_heavy_sources": [],
            }
        ),
    }

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.context_load.tier_invalid" in codes(findings)


def test_context_load_over_budget_warns_without_full_tier() -> None:
    state = base_state()
    state["lane"] = {
        "status": "route_green",
        "next_handoff": complete_handoff(
            context_load={
                "tier": "targeted_reference",
                "files_loaded": [f"file_{idx}.md" for idx in range(9)],
                "extraction_mode": "targeted",
                "rationale": "large validation set",
                "omitted_heavy_sources": [],
            }
        ),
    }

    findings = lint_orchestration_state(state, strict_handoff=True, include_historical=True)

    assert "zpp.context_load.over_budget" in codes(findings)


def test_post_boundary_isolated_probe_requires_apex_over_island_fields() -> None:
    state = base_state()
    state["active_prd_sha256"] = APEX_PRD_SHA256
    state["active_edge"] = "Apex Heterogeneous Cell"
    state["next_concrete_action"] = "Run isolated QNN operator island probe before apex command package."

    findings = lint_orchestration_state(state, strict_handoff=True)

    assert "zpp.apex_over_island.field_missing" in codes(findings)


def test_post_boundary_probe_with_apex_over_island_fields_passes_guard() -> None:
    state = base_state()
    state["active_prd_sha256"] = APEX_PRD_SHA256
    state["active_edge"] = "Apex Heterogeneous Cell"
    state["next_concrete_action"] = "Run isolated QNN operator island probe before apex command package."
    state["apex_over_island"] = {
        "apex_field_repaired": "qnn_causality_broken",
        "falsifier": "QNN tensor cannot be traced to packetized corpus input",
        "attempt_budget": "one bounded probe",
        "return_handoff_to_apex": "Phase Engineering -> Pipeline Integrator",
    }

    assert "zpp.apex_over_island.field_missing" not in codes(lint_orchestration_state(state, strict_handoff=True))


def test_stale_wavec_route_surface_is_flagged_under_apex_prd() -> None:
    state = base_state()
    state["active_prd_sha256"] = APEX_PRD_SHA256
    state["active_edge"] = "WaveC_Fused_Megakernel_Reorientation"
    state["next_concrete_action"] = "Freeze stale WaveC route table."

    findings = lint_orchestration_state(state)

    assert "zpp.apex.stale_route_surface" in codes(findings)


def test_historical_wavec_route_surface_is_not_active_drift() -> None:
    state = base_state()
    state["active_prd_sha256"] = APEX_PRD_SHA256
    state["active_edge"] = "WaveC_Fused_Megakernel_Reorientation"
    state["next_concrete_action"] = "Freeze stale WaveC route table."
    state["drift_action"] = "ignore_historical"

    assert "zpp.apex.stale_route_surface" not in codes(lint_orchestration_state(state))
