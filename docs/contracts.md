# Impact Agent Contract

Status: APPROVED. Shared by Person 1 and Person 2. Neither person edits this file alone; changes need both approvals.
Contract version: `1`

## 1. External contract

- Input: TDD text plus optional metadata (project, repository, revision, correlation ID). Metadata may use dummy defaults.
- Output: the same TDD text with impact content added. All original text is preserved.
- The only additions are an `Impact Analysis (Change N):` block after each change's `Done when:` list, and a final roll-up section numbered after the last section found in the TDD.
- Rerunning must not create duplicate impact sections.
- Dummy graph data must be labelled as fixture data.
- The LLM writes only the summary, the risk assessment and one-line reasons. Code does everything else. The LLM can never add, remove or move items.

### 1.1 API shape

`POST /impact`

Request (JSON transport wrapper; the TDD itself stays plain text):

| Field | Type | Required | Notes |
|---|---|---|---|
| `tdd_text` | string | yes | The TDD, unmodified |
| `project` | string | no | Dummy default allowed |
| `repository` | string | no | Dummy default allowed |
| `revision` | string | no | Dummy default allowed |
| `correlation_id` | string | no | Used for idempotency |

Response:

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | `"1"` |
| `status` | string | `ok`, `partial` (some items unresolved) or `error` |
| `correlation_id` | string or null | Echoed back |
| `tdd_text` | string | The enriched TDD |
| `unresolved` | list of UnresolvedItem | Items that could not be parsed or analysed |

Errors: empty or non-string `tdd_text` is a client error (422). Internal failures return `status = "error"` and never a partly written TDD.

## 2. Output format

Per-change block (all six parts always present, in this order; use `None.` where empty):

```
Impact Analysis (Change N):
Risk: ...
Summary: ...
Direct Impact:
- ...
Potential Impact:
- ...
Tests to Run:
- ...
Warnings and Unresolved:
- ...
```

Roll-up, appended after the last section (the number below is illustrative):

```
15. IMPACT ANALYSIS
===================
Overall Risk: ...
Summary: ...
Graph source: ...

Impact by Change:
- Change N (action) symbol: <risk text>

Tests to Run:
- ...

TDD Claims vs Graph:
- ...

Warnings and Unresolved Items:
- ...
```

Layout rules:
- Plain text, flush left, wrapped at about 96 characters.
- Roll-up heading underlined with `=` equal to the heading length.
- The roll-up number is `last_section_number + 1`.
- Fixture data prints `Graph source: dummy fixture (not a real code graph)`.

## 3. Enumerations

| Name | Values |
|---|---|
| `ChangeAction` | `modify`, `create`, `reference` |
| `CodeCheck` | `VERIFIED`, `NEW` (or null if not parsed) |
| `NodeKind` | `method`, `function`, `class`, `service`, `api`, `event`, `database`, `test` |
| `RiskLevel` | `low`, `medium`, `high` (rendered `Low`, `Medium`, `High`) |
| `ExplanationStatus` | `explained`, `not_applicable`, `skipped` |
| `GraphSource` | `fixture`, `graph` |
| `ClaimFinding` | `consistent`, `needs_review` |
| `ResponseStatus` | `ok`, `partial`, `error` |

Fallback risk when an LLM risk is missing or invalid: `medium`.

Risk text for changes that are not analysed:
- `create`: `Not applicable (new file, not in the dependency graph)`
- `reference`: `None (read only, no change proposed)`

## 4. Parser models (owned by Person 2)

### UnresolvedItem
| Field | Type | Notes |
|---|---|---|
| `scope` | `tdd`, `section`, `change` | Where the problem is |
| `change_number` | int or null | Set when `scope = change` |
| `field` | string or null | For example `file`, `symbol`, `service` |
| `reason` | string | Plain-language reason |
| `line` | int or null | 0-based line index in the original text |

### PlannedTest
| Field | Type | Notes |
|---|---|---|
| `kind` | string | `regression`, `unit`, `edge_case`, `integration` or `other` |
| `description` | string | |
| `expected` | string or null | |
| `existing` | bool | True for tests marked EXISTING, false for TO ADD |

### ParsedChange
| Field | Type | Notes |
|---|---|---|
| `number` | int | The N in `Change N` |
| `service` | string or null | From the nearest preceding service heading |
| `file` | string or null | Never guessed |
| `symbol` | string or null | Never guessed |
| `action` | ChangeAction or null | |
| `code_check` | CodeCheck or null | |
| `summary` | string or null | Text of the change's `Change:` field, used in the LLM prompt |
| `insert_before_line` | int or null | See below |

`insert_before_line`: the 0-based index of the first original line after this change's block, counted in `text.split("\n")` on the exact text given to the parser. The renderer inserts the change's impact block immediately before that line. The renderer never parses the TDD; if this is null it adds a warning and skips the block.

### ParsedTDD
| Field | Type | Notes |
|---|---|---|
| `title` | string or null | |
| `summary` | string or null | |
| `changes` | list of ParsedChange | |
| `no_change_services` | list of string | Services the TDD declares as no change |
| `planned_tests` | list of PlannedTest | From Section 10 |
| `last_section_number` | int or null | Used to number the roll-up |
| `unresolved` | list of UnresolvedItem | |

Parser rules: work on a normalised working copy and map back to original line positions; never modify the original text; never guess a missing file, symbol, service or relationship; record it as unresolved instead.

## 5. Graph and explanation models (owned by Person 1)

### ImpactQuery (input to the provider)
| Field | Type | Notes |
|---|---|---|
| `change_number` | int | |
| `service` | string or null | |
| `file` | string or null | |
| `symbol` | string or null | |
| `project`, `repository`, `revision` | string or null | Dummy defaults allowed |

### ImpactNode
| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique within a graph |
| `kind` | NodeKind | |
| `name` | string | |
| `service` | string or null | Owning service |
| `location` | string or null | File or path |
| `depth` | int, at least 1 | 1 means directly affected |
| `relation` | string | How it depends on the previous node, for example `calls`, `tests`, `reads` |

### ImpactGraph
| Field | Type | Notes |
|---|---|---|
| `changed` | string | `service::file::symbol` of the change |
| `nodes` | list of ImpactNode | |
| `source` | GraphSource | `fixture` for dummy data |
| `unresolved` | list of UnresolvedItem | |

### AffectedItem
`node_id`, `name`, `kind`, `service` (or null), `location` (or null), `depth`, `reason` (one line).

### ImpactExplanation (one per change)
| Field | Type | Notes |
|---|---|---|
| `change_number` | int | |
| `status` | ExplanationStatus | |
| `reason` | string or null | Why it was not analysed or skipped |
| `changed_location` | string | |
| `risk_level` | RiskLevel or null | Null when not analysed |
| `summary` | string | |
| `directly_affected` | list of AffectedItem | Depth 1, excluding tests |
| `potentially_affected` | list of AffectedItem | Depth 2 or more, excluding tests |
| `tests_to_run` | list of AffectedItem | Nodes of kind `test`, at any depth |
| `warnings` | list of string | Code-generated |
| `graph_source` | GraphSource | |

### TddImpactResult (container for the whole TDD)
| Field | Type | Notes |
|---|---|---|
| `changes` | list of ImpactExplanation | One per ParsedChange, same order |
| `overall_risk` | RiskLevel or null | Highest per-change risk; null if nothing was analysed |
| `summary` | string | |
| `graph_source` | GraphSource | `fixture` if any graph was fixture data |
| `tests_to_run` | list of string | Combined across changes, no duplicates |
| `claims_vs_graph` | list of ClaimCheck | |
| `warnings` | list of string | |

ClaimCheck: `service`, `tdd_claim` (for example `no change`), `finding` (ClaimFinding), `note`.

## 6. Deterministic rules

- **Grouping**: every graph node goes into exactly one group. Kind `test` goes to tests at any depth; otherwise depth 1 is direct and depth 2 or more is potential. Order by depth, then service, then name, then id. Duplicate ids collapse to the first.
- **Which changes are analysed**: only `modify`. `create` and `reference` get `not_applicable`.
- **TDD Claims vs Graph**: for each service in `no_change_services`, the finding is `needs_review` if any graph node belongs to that service, otherwise `consistent`. No LLM involvement in the finding.
- **Overall risk**: the highest per-change `risk_level`.
- **Warnings** (code-generated, fixed wording):
  - No test nodes for an analysed change: `No tests cover this change; add the regression test before merging.`
  - Empty graph, nodes without location, or unresolved changed location.
  - Parser-unresolved items for the change.
- **Empty graph**: no LLM call; deterministic summary; `risk_level = low`.

## 7. LLM contract

- The prompt contains only the change summary, the changed location and the already-grouped nodes.
- The LLM must return strict JSON: `summary`, `risk_level`, and `reasons` keyed by node id.
- Unknown node ids are dropped with a warning. An invalid risk becomes `medium`. Items with no reason get a deterministic placeholder.
- Malformed output (invalid JSON or wrong shape): fall back to a deterministic summary, `medium` risk and a warning that explanations are unavailable. Do not raise.

## 8. Interfaces

```python
def parse_tdd(text: str) -> ParsedTDD: ...                       # Person 2

class GraphProvider(Protocol):                                   # Person 2 implements
    def get_impact(self, query: ImpactQuery) -> ImpactGraph: ...

class LLMClient(Protocol):                                       # Person 1
    def complete(self, prompt: str) -> str: ...

def strip_impact_sections(text: str) -> str: ...                 # Person 1

class ImpactEngine(Protocol):                                    # Person 1 implements
    def enrich(
        self, tdd_text: str, parsed: ParsedTDD, graphs: Mapping[int, ImpactGraph]
    ) -> str: ...
```

Pipeline order: `strip_impact_sections` then `parse_tdd`, then `GraphProvider.get_impact` once per analysed change, then `ImpactEngine.enrich`. `graphs` is keyed by change number.

## 9. Preservation and reruns

- Original text is never modified, reflowed or normalised, including page-break characters, line endings and a missing final newline.
- Additions only: removing the added lines from the output reproduces the input exactly.
- `strip_impact_sections` removes previously generated blocks and roll-up by exact label and structure, and nothing else.
- Running the pipeline on its own output gives byte-identical output with no duplicate sections.
- The same correlation ID with the same input returns the stored result. The same ID with different input is a conflict error (409).

## 10. Versioning

All external responses carry `schema_version`. Changing any model or enum in this file requires both people's approval and a version bump if the external shape changes.

## 11. Open items

- Whether `relation` should be a fixed set of values instead of a free string.
- How long idempotent results are kept, and where (in-memory for now).
- How the Aetherion SDK is used by the agent entry point.
- Line-wrap width and exact wording of non-analysed risk text, once reviewed on real output.
