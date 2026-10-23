from impact_agent.models.common import UnresolvedItem
from impact_agent.models.parsed_tdd import ParsedTDD
from impact_agent.parser.normalize import collapse, normalise_lines
from impact_agent.parser.sections import (
    SECTION_SUMMARY,
    TITLE_MARKER,
    Section,
    find_glued_headings,
    find_section,
    find_sections,
)

REASON_GLUED_HEADING = "Possible glued section heading"
REASON_NO_SECTIONS = "No numbered sections found"
REASON_PARSER_FAILED = "Parser failed: {error}"


def _parse_title(norm: list[str]) -> tuple[str | None, list[UnresolvedItem]]:
    for index, line in enumerate(norm):
        if line != TITLE_MARKER:
            continue
        for candidate in norm[index + 1 :]:
            if not candidate:
                continue
            if candidate.startswith("Generated:") or set(candidate) == {"#"}:
                break
            return collapse(candidate), []
        break
    return None, [UnresolvedItem(scope="tdd", field="title", reason="Title not found")]


def _parse_summary(
    norm: list[str], sections: list[Section]
) -> tuple[str | None, list[UnresolvedItem]]:
    section = find_section(sections, SECTION_SUMMARY)
    if section is None:
        reason = f"Section '{SECTION_SUMMARY}' not found"
        return None, [UnresolvedItem(scope="section", field="summary", reason=reason)]
    text = collapse(" ".join(norm[section.body_start : section.end]))
    if not text:
        return None, [UnresolvedItem(scope="section", field="summary", reason="Summary is empty")]
    return text, []


def _parse(text: str) -> ParsedTDD:
    _, norm = normalise_lines(text)
    sections = find_sections(norm)

    title, title_unresolved = _parse_title(norm)
    summary, summary_unresolved = _parse_summary(norm, sections)
    unresolved = [*title_unresolved, *summary_unresolved]
    unresolved += [
        UnresolvedItem(scope="section", reason=REASON_GLUED_HEADING, line=index)
        for index in find_glued_headings(norm, sections)
    ]

    changes: list = []
    if not sections and not changes:
        return ParsedTDD(
            title=title,
            unresolved=[UnresolvedItem(scope="tdd", reason=REASON_NO_SECTIONS)],
        )

    return ParsedTDD(
        title=title,
        summary=summary,
        changes=changes,
        last_section_number=sections[-1].number if sections else None,
        unresolved=unresolved,
    )


def parse_tdd(text: str) -> ParsedTDD:
    """Parse TDD text into the contract's ParsedTDD. Never raises."""
    try:
        return _parse(text)
    except Exception as error:  # the parser must never break the pipeline
        reason = REASON_PARSER_FAILED.format(error=type(error).__name__)
        return ParsedTDD(unresolved=[UnresolvedItem(scope="tdd", reason=reason)])
