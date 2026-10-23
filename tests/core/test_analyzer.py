import json

from impact_agent.core.analyzer import analyze_tdd, highest_risk
from impact_agent.core.llm import FakeLLM
from impact_agent.models.common import UnresolvedItem
from impact_agent.models.impact import (
    ClaimFinding,
    ExplanationStatus,
    GraphSource,
    ImpactGraph,
    ImpactNode,
    RiskLevel,
)
from impact_agent.models.parsed_tdd import ParsedChange, ParsedTDD


def node(id, kind="method", depth=1, service="ui", location="a.tsx", name=None):
    return ImpactNode(
        id=id, kind=kind, name=name or id, service=service, location=location, depth=depth,
        relation="calls",
    )  # fmt: skip


def graph(*nodes, source="fixture", changed="ui::view.tsx::blur"):
    return ImpactGraph(changed=changed, nodes=list(nodes), source=source)


def change(number, action, service="ui", symbol="blur"):
    return ParsedChange(
        number=number, service=service, file="view.tsx", symbol=symbol, action=action,
        summary=f"summary {number}",
    )  # fmt: skip


def reply(risk, ids):
    return json.dumps(
        {"summary": f"{risk} summary", "risk_level": risk, "reasons": {i: f"why {i}" for i in ids}}
    )


STANDARD = ParsedTDD(
    changes=[
        change(1, "modify"),
        change(2, "create"),
        change(3, "reference"),
        change(4, "reference", service="candidate-service", symbol="validateEmails"),
    ],
    no_change_services=["accounts-service", "pdf-service"],
    last_section_number=14,
)
G1 = graph(
    node("d", depth=1, name="Direct"),
    node("p", depth=2, service="accounts-service", name="Persist"),
    node("t", kind="test", depth=3, name="blur test", location="v.test.tsx"),
)


def test_modify_create_and_references():
    llm = FakeLLM(reply("high", ["d", "p", "t"]))
    result = analyze_tdd(STANDARD, {1: G1}, llm)
    assert [c.change_number for c in result.changes] == [1, 2, 3, 4]
    first, create, ref1, ref2 = result.changes
    assert first.status is ExplanationStatus.EXPLAINED
    assert first.risk_level is RiskLevel.HIGH
    assert [i.node_id for i in first.directly_affected] == ["d"]
    assert [i.node_id for i in first.potentially_affected] == ["p"]
    assert [i.node_id for i in first.tests_to_run] == ["t"]
    assert first.directly_affected[0].reason == "why d"
    assert first.changed_location == "ui::view.tsx::blur"
    assert create.status is ExplanationStatus.NOT_APPLICABLE
    assert create.reason == "Not applicable (new file, not in the dependency graph)"
    assert create.risk_level is None
    for r in (ref1, ref2):
        assert r.status is ExplanationStatus.NOT_APPLICABLE
        assert r.reason == "None (read only, no change proposed)"
    assert llm.calls == 1
    assert result.overall_risk is RiskLevel.HIGH
    assert result.graph_source is GraphSource.FIXTURE
    assert result.tests_to_run == ["blur test (v.test.tsx)"]
    assert result.summary == (
        "1 change(s) analysed; overall risk high; 1 directly and 1 potentially affected "
        "item(s); 1 test(s) to run."
    )
    assert result.warnings == []


def test_multi_modify_highest_risk_and_deduplicated_tests():
    parsed = ParsedTDD(changes=[change(1, "modify"), change(2, "modify")], last_section_number=3)
    shared = node("t", kind="test", name="shared test", location="s.test.tsx")
    g1 = graph(node("a"), shared)
    g2 = graph(node("b"), shared, node("u", kind="test", name="own test", location=None))
    llm = FakeLLM(
        [reply("low", ["a", "t"]), reply("high", ["b", "t", "u"])]
    )  # replies are consumed in change order
    result = analyze_tdd(parsed, {1: g1, 2: g2}, llm)
    assert [c.risk_level for c in result.changes] == [RiskLevel.LOW, RiskLevel.HIGH]
    assert result.overall_risk is RiskLevel.HIGH
    assert result.tests_to_run == ["shared test (s.test.tsx)", "own test"]
    assert llm.calls == 2


def test_graph_source_fixture_if_any_fixture_else_graph():
    parsed = ParsedTDD(changes=[change(1, "modify"), change(2, "modify")], last_section_number=1)
    llm = FakeLLM(lambda prompt: reply("low", []))
    mixed = analyze_tdd(
        parsed, {1: graph(node("t", "test"), source="graph"), 2: graph(node("u", "test"))}, llm
    )
    assert mixed.graph_source is GraphSource.FIXTURE
    real = analyze_tdd(
        parsed,
        {1: graph(node("t", "test"), source="graph"), 2: graph(node("u", "test"), source="graph")},
        llm,
    )
    assert real.graph_source is GraphSource.GRAPH


def test_cross_service_claims():
    result = analyze_tdd(STANDARD, {1: G1}, FakeLLM(reply("low", ["d", "p", "t"])))
    claims = {c.service: c for c in result.claims_vs_graph}
    assert [c.service for c in result.claims_vs_graph] == ["accounts-service", "pdf-service"]
    assert claims["accounts-service"].finding is ClaimFinding.NEEDS_REVIEW
    assert claims["accounts-service"].note == "The graph lists 1 affected item(s) in this service."
    assert claims["accounts-service"].tdd_claim == "no change"
    assert claims["pdf-service"].finding is ClaimFinding.CONSISTENT
    assert (
        claims["pdf-service"].note == "No affected items were found in this service in the graph."
    )


def test_no_change_services_absent_gives_no_claims():
    parsed = ParsedTDD(changes=[change(1, "modify")], last_section_number=1)
    result = analyze_tdd(parsed, {1: G1}, FakeLLM(reply("low", [])))
    assert result.claims_vs_graph == []


def test_no_tests_in_graph_warns():
    parsed = ParsedTDD(changes=[change(1, "modify")], last_section_number=1)
    result = analyze_tdd(parsed, {1: graph(node("d"))}, FakeLLM(reply("low", ["d"])))
    assert result.changes[0].warnings == [
        "No tests cover this change; add the regression test before merging."
    ]
    assert result.tests_to_run == []


def test_empty_graph_low_risk_and_no_llm_call():
    parsed = ParsedTDD(changes=[change(1, "modify")], last_section_number=1)
    llm = FakeLLM("never used")
    result = analyze_tdd(parsed, {1: graph()}, llm)
    only = result.changes[0]
    assert llm.calls == 0
    assert only.risk_level is RiskLevel.LOW
    assert only.summary == "No callers, dependents or tests were found for the changed code."
    assert "No callers, dependents or tests were found for the changed code." in only.warnings


def test_modify_without_graph_is_skipped():
    parsed = ParsedTDD(changes=[change(1, "modify")], last_section_number=1)
    result = analyze_tdd(parsed, {}, FakeLLM(""))
    only = result.changes[0]
    assert only.status is ExplanationStatus.SKIPPED
    assert only.reason == "No graph was supplied for this change."
    assert only.warnings == ["No graph was supplied for this change."]
    assert only.risk_level is None
    assert result.overall_risk is None
    assert result.summary == "No change required graph analysis."


def test_action_none_is_skipped():
    parsed = ParsedTDD(changes=[ParsedChange(number=1)], last_section_number=1)
    only = analyze_tdd(parsed, {}, FakeLLM("")).changes[0]
    assert only.status is ExplanationStatus.SKIPPED
    assert only.reason == "Change action could not be determined."
    assert only.changed_location == "unknown::unknown::unknown"


def test_parser_and_tdd_level_unresolved_warnings():
    parsed = ParsedTDD(
        changes=[change(1, "modify"), change(2, "create")],
        unresolved=[
            UnresolvedItem(scope="change", change_number=2, field="file", reason="no path"),
            UnresolvedItem(scope="tdd", reason="no title"),
            UnresolvedItem(scope="section", reason="odd heading"),
        ],
        last_section_number=None,
    )
    result = analyze_tdd(parsed, {1: graph(node("t", "test"))}, FakeLLM(reply("low", ["t"])))
    assert result.changes[1].warnings == ["Unresolved (file): no path"]
    assert result.changes[0].warnings == []
    assert result.warnings == [
        "Unresolved: no title",
        "Unresolved: odd heading",
        "The section number could not be determined.",
    ]


def test_llm_failure_falls_back_but_keeps_lists():
    parsed = ParsedTDD(changes=[change(1, "modify")], last_section_number=1)
    result = analyze_tdd(parsed, {1: G1}, FakeLLM("not json"))
    only = result.changes[0]
    assert only.risk_level is RiskLevel.MEDIUM
    assert "LLM output was invalid; explanations are unavailable." in only.warnings
    assert [i.node_id for i in only.directly_affected] == ["d"]


def test_highest_risk():
    assert highest_risk([]) is None
    assert highest_risk([None]) is None
    assert highest_risk([RiskLevel.LOW, None, RiskLevel.MEDIUM]) is RiskLevel.MEDIUM
