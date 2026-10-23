import pytest
from fastapi.testclient import TestClient

from impact_agent.api.app import create_app


class FailingEngine:
    def enrich(self, tdd_text, parsed, graphs):
        raise RuntimeError("boom")


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_impact_ok(client, sample_text):
    response = client.post("/impact", json={"tdd_text": sample_text, "correlation_id": "abc"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"schema_version", "status", "correlation_id", "tdd_text", "unresolved"}
    assert body["schema_version"] == "1"
    assert body["status"] == "ok"
    assert body["correlation_id"] == "abc"
    assert body["unresolved"] == []
    assert "Impact Analysis (Change 1):" in body["tdd_text"]


def test_garbage_text_is_200_partial(client):
    response = client.post("/impact", json={"tdd_text": "hello"})
    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    assert response.json()["tdd_text"] == "hello"
    assert response.json()["correlation_id"] is None


@pytest.mark.parametrize("text", ["", "   ", "\n\t\n"])
def test_empty_or_blank_text_is_422(client, text):
    assert client.post("/impact", json={"tdd_text": text}).status_code == 422


def test_missing_or_non_string_text_is_422(client):
    assert client.post("/impact", json={}).status_code == 422
    assert client.post("/impact", json={"tdd_text": 5}).status_code == 422
    assert client.post("/impact", json={"tdd_text": None}).status_code == 422


def test_engine_failure_is_500_with_response_body(sample_text):
    client = TestClient(create_app(engine=FailingEngine()))
    response = client.post("/impact", json={"tdd_text": sample_text, "correlation_id": "x"})
    assert response.status_code == 500
    body = response.json()
    assert body["status"] == "error"
    assert body["schema_version"] == "1"
    assert body["tdd_text"] == sample_text
    assert body["correlation_id"] == "x"
    assert body["unresolved"][-1]["reason"] == "Engine failed: RuntimeError"
