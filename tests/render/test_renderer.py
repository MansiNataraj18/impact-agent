import json

from impact_agent.core.analyzer import analyze_tdd
from impact_agent.core.llm import FakeLLM
from impact_agent.models.impact import ImpactGraph, ImpactNode
from impact_agent.models.parsed_tdd import ParsedChange, ParsedTDD, PlannedTest
from impact_agent.render.blocks import WRAP_WIDTH
from impact_agent.render.renderer import render_tdd


def node(id, kind="method", depth=1, service="ui", location="view.tsx", name=None):
    return ImpactNode(
        id=id, kind=kind, name=name or id, service=service, location=location, depth=depth,
        relation="calls",
    )  # fmt: skip


MODIFY_GRAPH = ImpactGraph(
    changed="ui::view.tsx::blur",
    source="fixture",
    nodes=[
        node("d", name="Section"),
        node("p", depth=2, service="accounts-service", location=None, name="Persist"),
        node("t", kind="test", depth=2, name="blur test", location="v.test.tsx"),
    ],
)
REPLY = json.dumps(
    {
        "summary": "Small change.",
        "risk_level": "medium",
        "reasons": {"d": "renders it", "p": "stores it", "t": "covers it"},
    }
)
TEXT = "\n".join(
    [
        "Title",
        "Change 1: blur (modify)",
        "Done when:",
        "Change 2: view.test (create)",
        "Done when:",
        "Change 3: other (reference)",
        "Done when:",
        "End",
    ]
)


def parsed(**kwargs):
    base = dict(
        changes=[
            ParsedChange(
                number=1, service="ui", file="view.tsx", symbol="blur", action="modify",
                insert_before_line=3,
            ),
            ParsedChange(
                number=2, service="ui", file="view.test.tsx", symbol="view.test",
                action="create", insert_before_line=5,
            ),
            ParsedChange(
                number=3, service="ui", file="o.tsx", symbol="other", action="reference",
                insert_before_line=7,
            ),
        ],
        no_change_services=["accounts-service", "pdf-service"],
        last_section_number=14,
    )  # fmt: skip
    return ParsedTDD(**{**base, **kwargs})


def run(text=TEXT, p=None, graphs=None):
    p = p or parsed()
    result = analyze_tdd(p, {1: MODIFY_GRAPH} if graphs is None else graphs, FakeLLM(REPLY))
    return render_tdd(text, p, result)


MODIFY_BLOCK = """\
Impact Analysis (Change 1):
Risk: Medium
Summary: Small change.
Direct Impact:
- ui::Section (view.tsx): renders it
Potential Impact:
- accounts-service::Persist (depth 2): stores it
Tests to Run:
- ui::blur test (v.test.tsx): covers it
Warnings and Unresolved:
- 1 affected item(s) have no location in the graph.
"""
CREATE_BLOCK = """\
Impact Analysis (Change 2):
Risk: Not applicable (new file, not in the dependency graph)
Summary: New files have no existing callers or dependents, so nothing in the graph is affected.
Direct Impact:
- None.
Potential Impact:
- None.
Tests to Run:
- None.
Warnings and Unresolved:
- None.
"""
REFERENCE_BLOCK = """\
Impact Analysis (Change 3):
Risk: None (read only, no change proposed)
Summary: No code changes are proposed here, so no impact is expected.
Direct Impact:
- None.
Potential Impact:
- None.
Tests to Run:
- None.
Warnings and Unresolved:
- None.
"""


def test_golden_blocks_in_place():
    out = run()
    lines = out.split("\n")
    assert "".join(MODIFY_BLOCK) in out
    assert out.index("Done when:\n" + MODIFY_BLOCK + "Change 2:") >= 0
    assert out.index("Done when:\n" + CREATE_BLOCK + "Change 3:") >= 0
    assert out.index("Done when:\n" + REFERENCE_BLOCK + "End\n") >= 0
    assert lines[0] == "Title"


def test_additions_only_and_rollup_placement():
    out = run()
    assert out.startswith("Title\nChange 1: blur (modify)\nDone when:\nImpact Analysis (Change 1):")
    assert "End\n\n15. IMPACT ANALYSIS\n===================\n" in out
    assert out.endswith("\n")
    assert not out.endswith("\n\n")
    assert out.rindex("Impact Analysis (Change") < out.index("15. IMPACT ANALYSIS")


def test_wrapping_and_two_space_continuation():
    long_reason = "word " * 60
    reply = json.dumps(
        {"summary": long_reason, "risk_level": "low", "reasons": {"d": long_reason.strip()}}
    )
    p = parsed()
    result = analyze_tdd(p, {1: MODIFY_GRAPH}, FakeLLM(reply))
    out = render_tdd(TEXT, p, result)
    generated = out.split("\n")[3:30]
    assert all(len(line) <= WRAP_WIDTH for line in generated)
    summary_at = generated.index(next(x for x in generated if x.startswith("Summary:")))
    assert generated[summary_at + 1].startswith("  word")
    bullet_at = generated.index(next(x for x in generated if x.startswith("- ui::Section")))
    assert generated[bullet_at + 1].startswith("  ")


def test_rollup_content():
    out = run(p=parsed(planned_tests=[
        PlannedTest(kind="unit", description="new test", existing=False),
        PlannedTest(kind="unit", description="old test", existing=True),
    ]))  # fmt: skip
    roll = out[out.index("15. IMPACT ANALYSIS") :].replace("\n  ", " ")  # undo wrapping
    assert "Overall Risk: Medium\n" in roll
    assert "Graph source: dummy fixture (not a real code graph)\n" in roll
    assert "- Change 1 (modify) blur: Medium\n" in roll
    assert "- Change 2 (create) view.test: Not applicable (new file," in roll
    assert "- Change 3 (reference) other: None (read only, no change proposed)\n" in roll
    planned = (
        "- blur test (v.test.tsx)\n- Planned (to add): new test\n- Planned (existing): old test\n"
    )
    assert planned in roll
    assert (
        "- accounts-service (TDD: no change): Needs review. "
        "The graph lists 1 affected item(s) in this service.\n"
    ) in roll
    assert "- pdf-service (TDD: no change): Consistent. No affected items" in roll
    assert "- Change 1: 1 affected item(s) have no location in the graph.\n" in roll


def test_rollup_number_and_none_case():
    out = run(p=parsed(last_section_number=None))
    assert "\n\nIMPACT ANALYSIS\n===============\n" in out
    assert "- The section number could not be determined.\n" in out
    out = run(p=parsed(last_section_number=9))
    assert "\n10. IMPACT ANALYSIS\n===================\n" in out


def test_nothing_analysed_rollup():
    out = run(graphs={})
    assert "Overall Risk: Not applicable (no change was analysed)\n" in out
    assert "Graph source: none (no graph data used)\n" in out
    assert "- Change 1: No graph was supplied for this change.\n" in out


def test_fixture_labelled():
    assert "Graph source: dummy fixture (not a real code graph)" in run()


def test_missing_insert_position_skips_block_with_warning():
    p = parsed()
    p.changes[1].insert_before_line = None
    out = run(p=p)
    assert "Impact Analysis (Change 2):" not in out
    assert "Impact Analysis (Change 1):" in out
    assert "- Impact block for Change 2 could not be placed: insertion position missing.\n" in out
    assert "- Change 2 (create) view.test:" in out  # still in the roll-up


def test_out_of_range_position_skips_block():
    p = parsed()
    p.changes[0].insert_before_line = 99
    out = run(p=p)
    assert "Impact Analysis (Change 1):" not in out
    assert "insertion position outside the text" in out


def test_multiple_blocks_same_position_keep_change_order():
    p = parsed()
    for c in p.changes:
        c.insert_before_line = 3
    out = run(p=p)
    assert out.index("(Change 1):") < out.index("(Change 2):") < out.index("(Change 3):")
    assert out.index("(Change 3):") < out.index("Change 2: view.test (create)")


def test_text_without_trailing_newline_gains_one():
    out = run(text="a\nb", p=parsed(changes=[]))
    assert out.startswith("a\nb\n\n15. IMPACT ANALYSIS")


def test_block_at_end_of_unterminated_text():
    p = parsed(changes=[ParsedChange(number=1, action="create", insert_before_line=2)])
    out = render_tdd("a\nb", p, analyze_tdd(p, {}, FakeLLM("")))
    assert out.startswith("a\nb\nImpact Analysis (Change 1):\n")
    assert "- None.\n\n15. IMPACT ANALYSIS" in out


def test_crlf_input_gets_crlf_generated_lines():
    text = TEXT.replace("\n", "\r\n") + "\r\n"
    out = run(text=text)
    assert "\r\n" in out
    assert out.count("\n") == out.count("\r\n")
    assert "Impact Analysis (Change 1):\r\n" in out


def test_input_not_normalised():
    text = "Title\f\nChange 1: x  \n"
    p = parsed(changes=[ParsedChange(number=1, action="create", insert_before_line=2)])
    out = render_tdd(text, p, analyze_tdd(p, {}, FakeLLM("")))
    assert out.startswith("Title\f\nChange 1: x  \nImpact Analysis (Change 1):\n")
