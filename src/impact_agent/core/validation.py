import json
from dataclasses import dataclass, field

from impact_agent.core.evidence import WARNING_EMPTY_GRAPH
from impact_agent.core.grouping import GroupedNodes
from impact_agent.core.llm import LLMClient
from impact_agent.core.prompt import build_prompt
from impact_agent.models.impact import ImpactNode, RiskLevel

FALLBACK_RISK = RiskLevel.MEDIUM
FALLBACK_SUMMARY = "Impact explanations are unavailable; the lists below come from the graph only."
WARNING_LLM_INVALID = "LLM output was invalid; explanations are unavailable."
WARNING_UNKNOWN_NODE = "LLM reason ignored for unknown item: {id}"
PLACEHOLDER_REASON = "Depends on the changed code ({relation})."


@dataclass(frozen=True)
class NodeExplanation:
    summary: str
    risk_level: RiskLevel
    reasons: dict[str, str]  # one entry per grouped node id
    warnings: list[str] = field(default_factory=list)


def placeholder_reason(node: ImpactNode) -> str:
    return PLACEHOLDER_REASON.format(relation=node.relation)


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _parse_risk(value: object) -> RiskLevel:
    if isinstance(value, str):
        try:
            return RiskLevel(value.strip().lower())
        except ValueError:
            pass
    return FALLBACK_RISK


def _parse_reply(reply: str) -> tuple[str, object, dict[str, str]] | None:
    """Return (summary, raw risk, reasons) or None when the reply has the wrong shape."""
    try:
        data = json.loads(reply)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    summary = data.get("summary")
    reasons = data.get("reasons")
    if not isinstance(summary, str) or not _one_line(summary):
        return None
    if not isinstance(reasons, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in reasons.items()
    ):
        return None
    return _one_line(summary), data.get("risk_level"), reasons


def explain_nodes(
    llm: LLMClient,
    change_summary: str | None,
    changed_location: str,
    grouped: GroupedNodes,
) -> NodeExplanation:
    """Ask the LLM for a summary, risk and per-node reasons, and validate the reply.

    Group membership always comes from `grouped`; the reply can only supply text.
    Never raises on bad model output.
    """
    nodes = [*grouped.direct, *grouped.potential, *grouped.tests]
    if not nodes:
        return NodeExplanation(WARNING_EMPTY_GRAPH, RiskLevel.LOW, {})

    placeholders = {node.id: placeholder_reason(node) for node in nodes}
    prompt = build_prompt(change_summary, changed_location, grouped)
    try:
        parsed = _parse_reply(llm.complete(prompt))
    except Exception:  # a failing client must not break the analysis
        parsed = None
    if parsed is None:
        return NodeExplanation(FALLBACK_SUMMARY, FALLBACK_RISK, placeholders, [WARNING_LLM_INVALID])

    summary, raw_risk, raw_reasons = parsed
    warnings: list[str] = []
    reasons = dict(placeholders)
    for node_id, reason in raw_reasons.items():
        if node_id not in placeholders:
            warnings.append(WARNING_UNKNOWN_NODE.format(id=node_id))
        elif _one_line(reason):
            reasons[node_id] = _one_line(reason)
    return NodeExplanation(summary, _parse_risk(raw_risk), reasons, warnings)
