import json

from impact_agent.core.analyzer import analyze_tdd
from impact_agent.core.llm import FakeLLM
from impact_agent.models.impact import ImpactGraph, ImpactNode
from impact_agent.models.parsed_tdd import ParsedChange, ParsedTDD
from impact_agent.render.renderer import render_tdd
from impact_agent.render.strip import strip_impact_sections, strip_with_warnings

GRAPH = ImpactGraph(
    changed="ui::a.tsx::f",
    source="fixture",
    nodes=[
        ImpactNode(id="d", kind="method", name="D", service="ui", location="a.tsx", depth=1,
                   relation="calls"),
        ImpactNode(id="t", kind="test", name="T", service="ui", location="t.tsx", depth=2,
                   relation="tests"),
    ],
)  # fmt: skip
REPLY = json.dumps(
    {"summary": "word " * 40, "risk_level": "high", "reasons": {"d": "x " * 60, "t": "covers"}}
)


def parsed_for(lines):
    """Changes 1 (modify) and 2 (create) sit before the 'Change 2' and 'End' lines."""
    lines = [line.rstrip("\r") for line in lines]
    return ParsedTDD(
        changes=[
            ParsedChange(number=1, service="ui", file="a.tsx", symbol="f", action="modify",
                         insert_before_line=lines.index("Change 2")),
            ParsedChange(number=2, service="ui", file="b.tsx", symbol="g", action="create",
                         insert_before_line=lines.index("End")),
        ],
        no_change_services=["other"],
        last_section_number=9,
    )  # fmt: skip


def render(text):
    parsed = parsed_for(text.split("\n"))
    return render_tdd(text, parsed, analyze_tdd(parsed, {1: GRAPH}, FakeLLM(REPLY)))


def terminated(text):
    """The input with the terminating newline D7 adds, in the input's own line-ending style."""
    if text.endswith("\n"):
        return text
    return text + ("\r\n" if "\r\n" in text else "\n")


BASE = "Title\f\nChange 1\n- own bullet\nChange 2\nmore  \nEnd"
CASES = [BASE, BASE + "\n", BASE.replace("\n", "\r\n"), BASE.replace("\n", "\r\n") + "\r\n"]


def test_additions_only():
    for text in CASES:
        out_lines = [line.rstrip("\r") for line in render(text).split("\n")]
        original = [line.rstrip("\r") for line in text.split("\n")]
        position = 0
        for line in out_lines:
            if position < len(original) and line == original[position]:
                position += 1
        assert position == len(original), text  # every original line survives, in order
        assert strip_impact_sections(render(text)) == terminated(text)


def test_strip_of_render_equals_input_modulo_final_newline():
    for text in CASES:
        assert strip_impact_sections(render(text)) == terminated(text)


def test_render_strip_render_identical():
    for text in CASES:
        first = render(text)
        again = render(strip_impact_sections(first))
        assert again == first


def test_strip_is_noop_without_impact_sections():
    for text in (BASE, BASE + "\n", "", "\n", "a\r\nb", "x\f\n  - weird\n"):
        assert strip_impact_sections(text) == text


def test_input_with_existing_blocks_not_duplicated():
    out = render(BASE)
    twice = render(strip_impact_sections(out))
    assert twice.count("Impact Analysis (Change 1):") == 1
    assert twice.count("IMPACT ANALYSIS") == 1
    assert strip_impact_sections(twice) == terminated(BASE)


def test_form_feed_and_trailing_whitespace_untouched():
    out = render(BASE)
    assert out.startswith("Title\f\n")
    assert "more  \n" in out
    assert strip_impact_sections(out).split("\n")[0] == "Title\f"
    assert "more  \n" in strip_impact_sections(out)


def test_lookalike_block_left_alone_with_warning():
    fake = "Intro\nImpact Analysis (Change 1):\nRisk: High\nSummary: s\nEnd\n"
    out, warnings = strip_with_warnings(fake)
    assert out == fake
    assert len(warnings) == 1 and "Line 2" in warnings[0]
    near = "Impact Analysis (Change 1) :\nRisk: High\n"
    assert strip_impact_sections(near) == near


def test_block_missing_parts_or_bullets_is_left_alone():
    complete = render(BASE)
    block_start = complete.index("Impact Analysis (Change 1):")
    broken = complete[:block_start] + complete[block_start:].replace(
        "Potential Impact:\n- None.\n", "Potential Impact:\n", 1
    )
    stripped = strip_impact_sections(broken)
    assert "Impact Analysis (Change 1):" in stripped


def test_lookalike_rollup_left_alone():
    fake = "Intro\n\n10. IMPACT ANALYSIS\n==========\nOverall Risk: Low\nMy own paragraph.\n"
    fake = fake.replace("==========", "=" * len("10. IMPACT ANALYSIS"))
    out, warnings = strip_with_warnings(fake)
    assert out == fake
    assert len(warnings) == 1
    no_underline = "Intro\n\nIMPACT ANALYSIS\nOverall Risk: Low\n"
    assert strip_impact_sections(no_underline) == no_underline


def test_rollup_removed_with_single_blank_line_only():
    text = "a\n\n\nb\n"
    parsed = ParsedTDD(last_section_number=1)
    out = render_tdd(text, parsed, analyze_tdd(parsed, {}, FakeLLM("")))
    assert strip_impact_sections(out) == text
