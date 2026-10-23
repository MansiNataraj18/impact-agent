from pathlib import Path

import pytest

from impact_agent.parser.normalize import normalise_lines
from impact_agent.parser.sections import find_glued_headings, find_sections
from impact_agent.parser.tdd_parser import parse_tdd

SAMPLE = Path(__file__).resolve().parent.parent / "fixtures" / "tdd" / "sample_input.txt"


def sample_text():
    with open(SAMPLE, encoding="utf-8", newline="") as handle:
        return handle.read()


def headings(text):
    return [(s.number, s.title, s.line) for s in find_sections(normalise_lines(text)[1])]


def test_sample_sections_title_and_summary():
    parsed = parse_tdd(sample_text())
    sections = find_sections(normalise_lines(sample_text())[1])
    assert len(sections) == 14
    assert [s.number for s in sections] == list(range(1, 15))
    assert sections[0].title == "SUMMARY"
    assert sections[4].title == "SERVICES AND CHANGES"
    assert parsed.last_section_number == 14
    assert (
        parsed.title == "Preserve semicolon-separated ATS link CC email addresses in UI and storage"
    )
    assert parsed.summary.startswith("In ATS Portal Service settings, the 'Enable Link to user")
    assert parsed.summary.endswith("saves settings, and reloads the page.")
    assert "\n" not in parsed.summary and "  " not in parsed.summary
    assert parsed.unresolved == []


def test_numbered_list_lookalikes_rejected():
    text = "1. SUMMARY\n==========\nbody\n1. Administrator edits\n2. UI normalizes\n3. SAVE IT\n"
    assert headings(text) == [(1, "SUMMARY", 0)]


def test_out_of_sequence_numbers_rejected():
    text = "1. SUMMARY\nx\n3. SKIPPED AHEAD\ny\n2. REQUIREMENTS\nz\n1. AGAIN\n"
    assert [(n, t) for n, t, _ in headings(text)] == [(1, "SUMMARY"), (2, "REQUIREMENTS")]
    assert headings("2. FIRST\n") == []


def test_form_feed_before_heading():
    text = "1. SUMMARY\nx\n\f2. REQUIREMENTS\n=============\ny\n"
    assert headings(text) == [(1, "SUMMARY", 0), (2, "REQUIREMENTS", 2)]


def test_underline_belongs_to_heading_and_is_not_summary():
    text = (
        "TECHNICAL DESIGN DOCUMENT\nA title\n\n1. SUMMARY\n=======\n\nline one\n  line two\n"
        "2. NEXT\n"
    )
    parsed = parse_tdd(text)
    assert parsed.summary == "line one line two"
    assert parsed.title == "A title"


def test_crlf_input():
    text = sample_text().replace("\n", "\r\n")
    parsed = parse_tdd(text)
    assert parsed.last_section_number == 14
    assert parsed.title.startswith("Preserve semicolon")
    assert parsed.summary.endswith("reloads the page.")


def test_title_skipped_when_generated_line_or_rule_follows():
    for following in ("Generated: 2026-01-01", "#####"):
        text = f"TECHNICAL DESIGN DOCUMENT\n{following}\n1. SUMMARY\nx\n"
        parsed = parse_tdd(text)
        assert parsed.title is None
        assert any(u.scope == "tdd" and u.field == "title" for u in parsed.unresolved)


def test_missing_summary_section():
    parsed = parse_tdd("TECHNICAL DESIGN DOCUMENT\nT\n1. REQUIREMENTS\nx\n")
    assert parsed.summary is None
    assert [(u.scope, u.field) for u in parsed.unresolved] == [("section", "summary")]


def test_glued_heading_recorded_not_split():
    text = "TECHNICAL DESIGN DOCUMENT\nT\n1. SUMMARY\nsome text 2. REQUIREMENTS\nmore\n"
    parsed = parse_tdd(text)
    assert parsed.last_section_number == 1
    assert [(u.scope, u.reason, u.line) for u in parsed.unresolved] == [
        ("section", "Possible glued section heading", 3)
    ]
    norm = normalise_lines(text)[1]
    assert find_glued_headings(norm, find_sections(norm)) == [3]


def test_no_glued_heading_in_sample():
    norm = normalise_lines(sample_text())[1]
    assert find_glued_headings(norm, find_sections(norm)) == []


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n",
        "garbage",
        "\x00\x01\x02",
        "1. ",
        "1. SUMMARY",
        "=" * 50,
        "\f\f\f",
        "é\r\n\r\n",
        "1. A\n" * 500,
    ],
)
def test_garbage_and_empty_input_never_raise(text):
    parsed = parse_tdd(text)
    assert parsed.changes == []


def test_no_sections_gives_single_unresolved_item():
    parsed = parse_tdd("just some text\nwithout headings")
    assert parsed.last_section_number is None
    assert [(u.scope, u.reason) for u in parsed.unresolved] == [
        ("tdd", "No numbered sections found")
    ]
