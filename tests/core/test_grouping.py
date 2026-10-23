import random

from impact_agent.core.grouping import group_nodes
from impact_agent.models.impact import ImpactGraph, ImpactNode


def node(id, kind="method", depth=1, service="svc", name=None):
    return ImpactNode(
        id=id, kind=kind, name=name or id, service=service, depth=depth, relation="calls"
    )


def graph(*nodes):
    return ImpactGraph(changed="svc::a.py::f", nodes=list(nodes), source="fixture")


def ids(nodes):
    return [n.id for n in nodes]


def test_mixed_graph_lands_in_right_groups():
    g = graph(
        node("d1", depth=1),
        node("p2", depth=2),
        node("t1", kind="test", depth=2),
        node("p4", kind="api", depth=4),
    )
    out = group_nodes(g)
    assert ids(out.direct) == ["d1"]
    assert ids(out.potential) == ["p2", "p4"]
    assert ids(out.tests) == ["t1"]
    assert out.duplicate_ids == []


def test_test_nodes_at_any_depth_go_to_tests_only():
    out = group_nodes(graph(node("t1", kind="test", depth=1), node("t3", kind="test", depth=3)))
    assert ids(out.tests) == ["t1", "t3"]
    assert out.direct == []
    assert out.potential == []


def test_depth_split_for_non_tests():
    out = group_nodes(graph(node("a", depth=1), node("b", depth=2), node("c", depth=4)))
    assert ids(out.direct) == ["a"]
    assert ids(out.potential) == ["b", "c"]


def test_duplicate_ids_first_kept_and_listed_once():
    first = node("x", name="first")
    g = graph(first, node("y"), node("x", name="second"), node("x", name="third"), node("y"))
    out = group_nodes(g)
    assert [n.name for n in out.direct if n.id == "x"] == ["first"]
    assert len(out.direct) == 2
    assert out.duplicate_ids == ["x", "y"]


def test_duplicate_removed_before_sorting():
    # The kept (first) node has the later sort position; the dropped one would sort first.
    g = graph(node("x", name="zzz"), node("x", name="aaa"), node("m", name="mmm"))
    out = group_nodes(g)
    assert [n.name for n in out.direct] == ["mmm", "zzz"]


def test_ordering_each_tiebreak_level():
    g = graph(
        node("i5", depth=2, service="a", name="a"),  # depth
        node("i4", depth=1, service=None, name="a"),  # None service last within depth 1
        node("i3", depth=1, service="b", name="a"),
        node("i2", depth=1, service="a", name="b"),  # name
        node("i1b", depth=1, service="a", name="a"),  # id
        node("i1a", depth=1, service="a", name="a"),
        node("i0", depth=1, service="B", name="a"),  # case-sensitive: "B" < "a"
    )
    out = group_nodes(g)
    assert ids(out.direct) == ["i0", "i1a", "i1b", "i2", "i3", "i4"]
    assert ids(out.potential) == ["i5"]


def test_repeatable_and_order_independent():
    nodes = [
        node("a", depth=1, service="s2"),
        node("b", depth=1, service=None),
        node("c", depth=3, service="s1"),
        node("d", kind="test", depth=2, service="s1"),
        node("e", kind="test", depth=1, service=None),
        node("f", depth=2, service="s1", name="n"),
    ]
    expected = group_nodes(graph(*nodes))
    assert group_nodes(graph(*nodes)) == expected
    rng = random.Random(0)
    for _ in range(10):
        shuffled = nodes[:]
        rng.shuffle(shuffled)
        assert group_nodes(graph(*shuffled)) == expected


def test_input_graph_not_modified():
    g = graph(node("b", depth=2), node("a", depth=1), node("a", depth=1))
    before = g.model_copy(deep=True)
    group_nodes(g)
    assert g == before


def test_empty_graph():
    out = group_nodes(graph())
    assert out.tests == [] and out.direct == [] and out.potential == []
    assert out.duplicate_ids == []


def test_every_node_in_exactly_one_group():
    graphs = [
        graph(),
        graph(node("a"), node("b", depth=2), node("c", kind="test", depth=5)),
        graph(node("a"), node("a"), node("a", kind="test"), node("b", depth=3)),
        graph(
            *[
                node(f"n{i % 4}", kind="test" if i % 3 == 0 else "api", depth=i % 3 + 1)
                for i in range(12)
            ]
        ),
    ]
    for g in graphs:
        out = group_nodes(g)
        grouped = ids(out.tests) + ids(out.direct) + ids(out.potential)
        assert len(set(grouped)) == len(grouped)
        dropped = len(g.nodes) - len({n.id for n in g.nodes})
        assert len(grouped) + dropped == len(g.nodes)
