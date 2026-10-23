import pytest

from impact_agent.core.grouping import group_nodes
from impact_agent.models.impact import GraphSource, ImpactGraph, ImpactQuery
from impact_agent.providers.base import GraphProvider
from impact_agent.providers.fake import FakeGraphProvider
from impact_agent.providers.fixtures import SCENARIOS

QUERY = ImpactQuery(change_number=1, service="ui", file="view.tsx", symbol="blur")
CHANGED = "ui::view.tsx::blur"


def graph_for(scenario, query=QUERY):
    return FakeGraphProvider(scenario).get_impact(query)


def test_scenarios_are_the_documented_five():
    assert set(SCENARIOS) == {"normal", "no_tests", "empty", "cross_service", "missing_evidence"}


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_each_fixture_is_a_valid_fixture_graph(scenario):
    graph = graph_for(scenario)
    assert ImpactGraph.model_validate(graph.model_dump()) == graph
    assert graph.source is GraphSource.FIXTURE
    assert graph.changed == CHANGED


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_deterministic(scenario):
    assert graph_for(scenario) == graph_for(scenario)
    assert FakeGraphProvider(scenario).get_impact(QUERY) == FakeGraphProvider(scenario).get_impact(
        QUERY
    )


def test_satisfies_graph_provider_protocol():
    provider: GraphProvider = FakeGraphProvider()
    assert provider.get_impact(QUERY).source is GraphSource.FIXTURE


def test_unknown_scenario_raises_at_construction():
    with pytest.raises(ValueError):
        FakeGraphProvider("nope")
    with pytest.raises(ValueError):
        FakeGraphProvider("normal", by_symbol={"x": "nope"})


def test_by_symbol_selects_scenario_and_falls_back():
    provider = FakeGraphProvider("normal", by_symbol={"blur": "empty"})
    assert provider.get_impact(QUERY).nodes == []
    other = ImpactQuery(change_number=2, service="ui", file="f", symbol="other")
    assert provider.get_impact(other).nodes != []
    no_symbol = ImpactQuery(change_number=3)
    assert provider.get_impact(no_symbol).nodes != []


def test_changed_string_uses_unknown_for_none_parts():
    graph = FakeGraphProvider().get_impact(ImpactQuery(change_number=1, file="a.py"))
    assert graph.changed == "unknown::a.py::unknown"
    assert FakeGraphProvider().get_impact(ImpactQuery(change_number=1)).changed == (
        "unknown::unknown::unknown"
    )


def test_normal_groups():
    grouped = group_nodes(graph_for("normal"))
    assert [n.depth for n in grouped.direct] == [1, 1]
    assert [n.service for n in grouped.potential] == ["ui", "accounts-service", "candidate-service"]
    assert [n.depth for n in grouped.potential] == [2, 3, 4]
    assert len(grouped.tests) == 1 and grouped.tests[0].service == "ui"
    assert all(n.location for n in graph_for("normal").nodes)


def test_no_tests_has_empty_tests_group():
    grouped = group_nodes(graph_for("no_tests"))
    assert grouped.tests == []
    assert len(grouped.direct) == 2 and len(grouped.potential) == 3


def test_empty_has_no_nodes():
    graph = graph_for("empty")
    grouped = group_nodes(graph)
    assert graph.nodes == []
    assert grouped.tests == grouped.direct == grouped.potential == []


def test_cross_service_spans_several_services_and_depths():
    graph = graph_for("cross_service")
    grouped = group_nodes(graph)
    services = {n.service for n in graph.nodes}
    assert {"ui", "accounts-service", "candidate-service", "reports-api"} <= services
    assert {n.depth for n in graph.nodes} == {1, 2, 3}
    assert len(grouped.tests) == 1
    assert grouped.direct and grouped.potential


def test_missing_evidence_has_gaps_and_unresolved_item():
    graph = graph_for("missing_evidence")
    assert any(n.location is None for n in graph.nodes)
    assert any(n.service is None for n in graph.nodes)
    assert [(u.scope, u.field, u.reason) for u in graph.unresolved] == [
        ("change", "symbol", "Changed symbol could not be resolved in the graph")
    ]
    grouped = group_nodes(graph)
    assert grouped.tests == []
    assert any(n.service is None for n in grouped.potential)
