import json

import pytest

from impact_agent.core.engine import DefaultImpactEngine, ImpactEngine
from impact_agent.core.llm import FakeLLM
from impact_agent.models.impact import ImpactGraph, ImpactNode
from impact_agent.models.parsed_tdd import ParsedChange, ParsedTDD
from impact_agent.render.strip import strip_impact_sections

TEXT = "Title\nChange 1\nEnd\n"
PARSED = ParsedTDD(
    changes=[ParsedChange(number=1, service="s", file="f", symbol="x", action="modify",
                          insert_before_line=2)],
    last_section_number=3,
)  # fmt: skip
GRAPH = ImpactGraph(
    changed="s::f::x",
    source="fixture",
    nodes=[ImpactNode(id="t", kind="test", name="T", depth=1, relation="tests")],
)
REPLY = json.dumps({"summary": "s", "risk_level": "low", "reasons": {"t": "r"}})


def test_enrich_runs_analyze_then_render():
    engine: ImpactEngine = DefaultImpactEngine(FakeLLM(REPLY))
    out = engine.enrich(TEXT, PARSED, {1: GRAPH})
    assert out.startswith("Title\nChange 1\nImpact Analysis (Change 1):\nRisk: Low\n")
    assert "\nEnd\n\n4. IMPACT ANALYSIS\n" in out
    assert strip_impact_sections(out) == TEXT


def test_enrich_raises_on_unstripped_input():
    engine = DefaultImpactEngine(FakeLLM(REPLY))
    once = engine.enrich(TEXT, PARSED, {1: GRAPH})
    with pytest.raises(ValueError, match="call strip_impact_sections first"):
        engine.enrich(once, PARSED, {1: GRAPH})


def test_rerun_through_strip_is_byte_identical():
    engine = DefaultImpactEngine(FakeLLM(REPLY))
    first = engine.enrich(TEXT, PARSED, {1: GRAPH})
    second = engine.enrich(strip_impact_sections(first), PARSED, {1: GRAPH})
    assert second == first
