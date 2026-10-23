import re

from impact_agent.render import blocks, rollup

BLOCK_HEADER_RE = re.compile(r"^Impact Analysis \(Change \d+\):$")
ROLLUP_HEADING_RE = re.compile(rf"^(\d+\. )?{re.escape(rollup.HEADING_TITLE)}$")

WARNING_LOOKALIKE_BLOCK = (
    "Line {line}: text that looks like an impact block was left in place because it does not "
    "match the generated format."
)
WARNING_LOOKALIKE_ROLLUP = (
    "Line {line}: text that looks like an impact roll-up was left in place because it does not "
    "match the generated format."
)

# Part labels of a per-change block, in order. "Risk:" and "Summary:" carry text on the same line.
_BLOCK_PARTS = (
    blocks.LABEL_RISK + " ",
    blocks.LABEL_SUMMARY + " ",
    blocks.LABEL_DIRECT,
    blocks.LABEL_POTENTIAL,
    blocks.LABEL_TESTS,
    blocks.LABEL_WARNINGS,
)
_BULLET_PARTS = frozenset(_BLOCK_PARTS[2:])
_ROLLUP_LABELS = (
    rollup.LABEL_OVERALL + " ",
    rollup.LABEL_SUMMARY + " ",
    rollup.LABEL_SOURCE + " ",
    rollup.LABEL_BY_CHANGE,
    rollup.LABEL_TESTS,
    rollup.LABEL_CLAIMS,
    rollup.LABEL_WARNINGS,
)


def _clean(line: str) -> str:
    """The line without a CRLF carriage return; used for matching only."""
    return line[:-1] if line.endswith("\r") else line


def _is_continuation(line: str) -> bool:
    return line.startswith(blocks.CONTINUATION_INDENT)


def _is_bullet(line: str) -> bool:
    return line.startswith("- ")


def _block_end(lines: list[str], start: int) -> int | None:
    """Index after the generated block starting at `start`, or None if it is not exact."""
    index = start + 1
    for part in _BLOCK_PARTS:
        if index >= len(lines) or not _clean(lines[index]).startswith(part):
            return None
        index += 1
        while index < len(lines) and _is_continuation(_clean(lines[index])):
            index += 1
        if part in _BULLET_PARTS:
            first_bullet = index
            while index < len(lines) and (
                _is_bullet(_clean(lines[index])) or _is_continuation(_clean(lines[index]))
            ):
                index += 1
            if index == first_bullet:
                return None
    return index


def _is_generated_rollup_line(line: str) -> bool:
    return (
        line == ""
        or _is_bullet(line)
        or _is_continuation(line)
        or any(line.startswith(label) for label in _ROLLUP_LABELS)
    )


def _is_rollup_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    heading = _clean(lines[index])
    return bool(ROLLUP_HEADING_RE.match(heading)) and _clean(lines[index + 1]) == "=" * len(heading)


def _rollup_is_generated(lines: list[str], start: int) -> bool:
    return all(_is_generated_rollup_line(_clean(line)) for line in lines[start + 2 :])


def strip_with_warnings(text: str) -> tuple[str, list[str]]:
    lines = text.split("\n")
    kept: list[str] = []
    warnings: list[str] = []
    removed = False
    index = 0
    while index < len(lines):
        line = _clean(lines[index])
        if BLOCK_HEADER_RE.match(line):
            end = _block_end(lines, index)
            if end is None:
                warnings.append(WARNING_LOOKALIKE_BLOCK.format(line=index + 1))
            else:
                removed = True
                index = end
                continue
        elif _is_rollup_start(lines, index):
            if _rollup_is_generated(lines, index):
                if kept and _clean(kept[-1]) == "":
                    kept.pop()  # the one blank line the renderer put before the roll-up
                removed = True
                break
            warnings.append(WARNING_LOOKALIKE_ROLLUP.format(line=index + 1))
        kept.append(lines[index])
        index += 1
    else:
        # No roll-up cut the text short: keep the original ending exactly.
        return ("\n".join(kept) if removed else text), warnings

    # The roll-up (or its tail) was removed, so the last kept line is terminated again.
    if not kept:
        return "", warnings
    return "\n".join(kept) + "\n", warnings


def strip_impact_sections(text: str) -> str:
    """Remove previously generated impact blocks and roll-up, and nothing else."""
    return strip_with_warnings(text)[0]
