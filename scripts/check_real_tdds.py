"""Parse every .txt TDD in a folder and summarise what could not be read.

Run from the repository root:  python scripts/check_real_tdds.py local_tdds
Keep real TDDs in a folder that is NOT committed (for example local_tdds/).
"""

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from impact_agent.parser.tdd_parser import parse_tdd  # noqa: E402


def read_text(path: Path) -> str:
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def main(folder: str) -> None:
    files = sorted(Path(folder).glob("*.txt"))
    if not files:
        print(f"No .txt files found in {folder!r}.")
        return
    reasons: Counter[str] = Counter()
    for path in files:
        parsed = parse_tdd(read_text(path))
        print(
            f"{path.name}: sections={parsed.last_section_number} "
            f"changes={len(parsed.changes)} "
            f"no_change={len(parsed.no_change_services)} "
            f"tests={len(parsed.planned_tests)} "
            f"unresolved={len(parsed.unresolved)}"
        )
        for item in parsed.unresolved:
            reasons[f"{item.scope}/{item.field}: {item.reason}"] += 1
            print(
                f"    - {item.scope} change={item.change_number} field={item.field}: {item.reason}"
            )
    print("\nMost common problems:")
    for reason, count in reasons.most_common():
        print(f"  {count:3d}  {reason}")
    if not reasons:
        print("  none")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "local_tdds")
