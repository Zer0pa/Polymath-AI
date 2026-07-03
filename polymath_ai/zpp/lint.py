"""Lint helpers for ZER0PA Pipeline Protocol orchestration state."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    message: str


REQUIRED_TOP_LEVEL_FIELDS = (
    "active_edge",
    "status_classification",
    "first_missing_green_field",
    "next_concrete_action",
    "research_escalation",
)

RESEARCH_PACKET_REQUIRED_FIELDS = (
    "mode",
    "trigger",
    "why_execution_cannot_decide",
    "why_this_matters_now",
    "source_boundary",
    "test",
    "stop_condition",
    "expected_metric_impact",
)

BLOCKER_EVIDENCE_KEYS = (
    "blocking_evidence",
    "verification_failure",
    "technical_failure",
    "access_failure",
    "failure_evidence",
    "artifact_sha256",
    "probe_stdout_metadata_sha256",
    "probe_stderr_sha256",
    "native_probe_exit_code",
)

HANDOFF_KEYS = (
    "next_handoff",
    "NEXT_HANDOFF",
)

APEX_PRD_SHA256 = "a3606c186109c1597e43a793647cd7b7f3bd63c653d3986c25e1db09bf224a93"

APEX_PRD_SHA_FIELDS = (
    "active_prd_sha256",
    "living_prd_sha256",
    "current_prd_sha256",
    "apex_prd_sha256",
    "prd_sha256",
)

REQUIRED_HANDOFF_FIELDS = (
    "to",
    "status",
    "reasoning_level",
    "artifacts",
    "authority_metric",
    "first_missing_green_field",
    "next_action",
    "prompt_to_send",
    "provider_access_state",
    "raw_boundary_state",
    "drift_action",
    "research_escalation",
    "nonclaims",
)

REQUIRED_COMPLETION_FIELDS = (
    "authority_metric",
    "first_missing_green_field",
    "provider_access_state",
    "raw_boundary_state",
    "drift_action",
    "nonclaims",
)

APEX_ISLAND_REQUIRED_FIELDS = (
    "apex_field_repaired",
    "falsifier",
    "attempt_budget",
    "return_handoff_to_apex",
)

VALID_PROVIDER_ACCESS_STATES = (
    "PENDING_ACTION_PROVIDER_NOT_NEEDED_FOR_CURRENT_EDGE",
    "PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES",
    "PENDING_ACTION_PROVIDER_AUTH_SURFACE_MISSING",
    "BLOCKER_PROVIDER_AUTH_FAILED",
)

VALID_DRIFT_ACTIONS = (
    "none",
    "ignore_historical",
    "delete_candidate",
    "deletion_done_with_commit",
)

HISTORICAL_DRIFT_ACTIONS = (
    "ignore_historical",
    "delete_candidate",
    "deletion_done_with_commit",
)

ACCESS_FAILURE_TOKENS = (
    "SSH",
    "ADB",
    "TERMUX",
    "COMMAND_CHANNEL",
    "PROVIDER_AUTH",
    "RUNNER_ACCESS",
)

ACCESS_FAILURE_MARKERS = (
    "BLOCKER",
    "UNAVAILABLE",
    "DROPPED",
    "DETACHED",
    "MISSING",
    "FAILED",
)

RECOVERY_EVIDENCE_KEYS = (
    "recovery_attempt_packet",
    "recovery_attempts",
    "attempted_recovery",
    "bounded_recovery_attempted",
    "recovery_not_authorized_reason",
    "authority_to_recover",
)


def lint_orchestration_state(
    state: Any,
    *,
    strict_handoff: bool = False,
    include_historical: bool = False,
) -> list[Finding]:
    """Return ZPP process findings for a decoded orchestration state object."""

    findings: list[Finding] = []
    if not isinstance(state, dict):
        return [
            Finding(
                "error",
                "zpp.state.not_object",
                "$",
                "orchestration state must be a JSON object",
            )
        ]

    findings.extend(_required_top_level_findings(state))
    findings.extend(_stale_mirror_findings(state))
    process_nodes = list(_process_nodes(state, include_historical=include_historical))
    findings.extend(_blocker_semantics_findings(process_nodes))
    findings.extend(_access_recovery_findings(process_nodes))
    findings.extend(_research_escalation_findings(process_nodes))
    findings.extend(_handoff_integrity_findings(process_nodes, strict_handoff=strict_handoff))
    findings.extend(_handoff_packet_shape_findings(process_nodes, strict_handoff=strict_handoff))
    findings.extend(_completion_metadata_findings(process_nodes, strict_handoff=strict_handoff))
    findings.extend(_xhigh_reasoning_findings(process_nodes, strict_handoff=strict_handoff))
    findings.extend(_apex_over_island_findings(state, process_nodes, strict_handoff=strict_handoff))
    findings.extend(_stale_apex_route_findings(state, process_nodes))
    return findings


def _required_top_level_findings(state: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in state:
            findings.append(
                Finding(
                    "error",
                    "zpp.state.required_missing",
                    f"$.{field}",
                    f"required top-level field {field!r} is missing",
                )
            )
    return findings


def _stale_mirror_findings(state: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    watchdog = state.get("active_watchdog_state")
    if not isinstance(watchdog, dict):
        return findings

    comparisons = (
        ("active_edge", "active_edge"),
        ("status_classification", "status_classification"),
        ("first_missing_green_field", "first_missing_green_field"),
    )
    for top_key, nested_key in comparisons:
        top_value = state.get(top_key)
        nested_value = watchdog.get(nested_key)
        if top_value is None or nested_value is None or top_value == nested_value:
            continue
        findings.append(
            Finding(
                "warning",
                "zpp.state.stale_mirror",
                f"$.active_watchdog_state.{nested_key}",
                f"active watchdog {nested_key!r} differs from top-level {top_key!r}",
            )
        )
    return findings


def _blocker_semantics_findings(nodes: list[tuple[str, dict[str, Any]]]) -> list[Finding]:
    findings: list[Finding] = []
    for path, node in nodes:
        status_text = _status_text(node)
        if "BLOCKER" not in status_text:
            continue
        if _has_any_key(node, BLOCKER_EVIDENCE_KEYS):
            continue
        if node.get("user_action_required") is True and node.get("next_action"):
            continue
        findings.append(
            Finding(
                "error",
                "zpp.blocker.evidence_missing",
                path,
                "BLOCKER status requires access, verification, or technical-failure evidence",
            )
        )
    return findings


def _access_recovery_findings(nodes: list[tuple[str, dict[str, Any]]]) -> list[Finding]:
    findings: list[Finding] = []
    for path, node in nodes:
        status_text = _status_text(node)
        if not _looks_like_recoverable_access_failure(status_text):
            continue
        if _has_any_key(node, RECOVERY_EVIDENCE_KEYS):
            continue
        findings.append(
            Finding(
                "warning",
                "zpp.recovery.attempt_missing",
                path,
                "recoverable access failure should include bounded recovery attempts or an explicit not-authorized reason",
            )
        )
    return findings


def _research_escalation_findings(nodes: list[tuple[str, dict[str, Any]]]) -> list[Finding]:
    findings: list[Finding] = []
    for path, node in nodes:
        if "research_escalation" not in node:
            continue
        escalation = node["research_escalation"]
        if escalation in (None, "none", "None", "NONE"):
            continue
        if isinstance(escalation, dict):
            for field in RESEARCH_PACKET_REQUIRED_FIELDS:
                if field not in escalation:
                    findings.append(
                        Finding(
                            "error",
                            "zpp.research.packet_field_missing",
                            f"{path}.research_escalation.{field}",
                            f"research escalation packet is missing {field!r}",
                        )
                    )
            continue
        if isinstance(escalation, str) and _looks_like_research_required(escalation):
            findings.append(
                Finding(
                    "warning",
                    "zpp.research.packet_missing",
                    f"{path}.research_escalation",
                    "research escalation text indicates a sprint, but no structured packet is present",
                )
            )
    return findings


def _handoff_integrity_findings(
    nodes: list[tuple[str, dict[str, Any]]],
    *,
    strict_handoff: bool,
) -> list[Finding]:
    findings: list[Finding] = []
    for path, node in nodes:
        status_text = _status_text(node).lower()
        if not _looks_complete_or_ready(status_text):
            continue
        if _has_any_key(node, HANDOFF_KEYS):
            continue
        if strict_handoff:
            severity = "error"
            message = "complete or custody-ready lane state requires explicit NEXT_HANDOFF"
        elif not _has_routing_fallback(node):
            severity = "warning"
            message = "complete or custody-ready lane state has no explicit handoff or routing fallback"
        else:
            severity = "warning"
            message = "complete or custody-ready lane state should emit explicit NEXT_HANDOFF"
        findings.append(
            Finding(
                severity,
                "zpp.handoff.next_handoff_missing",
                path,
                message,
            )
        )
    return findings


def _handoff_packet_shape_findings(
    nodes: list[tuple[str, dict[str, Any]]],
    *,
    strict_handoff: bool,
) -> list[Finding]:
    findings: list[Finding] = []
    for path, node in nodes:
        for key in HANDOFF_KEYS:
            if key not in node:
                continue
            packet = node[key]
            findings.extend(_validate_handoff_packet(packet, f"{path}.{key}", strict_handoff=strict_handoff))
    return findings


def _validate_handoff_packet(packet: Any, path: str, *, strict_handoff: bool) -> list[Finding]:
    if isinstance(packet, dict):
        return _validate_structured_handoff(packet, path, strict_handoff=strict_handoff)
    if isinstance(packet, str):
        return _validate_text_handoff(packet, path, strict_handoff=strict_handoff)
    return [
        Finding(
            _handoff_shape_severity(strict_handoff),
            "zpp.handoff.invalid_type",
            path,
            "NEXT_HANDOFF must be a dict or text packet with ZPP fields",
        )
    ]


def _validate_structured_handoff(
    packet: dict[str, Any],
    path: str,
    *,
    strict_handoff: bool,
) -> list[Finding]:
    findings: list[Finding] = []
    for field in REQUIRED_HANDOFF_FIELDS:
        if field not in packet:
            findings.append(
                Finding(
                    _handoff_shape_severity(strict_handoff),
                    "zpp.handoff.packet_field_missing",
                    f"{path}.{field}",
                    f"NEXT_HANDOFF packet is missing required ZPP field {field!r}",
                )
            )
    if "reasoning_level" in packet and not _valid_xhigh_reasoning(packet):
        findings.append(
            Finding(
                _handoff_shape_severity(strict_handoff),
                "zpp.reasoning.xhigh_required",
                f"{path}.reasoning_level",
                "route-changing handoff requires reasoning_level 'xhigh' or explicit xhigh_unavailable_with_reason",
            )
        )
    findings.extend(_provider_access_state_value_findings(packet, path))
    findings.extend(_drift_action_value_findings(packet, path))
    if packet.get("to") and packet.get("sent") is False:
        findings.append(
            Finding(
                "warning",
                "zpp.handoff.not_sent",
                f"{path}.sent",
                "NEXT_HANDOFF names a next owner but is marked unsent",
            )
        )
    return findings


def _validate_text_handoff(packet: str, path: str, *, strict_handoff: bool) -> list[Finding]:
    findings: list[Finding] = []
    lowered = packet.lower()
    labels = {
        "to": "to:",
        "status": "status:",
        "reasoning_level": "reasoning_level:",
        "artifacts": "artifacts:",
        "authority_metric": "authority_metric:",
        "first_missing_green_field": "first_missing_green_field:",
        "next_action": "next_action:",
        "prompt_to_send": "prompt_to_send:",
        "provider_access_state": "provider_access_state:",
        "raw_boundary_state": "raw_boundary_state:",
        "drift_action": "drift_action:",
        "research_escalation": "research_escalation:",
        "nonclaims": "nonclaims:",
    }
    for field, label in labels.items():
        if label not in lowered:
            findings.append(
                Finding(
                    _handoff_shape_severity(strict_handoff),
                    "zpp.handoff.packet_field_missing",
                    f"{path}.{field}",
                    f"NEXT_HANDOFF text packet is missing required ZPP label {label!r}",
                )
            )
    if "reasoning_level:" in lowered and "reasoning_level: xhigh" not in lowered and "xhigh_unavailable_with_reason" not in lowered:
        findings.append(
            Finding(
                _handoff_shape_severity(strict_handoff),
                "zpp.reasoning.xhigh_required",
                f"{path}.reasoning_level",
                "route-changing text handoff requires reasoning_level: xhigh or xhigh_unavailable_with_reason",
            )
        )
    return findings


def _completion_metadata_findings(
    nodes: list[tuple[str, dict[str, Any]]],
    *,
    strict_handoff: bool,
) -> list[Finding]:
    findings: list[Finding] = []
    for path, node in nodes:
        if not _looks_complete_or_ready(_status_text(node).lower()):
            continue
        for field in REQUIRED_COMPLETION_FIELDS:
            if _field_present_on_node_or_handoff(node, field):
                continue
            findings.append(
                Finding(
                    _handoff_shape_severity(strict_handoff),
                    "zpp.completion.field_missing",
                    f"{path}.{field}",
                    f"complete or ready state is missing required authority field {field!r}",
                )
            )
        findings.extend(_provider_access_state_value_findings(node, path))
        findings.extend(_drift_action_value_findings(node, path))
    return findings


def _xhigh_reasoning_findings(
    nodes: list[tuple[str, dict[str, Any]]],
    *,
    strict_handoff: bool,
) -> list[Finding]:
    findings: list[Finding] = []
    for path, node in nodes:
        if not _looks_route_changing(node):
            continue
        if _valid_xhigh_reasoning(node):
            continue
        handoff_has_xhigh = any(
            isinstance(node.get(key), dict) and _valid_xhigh_reasoning(node[key])
            for key in HANDOFF_KEYS
        )
        text_handoff_has_xhigh = any(
            isinstance(node.get(key), str)
            and ("reasoning_level: xhigh" in node[key].lower() or "xhigh_unavailable_with_reason" in node[key].lower())
            for key in HANDOFF_KEYS
        )
        if handoff_has_xhigh or text_handoff_has_xhigh:
            continue
        findings.append(
            Finding(
                _handoff_shape_severity(strict_handoff),
                "zpp.reasoning.xhigh_required",
                f"{path}.reasoning_level",
                "route-changing mobilization requires xhigh or explicit xhigh_unavailable_with_reason",
            )
        )
    return findings


def _apex_over_island_findings(
    state: dict[str, Any],
    nodes: list[tuple[str, dict[str, Any]]],
    *,
    strict_handoff: bool,
) -> list[Finding]:
    if not _mechanical_boundary_crossed(state):
        return []

    findings: list[Finding] = []
    for path, node in nodes:
        if _is_historical_node(node):
            continue
        if not _looks_like_isolated_probe(node):
            continue
        for field in APEX_ISLAND_REQUIRED_FIELDS:
            if _field_present_on_node_or_handoff(node, field):
                continue
            findings.append(
                Finding(
                    _handoff_shape_severity(strict_handoff),
                    "zpp.apex_over_island.field_missing",
                    f"{path}.{field}",
                    f"post-boundary isolated probe/island requires {field!r}",
                )
            )
    return findings


def _stale_apex_route_findings(
    state: dict[str, Any],
    nodes: list[tuple[str, dict[str, Any]]],
) -> list[Finding]:
    if not _apex_prd_active(state):
        return []

    findings: list[Finding] = []
    for path, node in nodes:
        if _is_historical_node(node):
            continue
        route_text = _route_text(node).lower()
        if not _looks_like_stale_wavec_or_c5_surface(route_text):
            continue
        findings.append(
            Finding(
                "warning",
                "zpp.apex.stale_route_surface",
                path,
                "WaveC/C5 route surface is historical under the active apex PRD unless re-promoted by NEXT_HANDOFF",
            )
        )
    return findings


def _handoff_shape_severity(strict_handoff: bool) -> str:
    return "error" if strict_handoff else "warning"


def _process_nodes(
    state: dict[str, Any],
    *,
    include_historical: bool,
) -> Iterable[tuple[str, dict[str, Any]]]:
    if include_historical:
        yield from _walk_dict_nodes(state)
        return

    yielded: set[int] = set()

    def emit(path: str, node: Any) -> Iterable[tuple[str, dict[str, Any]]]:
        if not isinstance(node, dict):
            return
        marker = id(node)
        if marker in yielded:
            return
        yielded.add(marker)
        yield path, node

    yield from emit("$", state)

    for key in _active_candidate_keys(state):
        yield from emit(f"$.{key}", state.get(key))

    for container_key in ("active_watchdog_state", "prd_watchdog"):
        container = state.get(container_key)
        if isinstance(container, dict):
            for key in _active_candidate_keys(container):
                yield from emit(f"$.{container_key}.{key}", container.get(key))


def _active_candidate_keys(state: dict[str, Any]) -> list[str]:
    active_text = " ".join(
        str(state.get(key) or "")
        for key in (
            "active_edge",
            "current_gate",
            "governing_edge",
            "first_missing_green_field",
            "status_classification",
        )
    )
    active_tokens = _signal_tokens(active_text)
    keys: list[str] = []
    for key in state:
        key_tokens = _signal_tokens(key)
        if len(active_tokens.intersection(key_tokens)) >= 2:
            keys.append(key)
    return keys


def _signal_tokens(value: str) -> set[str]:
    stopwords = {
        "after",
        "before",
        "pending",
        "action",
        "blocker",
        "bounded",
        "command",
        "decoder",
        "forced",
        "full",
        "opencl",
        "phone",
        "probe",
        "result",
        "phase34",
        "phase3",
        "phase4",
        "phase5",
        "native",
        "runtime",
        "repair",
        "shape",
        "custody",
        "state",
        "current",
        "vendor",
        "waveb",
    }
    return {
        token
        for token in re.split(r"[^a-z0-9]+", value.lower())
        if len(token) >= 4 and token not in stopwords
    }


def _walk_dict_nodes(node: Any, path: str = "$") -> Iterable[tuple[str, dict[str, Any]]]:
    if isinstance(node, dict):
        yield path, node
        for key, child in node.items():
            if key in HANDOFF_KEYS:
                continue
            child_path = f"{path}.{key}" if _safe_path_token(key) else f"{path}[{key!r}]"
            yield from _walk_dict_nodes(child, child_path)
    elif isinstance(node, list):
        for idx, child in enumerate(node):
            yield from _walk_dict_nodes(child, f"{path}[{idx}]")


def _safe_path_token(value: str) -> bool:
    return value.replace("_", "").replace("-", "").isalnum()


def _status_text(node: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ("status", "status_classification", "first_missing_green_field", "current_verdict"):
        value = node.get(key)
        if isinstance(value, str):
            values.append(value)
    return " ".join(values)


def _looks_complete_or_ready(status_text: str) -> bool:
    if "pending_action" in status_text and "ready_for_custodian" not in status_text:
        return False
    markers = (
        "complete",
        "completed",
        "custody-ready",
        "custody_ready",
        "ready_for_custodian",
        "route_green",
        "committed_pushed",
        "frozen",
    )
    return any(marker in status_text for marker in markers)


def _looks_route_changing(node: dict[str, Any]) -> bool:
    if _looks_complete_or_ready(_status_text(node).lower()):
        return True
    if any(key in node for key in HANDOFF_KEYS):
        return True
    if any(key in node for key in ("prompt_to_send", "mobilization_prompt", "lane_mobilization_prompt")):
        return True

    route_text = _route_text(node).lower()
    markers = (
        "mobilization",
        "route-changing",
        "route changing",
        "apex command package",
        "go package",
        "next_handoff",
    )
    return any(marker in route_text for marker in markers)


def _has_routing_fallback(node: dict[str, Any]) -> bool:
    return bool(
        node.get("next_action")
        or node.get("next_owner_thread")
        or node.get("owner_thread")
        or node.get("threads_nudged_this_tick")
    )


def _looks_like_research_required(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in ("required", "sprint", "escalat"))


def _looks_like_recoverable_access_failure(status_text: str) -> bool:
    upper = status_text.upper()
    return any(token in upper for token in ACCESS_FAILURE_TOKENS) and any(
        marker in upper for marker in ACCESS_FAILURE_MARKERS
    )


def _has_any_key(node: dict[str, Any], keys: Iterable[str]) -> bool:
    return any(key in node for key in keys)


def _provider_access_state_value_findings(node: dict[str, Any], path: str) -> list[Finding]:
    value = node.get("provider_access_state")
    if value is None or value in VALID_PROVIDER_ACCESS_STATES:
        return []
    return [
        Finding(
            "error",
            "zpp.provider_access_state.invalid",
            f"{path}.provider_access_state",
            "provider_access_state must use the ZPP provider-access classification vocabulary",
        )
    ]


def _drift_action_value_findings(node: dict[str, Any], path: str) -> list[Finding]:
    value = node.get("drift_action")
    if value is None or value in VALID_DRIFT_ACTIONS:
        return []
    return [
        Finding(
            "error",
            "zpp.drift_action.invalid",
            f"{path}.drift_action",
            "drift_action must be none, ignore_historical, delete_candidate, or deletion_done_with_commit",
        )
    ]


def _field_present_on_node_or_handoff(node: dict[str, Any], field: str) -> bool:
    if _field_present(node.get(field)):
        return True
    for container_key in ("apex_over_island", "apex_over_island_rule", "anti_incrementalism"):
        container = node.get(container_key)
        if isinstance(container, dict) and _field_present(container.get(field)):
            return True
    for handoff_key in HANDOFF_KEYS:
        packet = node.get(handoff_key)
        if isinstance(packet, dict):
            if _field_present(packet.get(field)):
                return True
            for container_key in ("apex_over_island", "apex_over_island_rule", "anti_incrementalism"):
                container = packet.get(container_key)
                if isinstance(container, dict) and _field_present(container.get(field)):
                    return True
        elif isinstance(packet, str) and f"{field.lower()}:" in packet.lower():
            return True
    return False


def _field_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return bool(value)


def _valid_xhigh_reasoning(node: dict[str, Any]) -> bool:
    value = node.get("reasoning_level")
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "xhigh":
            return True
        if lowered.startswith("xhigh_unavailable_with_reason"):
            if ":" in lowered and lowered.split(":", 1)[1].strip():
                return True
            return _field_present(node.get("xhigh_unavailable_with_reason")) or _field_present(
                node.get("reasoning_unavailable_reason")
            )
    return _field_present(node.get("xhigh_unavailable_with_reason"))


def _mechanical_boundary_crossed(state: dict[str, Any]) -> bool:
    if _apex_prd_active(state):
        return True
    if state.get("mechanical_boundary_crossed") is True:
        return True
    boundary_text = " ".join(
        str(state.get(key) or "")
        for key in (
            "boundary_state",
            "current_highest_valid_state",
            "current_bounded_authority",
            "latest_authority_evidence",
        )
    ).lower()
    if "mechanical boundary" in boundary_text and "cross" in boundary_text:
        return True
    return all(marker in boundary_text for marker in ("layer0", "qnn", "vulkan"))


def _apex_prd_active(state: dict[str, Any]) -> bool:
    for field in APEX_PRD_SHA_FIELDS:
        if state.get(field) == APEX_PRD_SHA256:
            return True

    prd_path = str(state.get("active_prd_path") or state.get("living_prd_path") or "")
    if "PRD-APEX-HETEROGENEOUS-CELL-END-TO-END-2026-07-03.md" in prd_path:
        return True

    route_text = _route_text(state).lower()
    authority_metric = str(state.get("authority_metric") or state.get("governing_objective") or "").lower()
    combined = f"{route_text} {authority_metric}"
    return "apex" in combined and "heterogeneous" in combined and "qnn" in combined


def _looks_like_isolated_probe(node: dict[str, Any]) -> bool:
    route_text = _route_text(node).lower()
    if "apex" in route_text and "corpus" in route_text and "vulkan" in route_text:
        return False
    markers = (
        "isolated probe",
        "micro-island",
        "micro_island",
        "probe ladder",
        "probe_ladder",
        "component green",
        "qnn-only",
        "qnn_only",
        "vulkan-only",
        "vulkan_only",
        "operator island",
        "forward island",
    )
    return "island" in route_text or any(marker in route_text for marker in markers)


def _looks_like_stale_wavec_or_c5_surface(route_text: str) -> bool:
    return any(
        marker in route_text
        for marker in (
            "wavec",
            "wave c",
            "c5_after_c1",
            "c5 proxy",
            "c1-c5",
            "c1_c5",
            "canonical c5",
            "c5 scorer",
        )
    )


def _is_historical_node(node: dict[str, Any]) -> bool:
    if node.get("historical") is True or node.get("active_authority") is False:
        return True
    drift_action = node.get("drift_action")
    if drift_action in HISTORICAL_DRIFT_ACTIONS:
        return True
    status_text = _status_text(node).lower()
    return "historical" in status_text


def _route_text(node: dict[str, Any]) -> str:
    fields = (
        "status",
        "status_classification",
        "first_missing_green_field",
        "current_verdict",
        "current_gate",
        "active_edge",
        "governing_edge",
        "current_edge",
        "route",
        "objective",
        "task",
        "next_action",
        "next_concrete_action",
        "prompt_to_send",
        "mobilization_prompt",
        "lane_mobilization_prompt",
        "command_package",
        "implemented_surface",
    )
    return " ".join(str(node.get(field) or "") for field in fields)
