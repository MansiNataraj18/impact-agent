"""Standalone demo of the Person 1 core: hand-built ParsedTDD, fake graph data, fake LLM.

Run from the repository root:  uv run python scripts/demo_core.py
No parser, provider or API is involved; all data below is built by hand for the sample TDD.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from impact_agent.core.engine import DefaultImpactEngine  # noqa: E402
from impact_agent.core.llm import FakeLLM  # noqa: E402
from impact_agent.models.impact import ImpactGraph, ImpactNode  # noqa: E402
from impact_agent.models.parsed_tdd import ParsedChange, ParsedTDD  # noqa: E402

SAMPLE_INPUT = ROOT / "tests" / "fixtures" / "tdd" / "sample_input.txt"

UI_DIR = "src/common/accounts/client/components/SettingsForm/sections/AtsIntegrationSection"
VIEW = f"{UI_DIR}/view.tsx"
HANDLER = "src/main/kotlin/com/asurint/candidate/handlers/commands/SendDirectRequestEmailHandler.kt"

# change number -> (insert_before_line, text expected on that line)
ANCHORS = {
    1: (137, "Change 2: handleCcEmailAddressesBlur (create)"),
    2: (171, "Change 3: ReportEventsCCEmailAddressSettings (reference (read, not changed))"),
    3: (188, "accounts-service — no change"),
    4: (220, "reports-api — no change"),
}


def check_anchors(text: str) -> None:
    lines = text.split("\n")
    for number, (position, expected) in ANCHORS.items():
        actual = lines[position] if position < len(lines) else "<past end of text>"
        if actual != expected:
            raise SystemExit(
                f"Anchor mismatch for Change {number}: line {position} is {actual!r}, "
                f"expected {expected!r}. The sample input or the hand-built positions changed."
            )


def build_parsed() -> ParsedTDD:
    return ParsedTDD(
        title="Sample TDD",
        changes=[
            ParsedChange(
                number=1, service="ui", file=VIEW, symbol="handleCcEmailAddressesBlur",
                action="modify", code_check="VERIFIED",
                summary="Preserve semicolon separators when the CC email field loses focus.",
                insert_before_line=ANCHORS[1][0],
            ),
            ParsedChange(
                number=2, service="ui", file=f"{UI_DIR}/view.test.tsx", symbol="view.test.tsx",
                action="create", code_check="NEW", insert_before_line=ANCHORS[2][0],
            ),
            ParsedChange(
                number=3, service="ui", symbol="ReportEventsCCEmailAddressSettings",
                file="src/apps/client/modules/Settings/pages/ApplicationSettings/components/"
                "ReportEventsCCEmailAddressSettings.tsx",
                action="reference", code_check="VERIFIED", insert_before_line=ANCHORS[3][0],
            ),
            ParsedChange(
                number=4, service="candidate-service", file=HANDLER, symbol="validateEmails",
                action="reference", code_check="VERIFIED", insert_before_line=ANCHORS[4][0],
            ),
        ],
        no_change_services=["accounts-service", "reports-api", "pdf-service"],
        last_section_number=14,
    )  # fmt: skip


def _node(id, name, service, location, depth, relation, kind="method"):
    return ImpactNode(
        id=id, kind=kind, name=name, service=service, location=location, depth=depth,
        relation=relation,
    )  # fmt: skip


def build_graphs() -> dict[int, ImpactGraph]:
    """Fixture graph for the one modify change (no test nodes, as in the sample)."""
    return {
        1: ImpactGraph(
            changed=f"ui::{VIEW}::handleCcEmailAddressesBlur",
            source="fixture",
            nodes=[
                _node("ui.view", "AtsIntegrationSectionView", "ui", "view.tsx", 1, "registers",
                      kind="class"),
                _node("ui.change", "atsIntegrationChange", "ui", "view.tsx", 1, "calls"),
                _node("ui.form", "SettingsForm", "ui", "SettingsForm/index.tsx", 2, "calls",
                      kind="class"),
                _node("acc.input", "AtsIntegrationSettingsInput.sendReportRequestedLinkCcEmail"
                      "Addresses", "accounts-service", None, 3, "stores", kind="api"),
                _node("cand.validate", "SendDirectRequestEmailHandler.validateEmails",
                      "candidate-service", "SendDirectRequestEmailHandler.kt", 4, "reads"),
            ],
        )
    }  # fmt: skip


def build_llm() -> FakeLLM:
    return FakeLLM(
        json.dumps(
            {
                "summary": (
                    "The change is small and local to the blur handler, but it alters the stored "
                    "format of the CC email field, which accounts-service stores and "
                    "candidate-service reads."
                ),
                "risk_level": "medium",
                "reasons": {
                    "ui.view": "renders the field and registers the blur handler",
                    "ui.change": "receives the rejoined string and updates the form state",
                    "ui.form": "submits the form state on save",
                    "acc.input": "stored as a plain string; persistence code was not inspected",
                    "cand.validate": "reads the stored value and splits on [;,]+",
                },
            }
        )
    )


def read_sample() -> str:
    """Read the sample without translating line endings."""
    with open(SAMPLE_INPUT, encoding="utf-8", newline="") as handle:
        return handle.read()


def run_demo(text: str | None = None) -> str:
    text = read_sample() if text is None else text
    check_anchors(text)
    engine = DefaultImpactEngine(build_llm())
    return engine.enrich(text, build_parsed(), build_graphs())


if __name__ == "__main__":
    sys.stdout.write(run_demo())
