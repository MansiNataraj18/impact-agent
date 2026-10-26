from impact_agent.models.impact import GraphSource, ImpactQuery
from impact_agent.providers import neo4j_provider as module
from impact_agent.providers.base import GraphProvider
from impact_agent.providers.neo4j_provider import Neo4jGraphProvider

QUERY = ImpactQuery(
    change_number=1, service="ui", file="view.tsx", symbol="blur", project="p", revision="r"
)


def row(**overrides):
    base = {
        "id": "n1",
        "kind": "function",
        "name": "caller",
        "service": "ui",
        "location": "caller.tsx",
        "depth": 1,
        "relation": "CALLS",
    }
    return {**base, **overrides}


def fake_db(impact_rows, found=True):
    seen = []

    def run(cypher, params):
        seen.append((cypher, dict(params)))
        if cypher == module.FIND_CHANGED_QUERY:
            return [{"id": "c1"}] if found else []
        return impact_rows

    run.seen = seen
    return run


def test_satisfies_graph_provider_protocol():
    provider: GraphProvider = Neo4jGraphProvider(fake_db([]))
    assert provider.get_impact(QUERY).changed == "ui::view.tsx::blur"


def test_normal_rows_become_nodes_and_source_is_graph():
    rows = [row(), row(id="n2", kind="test", name="t", depth=2, relation="TESTS")]
    graph = Neo4jGraphProvider(fake_db(rows)).get_impact(QUERY)
    assert graph.source is GraphSource.GRAPH
    assert [n.id for n in graph.nodes] == ["n1", "n2"]
    assert graph.nodes[0].relation == "calls"
    assert graph.nodes[1].kind.value == "test"
    assert graph.unresolved == []


def test_query_parameters_come_from_the_change():
    db = fake_db([])
    Neo4jGraphProvider(db).get_impact(QUERY)
    assert db.seen[0][1] == {"project": "p", "revision": "r", "file": "view.tsx", "symbol": "blur"}


def test_no_rows_is_empty_graph_without_unresolved():
    graph = Neo4jGraphProvider(fake_db([])).get_impact(QUERY)
    assert graph.nodes == []
    assert graph.unresolved == []


def test_change_not_found_is_flagged_not_silently_empty():
    graph = Neo4jGraphProvider(fake_db([], found=False)).get_impact(QUERY)
    assert graph.nodes == []
    assert [i.reason for i in graph.unresolved] == [module.REASON_CHANGE_NOT_FOUND]


def test_missing_location_stays_none():
    graph = Neo4jGraphProvider(fake_db([row(location=None)])).get_impact(QUERY)
    assert graph.nodes[0].location is None


def test_unknown_kind_is_skipped_and_reported_never_guessed():
    rows = [row(), row(id="n2", kind="widget")]
    graph = Neo4jGraphProvider(fake_db(rows)).get_impact(QUERY)
    assert [n.id for n in graph.nodes] == ["n1"]
    assert len(graph.unresolved) == 1
    assert graph.unresolved[0].change_number == 1


def test_row_missing_a_field_is_skipped_and_reported():
    bad = row()
    del bad["name"]
    graph = Neo4jGraphProvider(fake_db([bad])).get_impact(QUERY)
    assert graph.nodes == []
    assert len(graph.unresolved) == 1


def test_missing_file_or_symbol_does_not_query_the_graph():
    db = fake_db([row()])
    query = ImpactQuery(change_number=2, service="ui", file=None, symbol="blur")
    graph = Neo4jGraphProvider(db).get_impact(query)
    assert db.seen == []
    assert graph.nodes == []
    assert "file" in graph.unresolved[0].reason
