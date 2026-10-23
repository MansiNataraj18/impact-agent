import json

from impact_agent.core.grouping import GroupedNodes
from impact_agent.models.impact import ImpactNode

GROUP_TITLES = (
    ("direct", "Directly affected (depth 1)"),
    ("potential", "Potentially affected (depth 2 or more)"),
    ("tests", "Tests"),
)

INSTRUCTIONS = (
    "You are explaining the impact of one proposed code change.\n"
    "The lists below were produced by code. You may not add, remove, rename or regroup items.\n"
    "Reply with strict JSON only, no prose and no code fences, in exactly this shape:\n"
    '{"summary": "<short summary of the impact>", '
    '"risk_level": "low" | "medium" | "high", '
    '"reasons": {"<item id>": "<one-line reason this item is affected>"}}\n'
    "Include a reason for every item id listed below, and use only the ids listed below."
)


def _node_line(node: ImpactNode) -> str:
    fields = {
        "id": node.id,
        "kind": node.kind.value,
        "name": node.name,
        "service": node.service,
        "location": node.location,
        "depth": node.depth,
        "relation": node.relation,
    }
    return "- " + json.dumps(fields, ensure_ascii=False)


def build_prompt(change_summary: str | None, changed_location: str, grouped: GroupedNodes) -> str:
    parts = [
        INSTRUCTIONS,
        f"Change summary: {change_summary or 'Not provided.'}",
        f"Changed location: {changed_location}",
    ]
    for attribute, title in GROUP_TITLES:
        nodes: list[ImpactNode] = getattr(grouped, attribute)
        lines = [_node_line(node) for node in nodes] or ["- None."]
        parts.append(f"{title}:\n" + "\n".join(lines))
    return "\n\n".join(parts) + "\n"
