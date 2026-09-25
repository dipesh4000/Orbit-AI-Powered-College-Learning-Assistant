# Orbit backend

FastAPI, PostgreSQL, local retrieval, and model orchestration, managed with uv.

## Source navigation

Implementation is organized under `orbit/api`, `orbit/features`, `orbit/core`,
`orbit/ai`, and `orbit/demo`. The root `orbit/*.py` modules are compatibility
imports for existing commands and integrations. New code belongs in the grouped
folders. See [orbit/README.md](orbit/README.md) for the module map and where to
place each kind of change.

## Setup and run

From this directory:

```powershell
uv venv
uv sync
uv run uvicorn orbit.main:app --reload --host 127.0.0.1 --port 8000
```

No activation is required. `uv sync` also creates `.venv` if it is missing. Dependencies live in `pyproject.toml` and resolved versions in `uv.lock`.

Keep your credentials in `.env`. See the [getting-started guide](../GET_STARTED.md) for first-time configuration, data import, indexing, and frontend commands.

## Checks

```powershell
uv run pytest -q
uv run ruff check orbit tests scripts
uv run ruff format --check orbit tests scripts
```
