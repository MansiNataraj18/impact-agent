from collections.abc import Mapping, Sequence

from impact_agent.core.evidence import WARNING_NO_GRAPH, graph_warnings, unresolved_warning
from impact_agent.core.grouping import group_nodes
from impact_agent.core.llm import LLMClient
from impact_agent.core.validation import explain_nodes
from impact_agent.models.impact import (
    AffectedItem,
    ClaimCheck,
    ClaimFinding,
    ExplanationStatus,
    GraphSource,
    ImpactExplanation,
    ImpactGraph,
    ImpactNode,
    RiskLevel,
    TddImpactResult,
)
from impact_agent.models.parsed_tdd import ChangeAction, ParsedChange, ParsedTDD

# Only these actions are looked up in the graph (contract section 6).
ANALYSED_ACTIONS = frozenset({ChangeAction.MODIFY})

# Lowest to highest; the overall risk is the highest per-change risk.
RISK_ORDER = (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH)

REASON_CREATE = "Not applicable (new file, not in the dependency graph)"
REASON_REFERENCE = "None (read only, no change proposed)"
REASON_NO_ACTION = "Change action could not be determined."
SUMMARY_CREATE = (
    "New files have no existing callers or dependents, so nothing in the graph is affected."
)
SUMMARY_REFERENCE = "No code changes are proposed here, so no impact is expected."
SUMMARY_NOT_ANALYSED = "This change was not analysed against the graph."
SUMMARY_NOTHING_ANALYSED = "No change required graph analysis."
SUMMARY_TEMPLATE = (
    "{a} change(s) analysed; overall risk {risk}; {d} directly and {p} potentially "
    "affected item(s); {t} test(s) to run."
)
NOTE_NEEDS_REVIEW = "The graph lists {n} affected item(s) in this service."
NOTE_CONSISTENT = "No affected items were found in this service in the graph."
CLAIM_NO_CHANGE = "no change"
WARNING_NO_SECTION_NUMBER = "The section number could not be determined."
UNKNOWN = "unknown"


def highest_risk(risks: Sequence[RiskLevel | None]) -> RiskLevel | None:
    present = [risk for risk in risks if risk is not None]
    return max(present, key=RISK_ORDER.index) if present else None


def changed_location_of(change: ParsedChange) -> str:
    return "::".join(part or UNKNOWN for part in (change.service, change.file, change.symbol))


def graph_test_label(item: AffectedItem) -> str:
    return f"{item.name} ({item.location})" if item.location else item.name


def _change_warnings(parsed: ParsedTDD, number: int) -> list[str]:
    return [
        unresolved_warning(item)
        for item in parsed.unresolved
        if item.scope == "change" and item.change_number == number
    ]


def _not_analysed(
    change: ParsedChange,
    status: ExplanationStatus,
    reason: str,
    summary: str,
    warnings: list[str],
) -> ImpactExplanation:
    return ImpactExplanation(
        change_number=change.number,
        status=status,
        reason=reason,
        changed_location=changed_location_of(change),
        risk_level=None,
        summary=summary,
        warnings=warnings,
        graph_source=GraphSource.FIXTURE,
    )


def _affected_item(node: ImpactNode, reasons: Mapping[str, str]) -> AffectedItem:
    return AffectedItem(
        node_id=node.id,
        name=node.name,
        kind=node.kind,
        service=node.service,
        location=node.location,
        depth=node.depth,
        reason=reasons[node.id],
    )


def _explain_change(
    change: ParsedChange,
    parsed: ParsedTDD,
    graph: ImpactGraph | None,
    llm: LLMClient,
) -> ImpactExplanation:
    parser_unresolved = [
        item
        for item in parsed.unresolved
        if item.scope == "change" and item.change_number == change.number
    ]
    if change.action is None:
        return _not_analysed(
            change,
            ExplanationStatus.SKIPPED,
            REASON_NO_ACTION,
            SUMMARY_NOT_ANALYSED,
            _change_warnings(parsed, change.number),
        )
    if change.action not in ANALYSED_ACTIONS:
        if change.action is ChangeAction.CREATE:
            reason, summary = REASON_CREATE, SUMMARY_CREATE
        else:
            reason, summary = REASON_REFERENCE, SUMMARY_REFERENCE
        return _not_analysed(
            change,
            ExplanationStatus.NOT_APPLICABLE,
            reason,
            summary,
            _change_warnings(parsed, change.number),
        )
    if graph is None:
        return _not_analysed(
            change,
            ExplanationStatus.SKIPPED,
            WARNING_NO_GRAPH,
            SUMMARY_NOT_ANALYSED,
            [WARNING_NO_GRAPH, *_change_warnings(parsed, change.number)],
        )

    grouped = group_nodes(graph)
    outcome = explain_nodes(llm, change.summary, graph.changed, grouped)
    warnings = [*graph_warnings(graph, grouped, parser_unresolved), *outcome.warnings]
    return ImpactExplanation(
        change_number=change.number,
        status=ExplanationStatus.EXPLAINED,
        changed_location=graph.changed,
        risk_level=outcome.risk_level,
        summary=outcome.summary,
        directly_affected=[_affected_item(n, outcome.reasons) for n in grouped.direct],
        potentially_affected=[_affected_item(n, outcome.reasons) for n in grouped.potential],
        tests_to_run=[_affected_item(n, outcome.reasons) for n in grouped.tests],
        warnings=warnings,
        graph_source=graph.source,
    )


def _claims(parsed: ParsedTDD, analysed: Sequence[ImpactExplanation]) -> list[ClaimCheck]:
    affected = [
        item
        for explanation in analysed
        for item in (
            *explanation.directly_affected,
            *explanation.potentially_affected,
            *explanation.tests_to_run,
        )
    ]
    claims = []
    for service in parsed.no_change_services:
        count = len({item.node_id for item in affected if item.service == service})
        if count:
            finding, note = ClaimFinding.NEEDS_REVIEW, NOTE_NEEDS_REVIEW.format(n=count)
        else:
            finding, note = ClaimFinding.CONSISTENT, NOTE_CONSISTENT
        claims.append(
            ClaimCheck(service=service, tdd_claim=CLAIM_NO_CHANGE, finding=finding, note=note)
        )
    return claims


def _tdd_level_warnings(parsed: ParsedTDD) -> list[str]:
    warnings = [
        unresolved_warning(item) for item in parsed.unresolved if item.scope in ("tdd", "section")
    ]
    if parsed.last_section_number is None:
        warnings.append(WARNING_NO_SECTION_NUMBER)
    return warnings


def analyze_tdd(
    parsed: ParsedTDD,
    graphs: Mapping[int, ImpactGraph],
    llm: LLMClient,
) -> TddImpactResult:
    changes = [
        _explain_change(change, parsed, graphs.get(change.number), llm) for change in parsed.changes
    ]
    analysed = [c for c in changes if c.status is ExplanationStatus.EXPLAINED]

    overall = highest_risk([c.risk_level for c in analysed])
    tests: list[str] = []
    for explanation in analysed:
        for item in explanation.tests_to_run:
            if graph_test_label(item) not in tests:
                tests.append(graph_test_label(item))

    if analysed:
        summary = SUMMARY_TEMPLATE.format(
            a=len(analysed),
            risk=overall.value if overall else UNKNOWN,
            d=sum(len(c.directly_affected) for c in analysed),
            p=sum(len(c.potentially_affected) for c in analysed),
            t=len(tests),
        )
    else:
        summary = SUMMARY_NOTHING_ANALYSED

    sources = {c.graph_source for c in analysed}
    if GraphSource.FIXTURE in sources or not sources:
        source = GraphSource.FIXTURE
    else:
        source = GraphSource.GRAPH

    return TddImpactResult(
        changes=changes,
        overall_risk=overall,
        summary=summary,
        graph_source=source,
        tests_to_run=tests,
        claims_vs_graph=_claims(parsed, analysed),
        warnings=_tdd_level_warnings(parsed),
    )
