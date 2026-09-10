# Orbit

A college learning assistant built with React and FastAPI: student progress, course-grounded chat, demo assessment eligibility, and practice questions.

## Backend setup

Install **uv** first. From the `Orbit` repository folder:

```powershell
cd backend
uv venv
uv sync
```

That's the environment setup. `pyproject.toml` declares dependencies, `uv.lock` pins them, and `uv sync` installs them into `.venv`, including development tools. Python 3.13 is selected by `.python-version`; uv can download it if needed.

**Activation is not required.** Use `uv run` for backend commands. `uv sync` also creates `.venv` if you skip `uv venv`.

## Configure once

From `backend/`:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `.env` with your settings. Existing credentials are preserved.

| Setting | Value |
|---|---|
| `DATABASE_URL` | Your PostgreSQL/Neon URL, with `sslmode=require` |
| `LLM_PROVIDER` | `anthropic` or `openai-compatible` |
| `LLM_BASE_URL` | Your provider's API base URL |
| `LLM_API_KEY` | Your API key |
| `LLM_MODEL` | An exact tool-capable model ID |
| `DATASET_DIR` | `../..` for this workspace, relative to `backend/` |

For a new database or missing course index:

```powershell
uv run python -m orbit.ingest --verify-only
uv run python -m orbit.ingest
uv run python -m orbit.rag
```

Skip this preparation if your database is already imported and the index exists. The first index build downloads local embedding weights. Secrets, datasets, model weights, and logs are ignored by Git.

## Run

**Backend** — from `backend/`:

```powershell
uv run uvicorn orbit.main:app --reload --host 127.0.0.1 --port 8000
```

**Frontend** — in a second terminal, from the repository folder:

```powershell
cd frontend
npm i
npm run dev
```

Open [localhost:5173](http://localhost:5173). Stop servers with `Ctrl+C`. The backend accepts both loopback hostnames on the configured development port.

From the repository folder, the same backend command is:

```powershell
uv run --directory backend uvicorn orbit.main:app --reload --host 127.0.0.1 --port 8000
```

Use `orbit.main:app` as the entry point. No custom launcher or activation script is needed.

## Build and serve together

For static frontend hosting, Render cold starts, environment variables, and the page/API route contract, see [Deployment](docs/DEPLOYMENT.md).

From the repository folder:

```powershell
cd frontend
npm.cmd ci
npm.cmd run build
cd ../backend
uv run uvicorn orbit.main:app --host 127.0.0.1 --port 8000
```

Stop any existing backend first. Open [127.0.0.1:8000](http://127.0.0.1:8000). FastAPI serves the built frontend and API together. API docs are at [/docs](http://127.0.0.1:8000/docs); startup status is at [/api/health](http://127.0.0.1:8000/api/health).

## Checks

From `backend/`:

```powershell
uv run pytest -q
uv run ruff check orbit tests scripts
uv run ruff format --check orbit tests scripts
```

Additional checks:

```powershell
uv run python scripts/verify_dataset.py
uv run python scripts/evaluate.py --interval 60
```

The dataset rehearsal uses a temporary database. Live evaluation needs the running backend and configured model, consumes provider quota, and saves results in `backend/data/`. Review answer quality alongside automated results.

To add a dependency, use `uv add package-name`; for a development dependency, use `uv add --dev package-name`. Commit both `pyproject.toml` and `uv.lock` after dependency changes.

## Troubleshooting

| Symptom | Action |
|---|---|
| Missing dependencies or a deleted `.venv` | Run `uv sync`, then use `uv run`. |
| Import error | Run the documented command from `backend/`, or use `--directory backend` from the repository folder. |
| Port 8000 is occupied | Stop the earlier backend with `Ctrl+C` before starting another. |
| Database unavailable | Check `.env` and run the importer for a new database. |
| Missing course index | Run `uv run python -m orbit.rag`. |
| Model rate limit | Wait for quota to recover; request one course at a time. |
| Root URL returns 404 on port 8000 | Build the frontend and restart the backend, or use port 5173. |

## Project notes

The student picker is a demo selector, not authentication. Assessment rules and course materials are explicitly demo-authored. Sessions and caches require one backend process. All **27,456 source rows** are preserved.

- [Architecture, dataset assumptions, and seeded-user rationale](docs/ARCHITECTURE.md)
- [Validation results and remaining AI acceptance work](VALIDATION.md)
- [Project requirements](ORBIT_PROJECT_INSTRUCTIONS.md)
