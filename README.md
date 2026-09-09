# Orbit

A college learning assistant built with React and FastAPI. Explore student progress, ask questions grounded in course materials, check demo assessment eligibility, and generate practice questions.

## Requirements

- Python 3.11–3.13, uv, and Node.js 22 or 24 with npm. The commands below use Python 3.12 for a fresh environment; the existing Python 3.13 environment was verified.
- A PostgreSQL/Neon database and a tool-capable Anthropic or OpenAI-compatible model.
- The supplied CSV files in the parent of this repository (or set `DATASET_DIR`).

## First-time setup

Run these PowerShell commands from the `Orbit` repository folder:

```powershell
cd backend
uv venv .venv --python 3.12
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

If `.venv` already exists, reuse it and run only the install command. Every Python command below uses this virtual environment directly; activation is optional.

Edit `backend/.env` locally:

| Setting | Value |
|---|---|
| `DATABASE_URL` | Your `postgresql+psycopg://` Neon URL with `sslmode=require` |
| `LLM_PROVIDER` | `anthropic` or `openai-compatible` |
| `LLM_BASE_URL` | Your provider's API base URL |
| `LLM_API_KEY` | Your API key |
| `LLM_MODEL` | An exact tool-capable model ID supported by your provider |
| `DATASET_DIR` | `../..` for this workspace; relative paths resolve from `backend/` |

Keep `.env` private. It is ignored by Git. See `.env.example` for optional settings.

Prepare the database and local course index from `backend/`:

```powershell
.venv/Scripts/python.exe -m orbit.ingest --verify-only
.venv/Scripts/python.exe -m orbit.ingest
.venv/Scripts/python.exe -m orbit.rag
```

The importer preserves all 27,456 source rows and is idempotent for unchanged inputs. The first index build downloads local embedding weights; subsequent retrieval uses cached weights without model API calls.

## Run the app

**Terminal 1 — backend**, starting from the repository folder:

```powershell
cd backend
.venv/Scripts/python.exe run.py
```

**Terminal 2 — frontend**, starting from the repository folder:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open [localhost:5173](http://localhost:5173). The backend accepts both `localhost` and `127.0.0.1` on the configured development port. Vite proxies API requests to port 8000. Stop each server with `Ctrl+C`.

The launcher resolves the project virtual environment and backend directory automatically. From the repository folder, `.\backend\.venv\Scripts\python.exe backend/run.py` works too. For backend auto-reload, append `--reload`.

The equivalent direct command, from `backend/`, is:

```powershell
.venv/Scripts/python.exe -m uvicorn orbit.main:app --host 127.0.0.1 --port 8000
```

The older `orbit.app:app` entry point remains supported.

## Run a production build locally

From the repository folder:

```powershell
cd frontend
npm.cmd ci
npm.cmd run build
cd ../backend
.venv/Scripts/python.exe run.py
```

Restart an already running backend after building. Open [127.0.0.1:8000](http://127.0.0.1:8000). FastAPI serves the frontend and API together. API docs are at [/docs](http://127.0.0.1:8000/docs), and startup status is at [/api/health](http://127.0.0.1:8000/api/health). Configuration flags indicate settings are present; they do not prove external services are reachable.

## Check the project

From `backend/`:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/verify_dataset.py
```

Tests use isolated database fixtures. The dataset rehearsal imports into a temporary SQLite database and checks preservation; the live app uses PostgreSQL.

With the backend running and the database, index, and model configured, run the next validation phase:

```powershell
.venv/Scripts/python.exe scripts/evaluate.py
```

This runs 24 live scenarios, makes model API calls, and saves `backend/data/live_evaluation.json`. Review answers for accuracy as well as automated tool-contract results.

For a provider with a low token quota, add `--interval 60` to pace scenarios. Temporary rate limits receive bounded retries; persistent throttling produces a clear error. The evaluation command exits with a failure code if any contract fails.

Optional code-quality checks, also inside the virtual environment:

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements-dev.txt
.venv/Scripts/python.exe -m ruff check orbit run.py tests scripts
.venv/Scripts/python.exe -m ruff format --check orbit run.py tests scripts
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Missing Python modules | Install requirements into `backend/.venv` and use its Python executable. |
| Cannot import `orbit.app` | Update the checkout; both entry points are supported. Prefer `run.py`. |
| Database unavailable or no students | Check `DATABASE_URL`, then run the importer. |
| Missing course index | Run `.venv/Scripts/python.exe -m orbit.rag` from `backend/`. |
| Model unavailable | Check provider, base URL, API key, model ID, and provider quota. |
| Untrusted request origin | Use `http://localhost:5173` for development, matching `ALLOWED_ORIGIN`. |
| Port already in use | Stop your earlier server. Changing the backend port also requires updating Vite's proxy. |
| Root URL returns 404 on port 8000 | Build the frontend and restart the backend, or use the Vite address. |

## Project notes

Five real student profiles cover the available dataset. Assessment rules, score assumptions, and nine course lessons are explicitly authored demo material. The student picker is a demo selector, not authentication. Sessions and caches require one backend process; Redis is the upgrade path for multiple workers. Set `COOKIE_SECURE=true` when serving behind HTTPS.

- [Architecture, data preservation, seeded-user rationale, and demo rules](docs/ARCHITECTURE.md)
- [Validation evidence and remaining work](VALIDATION.md)
- [Project requirements](ORBIT_PROJECT_INSTRUCTIONS.md)

The original UI is preserved in `frontend/prototype.html`. Local data, credentials, and turn logs are ignored by Git.
