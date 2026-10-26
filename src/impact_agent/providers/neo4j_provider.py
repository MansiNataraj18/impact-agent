"""Neo4j-backed GraphProvider (design only until graph access exists).

The provider never talks to a database itself. It is given a function that runs a Cypher query
and returns rows, so tests use hand-written rows and the real connection is a separate small step.

PLACEHOLDER: the Cypher below uses guessed labels, relationship types and property names.
Replace them with what the real graph uses before connecting.
"""

from collections.abc import Callable, Mapping, Sequence

from impact_agent.models.common import UnresolvedItem
from impact_agent.models.impact import (
    GraphSource,
    ImpactGraph,
    ImpactNode,
    ImpactQuery,
    NodeKind,
)

Row = Mapping[str, object]
RunQuery = Callable[[str, Mapping[str, object]], Sequence[Row]]

UNKNOWN = "unknown"
REASON_CHANGE_NOT_FOUND = "Changed symbol was not found in the code graph"
REASON_MISSING_KEY = "Cannot query the graph without {fields}"
REASON_BAD_ROW = "Graph row skipped: {detail}"

# PLACEHOLDER Cypher (labels, relationship types and properties are guesses).
FIND_CHANGED_QUERY = """
MATCH (c {project: $project, revision: $revision, file: $file, symbol: $symbol})
RETURN c.id AS id
LIMIT 1
"""

IMPACT_QUERY = """
MATCH (c {project: $project, revision: $revision, file: $file, symbol: $symbol})
MATCH path = (c)<-[:CALLS|TESTS|READS*1..4]-(n)
RETURN n.id AS id, n.kind AS kind, n.name AS name, n.service AS service,
       n.file AS location, length(path) AS depth,
       type(last(relationships(path))) AS relation
"""


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _to_node(row: Row) -> ImpactNode:
    return ImpactNode(
        id=str(row["id"]),
        kind=NodeKind(row["kind"]),  # an unknown kind raises ValueError
        name=str(row["name"]),
        service=_optional_text(row.get("service")),
        location=_optional_text(row.get("location")),
        depth=int(row["depth"]),  # type: ignore[call-overload]
        relation=str(row["relation"]).lower(),
    )


class Neo4jGraphProvider:
    """GraphProvider that reads the real code graph through an injected query function."""

    def __init__(self, run_query: RunQuery) -> None:
        self._run = run_query

    def get_impact(self, query: ImpactQuery) -> ImpactGraph:
        changed = "::".join(part or UNKNOWN for part in (query.service, query.file, query.symbol))

        missing = [name for name in ("file", "symbol") if not getattr(query, name)]
        if missing:
            return self._graph(changed, [], REASON_MISSING_KEY.format(fields=" and ".join(missing)))

        params = {
            "project": query.project,
            "revision": query.revision,
            "file": query.file,
            "symbol": query.symbol,
        }
        # An empty impact result is ambiguous: "nothing depends on it" or "not in the graph".
        if not self._run(FIND_CHANGED_QUERY, params):
            return self._graph(changed, [], REASON_CHANGE_NOT_FOUND)

        nodes: list[ImpactNode] = []
        skipped: list[str] = []
        for row in self._run(IMPACT_QUERY, params):
            try:
                nodes.append(_to_node(row))
            except (KeyError, ValueError, TypeError) as error:
                skipped.append(f"{error!r}")
        graph = self._graph(changed, nodes)
        graph.unresolved.extend(
            UnresolvedItem(
                scope="change",
                change_number=query.change_number,
                reason=REASON_BAD_ROW.format(detail=detail),
            )
            for detail in skipped
        )
        return graph

    @staticmethod
    def _graph(changed: str, nodes: list[ImpactNode], reason: str | None = None) -> ImpactGraph:
        unresolved = []
        if reason:
            unresolved.append(UnresolvedItem(scope="change", field="symbol", reason=reason))
        return ImpactGraph(
            changed=changed, nodes=nodes, source=GraphSource.GRAPH, unresolved=unresolved
        )
