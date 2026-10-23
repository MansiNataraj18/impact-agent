from collections.abc import Sequence

from impact_agent.models.impact import (
    ClaimFinding,
    ExplanationStatus,
    GraphSource,
    ImpactExplanation,
    TddImpactResult,
)
from impact_agent.models.parsed_tdd import ParsedTDD
from impact_agent.render.blocks import bullets, risk_text, wrap

HEADING_TITLE = "IMPACT ANALYSIS"
OVERALL_NOT_APPLICABLE = "Not applicable (no change was analysed)"
SOURCE_TEXT = {
    GraphSource.FIXTURE: "dummy fixture (not a real code graph)",
    GraphSource.GRAPH: "code graph",
}
SOURCE_NONE = "none (no graph data used)"
FINDING_TEXT = {ClaimFinding.CONSISTENT: "Consistent", ClaimFinding.NEEDS_REVIEW: "Needs review"}
UNKNOWN = "unknown"

LABEL_OVERALL = "Overall Risk:"
LABEL_SUMMARY = "Summary:"
LABEL_SOURCE = "Graph source:"
LABEL_BY_CHANGE = "Impact by Change:"
LABEL_TESTS = "Tests to Run:"
LABEL_CLAIMS = "TDD Claims vs Graph:"
LABEL_WARNINGS = "Warnings and Unresolved Items:"


def heading_for(last_section_number: int | None) -> str:
    if last_section_number is None:
        return HEADING_TITLE
    return f"{last_section_number + 1}. {HEADING_TITLE}"


def _dedupe(texts: Sequence[str]) -> list[str]:
    seen: list[str] = []
    for text in texts:
        if text not in seen:
            seen.append(text)
    return seen


def render_rollup(
    parsed: ParsedTDD, result: TddImpactResult, extra_warnings: Sequence[str] = ()
) -> list[str]:
    """Roll-up section lines (blank lines between sections, no trailing blank line)."""
    by_number = {c.number: c for c in parsed.changes}
    analysed = [c for c in result.changes if c.status is ExplanationStatus.EXPLAINED]

    heading = heading_for(parsed.last_section_number)
    lines = [heading, "=" * len(heading)]
    overall = result.overall_risk.value.capitalize() if result.overall_risk else None
    lines += wrap(f"{LABEL_OVERALL} {overall or OVERALL_NOT_APPLICABLE}")
    lines += wrap(f"{LABEL_SUMMARY} {result.summary}")
    source = SOURCE_TEXT[result.graph_source] if analysed else SOURCE_NONE
    lines += wrap(f"{LABEL_SOURCE} {source}")

    lines += ["", LABEL_BY_CHANGE]
    lines += bullets([_change_line(c, by_number) for c in result.changes])

    planned = [
        f"Planned ({'existing' if t.existing else 'to add'}): {t.description}"
        for t in parsed.planned_tests
    ]
    lines += ["", LABEL_TESTS]
    lines += bullets(_dedupe([*result.tests_to_run, *planned]))

    lines += ["", LABEL_CLAIMS]
    lines += bullets(
        [
            f"{c.service} (TDD: {c.tdd_claim}): {FINDING_TEXT[c.finding]}. {c.note}"
            for c in result.claims_vs_graph
        ]
    )

    warnings = [f"Change {c.change_number}: {w}" for c in result.changes for w in c.warnings]
    warnings += [*result.warnings, *extra_warnings]
    lines += ["", LABEL_WARNINGS]
    lines += bullets(_dedupe(warnings))
    return lines


def _change_line(explanation: ImpactExplanation, by_number: dict) -> str:
    change = by_number.get(explanation.change_number)
    action = change.action.value if change and change.action else UNKNOWN
    symbol = (change.symbol if change else None) or UNKNOWN
    return f"Change {explanation.change_number} ({action}) {symbol}: {risk_text(explanation)}"
