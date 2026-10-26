"""Entry point for the Aetherion agent. Pure Python: no SDK code lives in this module.

TODO: register `handle_tdd` with the Aetherion SDK once the SDK documentation is available
(see docs/aetherion.md). Only that registration should depend on the SDK.
"""

from impact_agent.api.pipeline import run_pipeline
from impact_agent.api.schemas import ImpactRequest, ResponseStatus
from impact_agent.core.engine import ImpactEngine
from impact_agent.providers.base import GraphProvider

ERROR_MESSAGE = "Impact analysis failed: {reasons}"


def handle_tdd(
    tdd_text: str,
    *,
    provider: GraphProvider,
    engine: ImpactEngine,
    correlation_id: str | None = None,
) -> str:
    """Return the enriched TDD for `tdd_text`. Raises RuntimeError if the analysis failed."""
    response = run_pipeline(
        ImpactRequest(tdd_text=tdd_text, correlation_id=correlation_id), provider, engine
    )
    if response.status is ResponseStatus.ERROR:
        reasons = "; ".join(item.reason for item in response.unresolved) or "unknown error"
        raise RuntimeError(ERROR_MESSAGE.format(reasons=reasons))
    return response.tdd_text
