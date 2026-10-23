from pathlib import Path

import pytest

from impact_agent.models.parsed_tdd import ChangeAction, CodeCheck
from impact_agent.parser.tdd_parser import parse_tdd

SAMPLE = Path(__file__).resolve().parent.parent / "fixtures" / "tdd" / "sample_input.txt"
UI_DIR = "src/common/accounts/client/components/SettingsForm/sections/AtsIntegrationSection"


@pytest.fixture(scope="module")
def parsed():
    with open(SAMPLE, encoding="utf-8", newline="") as handle:
        return parse_tdd(handle.read())


def test_four_changes_in_order(parsed):
    assert [c.number for c in parsed.changes] == [1, 2, 3, 4]
    assert [c.service for c in parsed.changes] == ["ui", "ui", "ui", "candidate-service"]
    assert [c.action for c in parsed.changes] == [
        ChangeAction.MODIFY,
        ChangeAction.CREATE,
        ChangeAction.REFERENCE,
        ChangeAction.REFERENCE,
    ]
    assert [c.code_check for c in parsed.changes] == [
        CodeCheck.VERIFIED,
        CodeCheck.NEW,
        CodeCheck.VERIFIED,
        CodeCheck.VERIFIED,
    ]
    assert [c.symbol for c in parsed.changes] == [
        "handleCcEmailAddressesBlur",
        "handleCcEmailAddressesBlur",
        "ReportEventsCCEmailAddressSettings",
        "validateEmails",
    ]


def test_files_including_wrapped_paths(parsed):
    files = [c.file for c in parsed.changes]
    assert files[0] == f"{UI_DIR}/view.tsx"
    assert files[1] == f"{UI_DIR}/view.test.tsx"
    assert files[2].endswith("/components/ReportEventsCCEmailAddressSettings.tsx")
    assert files[2].startswith("src/apps/client/modules/Settings/pages/ApplicationSettings/")
    assert files[3].endswith("/SendDirectRequestEmailHandler.kt")
    assert all(" " not in f for f in files)


def test_summaries(parsed):
    assert all(c.summary for c in parsed.changes)
    assert parsed.changes[0].summary.startswith(
        "Modify ATS integration CC email blur normalization"
    )
    assert all("\n" not in c.summary and "  " not in c.summary for c in parsed.changes)
    assert "Done when" not in parsed.changes[0].summary


def test_insert_before_line(parsed):
    assert [c.insert_before_line for c in parsed.changes] == [137, 171, 188, 220]


def test_no_change_services(parsed):
    assert parsed.no_change_services == ["accounts-service", "reports-api", "pdf-service"]


def test_planned_tests(parsed):
    tests = parsed.planned_tests
    assert [t.kind for t in tests] == [
        "regression", "unit", "edge_case", "regression", "integration", "integration",
    ]  # fmt: skip
    assert [t.existing for t in tests] == [False, False, False, False, True, True]
    assert any(t.expected for t in tests)
    assert all(t.description and "TO ADD" not in t.description for t in tests)
    assert tests[0].description.startswith("In ui AtsIntegrationSectionView, enter")
    assert "Expected:" not in tests[0].description


def test_nothing_unresolved_for_sample(parsed):
    assert parsed.unresolved == []
    assert parsed.last_section_number == 14
