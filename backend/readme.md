# Orbit backend

FastAPI, PostgreSQL, local retrieval, and model orchestration, managed with uv.

## Setup and run

From this directory:

```powershell
uv venv
uv sync
uv run uvicorn orbit.main:app --reload --host 127.0.0.1 --port 8000
```

No activation is required. `uv sync` also creates `.venv` if it is missing. Dependencies live in `pyproject.toml` and resolved versions in `uv.lock`.

Keep your credentials in `.env`. See the [project README](../README.md) for first-time configuration, data import, indexing, and frontend commands.

## Checks

```powershell
uv run pytest -q
uv run ruff check orbit tests scripts
uv run ruff format --check orbit tests scripts
```
