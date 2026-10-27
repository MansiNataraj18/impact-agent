import logging

import pytest

from impact_agent.api.app import FAKE_GRAPH_WARNING, TTL_ENV_VAR, create_app, ttl_from_env
from impact_agent.api.idempotency import DEFAULT_TTL_SECONDS
from impact_agent.providers.fake import FakeGraphProvider


def test_ttl_defaults_to_one_hour(monkeypatch):
    monkeypatch.delenv(TTL_ENV_VAR, raising=False)
    assert ttl_from_env() == DEFAULT_TTL_SECONDS == 3600.0


def test_ttl_from_env(monkeypatch):
    monkeypatch.setenv(TTL_ENV_VAR, "120")
    assert ttl_from_env() == 120.0
    monkeypatch.setenv(TTL_ENV_VAR, "none")
    assert ttl_from_env() is None


@pytest.mark.parametrize("bad", ["abc", "0", "-5"])
def test_ttl_rejects_bad_values(monkeypatch, bad):
    monkeypatch.setenv(TTL_ENV_VAR, bad)
    with pytest.raises(ValueError):
        ttl_from_env()


def test_default_provider_logs_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="impact_agent.api.app"):
        create_app()
    assert FAKE_GRAPH_WARNING in caplog.text


def test_explicit_provider_does_not_warn(caplog):
    with caplog.at_level(logging.WARNING, logger="impact_agent.api.app"):
        create_app(provider=FakeGraphProvider("normal"))
    assert FAKE_GRAPH_WARNING not in caplog.text
