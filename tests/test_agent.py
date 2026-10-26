import pytest

from impact_agent.agent import handle_tdd
from impact_agent.api.app import default_engine
from impact_agent.providers.fake import FakeGraphProvider


class FailingEngine:
    def enrich(self, tdd_text, parsed, graphs):
        raise RuntimeError("boom")


def enrich(text):
    return handle_tdd(text, provider=FakeGraphProvider("normal"), engine=default_engine())


def test_sample_gets_four_blocks_and_a_roll_up(sample_text):
    result = enrich(sample_text)
    assert result.count("Impact Analysis (Change ") == 4
    assert "15. IMPACT ANALYSIS" in result
    assert "dummy fixture" in result


def test_running_on_its_own_output_is_identical(sample_text):
    first = enrich(sample_text)
    assert enrich(first) == first


def test_correlation_id_is_accepted(sample_text):
    result = handle_tdd(
        sample_text,
        provider=FakeGraphProvider("normal"),
        engine=default_engine(),
        correlation_id="abc",
    )
    assert "15. IMPACT ANALYSIS" in result


def test_engine_failure_raises_instead_of_returning_unenriched_text(sample_text):
    with pytest.raises(RuntimeError, match="Impact analysis failed"):
        handle_tdd(sample_text, provider=FakeGraphProvider("normal"), engine=FailingEngine())
