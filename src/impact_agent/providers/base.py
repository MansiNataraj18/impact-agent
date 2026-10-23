from typing import Protocol

from impact_agent.models.impact import ImpactGraph, ImpactQuery


class GraphProvider(Protocol):
    def get_impact(self, query: ImpactQuery) -> ImpactGraph: ...
