# Impact Agent

The Impact Agent takes a Technical Design Document (TDD) as plain text, analyses the impact of each proposed change, and returns the same TDD with impact analysis added. It is built on the Aetherion SDK.

Implemented so far (all on dummy data):

- a TDD parser that turns the text into the contract's `ParsedTDD`, recording anything it cannot resolve instead of guessing
- the impact analysis core and renderer: deterministic grouping, code-generated warnings, validation of the LLM's reply, per-change impact blocks and a roll-up, and stripping so reruns never duplicate sections
- a fake graph provider with fixture scenarios, and a fake LLM
- a FastAPI endpoint (`POST /impact`) with in-memory idempotency by correlation id
- dummy orchestrator and coding-agent stubs, and a script that regenerates the golden expected output from the real pipeline

Not implemented yet: a real code graph (such as Neo4j), a real LLM, and production agent integration. The graph data and the LLM are fixtures and fakes.

Tooling: Python 3.12.10, [uv](https://docs.astral.sh/uv/), Aetherion SDK 0.0.55, FastAPI, Uvicorn, Pydantic, pydantic-settings, pytest, pytest-asyncio, Ruff, and the Temporal CLI for local workflow development.

## Prerequisites

These instructions target macOS on Apple Silicon (arm64) with zsh.

- **Git**
- **Python 3.12.10** (the project requires `>=3.12.10,<3.14`)
- **uv**
- **Homebrew**, used to install the Temporal CLI

> **Platform note:** The Aetherion SDK dependency in `pyproject.toml` points to a macOS ARM64 wheel (and is limited to that platform by a marker). On other platforms (Linux, Intel Macs, CI) `uv sync` will not install the SDK, and a compatible wheel URL must be added first.

## Clone the repository

```zsh
git clone https://github.com/MansiNataraj18/impact-agent.git
cd impact-agent
```

## Set up the Python environment

Run all `uv` commands from the project root (the folder containing `pyproject.toml`).

```zsh
# Optional: uv sync creates .venv automatically if it is missing
uv venv --python 3.12.10

# Install dependencies from pyproject.toml and uv.lock
uv sync

# Activate the environment
source .venv/bin/activate
```

## Local Temporal setup

Install the Temporal CLI if you don't have it:

```zsh
brew install temporal
```

Start the local development server:

```zsh
temporal server start-dev
```

Leave this terminal open while you work; stopping it (Ctrl+C) stops the server. Use a separate terminal for everything else.

- Temporal server: `localhost:7233`
- Temporal UI: http://localhost:8233

Local Temporal is for local development only. It does not replace or configure the Aetherion sandbox.

## Aetherion configuration

The `aetherion` CLI is installed by the SDK, so it is available once the virtual environment is active. Two commands are useful for diagnostics:

```zsh
aetherion --help
aetherion config list
```

Do not commit credentials, tokens, or machine-specific configuration. Do not overwrite `TARGET_HOST` (or run `aetherion config init`) until you have confirmed with your team which environment you should be using.

## Verification

With the environment activated and from the project root:

```zsh
python --version          # expect 3.12.10
which python              # expect .../impact-agent/.venv/bin/python
uv --version
uv pip show aetherion-sdk # expect Version: 0.0.55
uv run pytest --version
uv run ruff --version
uv lock --check
git status --short --branch

python -c "import fastapi, pydantic, pydantic_settings, uvicorn, aetherion_sdk; print('imports ok')"
```

Note that the SDK's import name is `aetherion_sdk`.

## Development workflow

- Create your own feature branch from `main`: `git switch main && git switch -c your-branch-name`
- Never commit `.venv/` or real `.env` files. They are listed in `.gitignore`. A `.env.example` containing placeholder values only is allowed.
- Run the tests, Ruff checks and the demo scripts described in the Running section before opening a pull request.
- The contract in `docs/contracts.md` is shared between both sides; changes to it need both people's approval.
- `tests/fixtures/tdd/sample_expected_output.txt` is generated. After an intentional rendering change, regenerate it with `uv run python scripts/regenerate_expected_output.py` and review the diff.
- Real graph, LLM and agent integrations are future work; keep fixtures clearly labelled as dummy data.

## Troubleshooting

**Python version mismatch**
If `uv sync` or `python --version` reports the wrong version, install 3.12.10 and recreate the environment: `uv python install 3.12.10`, then `uv venv --python 3.12.10 --clear` and `uv sync`. (`--clear` replaces the existing `.venv`, so only use it if you are sure.)

**Aetherion wheel missing or platform incompatible**
If `aetherion_sdk` cannot be imported, or `uv pip show aetherion-sdk` finds nothing, check that you are on macOS arm64 (`uname -sm` should print `Darwin arm64`) and that you ran `uv sync` from the project root. On any other platform, a compatible wheel URL for the SDK must be added to `pyproject.toml`; ask your team for the correct one.

**Temporal already running on port 7233**
If `temporal server start-dev` fails because the port is in use, a server is probably already running. Check with `lsof -i :7233`. You can reuse that server (UI at http://localhost:8233) or stop the process before starting a new one.

## Running

All commands run from the project root. Everything below uses dummy data: fixture graphs and a fake LLM. No real code graph, model or Aetherion service is called.

```zsh
# Set up
uv sync

# Tests (pytest is configured with -p no:phoenix; see the note below)
uv run pytest

# Lint and format checks
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts

# Core demo: hand-built parsed TDD, fake graph, fake LLM
uv run python scripts/demo_core.py

# Stub flow: orchestrator stub -> API -> coding agent stub, in process (no network)
uv run python scripts/run_stub_flow.py
```

Start the API (the package is not installed, so point uvicorn at `src`):

```zsh
uv run uvicorn impact_agent.api.app:create_app --factory --app-dir src --reload
```

Then, in another terminal:

```zsh
curl localhost:8000/health
# {"status":"ok"}

curl -s localhost:8000/impact -H 'content-type: application/json' \
  -d '{"tdd_text": "..."}'
```

`POST /impact` takes `tdd_text` plus optional `project`, `repository`, `revision` and `correlation_id`, and returns the enriched TDD. See `docs/contracts.md` for the response shape.

**Pytest note:** `pyproject.toml` passes `-p no:phoenix` to pytest. The `phoenix` pytest plugin comes in through the Aetherion SDK's dependencies and crashes at startup because of a `graphql-core` version conflict. Disabling it is only a workaround for that conflict.

More documentation:

- `docs/contracts.md`: the agreed contract between the parser/API side and the impact core
- `docs/fixtures.md`: the fixture graphs, the sample TDD files and how to regenerate the golden output
- `docs/implementation-plan.md`: the original implementation plan
