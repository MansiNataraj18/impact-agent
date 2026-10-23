import json

import pytest

from impact_agent.core.grouping import group_nodes
from impact_agent.core.llm import SCENARIOS, FakeLLM
from impact_agent.core.validation import (
    FALLBACK_SUMMARY,
    explain_nodes,
)
from impact_agent.models.impact import ImpactGraph, ImpactNode, RiskLevel


def node(id, kind="method", depth=1, relation="calls"):
    return ImpactNode(
        id=id, kind=kind, name=id, service="s", location="a.py", depth=depth, relation=relation
    )


def grouped(*nodes):
    return group_nodes(ImpactGraph(changed="c", nodes=list(nodes), source="fixture"))


G = grouped(node("d1"), node("p1", depth=2), node("t1", kind="test"))
IDS = ["d1", "p1", "t1"]
INVALID_WARNING = "LLM output was invalid; explanations are unavailable."


def run(llm, g=G):
    return explain_nodes(llm, "summary", "loc", g)


def test_valid_reply():
    out = run(FakeLLM.for_scenario("valid", IDS))
    assert out.summary == "Fake summary."
    assert out.risk_level is RiskLevel.MEDIUM
    assert out.reasons == {i: f"Reason for {i}." for i in IDS}
    assert out.warnings == []


@pytest.mark.parametrize("scenario", ["invalid_json", "wrong_shape", "empty"])
def test_malformed_output_falls_back_without_raising(scenario):
    out = run(FakeLLM.for_scenario(scenario, IDS))
    assert out.summary == FALLBACK_SUMMARY
    assert out.risk_level is RiskLevel.MEDIUM
    assert out.warnings == [INVALID_WARNING]
    assert set(out.reasons) == set(IDS)


@pytest.mark.parametrize(
    "reply",
    [
        json.dumps({"risk_level": "low", "reasons": {}}),
        json.dumps({"summary": "s", "risk_level": "low"}),
        json.dumps({"summary": "s", "reasons": ["x"]}),
        json.dumps({"summary": "s", "reasons": {"d1": 5}}),
        json.dumps({"summary": "   ", "reasons": {}}),
        "null",
    ],
)
def test_wrong_shapes_fall_back(reply):
    assert run(FakeLLM(reply)).warnings == [INVALID_WARNING]


def test_failing_client_falls_back():
    def boom(prompt):
        raise RuntimeError("down")

    out = run(FakeLLM(boom))
    assert out.warnings == [INVALID_WARNING]
    assert out.risk_level is RiskLevel.MEDIUM


def test_unknown_node_id_dropped_with_warning():
    out = run(FakeLLM.for_scenario("unknown_node_id", IDS))
    assert "unknown-id" not in out.reasons
    assert out.warnings == ["LLM reason ignored for unknown item: unknown-id"]
    assert out.summary == "Fake summary."


def test_invalid_risk_becomes_medium():
    out = run(FakeLLM.for_scenario("invalid_risk", IDS))
    assert out.risk_level is RiskLevel.MEDIUM
    assert out.warnings == []


def test_missing_risk_becomes_medium_and_valid_risk_kept():
    reply = json.dumps({"summary": "s", "reasons": {}})
    assert run(FakeLLM(reply)).risk_level is RiskLevel.MEDIUM
    reply = json.dumps({"summary": "s", "risk_level": "HIGH", "reasons": {}})
    assert run(FakeLLM(reply)).risk_level is RiskLevel.HIGH


def test_missing_and_blank_reasons_get_placeholder():
    reply = json.dumps({"summary": "s", "risk_level": "low", "reasons": {"d1": "  "}})
    out = run(FakeLLM(reply))
    assert out.reasons["d1"] == "Depends on the changed code (calls)."
    assert out.reasons["p1"] == "Depends on the changed code (calls)."


def test_reasons_collapsed_to_one_line():
    reply = json.dumps({"summary": "a\nb", "risk_level": "low", "reasons": {"d1": "x\n  y"}})
    out = run(FakeLLM(reply))
    assert out.summary == "a b"
    assert out.reasons["d1"] == "x y"


def test_extra_item_reply_changes_nothing():
    plain = run(FakeLLM.for_scenario("valid", IDS))
    extra = run(FakeLLM.for_scenario("extra_item", IDS))
    assert set(extra.reasons) == set(plain.reasons)
    assert extra.warnings == ["LLM reason ignored for unknown item: extra-item"]
    assert (extra.summary, extra.risk_level) == (plain.summary, plain.risk_level)


def test_empty_graph_makes_no_llm_call():
    llm = FakeLLM.for_scenario("valid", [])
    out = run(llm, grouped())
    assert llm.calls == 0
    assert out.summary == "No callers, dependents or tests were found for the changed code."
    assert out.risk_level is RiskLevel.LOW
    assert out.reasons == {}


def test_one_call_with_prompt_recorded():
    llm = FakeLLM.for_scenario("valid", IDS)
    run(llm)
    assert llm.calls == 1
    assert all(i in llm.prompts[0] for i in IDS)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_no_scenario_raises(scenario):
    run(FakeLLM.for_scenario(scenario, IDS))
