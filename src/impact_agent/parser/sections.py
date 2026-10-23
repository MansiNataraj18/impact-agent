import re
from dataclasses import dataclass

# "N. TITLE": uppercase title; accepted only when N continues the 1, 2, 3... sequence.
HEADING_RE = re.compile(r"^(\d{1,2})\. ([A-Z][A-Z0-9 ,&/'-]*)$")
# A heading-like tail glued onto other text, e.g. "some text 6. FILES TO CHANGE".
GLUED_HEADING_RE = re.compile(r"\s\d{1,2}\. [A-Z][A-Z0-9 ,&/'-]{2,}$")
UNDERLINE_CHAR = "="

TITLE_MARKER = "TECHNICAL DESIGN DOCUMENT"

SECTION_SUMMARY = "SUMMARY"
SECTION_CHANGES = "SERVICES AND CHANGES"
SECTION_TESTING = "TESTING"


@dataclass(frozen=True)
class Section:
    number: int
    title: str
    line: int  # index of the heading line
    body_start: int  # first line after the heading and its underline
    end: int  # index of the next heading line, or the number of lines


def is_underline(norm_line: str) -> bool:
    return bool(norm_line) and set(norm_line) == {UNDERLINE_CHAR}


def find_sections(norm: list[str]) -> list[Section]:
    """Accepted sections in order; numbers must run 1, 2, 3... (lookalikes are rejected)."""
    found: list[tuple[int, str, int]] = []
    expected = 1
    for index, line in enumerate(norm):
        match = HEADING_RE.match(line)
        if match and int(match.group(1)) == expected:
            found.append((expected, match.group(2), index))
            expected += 1

    sections = []
    for position, (number, title, line) in enumerate(found):
        end = found[position + 1][2] if position + 1 < len(found) else len(norm)
        body_start = line + 1
        if body_start < end and is_underline(norm[body_start]):
            body_start += 1
        sections.append(Section(number, title, line, body_start, end))
    return sections


def find_section(sections: list[Section], title: str) -> Section | None:
    return next((s for s in sections if s.title == title), None)


def find_glued_headings(norm: list[str], sections: list[Section]) -> list[int]:
    """Lines where an unaccepted 'N. TITLE' appears mid-line (nothing is split)."""
    accepted = {s.line for s in sections}
    return [
        index
        for index, line in enumerate(norm)
        if index not in accepted and not HEADING_RE.match(line) and GLUED_HEADING_RE.search(line)
    ]
