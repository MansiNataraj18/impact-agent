"""Regenerate tests/fixtures/tdd/sample_expected_output.txt from the real pipeline.

Run from the repository root:  uv run python scripts/regenerate_expected_output.py
Pipeline: sample input -> API (real parser, fake provider, dummy LLM) -> output. Review the diff
before committing. The output is written byte-exact (no newline translation).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from impact_agent.api.app import create_app  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "tdd"
SAMPLE_INPUT = FIXTURES / "sample_input.txt"
EXPECTED_OUTPUT = FIXTURES / "sample_expected_output.txt"


def generate() -> str:
    with open(SAMPLE_INPUT, encoding="utf-8", newline="") as handle:
        text = handle.read()
    response = TestClient(create_app()).post("/impact", json={"tdd_text": text})
    body = response.json()
    if response.status_code != 200 or body["status"] != "ok":
        raise SystemExit(f"Pipeline did not succeed: HTTP {response.status_code}, {body['status']}")
    return body["tdd_text"]


if __name__ == "__main__":
    with open(EXPECTED_OUTPUT, "w", encoding="utf-8", newline="") as handle:
        handle.write(generate())
    print(f"Wrote {EXPECTED_OUTPUT.relative_to(ROOT)}")
