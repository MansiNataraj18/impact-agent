import importlib.util
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from impact_agent.api.app import create_app
from impact_agent.render.strip import strip_impact_sections
from impact_agent.stubs import coding_agent, orchestrator

ROOT = Path(__file__).resolve().parent.parent.parent
INSERT_BEFORE = {1: 137, 2: 171, 3: 188, 4: 220}  # lines of the sample input


def load_stub_flow():
    spec = importlib.util.spec_from_file_location(
        "run_stub_flow", ROOT / "scripts" / "run_stub_flow.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


@pytest.fixture(scope="module")
def output(client, sample_text):
    response = client.post("/impact", json={"tdd_text": sample_text})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    return response.json()["tdd_text"]


def test_additions_only(output, sample_text):
    original = sample_text.split("\n")
    out_lines = output.split("\n")
    position = 0
    for line in out_lines:
        if position < len(original) and line == original[position]:
            position += 1
    assert position == len(original)  # every original line, in order (final newline aside)
    assert strip_impact_sections(output) == sample_text + "\n"


def test_blocks_are_placed_before_the_right_lines(output, sample_text):
    original = sample_text.split("\n")
    out_lines = output.split("\n")
    for number, position in INSERT_BEFORE.items():
        header = out_lines.index(f"Impact Analysis (Change {number}):")
        following = next(
            i for i in range(header + 1, len(out_lines)) if out_lines[i] == original[position]
        )
        assert out_lines[header - 1] == original[position - 1]
        assert all(not re.match(r"^Change \d+:", out_lines[i]) for i in range(header, following))
    headers = [x for x in out_lines if x.startswith("Impact Analysis (Change ")]
    assert headers == [f"Impact Analysis (Change {n}):" for n in (1, 2, 3, 4)]


def test_rollup_is_last_and_fixture_is_labelled(output):
    lines = output.split("\n")
    rollup = lines.index("15. IMPACT ANALYSIS")
    assert lines[rollup + 1] == "=" * len("15. IMPACT ANALYSIS")
    assert not any(x.startswith("Impact Analysis (Change") for x in lines[rollup:])
    assert "Graph source: dummy fixture (not a real code graph)" in lines[rollup:]
    assert output.count("IMPACT ANALYSIS") == 1


def test_resubmitting_the_output_is_byte_identical(client, output):
    again = client.post("/impact", json={"tdd_text": output}).json()["tdd_text"]
    assert again == output


def test_stub_flow_submissions_agree(client, sample_text):
    first = client.post("/impact", json={"tdd_text": sample_text}).json()["tdd_text"]
    second = client.post("/impact", json={"tdd_text": first}).json()["tdd_text"]
    assert first == second
    summary = orchestrator.run(sample_text, client)
    assert summary == coding_agent.receive(first)
    assert "4 impact block(s)" in summary
    assert "Roll-up: 15. IMPACT ANALYSIS" in summary
    assert "Overall Risk: Medium" in summary
    assert "Tests to run:" in summary


def test_stub_flow_script_runs(sample_text):
    assert "Roll-up: 15. IMPACT ANALYSIS" in load_stub_flow().run_flow()


def test_output_matches_the_golden_file_byte_for_byte(output):
    path = ROOT / "tests" / "fixtures" / "tdd" / "sample_expected_output.txt"
    with open(path, encoding="utf-8", newline="") as handle:
        assert output == handle.read()
