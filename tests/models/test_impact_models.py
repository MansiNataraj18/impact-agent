import pytest
from pydantic import ValidationError

from impact_agent.models.common import UnresolvedItem
from impact_agent.models.impact import (
    AffectedItem,
    ClaimCheck,
    ClaimFinding,
    ExplanationStatus,
    GraphSource,
    ImpactExplanation,
    ImpactGraph,
    ImpactNode,
    ImpactQuery,
    NodeKind,
    RiskLevel,
    TddImpactResult,
)


def make_node(**overrides):
    data = {"id": "n1", "kind": "method", "name": "pay", "depth": 1, "relation": "calls"}
    return ImpactNode(**{**data, **overrides})


def make_explanation(**overrides):
    data = {
        "change_number": 1,
        "status": "explained",
        "changed_location": "svc::a.py::f",
        "summary": "s",
        "graph_source": "fixture",
    }
    return ImpactExplanation(**{**data, **overrides})


def test_enum_values_match_contract():
    assert {e.value for e in NodeKind} == {
        "method", "function", "class", "service", "api", "event", "database", "test",
    }  # fmt: skip
    assert {e.value for e in RiskLevel} == {"low", "medium", "high"}
    assert {e.value for e in ExplanationStatus} == {"explained", "not_applicable", "skipped"}
    assert {e.value for e in GraphSource} == {"fixture", "graph"}
    assert {e.value for e in ClaimFinding} == {"consistent", "needs_review"}


def test_models_construct_with_valid_data():
    ImpactQuery(change_number=1)
    ImpactQuery(change_number=1, service="s", file="f", symbol="x", project="p",
                repository="r", revision="v")  # fmt: skip
    node = make_node(service="svc", location="a.py")
    graph = ImpactGraph(
        changed="svc::a.py::f",
        nodes=[node],
        source="fixture",
        unresolved=[UnresolvedItem(scope="change", change_number=1, reason="r")],
    )
    item = AffectedItem(node_id="n1", name="pay", kind="method", depth=1, reason="calls it")
    explanation = make_explanation(directly_affected=[item])
    claim = ClaimCheck(service="s", tdd_claim="no change", finding="consistent", note="n")
    result = TddImpactResult(
        changes=[explanation],
        overall_risk="high",
        summary="s",
        graph_source="graph",
        tests_to_run=["t"],
        claims_vs_graph=[claim],
        warnings=["w"],
    )
    assert graph.nodes[0].kind is NodeKind.METHOD
    assert result.overall_risk is RiskLevel.HIGH


def test_unresolved_item_defaults():
    item = UnresolvedItem(scope="tdd", reason="r")
    assert item.change_number is None
    assert item.field is None
    assert item.line is None


def test_depth_below_one_rejected():
    with pytest.raises(ValidationError):
        make_node(depth=0)


@pytest.mark.parametrize(
    ("factory", "kwargs"),
    [
        (make_node, {"kind": "widget"}),
        (make_explanation, {"risk_level": "critical"}),
        (make_explanation, {"status": "done"}),
        (make_explanation, {"graph_source": "database"}),
    ],
)
def test_unknown_enum_values_rejected(factory, kwargs):
    with pytest.raises(ValidationError):
        factory(**kwargs)


def test_unknown_graph_source_rejected_on_graph():
    with pytest.raises(ValidationError):
        ImpactGraph(changed="c", nodes=[], source="database")


def test_unresolved_item_unknown_scope_rejected():
    with pytest.raises(ValidationError):
        UnresolvedItem(scope="file", reason="r")


def test_not_applicable_with_risk_rejected():
    with pytest.raises(ValidationError):
        make_explanation(status="not_applicable", risk_level="low")


def test_not_applicable_without_risk_accepted():
    assert make_explanation(status="not_applicable").risk_level is None


def test_explained_with_risk_accepted():
    assert make_explanation(status="explained", risk_level="high").risk_level is RiskLevel.HIGH


def test_skipped_allows_either():
    assert make_explanation(status="skipped").risk_level is None
    assert make_explanation(status="skipped", risk_level="low").risk_level is RiskLevel.LOW


def test_empty_graph_is_valid():
    assert ImpactGraph(changed="c", nodes=[], source="fixture").nodes == []
