from pathlib import Path

import pytest

from impact_agent.api.app import default_engine
from impact_agent.api.pipeline import run_pipeline
from impact_agent.api.schemas import ImpactRequest, ResponseStatus
from impact_agent.providers.fake import FakeGraphProvider
from impact_agent.providers.fixtures import SCENARIOS

FOLDER = Path(__file__).resolve().parent.parent / "fixtures" / "dummy_tdds"
FILES = sorted(FOLDER.glob("*.txt"))


def run(path: Path, scenario: str):
    with open(path, encoding="utf-8", newline="") as handle:
        text = handle.read()
    return text, run_pipeline(
        ImpactRequest(tdd_text=text), FakeGraphProvider(scenario), default_engine()
    )


def test_dummy_tdds_exist():
    assert len(FILES) >= 4


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_every_dummy_tdd_runs_and_is_stable(path, scenario):
    text, first = run(path, scenario)
    expected = ResponseStatus.PARTIAL if "no_testing" in path.name else ResponseStatus.OK
    assert first.status is expected
    assert first.tdd_text.startswith(text.rstrip("\r\n")[:200])
    _, second = run_from_text(first.tdd_text, scenario)
    assert second.tdd_text == first.tdd_text


def run_from_text(text: str, scenario: str):
    response = run_pipeline(
        ImpactRequest(tdd_text=text), FakeGraphProvider(scenario), default_engine()
    )
    return text, response
