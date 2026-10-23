from impact_agent.models.common import UnresolvedItem
from impact_agent.models.parsed_tdd import ParsedChange, ParsedTDD, PlannedTest

# Field names listed in docs/contracts.md section 4.
CONTRACT_FIELDS = {
    UnresolvedItem: {"scope", "change_number", "field", "reason", "line"},
    PlannedTest: {"kind", "description", "expected", "existing"},
    ParsedChange: {
        "number",
        "service",
        "file",
        "symbol",
        "action",
        "code_check",
        "summary",
        "insert_before_line",
    },  # fmt: skip
    ParsedTDD: {
        "title",
        "summary",
        "changes",
        "no_change_services",
        "planned_tests",
        "last_section_number",
        "unresolved",
    },  # fmt: skip
}


def test_models_have_exactly_the_contract_fields():
    for model, names in CONTRACT_FIELDS.items():
        assert set(model.model_fields) == names, model.__name__
