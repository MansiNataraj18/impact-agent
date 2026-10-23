"""DUMMY stand-in for the orchestrator that sits between the TDD generator and the coding agent."""

from typing import Protocol

from impact_agent.stubs import coding_agent

GENERATED_ID = "orchestrator-generated"
APPROVED_ID = "orchestrator-approved"
ENDPOINT = "/impact"


class HttpClient(Protocol):
    def post(self, url: str, json: dict): ...


def _submit(client: HttpClient, tdd_text: str, correlation_id: str) -> str:
    response = client.post(ENDPOINT, json={"tdd_text": tdd_text, "correlation_id": correlation_id})
    if response.status_code != 200:
        raise RuntimeError(f"Impact API returned HTTP {response.status_code}")
    return response.json()["tdd_text"]


def run(tdd_text: str, client: HttpClient) -> str:
    """Submit the generated TDD, submit the returned text as 'approved', then hand it on."""
    enriched = _submit(client, tdd_text, GENERATED_ID)
    approved = _submit(client, enriched, APPROVED_ID)
    if approved != enriched:
        raise ValueError("Resubmitting the enriched TDD changed it; the rerun is not stable.")
    return coding_agent.receive(approved)
