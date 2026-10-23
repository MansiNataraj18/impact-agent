"""Parser output models.

Owned by the parser (Person 2). Fields are identical to contract section 4.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from impact_agent.models.common import UnresolvedItem


class ChangeAction(StrEnum):
    MODIFY = "modify"
    CREATE = "create"
    REFERENCE = "reference"


class CodeCheck(StrEnum):
    VERIFIED = "VERIFIED"
    NEW = "NEW"


class PlannedTest(BaseModel):
    kind: str
    description: str
    expected: str | None = None
    existing: bool


class ParsedChange(BaseModel):
    number: int
    service: str | None = None
    file: str | None = None
    symbol: str | None = None
    action: ChangeAction | None = None
    code_check: CodeCheck | None = None
    summary: str | None = None
    insert_before_line: int | None = None


class ParsedTDD(BaseModel):
    title: str | None = None
    summary: str | None = None
    changes: list[ParsedChange] = Field(default_factory=list)
    no_change_services: list[str] = Field(default_factory=list)
    planned_tests: list[PlannedTest] = Field(default_factory=list)
    last_section_number: int | None = None
    unresolved: list[UnresolvedItem] = Field(default_factory=list)
