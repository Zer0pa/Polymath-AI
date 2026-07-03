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
        "provider_access_state": "PENDING_ACTION_PROVIDER_NOT_NEEDED_FOR_CURRENT_EDGE",
        "raw_boundary_state": "metadata_only_no_raw_payloads",
        "drift_action": "none",
        "research_escalation": "none",
        "nonclaims": ["no C5 pass"],
    }
    handoff.update(overrides)
    return handoff


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
