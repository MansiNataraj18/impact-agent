from collections.abc import Sequence

from impact_agent.core.grouping import GroupedNodes
from impact_agent.models.common import UnresolvedItem
from impact_agent.models.impact import ImpactGraph

WARNING_NO_TESTS = "No tests cover this change; add the regression test before merging."
WARNING_EMPTY_GRAPH = "No callers, dependents or tests were found for the changed code."
WARNING_MISSING_LOCATION = "{n} affected item(s) have no location in the graph."
WARNING_UNRESOLVED_LOCATION = "The changed location could not be resolved: {reason}"
WARNING_UNRESOLVED_FIELD = "Unresolved ({field}): {reason}"
WARNING_UNRESOLVED = "Unresolved: {reason}"
WARNING_DUPLICATE_ID = "Duplicate graph node id ignored: {id}"
WARNING_NO_GRAPH = "No graph was supplied for this change."


def unresolved_warning(item: UnresolvedItem) -> str:
    if item.field is None:
        return WARNING_UNRESOLVED.format(reason=item.reason)
    return WARNING_UNRESOLVED_FIELD.format(field=item.field, reason=item.reason)


def graph_warnings(
    graph: ImpactGraph,
    grouped: GroupedNodes,
    parser_unresolved: Sequence[UnresolvedItem] = (),
) -> list[str]:
    """Code-generated warnings for one analysed change, in a fixed order."""
    warnings: list[str] = []
    if not grouped.tests:
        warnings.append(WARNING_NO_TESTS)
    if not graph.nodes:
        warnings.append(WARNING_EMPTY_GRAPH)
    kept = [*grouped.tests, *grouped.direct, *grouped.potential]
    missing_location = sum(1 for node in kept if not node.location)
    if missing_location:
        warnings.append(WARNING_MISSING_LOCATION.format(n=missing_location))
    for item in graph.unresolved:
        warnings.append(WARNING_UNRESOLVED_LOCATION.format(reason=item.reason))
    for node_id in grouped.duplicate_ids:
        warnings.append(WARNING_DUPLICATE_ID.format(id=node_id))
    for item in parser_unresolved:
        warnings.append(unresolved_warning(item))
    return warnings
