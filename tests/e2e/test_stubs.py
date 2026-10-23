import pytest

from impact_agent.stubs import coding_agent, orchestrator

ENRICHED = """\
Title
Impact Analysis (Change 1):
Risk: Low
Impact Analysis (Change 2):
Risk: Low

15. IMPACT ANALYSIS
===================
Overall Risk: Low
Summary: s
Graph source: x

Impact by Change:
- Change 1 (modify) f: Low

Tests to Run:
- first test (a.py)
- second test that is long
  and wraps

TDD Claims vs Graph:
- None.
"""


def test_receive_summarises_enriched_text():
    summary = coding_agent.receive(ENRICHED)
    assert summary == (
        "Coding agent received a TDD with 2 impact block(s).\n"
        "Roll-up: 15. IMPACT ANALYSIS\n"
        "Overall Risk: Low\n"
        "Tests to run:\n"
        "- first test (a.py)\n"
        "- second test that is long and wraps"
    )


def test_receive_handles_text_without_rollup():
    assert coding_agent.receive("plain text") == (
        "Coding agent received a TDD with 0 impact block(s).\nNo impact roll-up found."
    )


def test_receive_handles_crlf():
    assert "Overall Risk: Low" in coding_agent.receive(ENRICHED.replace("\n", "\r\n"))


class Response:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self._text = text

    def json(self):
        return {"tdd_text": self._text}


class EchoClient:
    def __init__(self, status_code=200, mutate=False):
        self.status_code = status_code
        self.mutate = mutate
        self.posted = []

    def post(self, url, json):
        self.posted.append((url, json))
        text = json["tdd_text"]
        return Response(self.status_code, text + "x" if self.mutate else text)


def test_orchestrator_submits_twice_with_labelled_ids():
    client = EchoClient()
    summary = orchestrator.run(ENRICHED, client)
    assert [p[0] for p in client.posted] == ["/impact", "/impact"]
    assert [p[1]["correlation_id"] for p in client.posted] == [
        "orchestrator-generated",
        "orchestrator-approved",
    ]
    assert summary == coding_agent.receive(ENRICHED)


def test_orchestrator_rejects_an_unstable_rerun():
    with pytest.raises(ValueError):
        orchestrator.run(ENRICHED, EchoClient(mutate=True))


def test_orchestrator_reports_http_errors_without_body():
    with pytest.raises(RuntimeError, match="HTTP 500"):
        orchestrator.run(ENRICHED, EchoClient(status_code=500))
