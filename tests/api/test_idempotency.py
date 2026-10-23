import threading

from fastapi.testclient import TestClient

from impact_agent.api.app import create_app, default_engine
from impact_agent.api.idempotency import IdempotencyStore
from impact_agent.api.schemas import ImpactRequest, ImpactResponse, ResponseStatus
from impact_agent.providers.fake import FakeGraphProvider


class CountingProvider(FakeGraphProvider):
    def __init__(self):
        super().__init__("normal")
        self.calls = 0

    def get_impact(self, query):
        self.calls += 1
        return super().get_impact(query)


class CountingEngine:
    def __init__(self, inner=None, fail_times=0):
        self.inner = inner or default_engine()
        self.calls = 0
        self.fail_times = fail_times

    def enrich(self, tdd_text, parsed, graphs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("temporary")
        return self.inner.enrich(tdd_text, parsed, graphs)


def make(engine=None):
    provider = CountingProvider()
    engine = engine or CountingEngine()
    return TestClient(create_app(provider=provider, engine=engine)), provider, engine


def test_same_id_and_input_returns_stored_response_without_rerunning(sample_text):
    client, provider, engine = make()
    body = {"tdd_text": sample_text, "correlation_id": "id-1"}
    first = client.post("/impact", json=body)
    second = client.post("/impact", json=body)
    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert provider.calls == 1
    assert engine.calls == 1


def test_same_id_with_different_input_is_409(sample_text):
    client, provider, engine = make()
    client.post("/impact", json={"tdd_text": sample_text, "correlation_id": "id-1"})
    other = client.post(
        "/impact", json={"tdd_text": sample_text + "\nextra", "correlation_id": "id-1"}
    )
    assert other.status_code == 409
    assert "detail" in other.json()
    assert engine.calls == 1
    metadata = client.post(
        "/impact", json={"tdd_text": sample_text, "correlation_id": "id-1", "project": "other"}
    )
    assert metadata.status_code == 409


def test_without_id_nothing_is_cached(sample_text):
    client, provider, engine = make()
    client.post("/impact", json={"tdd_text": sample_text})
    client.post("/impact", json={"tdd_text": sample_text})
    assert engine.calls == 2


def test_different_ids_are_independent(sample_text):
    client, _, engine = make()
    client.post("/impact", json={"tdd_text": sample_text, "correlation_id": "a"})
    client.post("/impact", json={"tdd_text": sample_text, "correlation_id": "b"})
    assert engine.calls == 2


def test_errors_are_not_cached_so_retry_can_succeed(sample_text):
    client, _, engine = make(CountingEngine(fail_times=1))
    body = {"tdd_text": sample_text, "correlation_id": "retry"}
    assert client.post("/impact", json=body).status_code == 500
    retry = client.post("/impact", json=body)
    assert retry.status_code == 200
    assert retry.json()["status"] == "ok"
    assert engine.calls == 2
    assert client.post("/impact", json=body).content == retry.content
    assert engine.calls == 2


def test_partial_responses_are_cached():
    client, _, engine = make()
    body = {"tdd_text": "no sections here", "correlation_id": "p"}
    assert client.post("/impact", json=body).json()["status"] == "partial"
    client.post("/impact", json=body)
    # garbage text never reaches the engine; the stored response is simply returned
    assert engine.calls == 0


def test_store_is_safe_under_concurrent_requests():
    store = IdempotencyStore()
    request = ImpactRequest(tdd_text="x", correlation_id="same")
    calls = []

    def compute():
        calls.append(1)
        return ImpactResponse(status=ResponseStatus.OK, tdd_text="done", correlation_id="same")

    results = []
    threads = [
        threading.Thread(target=lambda: results.append(store.run(request, compute)))
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(calls) == 1
    assert [r.tdd_text for r in results] == ["done"] * 8
