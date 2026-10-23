import re

from impact_agent.models.common import UnresolvedItem
from impact_agent.models.parsed_tdd import PlannedTest
from impact_agent.parser.normalize import collapse
from impact_agent.parser.sections import SECTION_TESTING, Section

ENTRY_RE = re.compile(r"^- \[([a-z_]+)\] (.*)$")
EXPECTED_LABEL = "Expected:"
EXISTING_MARKER = "EXISTING"
KNOWN_KINDS = frozenset({"regression", "unit", "edge_case", "integration"})
OTHER_KIND = "other"

REASON_SECTION_MISSING = f"Section '{SECTION_TESTING}' not found"


def missing_section_item() -> UnresolvedItem:
    return UnresolvedItem(scope="section", field="planned_tests", reason=REASON_SECTION_MISSING)


def parse_planned_tests(norm: list[str], section: Section) -> list[PlannedTest]:
    starts = [i for i in range(section.body_start, section.end) if ENTRY_RE.match(norm[i])]
    tests = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else section.end
        kind, rest = ENTRY_RE.match(norm[start]).groups()

        description_lines = [rest.split(": ", 1)[1] if ": " in rest else rest]
        expected_lines: list[str] | None = None
        for line in norm[start + 1 : end]:
            if expected_lines is None and line.startswith(EXPECTED_LABEL):
                expected_lines = [line[len(EXPECTED_LABEL) :]]
            elif expected_lines is not None:
                expected_lines.append(line)
            else:
                description_lines.append(line)

        tests.append(
            PlannedTest(
                kind=kind if kind in KNOWN_KINDS else OTHER_KIND,
                description=collapse(" ".join(description_lines)),
                expected=collapse(" ".join(expected_lines)) or None if expected_lines else None,
                existing=rest.startswith(EXISTING_MARKER),
            )
        )
    return tests
