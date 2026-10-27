from pathlib import Path

from dummy_graph import dummy_run_query

from impact_agent.api.app import default_engine
from impact_agent.api.pipeline import run_pipeline
from impact_agent.api.schemas import ImpactRequest, ResponseStatus
from impact_agent.models.impact import ImpactQuery
from impact_agent.providers.neo4j_provider import (
    REASON_CHANGE_NOT_FOUND,
    Neo4jGraphProvider,
)

DUMMY_TDDS = Path(__file__).resolve().parent.parent / "fixtures" / "dummy_tdds"
provider = Neo4jGraphProvider(dummy_run_query)


def query(file, symbol):
    return ImpactQuery(
        change_number=1,
        service="ui",
        file=file,
        symbol=symbol,
        project="p",
        repository="r",
        revision="v",
    )


def test_returns_only_what_depends_on_the_change():
    graph = provider.get_impact(query("src/profile/form/view.tsx", "handleNameBlur"))
    assert {n.name: n.depth for n in graph.nodes} == {
        "ProfileForm": 1,
        "handleNameBlur blur test": 1,
        "ProfilePage": 2,
        "updateProfile": 3,
    }
    assert "formatReceipt" not in {n.name for n in graph.nodes}
    assert graph.unresolved == []


def test_symbol_not_in_graph_is_unresolved_not_guessed():
    graph = provider.get_impact(query("src/profile/form/view.tsx", "doesNotExist"))
    assert graph.nodes == []
    assert [u.reason for u in graph.unresolved] == [REASON_CHANGE_NOT_FOUND]


def test_dummy_tdd_runs_through_the_neo4j_provider():
    path = DUMMY_TDDS / "01_simple_modify.txt"
    with open(path, encoding="utf-8", newline="") as handle:
        text = handle.read()
    response = run_pipeline(ImpactRequest(tdd_text=text), provider, default_engine())
    assert response.status is ResponseStatus.OK
    assert "ProfileForm" in response.tdd_text
    assert "formatReceipt" not in response.tdd_text.split("IMPACT ANALYSIS")[1]
    again = run_pipeline(ImpactRequest(tdd_text=response.tdd_text), provider, default_engine())
    assert again.tdd_text == response.tdd_text
