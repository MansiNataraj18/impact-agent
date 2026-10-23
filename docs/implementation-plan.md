# Impact Agent: Implementation Plan

Status: draft for review by both people before implementation starts.
Target location in the repository: `docs/implementation-plan.md`.

This plan was written without access to the repository. It does not describe existing code. Anything that depends on the already-defined contract (`docs/contracts.md`, if it exists) is marked for verification and not decided here.

## 0. How to read this document

Every statement about shape or behaviour carries one of these labels.

| Label | Meaning |
|---|---|
| **[AGREED]** | Settled in earlier discussion: work split, architecture, output format, behaviour rules. Do not change without both people agreeing. |
| **[PROPOSED]** | A suggestion made in this plan to make the work concrete. Needs confirmation by both people before it is relied on. |
| **[VERIFY]** | Should already exist in the contract or repository. Check it and correct this plan if it differs. |
| **[UNRESOLVED]** | Not decided. Do not guess; resolve it in the contract sync (Step 0) or leave it as a clearly marked gap. |

Terms used throughout:

- **TDD**: Technical Design Document, plain text.
- **Person 1 (P1)**: impact analysis core and TDD renderer.
- **Person 2 (P2)**: TDD parser, fake graph provider, API and integration stubs.
- **Change**: one numbered entry (`Change N: symbol (action)`) in Section 5 of a TDD.

## 1. Project overview and end-to-end data flow

### 1.1 What the agent does [AGREED]

The Impact Agent receives a TDD as plain text, analyses the potential impact of each proposed change using graph data, and returns the same TDD with impact analysis added. TDD text is the external input and output. JSON and Python models are internal implementation details only.

Input: the TDD text plus optional metadata (project, repository, revision, correlation ID). Metadata may use dummy defaults at first.

### 1.2 Division of labour between code and LLM [AGREED]

- Deterministic code decides the structure: which changes exist, how graph nodes are grouped (direct, potential, tests), which warnings apply, the layout of the output and all validation.
- The LLM writes only three things: the summary, the risk assessment and a one-line explanation per affected item.
- The LLM can never add, remove or move items, and can never mark anything as verified.
- Tests use a fake LLM so results are deterministic.

### 1.3 Data flow [PROPOSED boundaries, AGREED stages]

```
 TDD text + optional metadata
          |
          v
 [API]  POST /impact                                   (P2)
          |
          v
 strip_impact_sections(text)   remove earlier output    (P1 function)
          |
          v
 [Parser]  parse_tdd(text) -> ParsedTDD                (P2)
          |
          v
 [Provider] get_impact(query) -> ImpactGraph           (P2)
          |   called once per change that needs analysis
          v
 [Core]    analyze_tdd(parsed, graphs, llm)            (P1)
          |   grouping, warnings, LLM call, validation
          v
 [Renderer] render_tdd(text, parsed, result) -> text   (P1)
          |
          v
 Enriched TDD text  ->  response  ->  coding agent (future) / stub consumer (now)
```

Real Neo4j integration, the real orchestrator and the real coding agent are future work and not part of this initial implementation.

## 2. Input/output contract and internal models

### 2.1 External contract [AGREED]

- Input: TDD text plus optional metadata.
- Output: the same TDD text with impact content added. All original text is preserved.
- The only additions are:
  1. An `Impact Analysis (Change N):` block after each change's `Done when:` list.
  2. A final `15. IMPACT ANALYSIS` roll-up. The number `15` is illustrative; it is the number after the last section found in the actual TDD.
- Rerunning the agent must not create duplicate impact sections.
- Dummy graph data must be identified as fixture data, never presented as real evidence.

### 2.2 Output format [AGREED]

Per-change block, same six parts in the same order every time:

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

Roll-up appended at the end:

```
15. IMPACT ANALYSIS
===================
Overall Risk: ...
Summary: ...
Graph source: ...

Impact by Change:
- Change N (action) symbol: <risk>

Tests to Run:
- ...

TDD Claims vs Graph:
- ...

Warnings and Unresolved Items:
- ...
```

The reference example is `tests/fixtures/tdd/sample_expected_output.txt` (see Section 11). It is a hand-written illustration; see open questions about regenerating it.

Details that were used in the example but are **[PROPOSED]** and need confirmation:

- Blocks are written flush-left, lines wrapped at roughly 96 characters, matching the style of the input TDD.
- Changes whose action is `create` or `reference` still receive a full block, with `None.` or `Not applicable` filled in, so the six parts are always present and a parser never has to guess whether a block is missing.
- Underline length in the roll-up heading equals the heading length.

### 2.3 Internal models [AGREED names, fields PROPOSED/VERIFY]

The four models are agreed by name. Field-level shapes below are proposals taken from earlier design notes; check each against `docs/contracts.md`.

**ParsedTDD** (owned by P2)
- `title`, `summary` [PROPOSED]
- `changes: list[ParsedChange]`
- `no_change_services: list[str]`
- `planned_tests: list[PlannedTest]` from Section 10
- `last_section_number: int | None`, used by the renderer to number the roll-up [PROPOSED]
- `unresolved: list[UnresolvedItem]`

**ParsedChange** (part of ParsedTDD)
- `number` (the N in `Change N`), `service`, `file`, `symbol`, `action` (`modify`, `create` or `reference`), `code_check` (`VERIFIED` or `NEW`) [PROPOSED]
- Source position: the line span of the change block and the line index immediately after the end of its `Done when:` list. The renderer needs this to insert blocks without re-parsing. [PROPOSED, critical interface; see Section 5]
- Any field that could not be parsed is `None` with a matching entry in `unresolved`. Fields are never guessed.

**ImpactNode** (owned by P1) [VERIFY]
- `id`, `kind` (method, function, class, service, api, event, database, test), `name`, `location` (optional), `depth` (1 = direct), `relation` (for example calls, tests, exposes), plus the owning `service` if available.

**ImpactGraph** (owned by P1) [VERIFY]
- `changed` (the changed location), `nodes: list[ImpactNode]`, `source` (`fixture` or a real source), `unresolved` items.

**ImpactExplanation** (owned by P1) [VERIFY]
- `status` (proposed values: `explained`, `skipped`), optional `reason`, `changed_location`, `risk_level`, `summary`, `directly_affected`, `potentially_affected`, `tests_to_run`, `warnings`. Each affected item carries `name`, `kind`, `location`, `depth` and a one-line `reason`.

### 2.4 Risk and status values [VERIFY]

Do not invent a new contract. Proposed values, to be checked against the existing contract: risk `low`, `medium`, `high`, rendered capitalised; status `explained` or `skipped`. The text used for non-analysed changes in the example (`Not applicable (...)`, `None (read only, ...)`) is a rendering choice that must be confirmed. If the contract already defines these values, the contract wins.

## 3. Work split

### 3.1 Person 1: impact analysis core and TDD renderer [AGREED]

1. Internal impact models and interfaces required by the contract.
2. Deterministic grouping of changed locations, direct impact, potential impact and tests to run.
3. LLM prompt and generation for summaries, risk and one-line explanations.
4. LLM response validation, malformed-output handling, unknown-item filtering and safe fallbacks.
5. Code-generated warnings for missing test coverage and insufficient graph evidence.
6. TDD renderer for per-change impact blocks and the final roll-up.
7. Original TDD text preservation and rerun/duplicate-section behaviour.
8. Unit tests for grouping, validation, warnings, fallbacks and rendering.
9. Standalone demo using manually constructed ParsedTDD data, fake graph data and a fake LLM.

**Out of scope for P1:** the TDD parser, the fake provider implementation, the FastAPI endpoint and the integration stubs.

### 3.2 Person 2: TDD parser, fake graph provider, API and integration [AGREED]

1. TDD parser and ParsedTDD model.
2. Extraction of changes, services, files, symbols, actions, code-check status, no-change services and planned tests.
3. Handling PDF extraction quirks and incomplete or malformed entries, with explicit unresolved values.
4. Graph-provider interface and deterministic fake graph provider.
5. Fixtures for normal impact, empty graph, no tests and cross-service impact, including direct and indirect relationships and missing-evidence cases.
6. FastAPI endpoint accepting TDD text and optional metadata and returning enriched TDD text in the agreed response format.
7. Agreed statuses, schema versioning, correlation-ID idempotency and error handling.
8. Stub orchestrator submitting a sample TDD and stub coding-agent consumer receiving the enriched TDD.
9. Parser, provider, API contract and end-to-end tests.
10. Run instructions and fixture documentation.

**Out of scope for P2:** impact grouping, LLM prompt and validation, and the TDD renderer.

### 3.3 Ownership of shared artefacts [PROPOSED]

| Artefact | Owner | Other person's rule |
|---|---|---|
| `ParsedTDD`, `ParsedChange` models | P2 | P1 imports and constructs them in tests; changes need P1's approval |
| `ImpactGraph`, `ImpactNode`, `ImpactExplanation` | P1 | P2's provider returns `ImpactGraph`; changes need P2's approval |
| `docs/contracts.md` | Both (reviewed jointly) | No one edits alone after Step 0 |
| `tests/fixtures/tdd/*` (sample input and expected output) | Both | Changes need both reviews |
| `docs/implementation-plan.md` | P1 maintains | P2 proposes edits by PR |

## 4. Proposed module and file structure

This is a **proposal**, not the existing repository layout. Package name and layout must be adapted to what is already committed. [UNRESOLVED]

```
src/impact_agent/                 # package name UNRESOLVED
  models/
    impact.py                     # ImpactGraph, ImpactNode, ImpactExplanation   (P1)
    parsed_tdd.py                 # ParsedTDD, ParsedChange, UnresolvedItem      (P2)
  core/                           # (P1)
    grouping.py                   # deterministic grouping
    evidence.py                   # code-generated warnings
    llm.py                        # LLMClient protocol, FakeLLM
    prompt.py                     # prompt construction
    validation.py                 # LLM output validation and fallbacks
    analyzer.py                   # analyze_tdd(...)
    engine.py                     # ImpactEngine implementation (handoff point)
  render/                         # (P1)
    blocks.py                     # per-change block text
    rollup.py                     # final roll-up text
    strip.py                      # strip_impact_sections(...)
    renderer.py                   # render_tdd(...)
  parser/                         # (P2)
    normalize.py                  # working copy + line map for quirks
    sections.py                   # section splitting
    changes.py                    # change extraction
    tdd_parser.py                 # parse_tdd(...)
  providers/                      # (P2)
    base.py                       # GraphProvider protocol
    fake.py                       # deterministic fake provider
    fixtures.py                   # fixture graphs
  api/                            # (P2)
    app.py                        # FastAPI app
    schemas.py                    # request/response models
    pipeline.py                   # strip -> parse -> provider -> engine
    idempotency.py                # correlation-ID handling
  stubs/                          # (P2)
    orchestrator.py
    coding_agent.py
scripts/
  demo_core.py                    # standalone demo                              (P1)
tests/
  core/  render/                  # (P1)
  parser/  providers/  api/  e2e/ # (P2)
  fixtures/tdd/                   # shared sample TDDs
docs/
  contracts.md                    # shared contract                              [VERIFY if it exists]
  implementation-plan.md          # this document
  fixtures.md                     # fixture documentation                        (P2)
```

Branches [PROPOSED]: `feature/impact-core` (P1) and `feature/tdd-parser-api` (P2), both from the same base commit. Each person edits only files they own, so merges should not conflict.

## 5. Interfaces and handoff

### 5.1 Already agreed in the contract [VERIFY]

- Model names: `ParsedTDD`, `ImpactGraph`, `ImpactNode`, `ImpactExplanation`.
- TDD text is the external input and output.
- The output format in Section 2.2.

### 5.2 Proposed interfaces requiring confirmation [PROPOSED]

Signatures only; bodies are not part of this plan.

```python
# Parser (P2)
def parse_tdd(text: str) -> ParsedTDD: ...

# Graph provider (P2)
class GraphProvider(Protocol):
    def get_impact(self, query: ImpactQuery) -> ImpactGraph: ...
# ImpactQuery: change number, service, file, symbol, project, repository, revision

# LLM (P1)
class LLMClient(Protocol):
    def complete(self, prompt: str) -> str: ...

# Core (P1)
def analyze_tdd(
    parsed: ParsedTDD,
    graphs: Mapping[int, ImpactGraph],   # keyed by change number
    llm: LLMClient,
) -> TddImpactResult: ...                # container for per-change explanations and roll-up

# Renderer (P1)
def render_tdd(original_text: str, parsed: ParsedTDD, result: TddImpactResult) -> str: ...
def strip_impact_sections(text: str) -> str: ...

# The handoff between workstreams (P1 implements, P2 calls)
class ImpactEngine(Protocol):
    def enrich(
        self, tdd_text: str, parsed: ParsedTDD, graphs: Mapping[int, ImpactGraph]
    ) -> str: ...
```

Design reasons:

- The core takes already-fetched graphs, so P1 never depends on the provider implementation. The API (P2) calls the provider per change and passes the results in.
- `ImpactEngine` is the single boundary the API depends on. P2 develops against a fake engine; P1 later supplies the real one.
- `strip_impact_sections` belongs to P1 because it must recognise exactly what the renderer writes. P2 uses an identity stub until it exists.
- `TddImpactResult` (roll-up container) is not one of the four agreed models. Whether it exists, or the roll-up lives elsewhere, is [UNRESOLVED].

### 5.3 The critical parser-to-renderer dependency [PROPOSED]

The renderer must insert each block after the end of that change's `Done when:` list. P1 must not re-parse the TDD, so `ParsedChange` must carry that insertion position (a line index into the original text as given to the parser). If the contract does not allow this, the alternatives are to let the renderer find anchors itself (duplicating parser logic, which breaks the split) or to move insertion-position logic into P2. This must be decided in Step 0.

### 5.4 Handoff milestones

1. **Contract sync (Step 0)**: the four models, `ImpactQuery`, `ImpactEngine`, statuses and risk values are merged as type-only definitions.
2. **P2 hands P1**: a parser that produces real `ParsedTDD` objects for the sample TDD. Until then P1 builds `ParsedTDD` by hand.
3. **P1 hands P2**: a working `ImpactEngine` and `strip_impact_sections`. Until then P2 uses a fake engine.

## 6. Step 0: contract sync (both people, before any parallel work)

**Goal:** remove every ambiguity that would make the two workstreams diverge.

**Work:**
1. Review `docs/contracts.md` if it exists; if not, create it from Section 2.3.
2. Decide the [UNRESOLVED] and [VERIFY] items in Section 15 that block parallel work: risk/status values, `ParsedChange` source positions, `ImpactQuery` shape, the response format, and the `TddImpactResult` question.
3. Merge type-only model definitions (no logic) for `ParsedTDD`, `ParsedChange`, `UnresolvedItem`, `ImpactQuery`, `ImpactGraph`, `ImpactNode`, `ImpactExplanation` and the `ImpactEngine`, `GraphProvider` and `LLMClient` protocols.
4. Commit the sample input and expected output to `tests/fixtures/tdd/`.

**Dependencies:** none.
**Tests:** models import cleanly; Ruff passes.
**Acceptance:** both people have approved the PR; both can import every model and protocol.

## 7. Person 1: numbered steps

### P1-1. Impact models and interfaces
- **Goal:** the P1-owned models and the `LLMClient` protocol, exactly as agreed in Step 0.
- **Files:** `models/impact.py`, `core/llm.py`.
- **Details:** validate fields (depth at least 1, kind and risk from the agreed sets). Invalid values must fail construction, not pass silently.
- **Dependencies:** Step 0.
- **Tests:** valid and invalid construction for each model.
- **Acceptance:** models match the contract field for field; invalid values are rejected.

### P1-2. Deterministic grouping
- **Goal:** sort each graph's nodes into tests, direct (depth 1) and potential (depth 2 or more).
- **Files:** `core/grouping.py`.
- **Details:** every node lands in exactly one group, with tests taking precedence over depth. Ordering is deterministic (depth, then service, then name). Duplicate node ids are collapsed. Nodes are never dropped or added by anything else.
- **Dependencies:** P1-1.
- **Tests:** mixed graph, tests at any depth, duplicate ids, single node, empty graph.
- **Acceptance:** no node is lost or duplicated across groups; output is stable across runs.

### P1-3. Code-generated warnings and evidence checks
- **Goal:** produce warnings from facts, not from the LLM.
- **Files:** `core/evidence.py`.
- **Details:** warn when no test nodes exist for a modified change ("No tests cover this change; add the regression test before merging"). Warn on an empty graph, on nodes with missing location, on a changed location that could not be resolved, and on unresolved items carried over from the parser. When graph `source` is a fixture, record that so the renderer can label it.
- **Dependencies:** P1-1, P1-2.
- **Tests:** one test per warning, plus a case with several warnings together.
- **Acceptance:** each condition yields exactly one warning with stable wording.

### P1-4. LLM prompt and fake LLM
- **Goal:** a prompt that carries only grouped graph data, and a fake LLM for deterministic tests.
- **Files:** `core/prompt.py`, `core/llm.py`.
- **Details:** the prompt includes the change summary from the TDD and the already-grouped nodes, and asks for strict JSON: summary, risk level and a one-line reason per node id. The fake LLM returns canned responses keyed by scenario and can simulate failure modes (invalid JSON, wrong shape, unknown node id, invalid risk, empty reply).
- **Dependencies:** P1-1.
- **Tests:** prompt contains every node id and nothing outside the graph; fake LLM returns the scripted responses.
- **Acceptance:** with the fake LLM, the whole core runs offline.

### P1-5. LLM response validation and fallbacks
- **Goal:** accept only well-formed LLM output and degrade safely otherwise.
- **Files:** `core/validation.py`.
- **Details:** parse the reply as JSON and check its shape. Drop reasons that reference unknown node ids and add a warning. Replace an unrecognised risk with the agreed fallback value. Keep the LLM from adding, removing or regrouping items. On an empty graph, skip the LLM call and use a fixed deterministic summary. On malformed output, use a deterministic fallback summary, mark risk with the agreed fallback, and add a warning that explanations are unavailable. Whether malformed output raises an error or falls back is [UNRESOLVED]; the requirement for safe fallbacks suggests falling back.
- **Dependencies:** P1-2, P1-4.
- **Tests:** each failure mode from the fake LLM; empty graph makes zero LLM calls.
- **Acceptance:** no input from the LLM can change group membership; every failure ends in a valid explanation or a documented error.

### P1-6. Analyzer and roll-up logic
- **Goal:** turn a `ParsedTDD` plus graphs into per-change explanations and the roll-up.
- **Files:** `core/analyzer.py`, `core/engine.py` (skeleton).
- **Details:** analyse only changes that need it (action `modify`, per the proposal); mark `create` and `reference` changes as not requiring graph analysis. Combine tests to run across changes without duplicates. Compute `TDD Claims vs Graph` deterministically: a service the TDD declares as no change is flagged for review if it appears among graph nodes, and consistent if it does not. Overall risk aggregation (for example highest per-change risk) is [PROPOSED].
- **Dependencies:** P1-3, P1-5; hand-built `ParsedTDD` objects.
- **Tests:** single and multi-change TDDs, cross-service graph, no-change service present and absent in the graph.
- **Acceptance:** result is complete and deterministic with the fake LLM.

### P1-7. TDD renderer
- **Goal:** write per-change blocks and the roll-up into the original text.
- **Files:** `render/blocks.py`, `render/rollup.py`, `render/renderer.py`.
- **Details:** insert each block at the insertion position carried by `ParsedChange`. Build the roll-up with the number after the last section. Label fixture data (`Graph source: dummy fixture (not a real code graph)`). Use the agreed wording and ordering from Section 2.2. If the last section number or an insertion position is missing, add a warning in the roll-up instead of guessing a position.
- **Dependencies:** P1-6, the position field from Step 0.
- **Tests:** golden-text comparison for each block type; roll-up numbering; missing-position case.
- **Acceptance:** output for the hand-built sample matches the expected output's structure line for line.

### P1-8. Preservation and rerun behaviour
- **Goal:** original text is untouched and reruns never duplicate output.
- **Files:** `render/strip.py`.
- **Details:** `strip_impact_sections` removes previously generated blocks and the generated roll-up, recognising them by their exact labels. Do not normalise line endings, page-break characters or trailing whitespace. Properties to test: removing the added lines from the output reproduces the input exactly; `strip(render(x))` equals the original; `render` applied to its own output (after strip) is identical to the first output.
- **Dependencies:** P1-7.
- **Tests:** additions-only diff check, double-run test, text with page-break characters and no trailing newline, a TDD that already contains impact blocks.
- **Acceptance:** two consecutive runs produce byte-identical output; the original is recoverable.

### P1-9. Unit test completion and standalone demo
- **Goal:** full coverage of P1's scope and a demo requiring nothing from P2.
- **Files:** `tests/core/`, `tests/render/`, `scripts/demo_core.py`.
- **Details:** the demo builds a `ParsedTDD` by hand, uses fake graph data and the fake LLM, and prints the enriched TDD.
- **Dependencies:** P1-1 to P1-8.
- **Tests:** the demo runs as part of a smoke test.
- **Acceptance:** `python scripts/demo_core.py` prints an enriched TDD; all P1 tests pass.

## 8. Person 2: numbered steps

### P2-1. ParsedTDD and parser models
- **Goal:** the P2-owned models, exactly as agreed in Step 0.
- **Files:** `models/parsed_tdd.py`.
- **Details:** include source positions, `last_section_number` and `UnresolvedItem` (what could not be parsed, where, and why).
- **Dependencies:** Step 0.
- **Tests:** model construction; unresolved entries.
- **Acceptance:** models match the contract; P1 can construct them by hand.

### P2-2. Text normalisation and section splitting
- **Goal:** split the TDD into sections despite extraction artefacts.
- **Files:** `parser/normalize.py`, `parser/sections.py`.
- **Details:** work on a normalised working copy with a line map back to the original; never modify the original text. Handle page-break characters at the start of lines, headings glued to the previous line, and text that runs together without a line break. Section headings are numbered, upper-case lines. Exact patterns must be checked against the real sample, not assumed.
- **Dependencies:** P2-1.
- **Tests:** the sample TDD; synthetic samples with page breaks and glued headings.
- **Acceptance:** every numbered section is located with correct original line positions.

### P2-3. Change extraction
- **Goal:** extract each `Change N` entry.
- **Files:** `parser/changes.py`.
- **Details:** capture number, symbol, action, file (which can wrap onto a second line), code-check status, and the end of the `Done when:` list. Attribute each change to its service from the nearest preceding service heading in Section 5. Missing or ambiguous values stay unset and are recorded as unresolved. Never infer a file, symbol or service.
- **Dependencies:** P2-2.
- **Tests:** all four change kinds in the sample; a change with a wrapped file path; a change with no `Done when:`.
- **Acceptance:** sample yields the right changes, services, actions and insertion positions.

### P2-4. No-change services and planned tests
- **Goal:** extract declared no-change services and planned tests.
- **Files:** `parser/changes.py` (or a sibling module), `parser/tdd_parser.py`.
- **Details:** no-change services come from service headings marked "no change" in Section 5. Planned tests come from Section 10 with their type and expectation where present. Also extract title and summary.
- **Dependencies:** P2-2.
- **Tests:** sample TDD; a TDD with no Section 10; a TDD with no no-change services.
- **Acceptance:** `parse_tdd` returns a complete `ParsedTDD` for the sample.

### P2-5. Robustness and unresolved handling
- **Goal:** malformed input never crashes the parser or produces invented values.
- **Files:** `parser/tdd_parser.py`, tests.
- **Details:** each defect becomes an unresolved item. A TDD with no recognisable changes returns an empty change list plus unresolved items, not an exception. Decide whether a wholly unparseable input is an API error (see P2-8).
- **Dependencies:** P2-3, P2-4.
- **Tests:** a set of deliberately broken TDDs (missing symbol, missing file, bad action, truncated text, empty string).
- **Acceptance:** no guessed values anywhere; each defect is reported.

### P2-6. Graph provider interface and fake provider
- **Goal:** a deterministic provider behind `GraphProvider`.
- **Files:** `providers/base.py`, `providers/fake.py`.
- **Details:** the fake provider returns a fixture graph chosen from the query (project, revision or symbol) or from configuration. Every graph it returns is marked as fixture data. Unknown queries return an empty graph with an unresolved item, not an error.
- **Dependencies:** Step 0.
- **Tests:** each fixture selected by its key; unknown query behaviour.
- **Acceptance:** same input always yields the same graph; fixture marker is always set.

### P2-7. Fixtures and documentation
- **Goal:** the four required scenarios plus missing evidence.
- **Files:** `providers/fixtures.py`, `docs/fixtures.md`, `tests/fixtures/`.
- **Details:** fixtures: normal impact (direct and indirect), empty graph, no tests, cross-service impact (a node in a different service from the change), and a missing-evidence case (nodes without location, or an unresolved changed location). Document what each fixture represents and which expected behaviour it exercises.
- **Dependencies:** P2-6.
- **Tests:** each fixture validates against the models.
- **Acceptance:** `docs/fixtures.md` explains each fixture; every fixture loads.

### P2-8. Pipeline and FastAPI endpoint
- **Goal:** a working `POST /impact`.
- **Files:** `api/app.py`, `api/schemas.py`, `api/pipeline.py`.
- **Details:** accept TDD text and optional metadata (project, repository, revision, correlation ID; dummy defaults allowed). Pipeline: strip, parse, call the provider per change that needs analysis, call the engine, return enriched text. Include a schema version and an agreed status. Error handling: empty or non-text input is a client error; internal failures return a clear error and never a partly written TDD. The exact request and response encoding is [UNRESOLVED] (see Section 15). Until P1's engine exists, use a fake engine behind `ImpactEngine`.
- **Dependencies:** P2-3 to P2-6, Step 0.
- **Tests:** API contract tests with the fake engine: success, empty body, invalid metadata.
- **Acceptance:** endpoint returns a response in the agreed format for the sample TDD.

### P2-9. Correlation-ID idempotency
- **Goal:** repeating a request with the same correlation ID gives the same result.
- **Files:** `api/idempotency.py`.
- **Details:** the same correlation ID with the same input returns the stored result; the same ID with different input is an explicit conflict. Storage can be in-memory for now; durable storage is future work. How long results are kept is [UNRESOLVED].
- **Dependencies:** P2-8.
- **Tests:** repeat request, conflicting repeat, no correlation ID.
- **Acceptance:** repeated calls never trigger a second analysis or a second set of impact sections.

### P2-10. Integration stubs, end-to-end tests and run instructions
- **Goal:** show the whole flow with stubs.
- **Files:** `stubs/orchestrator.py`, `stubs/coding_agent.py`, `tests/e2e/`, README section.
- **Details:** the stub orchestrator submits the sample TDD and passes the response to the stub coding agent, which receives the enriched TDD and prints what it received. Add run instructions and commands (Section 13).
- **Dependencies:** P2-8, P2-9; later P1's engine.
- **Tests:** end-to-end tests using the fake engine, and later the real engine.
- **Acceptance:** one command runs the stub orchestrator and shows the stub coding agent receiving an enriched TDD.

## 9. Independent testing strategy

| Concern | P1 tests with | P2 tests with |
|---|---|---|
| Input TDD | Hand-built `ParsedTDD` objects | Real TDD text files in `tests/fixtures/tdd/` |
| Graph data | Small graphs built inside tests | The fake provider and its fixtures |
| LLM | `FakeLLM` with scripted replies | Not used |
| Impact engine | The real core | A fake `ImpactEngine` returning fixed text |
| Renderer | Direct calls with hand-built results | Not used |
| API | Not used | FastAPI test client |

Rules:

- Neither person imports the other's implementation in unit tests, only the shared models and protocols.
- No test calls a real LLM, a real Neo4j or the network.
- Shared fixtures (sample input and expected output) are read-only for both after Step 0 unless both approve a change.
- Each person's tests must pass on their own branch before opening a PR.

## 10. Error handling, unresolved items, risk/status and TDD preservation

**Never guess.** If the parser cannot read a file, symbol, service or relationship, the value is empty and an unresolved item is recorded. The renderer shows unresolved items in `Warnings and Unresolved` (per change) and in the roll-up. Nothing downstream fills the gap.

**Graph evidence.** The agent states only what the graph returned. Missing tests, missing locations, empty graphs and unresolved changed locations all become code-generated warnings.

**LLM failures.** Invalid JSON, wrong shape, unknown ids and bad risk values are handled in P1-5. The LLM never changes which items exist or which group they are in.

**Risk and status.** Use only the values defined in the contract [VERIFY]. When a change is not analysed (create or reference), the risk text follows the confirmed convention, not an invented one.

**Fixture data.** Any graph marked as fixture data is labelled in the roll-up as a dummy fixture. This label is mandatory and tested.

**TDD preservation.**
- Original text is never modified, reflowed or normalised, including page-break characters, line endings and a missing trailing newline.
- The parser works on a working copy and maps back to original positions.
- Additions-only is a test invariant: removing the added lines reproduces the input exactly.

**Reruns.** Before parsing, previously generated content is stripped; the same input yields byte-identical output. The API additionally honours the correlation ID.

## 11. Fixtures, expected-output testing and rerun behaviour

**Shared files** [PROPOSED paths]:
- `tests/fixtures/tdd/sample_input.txt`: the TDD text extracted from the sample PDF, including its extraction quirks.
- `tests/fixtures/tdd/sample_expected_output.txt`: the sample with impact blocks and the roll-up added.

**Caveat:** the expected-output file was written by hand as an illustration. Its graph content and some `TDD Claims vs Graph` wording are made up. Before it is used as a golden test it must be regenerated or reconciled with the real fixture graph, the fake LLM's scripted replies and the deterministic claims rule (see Section 15).

**Test types:**
1. Parser tests (P2): sample input produces the expected `ParsedTDD`.
2. Renderer tests (P1): hand-built `ParsedTDD` plus fake graphs produce the expected text.
3. Golden end-to-end test (both): sample input through the full pipeline equals the expected output.
4. Preservation test: the output with added lines removed equals the input.
5. Rerun test: running the output through the pipeline again produces identical output with no duplicate sections.
6. Fixture matrix: normal, empty graph, no tests, cross-service and missing evidence each have an expected-behaviour test.

## 12. Integration order and end-to-end acceptance criteria

**Integration order:**
1. Step 0 merged.
2. P1 and P2 work in parallel on their branches until their own tests pass.
3. **Integration 1:** P2's parser output feeds P1's renderer and analyzer (replace P1's hand-built `ParsedTDD` with the real parser output for the sample).
4. **Integration 2:** P2's fake provider feeds P1's core through the API pipeline (replace the fake engine with the real one).
5. **Integration 3:** idempotency and error handling verified against the real engine.
6. **Integration 4:** stub orchestrator and stub coding agent run end to end.

**End-to-end acceptance criteria:**
- The sample TDD, submitted through the endpoint, returns the TDD with one impact block per change and the roll-up appended.
- The returned text contains all original text unchanged.
- Submitting the returned text again produces identical output with no duplicate sections.
- The same correlation ID returns the same result without re-analysis.
- Dummy data is labelled as fixture data.
- All parser, core, renderer, provider, API and end-to-end tests pass; Ruff reports no errors.
- No real Neo4j, real LLM or production integration is involved.

## 13. Python environment and test commands

The project is described as Python with the Aetherion SDK environment, FastAPI, Pydantic, pytest and Ruff, with its initial environment setup committed. Python version, dependency manager and exact configuration are [VERIFY]. The commands below assume a standard setup; adapt them to the repository's actual tooling.

```bash
# run all tests
python -m pytest

# run one area
python -m pytest tests/core tests/render -q       # P1
python -m pytest tests/parser tests/providers tests/api tests/e2e -q   # P2

# lint and format
ruff check .
ruff format --check .

# P1 demo
python scripts/demo_core.py

# API (module path UNRESOLVED, depends on the package name)
uvicorn <package>.api.app:app --reload
```

Do not add dependencies beyond what the repository already has unless both people agree. No unrelated refactoring.

How the Aetherion SDK is used (agent entry point, LLM access) is [UNRESOLVED]. The initial scope is FastAPI plus the models, so P1's `LLMClient` is a protocol that a later Aetherion-backed client can implement.

## 14. Progress checklist

**Shared**
- [ ] Contract reviewed against `docs/contracts.md`
- [ ] Open questions that block parallel work resolved (Section 15)
- [ ] Type-only models and protocols merged
- [ ] Sample input and expected output committed
- [ ] Feature branches created from the same base commit

**Person 1**
- [ ] P1-1 Impact models and interfaces
- [ ] P1-2 Deterministic grouping
- [ ] P1-3 Code-generated warnings
- [ ] P1-4 LLM prompt and fake LLM
- [ ] P1-5 Validation and fallbacks
- [ ] P1-6 Analyzer and roll-up logic
- [ ] P1-7 TDD renderer
- [ ] P1-8 Preservation and rerun behaviour
- [ ] P1-9 Tests and standalone demo

**Person 2**
- [ ] P2-1 ParsedTDD and parser models
- [ ] P2-2 Normalisation and section splitting
- [ ] P2-3 Change extraction
- [ ] P2-4 No-change services and planned tests
- [ ] P2-5 Robustness and unresolved handling
- [ ] P2-6 Provider interface and fake provider
- [ ] P2-7 Fixtures and documentation
- [ ] P2-8 Pipeline and FastAPI endpoint
- [ ] P2-9 Correlation-ID idempotency
- [ ] P2-10 Stubs, end-to-end tests and run instructions

**Integration**
- [ ] Integration 1: parser output into core and renderer
- [ ] Integration 2: fake provider and real engine through the API
- [ ] Integration 3: idempotency and error handling
- [ ] Integration 4: stub orchestrator and coding agent end to end
- [ ] End-to-end acceptance criteria met
- [ ] Ruff and all tests pass

## 15. Open questions to check against the existing contract

Items marked **(blocks Step 0)** must be answered before parallel work starts.

1. **(blocks Step 0)** Do `ParsedChange` objects carry the insertion position (end of the `Done when:` list) for the renderer? If not, who computes it? (Section 5.3)
2. **(blocks Step 0)** Exact risk values, status values and fallback values in the contract, and the text used for non-analysed changes (`create`, `reference`).
3. **(blocks Step 0)** Exact field names and types of the four models in `docs/contracts.md`, including whether `ImpactNode` has a `service` field.
4. **(blocks Step 0)** Request and response encoding of `POST /impact`: plain text body, or a wrapper holding the TDD text plus metadata, status and schema version? How are metadata and correlation ID supplied?
5. What is the shape of `ImpactQuery`, and does the provider return one graph per change or one graph for the whole TDD?
6. Does `TddImpactResult` exist, or where does roll-up data live?
7. Should a malformed LLM response raise an error or fall back to a deterministic explanation?
8. Overall-risk aggregation rule (for example, highest per-change risk) and which actions are analysed (only `modify`?).
9. Deterministic definition of `TDD Claims vs Graph`: the hand-written example marks some entries "Consistent" using judgment. What is the rule, and should one-line reasons come from the LLM?
10. The expected-output example needs to be regenerated once the fixture graph, fake LLM replies and claims rule are fixed.
11. Output layout details: line-wrap width, flush-left style, and the roll-up heading underline.
12. Handling of an input that already contains impact content (strip then regenerate, as proposed) and of an input with no recognisable Section 5.
13. Behaviour when the last section number cannot be determined.
14. Idempotency storage and retention, and whether a repeated correlation ID with different input is a conflict error.
15. Python version, dependency manager and package name, and how the Aetherion SDK is meant to be used in this project.
16. Where `tests/fixtures/tdd/` and `docs/fixtures.md` should live if the repository already has a convention.
