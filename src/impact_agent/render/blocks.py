import textwrap

from impact_agent.models.impact import AffectedItem, ExplanationStatus, ImpactExplanation

WRAP_WIDTH = 96
CONTINUATION_INDENT = "  "  # lets strip_impact_sections recognise where a block ends

BLOCK_HEADER = "Impact Analysis (Change {n}):"
LABEL_RISK = "Risk:"
LABEL_SUMMARY = "Summary:"
LABEL_DIRECT = "Direct Impact:"
LABEL_POTENTIAL = "Potential Impact:"
LABEL_TESTS = "Tests to Run:"
LABEL_WARNINGS = "Warnings and Unresolved:"
NONE_ITEM = "None."
NOT_ASSESSED = "Not assessed"


def wrap(text: str, first: str = "", rest: str = CONTINUATION_INDENT) -> list[str]:
    """Wrap one logical line at WRAP_WIDTH; continuation lines are indented."""
    lines = textwrap.wrap(
        " ".join(text.split()),
        width=WRAP_WIDTH,
        initial_indent=first,
        subsequent_indent=rest,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return lines or [first.rstrip()]


def bullets(texts: list[str]) -> list[str]:
    if not texts:
        return [f"- {NONE_ITEM}"]
    return [line for text in texts for line in wrap(text, first="- ")]


def risk_text(explanation: ImpactExplanation) -> str:
    if explanation.status is ExplanationStatus.EXPLAINED and explanation.risk_level is not None:
        return explanation.risk_level.value.capitalize()
    if explanation.status is ExplanationStatus.NOT_APPLICABLE and explanation.reason:
        return explanation.reason
    if explanation.reason:
        return f"{NOT_ASSESSED} ({explanation.reason})"
    return NOT_ASSESSED


def item_text(item: AffectedItem, with_depth: bool = False) -> str:
    label = f"{item.service}::{item.name}" if item.service else item.name
    if item.location:
        label += f" ({item.location})"
    if with_depth:
        label += f" (depth {item.depth})"
    return f"{label}: {item.reason}"


def render_block(explanation: ImpactExplanation) -> list[str]:
    """The six-part block for one change, in contract order, with no blank lines."""
    lines = [BLOCK_HEADER.format(n=explanation.change_number)]
    lines += wrap(f"{LABEL_RISK} {risk_text(explanation)}")
    lines += wrap(f"{LABEL_SUMMARY} {explanation.summary}")
    lines.append(LABEL_DIRECT)
    lines += bullets([item_text(i) for i in explanation.directly_affected])
    lines.append(LABEL_POTENTIAL)
    lines += bullets([item_text(i, with_depth=True) for i in explanation.potentially_affected])
    lines.append(LABEL_TESTS)
    lines += bullets([item_text(i) for i in explanation.tests_to_run])
    lines.append(LABEL_WARNINGS)
    lines += bullets(explanation.warnings)
    return lines
