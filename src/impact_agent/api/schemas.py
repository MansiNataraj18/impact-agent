from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from impact_agent.models.common import UnresolvedItem

SCHEMA_VERSION = "1"


class ResponseStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    ERROR = "error"


class ImpactRequest(BaseModel):
    tdd_text: str
    project: str | None = None
    repository: str | None = None
    revision: str | None = None
    correlation_id: str | None = None

    @field_validator("tdd_text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("tdd_text must not be empty")
        return value


class ImpactResponse(BaseModel):
    schema_version: str = SCHEMA_VERSION
    status: ResponseStatus
    correlation_id: str | None = None
    tdd_text: str
    unresolved: list[UnresolvedItem] = Field(default_factory=list)
