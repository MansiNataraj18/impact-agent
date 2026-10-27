"""Run the full pipeline (parse -> fake graph -> dummy LLM -> render) on a folder of TDDs.

Run from the repository root:
  uv run python scripts/run_dummy_tdds.py [folder] [--scenario normal] [--out out_dir]

Everything is dummy: fixture graphs and a fake LLM. With --out, each rendered TDD is written
to <out>/<name>.out.txt; without it only a summary is printed.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from impact_agent.api.app import default_engine  # noqa: E402
from impact_agent.api.pipeline import run_pipeline  # noqa: E402
from impact_agent.api.schemas import ImpactRequest  # noqa: E402
from impact_agent.providers.fake import FakeGraphProvider  # noqa: E402
from impact_agent.providers.fixtures import SCENARIOS  # noqa: E402

DEFAULT_FOLDER = ROOT / "tests" / "fixtures" / "dummy_tdds"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", nargs="?", default=str(DEFAULT_FOLDER))
    parser.add_argument("--scenario", default="normal", choices=sorted(SCENARIOS))
    parser.add_argument("--out", help="write rendered output files to this folder")
    args = parser.parse_args()

    files = sorted(Path(args.folder).glob("*.txt"))
    if not files:
        print(f"No .txt files found in {args.folder!r}.")
        return
    out = Path(args.out) if args.out else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    provider = FakeGraphProvider(args.scenario)
    for path in files:
        with open(path, encoding="utf-8", newline="") as handle:
            text = handle.read()
        response = run_pipeline(ImpactRequest(tdd_text=text), provider, default_engine())
        print(f"{path.name}: status={response.status.value} unresolved={len(response.unresolved)}")
        for item in response.unresolved:
            print(
                f"    - {item.scope} change={item.change_number} field={item.field}: {item.reason}"
            )
        if out:
            with open(out / f"{path.stem}.out.txt", "w", encoding="utf-8", newline="") as handle:
                handle.write(response.tdd_text)


if __name__ == "__main__":
    main()
