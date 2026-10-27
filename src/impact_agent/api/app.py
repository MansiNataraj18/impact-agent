import logging
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from impact_agent.api.idempotency import (
    DEFAULT_TTL_SECONDS,
    IdempotencyConflict,
    IdempotencyStore,
)
from impact_agent.api.pipeline import run_pipeline
from impact_agent.api.schemas import ImpactRequest, ImpactResponse, ResponseStatus
from impact_agent.core.engine import DefaultImpactEngine, ImpactEngine
from impact_agent.core.llm import FakeLLM
from impact_agent.providers.base import GraphProvider
from impact_agent.providers.fake import FakeGraphProvider

logger = logging.getLogger(__name__)

TTL_ENV_VAR = "IMPACT_IDEMPOTENCY_TTL_SECONDS"
FAKE_GRAPH_WARNING = (
    "No graph provider configured: using FakeGraphProvider. Results are fixture data, "
    "not real impact analysis."
)


def ttl_from_env() -> float | None:
    """Idempotency TTL in seconds from the environment. 'none' keeps results forever."""
    raw = os.environ.get(TTL_ENV_VAR)
    if raw is None or not raw.strip():
        return DEFAULT_TTL_SECONDS
    if raw.strip().lower() == "none":
        return None
    try:
        ttl = float(raw)
    except ValueError:
        raise ValueError(f"{TTL_ENV_VAR} must be a number of seconds or 'none', got {raw!r}")
    if ttl <= 0:
        raise ValueError(f"{TTL_ENV_VAR} must be greater than 0, got {raw!r}")
    return ttl


class QuietFakeLLM(FakeLLM):
    """DUMMY: a FakeLLM that does not keep prompts, so a long-running server does not grow."""

    def complete(self, prompt: str) -> str:
        reply = super().complete(prompt)
        self.prompts.clear()
        return reply


def default_engine() -> ImpactEngine:
    """DUMMY: a fake LLM that always gives the same fixture analysis. Not a real model."""
    return DefaultImpactEngine(QuietFakeLLM.for_scenario("minimal_valid"))


def create_app(
    provider: GraphProvider | None = None,
    engine: ImpactEngine | None = None,
    ttl_seconds: float | None = None,
) -> FastAPI:
    """`ttl_seconds` overrides the environment setting; None reads it from the environment."""
    if provider is None:
        logger.warning(FAKE_GRAPH_WARNING)
        provider = FakeGraphProvider("normal")  # DUMMY fixture graphs
    engine = engine or default_engine()
    store = IdempotencyStore(ttl_seconds=ttl_seconds if ttl_seconds is not None else ttl_from_env())
    app = FastAPI(title="Impact Agent")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/impact", response_model=ImpactResponse)
    def impact(request: ImpactRequest):
        try:
            response = store.run(request, lambda: run_pipeline(request, provider, engine))
        except IdempotencyConflict as conflict:
            return JSONResponse(status_code=409, content={"detail": str(conflict)})
        if response.status is ResponseStatus.ERROR:
            return JSONResponse(status_code=500, content=response.model_dump(mode="json"))
        return response

    return app
