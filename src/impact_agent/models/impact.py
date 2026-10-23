from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator

from impact_agent.models.common import UnresolvedItem


class NodeKind(StrEnum):
    METHOD = "method"
    FUNCTION = "function"
    CLASS = "class"
    SERVICE = "service"
    API = "api"
    EVENT = "event"
    DATABASE = "database"
    TEST = "test"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExplanationStatus(StrEnum):
    EXPLAINED = "explained"
    NOT_APPLICABLE = "not_applicable"
    SKIPPED = "skipped"


class GraphSource(StrEnum):
    FIXTURE = "fixture"
    GRAPH = "graph"


class ClaimFinding(StrEnum):
    CONSISTENT = "consistent"
    NEEDS_REVIEW = "needs_review"


class ImpactQuery(BaseModel):
    change_number: int
    service: str | None = None
    file: str | None = None
    symbol: str | None = None
    project: str | None = None
    repository: str | None = None
    revision: str | None = None


class ImpactNode(BaseModel):
    id: str
    kind: NodeKind
    name: str
    service: str | None = None
    location: str | None = None
    depth: int = Field(ge=1)
    relation: str


class ImpactGraph(BaseModel):
    changed: str
    nodes: list[ImpactNode]
    source: GraphSource
    unresolved: list[UnresolvedItem] = Field(default_factory=list)


class AffectedItem(BaseModel):
    node_id: str
    name: str
    kind: NodeKind
    service: str | None = None
    location: str | None = None
    depth: int
    reason: str


class ImpactExplanation(BaseModel):
    change_number: int
    status: ExplanationStatus
    reason: str | None = None
    changed_location: str
    risk_level: RiskLevel | None = None
    summary: str
    directly_affected: list[AffectedItem] = Field(default_factory=list)
    potentially_affected: list[AffectedItem] = Field(default_factory=list)
    tests_to_run: list[AffectedItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    graph_source: GraphSource

    @model_validator(mode="after")
    def _no_risk_when_not_applicable(self) -> Self:
        if self.status is ExplanationStatus.NOT_APPLICABLE and self.risk_level is not None:
            raise ValueError("risk_level must be None when status is not_applicable")
        return self


class ClaimCheck(BaseModel):
    service: str
    tdd_claim: str
    finding: ClaimFinding
    note: str


class TddImpactResult(BaseModel):
    changes: list[ImpactExplanation]
    overall_risk: RiskLevel | None = None
    summary: str
    graph_source: GraphSource
    tests_to_run: list[str] = Field(default_factory=list)
    claims_vs_graph: list[ClaimCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
