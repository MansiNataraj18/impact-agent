from impact_agent.api.app import default_engine
from impact_agent.api.pipeline import run_pipeline
from impact_agent.api.schemas import ImpactRequest, ResponseStatus
from impact_agent.providers.fake import FakeGraphProvider


class RecordingProvider(FakeGraphProvider):
    def __init__(self):
        super().__init__("normal")
        self.queries = []

    def get_impact(self, query):
        self.queries.append(query)
        return super().get_impact(query)


class FailingProvider:
    def get_impact(self, query):
        raise RuntimeError("secret detail that must not leak")


class FailingEngine:
    def enrich(self, tdd_text, parsed, graphs):
        raise KeyError("boom")


def run(text, provider=None, engine=None, **kwargs):
    request = ImpactRequest(tdd_text=text, **kwargs)
    return run_pipeline(
        request, provider or FakeGraphProvider("normal"), engine or default_engine()
    )


def test_success_on_sample(sample_text):
    response = run(sample_text, correlation_id="c1")
    assert response.status is ResponseStatus.OK
    assert response.schema_version == "1"
    assert response.correlation_id == "c1"
    assert response.unresolved == []
    assert response.tdd_text.count("Impact Analysis (Change ") == 4
    assert "15. IMPACT ANALYSIS" in response.tdd_text
    assert "Graph source: dummy fixture (not a real code graph)" in response.tdd_text


def test_provider_failure_gives_partial_and_continues(sample_text):
    response = run(sample_text, provider=FailingProvider())
    assert response.status is ResponseStatus.PARTIAL
    assert [(u.scope, u.change_number, u.field, u.reason) for u in response.unresolved] == [
        ("change", 1, "graph", "Graph provider failed: RuntimeError")
    ]
    assert "secret detail" not in response.tdd_text
    assert response.tdd_text.count("Impact Analysis (Change ") == 4
    assert "No graph was supplied for this change." in response.tdd_text


def test_engine_failure_gives_error_with_original_text(sample_text):
    response = run(sample_text, engine=FailingEngine())
    assert response.status is ResponseStatus.ERROR
    assert response.tdd_text == sample_text
    assert [(u.scope, u.reason) for u in response.unresolved] == [
        ("tdd", "Engine failed: KeyError")
    ]


def test_garbage_text_is_partial_and_unchanged():
    text = "just some notes\nwith no sections"
    response = run(text)
    assert response.status is ResponseStatus.PARTIAL
    assert response.tdd_text == text
    assert [u.reason for u in response.unresolved] == ["No numbered sections found"]


def test_metadata_defaults_and_overrides(sample_text):
    provider = RecordingProvider()
    run(sample_text, provider=provider)
    query = provider.queries[0]
    assert (query.project, query.repository, query.revision) == (
        "dummy-project",
        "dummy-repo",
        "dummy-revision",
    )
    assert (query.change_number, query.service, query.symbol) == (
        1,
        "ui",
        "handleCcEmailAddressesBlur",
    )
    assert len(provider.queries) == 1  # only the modify change is looked up

    provider = RecordingProvider()
    run(sample_text, provider=provider, project="p", repository="r", revision="v")
    query = provider.queries[0]
    assert (query.project, query.repository, query.revision) == ("p", "r", "v")


def test_input_with_existing_impact_sections_is_not_duplicated(sample_text):
    first = run(sample_text).tdd_text
    second = run(first).tdd_text
    assert second == first
    assert second.count("Impact Analysis (Change 1):") == 1
    assert second.count("IMPACT ANALYSIS") == 1
