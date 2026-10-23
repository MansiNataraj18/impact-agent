import importlib.util
from pathlib import Path

from impact_agent.render.strip import strip_impact_sections

ROOT = Path(__file__).resolve().parent.parent.parent
spec = importlib.util.spec_from_file_location("demo_core", ROOT / "scripts" / "demo_core.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)

INPUT = demo.read_sample()
PART_PREFIXES = [
    "Risk: ",
    "Summary: ",
    "Direct Impact:",
    "Potential Impact:",
    "Tests to Run:",
    "Warnings and Unresolved:",
]


def test_four_blocks_at_the_right_positions_with_all_parts_in_order():
    out_lines = demo.run_demo().split("\n")
    in_lines = INPUT.split("\n")
    for number, (position, anchor) in demo.ANCHORS.items():
        header = out_lines.index(f"Impact Analysis (Change {number}):")
        assert out_lines[header - 1] == in_lines[position - 1]
        parts = [
            next(i for i in range(header, header + 40) if out_lines[i].startswith(prefix))
            for prefix in PART_PREFIXES
        ]
        assert parts == sorted(parts)
        assert out_lines.index(anchor, header) > parts[-1]
    headers = [line for line in out_lines if line.startswith("Impact Analysis (Change ")]
    assert headers == [f"Impact Analysis (Change {n}):" for n in (1, 2, 3, 4)]


def test_rollup_last_and_fixture_labelled():
    out = demo.run_demo()
    lines = out.split("\n")
    assert out.count("IMPACT ANALYSIS") == 1
    rollup = lines.index("15. IMPACT ANALYSIS")
    assert lines[rollup + 1] == "=" * len("15. IMPACT ANALYSIS")
    assert not any(line.startswith("Impact Analysis (Change") for line in lines[rollup:])
    assert "Graph source: dummy fixture (not a real code graph)" in lines[rollup:]


def test_additions_only_and_rerun():
    out = demo.run_demo()
    assert strip_impact_sections(out) == INPUT + "\n"  # input had no final newline (D7)
    again = demo.run_demo(strip_impact_sections(out))
    assert again == out
