from collections.abc import Mapping

from impact_agent.models.impact import ImpactGraph, ImpactQuery
from impact_agent.providers.fixtures import SCENARIOS

UNKNOWN = "unknown"


def _check(scenario: str) -> None:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario!r}; expected one of {sorted(SCENARIOS)}")


class FakeGraphProvider:
    """GraphProvider that returns fixture (dummy) graphs. Pure and deterministic."""

    def __init__(self, scenario: str = "normal", by_symbol: Mapping[str, str] | None = None):
        _check(scenario)
        self._scenario = scenario
        self._by_symbol = dict(by_symbol or {})
        for name in self._by_symbol.values():
            _check(name)

    def get_impact(self, query: ImpactQuery) -> ImpactGraph:
        changed = "::".join(part or UNKNOWN for part in (query.service, query.file, query.symbol))
        scenario = (
            self._by_symbol.get(query.symbol, self._scenario) if query.symbol else self._scenario
        )
        return SCENARIOS[scenario](changed)
