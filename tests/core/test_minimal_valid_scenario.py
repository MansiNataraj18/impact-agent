import json

from impact_agent.core.grouping import group_nodes
from impact_agent.core.llm import SCENARIOS, FakeLLM
from impact_agent.core.validation import explain_nodes
from impact_agent.models.impact import ImpactGraph, ImpactNode, RiskLevel


def test_minimal_valid_reply_shape():
    assert "minimal_valid" in SCENARIOS
    data = json.loads(FakeLLM.for_scenario("minimal_valid").complete("p"))
    assert data == {
        "summary": "Fixture analysis: the change touches the listed items.",
        "risk_level": "medium",
        "reasons": {},
    }


def test_minimal_valid_is_accepted_with_placeholder_reasons():
    node = ImpactNode(id="a", kind="method", name="a", depth=1, relation="calls")
    grouped = group_nodes(ImpactGraph(changed="c", nodes=[node], source="fixture"))
    out = explain_nodes(FakeLLM.for_scenario("minimal_valid"), "s", "c", grouped)
    assert out.summary == "Fixture analysis: the change touches the listed items."
    assert out.risk_level is RiskLevel.MEDIUM
    assert out.reasons == {"a": "Depends on the changed code (calls)."}
    assert out.warnings == []
