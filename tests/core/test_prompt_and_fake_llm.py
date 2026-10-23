import json

import pytest

from impact_agent.core.grouping import group_nodes
from impact_agent.core.llm import SCENARIOS, FakeLLM, LLMClient, scripted_reply
from impact_agent.core.prompt import build_prompt
from impact_agent.models.impact import ImpactGraph, ImpactNode


def node(id, kind="method", depth=1):
    return ImpactNode(
        id=id, kind=kind, name=f"name-{id}", service="svc", location="a.py", depth=depth,
        relation="calls",
    )  # fmt: skip


def grouped(*nodes):
    return group_nodes(ImpactGraph(changed="c", nodes=list(nodes), source="fixture"))


def test_prompt_includes_every_node_id_and_inputs():
    g = grouped(node("d1"), node("p1", depth=2), node("t1", kind="test"))
    prompt = build_prompt("Rejoin with semicolons.", "ui::view.tsx::blur", g)
    for needle in ("d1", "p1", "t1", "Rejoin with semicolons.", "ui::view.tsx::blur"):
        assert needle in prompt


def test_prompt_demands_strict_json_and_forbids_changes():
    prompt = build_prompt(None, "loc", grouped())
    assert "strict JSON" in prompt
    assert "may not add, remove, rename or regroup" in prompt
    for key in ("summary", "risk_level", "reasons"):
        assert key in prompt
    assert "Not provided." in prompt
    assert "- None." in prompt


def test_prompt_contains_nothing_beyond_given_data():
    g = grouped(node("d1"))
    p1 = build_prompt("s", "loc", g)
    assert p1 == build_prompt("s", "loc", g)
    assert "fixture" not in p1  # graph source is not sent


def test_fake_llm_satisfies_protocol_and_records_calls():
    llm = FakeLLM("reply")
    client: LLMClient = llm
    assert client.complete("p1") == "reply"
    assert client.complete("p2") == "reply"
    assert llm.calls == 2
    assert llm.prompts == ["p1", "p2"]


def test_fake_llm_sequence_and_callable():
    seq = FakeLLM(["a", "b"])
    assert [seq.complete("x"), seq.complete("x"), seq.complete("x")] == ["a", "b", "b"]
    assert FakeLLM(lambda prompt: prompt.upper()).complete("hi") == "HI"


def test_scenarios_have_expected_shapes():
    ids = ["a", "b"]
    valid = json.loads(scripted_reply("valid", ids))
    assert set(valid) == {"summary", "risk_level", "reasons"}
    assert set(valid["reasons"]) == set(ids)
    with pytest.raises(json.JSONDecodeError):
        json.loads(scripted_reply("invalid_json", ids))
    assert isinstance(json.loads(scripted_reply("wrong_shape", ids)), list)
    assert "unknown-id" in json.loads(scripted_reply("unknown_node_id", ids))["reasons"]
    assert json.loads(scripted_reply("invalid_risk", ids))["risk_level"] == "critical"
    assert scripted_reply("empty", ids) == ""
    extra = json.loads(scripted_reply("extra_item", ids))
    assert "extra-item" in extra["reasons"]
    assert extra["directly_affected"]


def test_all_scenarios_buildable_and_unknown_rejected():
    for scenario in SCENARIOS:
        assert isinstance(FakeLLM.for_scenario(scenario, ["a"]).complete("p"), str)
    with pytest.raises(ValueError):
        scripted_reply("nope", [])
