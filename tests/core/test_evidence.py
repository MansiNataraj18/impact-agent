from impact_agent.core.evidence import graph_warnings
from impact_agent.core.grouping import group_nodes
from impact_agent.models.common import UnresolvedItem
from impact_agent.models.impact import ImpactGraph, ImpactNode


def node(id, kind="method", depth=1, location="a.py"):
    return ImpactNode(
        id=id, kind=kind, name=id, service="s", location=location, depth=depth, relation="calls"
    )


def warn(nodes, unresolved=(), parser_unresolved=()):
    graph = ImpactGraph(
        changed="s::a.py::f", nodes=list(nodes), source="fixture", unresolved=list(unresolved)
    )
    return graph_warnings(graph, group_nodes(graph), parser_unresolved)


def test_clean_graph_has_no_warnings():
    assert warn([node("a"), node("t", kind="test")]) == []


def test_no_tests():
    assert warn([node("a")]) == [
        "No tests cover this change; add the regression test before merging."
    ]


def test_empty_graph():
    assert warn([]) == [
        "No tests cover this change; add the regression test before merging.",
        "No callers, dependents or tests were found for the changed code.",
    ]


def test_missing_location_counts_nodes():
    out = warn([node("a", location=None), node("b", location=""), node("t", "test")])
    assert out == ["2 affected item(s) have no location in the graph."]


def test_unresolved_changed_location():
    item = UnresolvedItem(scope="change", reason="symbol not found")
    out = warn([node("t", "test")], unresolved=[item])
    assert out == ["The changed location could not be resolved: symbol not found"]


def test_parser_unresolved_with_and_without_field():
    items = [
        UnresolvedItem(scope="change", change_number=1, field="file", reason="missing"),
        UnresolvedItem(scope="change", change_number=1, reason="odd"),
    ]
    out = warn([node("t", "test")], parser_unresolved=items)
    assert out == ["Unresolved (file): missing", "Unresolved: odd"]


def test_duplicate_ids():
    out = warn([node("t", "test"), node("t", "test"), node("x"), node("x")])
    assert out == ["Duplicate graph node id ignored: t", "Duplicate graph node id ignored: x"]


def test_combined_order():
    out = warn(
        [node("a", location=None), node("a")],
        unresolved=[UnresolvedItem(scope="change", reason="r")],
        parser_unresolved=[UnresolvedItem(scope="change", field="symbol", reason="p")],
    )
    assert out == [
        "No tests cover this change; add the regression test before merging.",
        "1 affected item(s) have no location in the graph.",
        "The changed location could not be resolved: r",
        "Duplicate graph node id ignored: a",
        "Unresolved (symbol): p",
    ]
