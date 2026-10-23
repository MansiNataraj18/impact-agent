import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "scripts" / "demo_core.py"


def load_demo():
    spec = importlib.util.spec_from_file_location("demo_core", DEMO)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_function_runs():
    out = load_demo().run_demo()
    assert "Impact Analysis (Change 1):" in out
    assert "15. IMPACT ANALYSIS" in out


def test_demo_script_runs_as_a_program():
    done = subprocess.run(
        [sys.executable, str(DEMO)], capture_output=True, text=True, cwd=ROOT, check=False
    )
    assert done.returncode == 0, done.stderr
    assert "Graph source: dummy fixture (not a real code graph)" in done.stdout


def test_demo_stops_clearly_on_anchor_mismatch():
    demo = load_demo()
    text = demo.read_sample()
    try:
        demo.run_demo("\n" + text)
    except SystemExit as exc:
        assert "Anchor mismatch for Change 1" in str(exc)
    else:
        raise AssertionError("expected SystemExit")
