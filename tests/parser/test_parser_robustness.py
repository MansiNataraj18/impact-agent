from pathlib import Path

import pytest

from impact_agent.parser.tdd_parser import parse_tdd

SAMPLE = Path(__file__).resolve().parent.parent / "fixtures" / "tdd" / "sample_input.txt"
# 0-based line indexes in the sample (see tests/fixtures/tdd/sample_input.txt)
CHANGE_1_HEADER, CHANGE_1_FILE, CHANGE_1_CODE_CHECK, CHANGE_1_DONE_WHEN = 99, 100, 101, 128
CHANGE_2_HEADER, UI_HEADING_FIRST, UI_HEADING_LAST = 137, 90, 92


def sample_lines():
    with open(SAMPLE, encoding="utf-8", newline="") as handle:
        return handle.read().split("\n")


def parse_with(edit):
    lines = sample_lines()
    edit(lines)
    return parse_tdd("\n".join(lines))


def keys(parsed):
    return {(u.scope, u.change_number, u.field) for u in parsed.unresolved}


def change(parsed, number):
    return next(c for c in parsed.changes if c.number == number)


def test_missing_done_when():
    def edit(lines):
        lines[CHANGE_1_DONE_WHEN] = "Finished when:"

    parsed = parse_with(edit)
    assert change(parsed, 1).insert_before_line is None
    assert ("change", 1, "insert_before_line") in keys(parsed)
    assert [c.insert_before_line for c in parsed.changes[1:]] == [171, 188, 220]


def test_missing_file_line():
    def edit(lines):
        lines[CHANGE_1_FILE] = "Path: somewhere"

    parsed = parse_with(edit)
    assert change(parsed, 1).file is None
    assert keys(parsed) == {("change", 1, "file")}


def test_empty_file_value():
    def edit(lines):
        lines[CHANGE_1_FILE] = "File:"

    parsed = parse_with(edit)
    assert change(parsed, 1).file is None
    assert keys(parsed) == {("change", 1, "file")}


def test_unknown_action_in_header():
    def edit(lines):
        lines[CHANGE_1_HEADER] = "Change 1: handleCcEmailAddressesBlur (delete)"

    parsed = parse_with(edit)
    assert [c.number for c in parsed.changes] == [2, 3, 4]
    item = next(u for u in parsed.unresolved if u.scope == "change")
    assert (item.change_number, item.field, item.line) == (1, None, CHANGE_1_HEADER)
    assert item.reason == "Change header could not be parsed"
    assert keys(parsed) == {("change", 1, None)}
    assert change(parsed, 2).insert_before_line == 171


@pytest.mark.parametrize("value", ["Code check: UNKNOWN", "Code check:", "Checked: VERIFIED"])
def test_missing_or_invalid_code_check(value):
    def edit(lines):
        lines[CHANGE_1_CODE_CHECK] = value

    parsed = parse_with(edit)
    assert change(parsed, 1).code_check is None
    assert keys(parsed) == {("change", 1, "code_check")}


def test_no_services_and_changes_section():
    def edit(lines):
        lines[88] = "5. SOMETHING ELSE"

    parsed = parse_with(edit)
    assert parsed.changes == []
    assert parsed.no_change_services == []
    assert keys(parsed) == {("section", None, "changes")}
    assert parsed.last_section_number == 14


def test_no_testing_section():
    def edit(lines):
        lines[335] = "10. SOMETHING ELSE"

    parsed = parse_with(edit)
    assert parsed.planned_tests == []
    assert keys(parsed) == {("section", None, "planned_tests")}
    assert len(parsed.changes) == 4


def test_duplicate_change_number_keeps_first():
    def edit(lines):
        lines[CHANGE_2_HEADER] = "Change 1: handleCcEmailAddressesBlur (create)"

    parsed = parse_with(edit)
    assert [c.number for c in parsed.changes] == [1, 3, 4]
    assert change(parsed, 1).action.value == "modify"
    assert [(u.scope, u.reason, u.line) for u in parsed.unresolved] == [
        ("section", "Duplicate change number 1", CHANGE_2_HEADER)
    ]
    assert change(parsed, 1).insert_before_line == 137  # the duplicate still ends the block


def test_glued_heading_lookalike():
    def edit(lines):
        lines[7] += " 6. FILES TO CHANGE"

    parsed = parse_with(edit)
    assert parsed.last_section_number == 14
    assert [(u.scope, u.reason, u.line) for u in parsed.unresolved] == [
        ("section", "Possible glued section heading", 7)
    ]
    assert len(parsed.changes) == 4


def test_change_before_any_service_heading():
    def edit(lines):
        for index in range(UI_HEADING_FIRST, UI_HEADING_LAST + 1):
            lines[index] = ""

    parsed = parse_with(edit)
    assert [c.service for c in parsed.changes] == [None, None, None, "candidate-service"]
    assert keys(parsed) == {("change", n, "service") for n in (1, 2, 3)}


def test_no_numbered_sections():
    parsed = parse_tdd("Change 1: foo (modify)\nFile: a.py\nDone when:\n- x\n")
    assert parsed.last_section_number is None
    assert parsed.changes == []
    assert [(u.scope, u.change_number, u.field, u.reason) for u in parsed.unresolved] == [
        ("tdd", None, None, "No numbered sections found")
    ]


def test_truncated_inside_a_change():
    lines = sample_lines()[:150]
    parsed = parse_tdd("\n".join(lines))
    assert [c.number for c in parsed.changes] == [1, 2]
    assert change(parsed, 1).insert_before_line == 137
    assert change(parsed, 2).insert_before_line is None
    assert ("change", 2, "insert_before_line") in keys(parsed)
    assert parsed.planned_tests == []


def test_truncated_after_last_done_when_has_no_boundary():
    parsed = parse_tdd("\n".join(sample_lines()[:219]))
    last = change(parsed, 4)
    assert last.insert_before_line is None
    reasons = [u.reason for u in parsed.unresolved if u.field == "insert_before_line"]
    assert reasons == ["No boundary found after the change block"]


def test_empty_and_blank_text():
    for text in ("", "\n\n", "   "):
        parsed = parse_tdd(text)
        assert parsed.changes == [] and parsed.planned_tests == []
        assert parsed.last_section_number is None


def test_crlf_sample_matches_lf_values():
    text = "\n".join(sample_lines()).replace("\n", "\r\n")
    parsed = parse_tdd(text)
    assert [c.insert_before_line for c in parsed.changes] == [137, 171, 188, 220]
    assert parsed.no_change_services == ["accounts-service", "reports-api", "pdf-service"]
    assert len(parsed.planned_tests) == 6
    assert parsed.unresolved == []


def test_never_raises_on_every_prefix_of_the_sample():
    text = "\n".join(sample_lines())
    for cut in range(0, len(text), 997):
        parse_tdd(text[:cut])
