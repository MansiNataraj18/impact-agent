"""Hand-built fixture graphs. All of this is dummy data, never a real code graph."""

from collections.abc import Callable

from impact_agent.models.common import UnresolvedItem
from impact_agent.models.impact import ImpactGraph, ImpactNode, NodeKind

UI_VIEW = (
    "src/common/accounts/client/components/SettingsForm/sections/AtsIntegrationSection/view.tsx"
)
UI_TEST = (
    "src/common/accounts/client/components/SettingsForm/sections/AtsIntegrationSection/"
    "view.test.tsx"
)
UI_FORM = "src/common/accounts/client/components/SettingsForm/index.tsx"
ACCOUNTS_SCHEMA = "src/main/resources/graphql/settings.graphqls"
CANDIDATE_HANDLER = (
    "src/main/kotlin/com/asurint/candidate/handlers/commands/SendDirectRequestEmailHandler.kt"
)
REPORTS_HANDLER = "src/main/kotlin/com/asurint/reports/handlers/ReportEmailQueuedHandler.kt"


def _node(
    id: str,
    kind: str,
    name: str,
    service: str | None,
    location: str | None,
    depth: int,
    relation: str,
) -> ImpactNode:
    return ImpactNode(
        id=id,
        kind=NodeKind(kind),
        name=name,
        service=service,
        location=location,
        depth=depth,
        relation=relation,
    )


def _graph(changed: str, nodes: list[ImpactNode], unresolved=()) -> ImpactGraph:
    return ImpactGraph(changed=changed, nodes=nodes, source="fixture", unresolved=list(unresolved))


def _normal_nodes() -> list[ImpactNode]:
    return [
        _node("ui.section_view", "method", "AtsIntegrationSectionView", "ui", UI_VIEW, 1, "calls"),
        _node("ui.ats_change", "function", "atsIntegrationChange", "ui", UI_VIEW, 1, "calls"),
        _node("ui.settings_form", "class", "SettingsForm", "ui", UI_FORM, 2, "calls"),
        _node(
            "accounts.settings_input",
            "api",
            "AtsIntegrationSettingsInput.sendReportRequestedLinkCcEmailAddresses",
            "accounts-service",
            ACCOUNTS_SCHEMA,
            3,
            "exposes",
        ),
        _node(
            "candidate.validate_emails",
            "method",
            "SendDirectRequestEmailHandler.validateEmails",
            "candidate-service",
            CANDIDATE_HANDLER,
            4,
            "reads",
        ),
    ]


def normal(changed: str) -> ImpactGraph:
    """Callers in ui, an API in accounts-service, a reader in candidate-service, and one test."""
    test = _node(
        "ui.view_test", "test", "AtsIntegrationSectionView blur test", "ui", UI_TEST, 1, "tests"
    )
    return _graph(changed, [*_normal_nodes(), test])


def no_tests(changed: str) -> ImpactGraph:
    """Same as `normal` but nothing covers the change."""
    return _graph(changed, _normal_nodes())


def empty(changed: str) -> ImpactGraph:
    """The graph knows the symbol but found no callers, dependents or tests."""
    return _graph(changed, [])


def cross_service(changed: str) -> ImpactGraph:
    """Items in four services at depths 1 to 3, with a test."""
    return _graph(
        changed,
        [
            _node(
                "ui.section_view", "method", "AtsIntegrationSectionView", "ui", UI_VIEW, 1, "calls"
            ),
            _node(
                "accounts.resolver",
                "method",
                "AtsSettingsResolver.save",
                "accounts-service",
                ACCOUNTS_SCHEMA,
                1,
                "calls",
            ),  # fmt: skip
            _node(
                "candidate.validate_emails",
                "method",
                "SendDirectRequestEmailHandler.validateEmails",
                "candidate-service",
                CANDIDATE_HANDLER,
                2,
                "reads",
            ),  # fmt: skip
            _node(
                "reports.email_queued",
                "event",
                "ReportEmailQueued",
                "reports-api",
                REPORTS_HANDLER,
                3,
                "reads",
            ),  # fmt: skip
            _node(
                "ui.view_test",
                "test",
                "AtsIntegrationSectionView blur test",
                "ui",
                UI_TEST,
                1,
                "tests",
            ),
        ],
    )


def missing_evidence(changed: str) -> ImpactGraph:
    """Nodes without a location, a node without a service, and an unresolved changed symbol."""
    return _graph(
        changed,
        [
            _node("ui.section_view", "method", "AtsIntegrationSectionView", "ui", None, 1, "calls"),
            _node("unknown.handler", "function", "mysteryHandler", None, UI_VIEW, 2, "calls"),
            _node(
                "accounts.settings_input",
                "api",
                "AtsIntegrationSettingsInput",
                "accounts-service",
                None,
                3,
                "exposes",
            ),  # fmt: skip
        ],
        unresolved=[
            UnresolvedItem(
                scope="change",
                field="symbol",
                reason="Changed symbol could not be resolved in the graph",
            )
        ],
    )


SCENARIOS: dict[str, Callable[[str], ImpactGraph]] = {
    "normal": normal,
    "no_tests": no_tests,
    "empty": empty,
    "cross_service": cross_service,
    "missing_evidence": missing_evidence,
}
