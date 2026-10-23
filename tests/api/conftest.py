from pathlib import Path

import pytest

SAMPLE = Path(__file__).resolve().parent.parent / "fixtures" / "tdd" / "sample_input.txt"


@pytest.fixture(scope="session")
def sample_text() -> str:
    with open(SAMPLE, encoding="utf-8", newline="") as handle:
        return handle.read()
