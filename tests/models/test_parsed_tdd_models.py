import pytest
from pydantic import ValidationError

from impact_agent.models.parsed_tdd import (
    ChangeAction,
    CodeCheck,
    ParsedChange,
    ParsedTDD,
    PlannedTest,
)


def test_enum_values_match_contract():
    assert {e.value for e in ChangeAction} == {"modify", "create", "reference"}
    assert {e.value for e in CodeCheck} == {"VERIFIED", "NEW"}


def test_parsed_change_minimal_and_full():
    minimal = ParsedChange(number=1)
    assert minimal.action is None
    assert minimal.insert_before_line is None
    full = ParsedChange(
        number=2,
        service="ui",
        file="a.tsx",
        symbol="f",
        action="modify",
        code_check="VERIFIED",
        summary="s",
        insert_before_line=10,
    )
    assert full.action is ChangeAction.MODIFY
    assert full.code_check is CodeCheck.VERIFIED


def test_parsed_tdd_defaults_and_planned_test():
    tdd = ParsedTDD()
    assert tdd.changes == []
    assert tdd.no_change_services == []
    assert tdd.last_section_number is None
    test = PlannedTest(kind="unit", description="d", existing=False)
    assert test.expected is None
    assert ParsedTDD(planned_tests=[test]).planned_tests[0].existing is False


@pytest.mark.parametrize(
    "kwargs", [{"number": 1, "action": "delete"}, {"number": 1, "code_check": "OLD"}]
)
def test_invalid_values_rejected(kwargs):
    with pytest.raises(ValidationError):
        ParsedChange(**kwargs)


def test_planned_test_requires_existing_flag():
    with pytest.raises(ValidationError):
        PlannedTest(kind="unit", description="d")
