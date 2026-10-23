# Fixtures

Everything here is **dummy data**. Graph fixtures are labelled `source = "fixture"`, and the
rendered roll-up prints `Graph source: dummy fixture (not a real code graph)`.

## Fake graph provider

`impact_agent.providers.fake.FakeGraphProvider(scenario="normal", by_symbol=None)` implements the
`GraphProvider` protocol from contract section 8. It is pure and deterministic. For a query it
builds `changed` as `{service}::{file}::{symbol}` (`unknown` for a missing part) and returns the
fixture graph for `by_symbol.get(query.symbol, scenario)`. An unknown scenario name raises
`ValueError` when the provider is constructed.

`by_symbol` maps a changed symbol to a scenario name, so one TDD can exercise several behaviours:

```python
FakeGraphProvider("normal", by_symbol={"validateEmails": "empty"})
```

The builders live in `src/impact_agent/providers/fixtures.py`.

| Scenario | What it represents | Behaviour it exercises |
|---|---|---|
| `normal` | Two direct callers in `ui`, a depth 2 `ui` class, an `accounts-service` API (depth 3), a `candidate-service` reader (depth 4) and one `ui` test. Every node has a location. | The full happy path: direct, potential and test groups, no warnings. |
| `no_tests` | The `normal` graph without the test node. | The "No tests cover this change" warning. |
| `empty` | The symbol is known but nothing depends on it. | Empty-graph path: no LLM call, low risk, deterministic summary and warnings. |
| `cross_service` | Nodes in `ui`, `accounts-service`, `candidate-service` and `reports-api` at depths 1 to 3, plus a test. | Several services in one result and "TDD Claims vs Graph" findings (`needs_review` for a service the TDD says has no change). |
| `missing_evidence` | Nodes without a location, a node without a service, and a graph-level unresolved item for the changed symbol. | Missing-location and unresolved-location warnings, and `None` services in the sort order. |

## Sample TDD files

Both live in `tests/fixtures/tdd/`:

- `sample_input.txt`: a TDD with 14 sections and four changes (1 modify, 2 create, 3 and 4
  reference). It has form feeds and no final newline. Never open and re-save it; read it as-is.
- `sample_expected_output.txt`: the expected output for the sample input.
