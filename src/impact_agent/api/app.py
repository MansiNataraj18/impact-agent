from fastapi import FastAPI
from fastapi.responses import JSONResponse

from impact_agent.api.idempotency import IdempotencyConflict, IdempotencyStore
from impact_agent.api.pipeline import run_pipeline
from impact_agent.api.schemas import ImpactRequest, ImpactResponse, ResponseStatus
from impact_agent.core.engine import DefaultImpactEngine, ImpactEngine
from impact_agent.core.llm import FakeLLM
from impact_agent.providers.base import GraphProvider
from impact_agent.providers.fake import FakeGraphProvider


def default_engine() -> ImpactEngine:
    """DUMMY: a fake LLM that always gives the same fixture analysis. Not a real model."""
    return DefaultImpactEngine(FakeLLM.for_scenario("minimal_valid"))


def create_app(
    provider: GraphProvider | None = None, engine: ImpactEngine | None = None
) -> FastAPI:
    provider = provider or FakeGraphProvider("normal")  # DUMMY fixture graphs
    engine = engine or default_engine()
    store = IdempotencyStore()
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
