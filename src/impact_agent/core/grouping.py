from pydantic import BaseModel, ConfigDict

from impact_agent.models.impact import ImpactGraph, ImpactNode, NodeKind


class GroupedNodes(BaseModel):
    model_config = ConfigDict(frozen=True)

    tests: list[ImpactNode]
    direct: list[ImpactNode]
    potential: list[ImpactNode]
    duplicate_ids: list[str]


def _sort_key(node: ImpactNode) -> tuple[int, bool, str, str, str]:
    """Order by depth, then service (missing service last), then name, then id."""
    return (node.depth, node.service is None, node.service or "", node.name, node.id)


def group_nodes(graph: ImpactGraph) -> GroupedNodes:
    seen: set[str] = set()
    duplicate_ids: list[str] = []
    unique: list[ImpactNode] = []
    for node in graph.nodes:
        if node.id in seen:
            if node.id not in duplicate_ids:
                duplicate_ids.append(node.id)
            continue
        seen.add(node.id)
        unique.append(node)

    tests = [n for n in unique if n.kind is NodeKind.TEST]
    direct = [n for n in unique if n.kind is not NodeKind.TEST and n.depth == 1]
    potential = [n for n in unique if n.kind is not NodeKind.TEST and n.depth >= 2]

    return GroupedNodes(
        tests=sorted(tests, key=_sort_key),
        direct=sorted(direct, key=_sort_key),
        potential=sorted(potential, key=_sort_key),
        duplicate_ids=duplicate_ids,
    )
