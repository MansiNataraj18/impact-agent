"""Run the orchestrator and coding-agent stubs against the API in-process (no network).

Run from the repository root:  uv run python scripts/run_stub_flow.py
Everything here is dummy data: fixture graphs and a fake LLM.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from impact_agent.api.app import create_app  # noqa: E402
from impact_agent.stubs import orchestrator  # noqa: E402

SAMPLE_INPUT = ROOT / "tests" / "fixtures" / "tdd" / "sample_input.txt"


def read_sample() -> str:
    """Read the sample without translating line endings."""
    with open(SAMPLE_INPUT, encoding="utf-8", newline="") as handle:
        return handle.read()


def run_flow(text: str | None = None) -> str:
    client = TestClient(create_app())
    return orchestrator.run(read_sample() if text is None else text, client)


if __name__ == "__main__":
    print(run_flow())
