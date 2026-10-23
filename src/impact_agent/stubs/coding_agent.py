"""DUMMY stand-in for the downstream coding agent. It only reads the enriched TDD text."""

import re

from impact_agent.render import blocks, rollup
from impact_agent.render.strip import ROLLUP_HEADING_RE

BLOCK_HEADER_RE = re.compile(r"^Impact Analysis \(Change \d+\):$")


def _lines(tdd_text: str) -> list[str]:
    return [line.rstrip("\r") for line in tdd_text.split("\n")]


def _rollup_start(lines: list[str]) -> int | None:
    for index in range(len(lines) - 1):
        heading = lines[index]
        if ROLLUP_HEADING_RE.match(heading) and lines[index + 1] == "=" * len(heading):
            return index
    return None


def _rollup_tests(lines: list[str], start: int) -> list[str]:
    tests: list[str] = []
    in_tests = False
    for line in lines[start:]:
        if line == rollup.LABEL_TESTS:
            in_tests = True
        elif in_tests and line.startswith("- "):
            tests.append(line[2:])
        elif in_tests and line.startswith(blocks.CONTINUATION_INDENT) and tests:
            tests[-1] += " " + line.strip()
        elif in_tests:
            break
    return tests


def receive(tdd_text: str) -> str:
    """Summarise an enriched TDD: block count, roll-up heading, overall risk, tests to run."""
    lines = _lines(tdd_text)
    block_count = sum(1 for line in lines if BLOCK_HEADER_RE.match(line))
    start = _rollup_start(lines)
    out = [f"Coding agent received a TDD with {block_count} impact block(s)."]
    if start is None:
        out.append("No impact roll-up found.")
        return "\n".join(out)
    out.append(f"Roll-up: {lines[start]}")
    risk = next((x for x in lines[start:] if x.startswith(rollup.LABEL_OVERALL)), None)
    out.append(risk or f"{rollup.LABEL_OVERALL} not found")
    tests = _rollup_tests(lines, start)
    out.append("Tests to run:")
    out += [f"- {test}" for test in tests] or ["- None."]
    return "\n".join(out)
