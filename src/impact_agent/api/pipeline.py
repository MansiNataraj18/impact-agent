from impact_agent.api.schemas import ImpactRequest, ImpactResponse, ResponseStatus
from impact_agent.core.analyzer import ANALYSED_ACTIONS
from impact_agent.core.engine import ImpactEngine
from impact_agent.models.common import UnresolvedItem
from impact_agent.models.impact import ImpactGraph, ImpactQuery
from impact_agent.parser.tdd_parser import parse_tdd
from impact_agent.providers.base import GraphProvider
from impact_agent.render.strip import strip_impact_sections

DEFAULT_PROJECT = "dummy-project"
DEFAULT_REPOSITORY = "dummy-repo"
DEFAULT_REVISION = "dummy-revision"

REASON_PROVIDER_FAILED = "Graph provider failed: {error}"
REASON_ENGINE_FAILED = "Engine failed: {error}"


def run_pipeline(
    request: ImpactRequest, provider: GraphProvider, engine: ImpactEngine
) -> ImpactResponse:
    """strip -> parse -> graph per analysed change -> enrich. Never returns partial text."""
    original = request.tdd_text
    stripped = strip_impact_sections(original)
    parsed = parse_tdd(stripped)

    if parsed.last_section_number is None and not parsed.changes:
        return ImpactResponse(
            status=ResponseStatus.PARTIAL,
            correlation_id=request.correlation_id,
            tdd_text=original,
            unresolved=parsed.unresolved,
        )

    graphs: dict[int, ImpactGraph] = {}
    unresolved = list(parsed.unresolved)
    provider_failed = False
    for change in parsed.changes:
        if change.action not in ANALYSED_ACTIONS:
            continue
        query = ImpactQuery(
            change_number=change.number,
            service=change.service,
            file=change.file,
            symbol=change.symbol,
            project=request.project or DEFAULT_PROJECT,
            repository=request.repository or DEFAULT_REPOSITORY,
            revision=request.revision or DEFAULT_REVISION,
        )
        try:
            graphs[change.number] = provider.get_impact(query)
        except Exception as error:
            provider_failed = True
            reason = REASON_PROVIDER_FAILED.format(error=type(error).__name__)
            unresolved.append(
                UnresolvedItem(
                    scope="change", change_number=change.number, field="graph", reason=reason
                )
            )

    try:
        enriched = engine.enrich(stripped, parsed, graphs)
    except Exception as error:
        reason = REASON_ENGINE_FAILED.format(error=type(error).__name__)
        unresolved.append(UnresolvedItem(scope="tdd", reason=reason))
        return ImpactResponse(
            status=ResponseStatus.ERROR,
            correlation_id=request.correlation_id,
            tdd_text=original,
            unresolved=unresolved,
        )

    partial = bool(parsed.unresolved) or provider_failed
    return ImpactResponse(
        status=ResponseStatus.PARTIAL if partial else ResponseStatus.OK,
        correlation_id=request.correlation_id,
        tdd_text=enriched,
        unresolved=unresolved,
    )
