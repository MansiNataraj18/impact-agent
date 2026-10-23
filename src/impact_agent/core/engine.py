from collections.abc import Mapping
from typing import Protocol

from impact_agent.core.analyzer import analyze_tdd
from impact_agent.core.llm import LLMClient
from impact_agent.models.impact import ImpactGraph
from impact_agent.models.parsed_tdd import ParsedTDD
from impact_agent.render.renderer import render_tdd
from impact_agent.render.strip import strip_impact_sections

ERROR_UNSTRIPPED = "Input still contains impact sections; call strip_impact_sections first."


class ImpactEngine(Protocol):
    def enrich(
        self, tdd_text: str, parsed: ParsedTDD, graphs: Mapping[int, ImpactGraph]
    ) -> str: ...


class DefaultImpactEngine:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def enrich(self, tdd_text: str, parsed: ParsedTDD, graphs: Mapping[int, ImpactGraph]) -> str:
        # The positions in `parsed` refer to the stripped text, so the caller must strip first.
        if strip_impact_sections(tdd_text) != tdd_text:
            raise ValueError(ERROR_UNSTRIPPED)
        result = analyze_tdd(parsed, graphs, self._llm)
        return render_tdd(tdd_text, parsed, result)
