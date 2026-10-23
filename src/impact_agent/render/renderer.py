from impact_agent.models.impact import TddImpactResult
from impact_agent.models.parsed_tdd import ParsedTDD
from impact_agent.render.blocks import render_block
from impact_agent.render.rollup import render_rollup

WARNING_NOT_PLACED = "Impact block for Change {n} could not be placed: insertion position missing."
WARNING_OUT_OF_RANGE = (
    "Impact block for Change {n} could not be placed: insertion position outside the text."
)


def render_tdd(original_text: str, parsed: ParsedTDD, result: TddImpactResult) -> str:
    """Return the original text with impact blocks and the roll-up added.

    Uses only `insert_before_line` (an index into `original_text.split("\\n")`); the text
    is never parsed. Generated lines copy the CRLF/LF style of the input.
    """
    crlf = "\r\n" in original_text
    suffix, eol = ("\r", "\r\n") if crlf else ("", "\n")
    explanations = {c.change_number: c for c in result.changes}
    lines = original_text.split("\n")

    warnings: list[str] = []
    placements: list[tuple[int, int]] = []
    for change in parsed.changes:
        position = change.insert_before_line
        if position is None:
            warnings.append(WARNING_NOT_PLACED.format(n=change.number))
        elif not 0 <= position <= len(lines):
            warnings.append(WARNING_OUT_OF_RANGE.format(n=change.number))
        else:
            placements.append((position, change.number))

    # Bottom-up so earlier indexes stay valid; for equal positions the lower number ends first.
    for position, number in sorted(placements, reverse=True):
        block = [line + suffix for line in render_block(explanations[number])]
        if position == len(lines):
            block.append("")  # the last input line gains its terminating newline
        lines[position:position] = block

    out = "\n".join(lines)
    if not out.endswith("\n"):
        out += eol
    rollup = render_rollup(parsed, result, warnings)
    return out + eol + eol.join(rollup) + eol
