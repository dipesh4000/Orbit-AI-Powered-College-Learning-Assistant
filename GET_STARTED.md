# Get started with Orbit

Installation, configuration, local development, and validation. See [README](README.md) for the project and AI diagrams, or [Deployment](docs/DEPLOYMENT.md) for hosting.

## Prerequisites and dataset placement

Install Git, Node.js 22 LTS with npm, and [uv](https://docs.astral.sh/uv/getting-started/installation/).
You need PostgreSQL (such as Neon), the supplied CSVs, and a tool-capable LLM API key.
Commands start in the repository folder containing `backend/` and `frontend/`.
On Windows use `npm.cmd` if PowerShell blocks `npm.ps1`. On macOS/Linux use `npm`.

Set `DATASET_DIR` to the directory containing these six files. Relative paths resolve
from `backend/`; `../..` matches the original workspace. Preserve exact filenames,
including the supplied spelling of `enagagement`:

```text
valid_uuid_engagement.csv
invalid_uuid_enagagement.csv
valid_uuid_submissions.csv
invalid_uuid_submissions.csv
student_course_engagement - Course Engagement.csv
Hackathon Submissions.csv
```

Datasets are ignored by Git and must be obtained separately. Run ingestion only against
the intended demo database: it writes data and is not part of normal server startup.

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

On macOS/Linux, use `test -f .env || cp .env.example .env` instead.

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

**Backend** â€” from `backend/`:

```powershell
uv run uvicorn orbit.main:app --reload --host 127.0.0.1 --port 8000
```

**Frontend** â€” in a second terminal, from the repository folder:

```powershell
cd frontend
npm ci
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
| Model rate limit | Add `NVIDIA_API_KEY` and restart to enable fallback. If both providers fail, check their quotas. |
| Root URL returns 404 on port 8000 | Build the frontend and restart the backend, or use port 5173. |

## Project notes

The student picker is a demo selector, not authentication. Assessment rules and course materials are explicitly demo-authored. Sessions and caches require one backend process. All **27,456 source rows** are preserved.

- [Architecture, dataset assumptions, and seeded-user rationale](docs/ARCHITECTURE.md)
- [Validation results and remaining AI acceptance work](VALIDATION.md)
- [Project requirements](ORBIT_PROJECT_INSTRUCTIONS.md)


## NVIDIA failover

Add `NVIDIA_API_KEY` to `backend/.env` (or your hosting environment) and restart
the backend. Existing `LLM_*` settings remain the primary provider. The default
fallback is `nvidia/nemotron-3-nano-30b-a3b`, with thinking disabled for lower
latency. Set `NVIDIA_MODEL=nvidia/nemotron-3-super-120b-a12b` to use Super instead.
The endpoint defaults to `https://integrate.api.nvidia.com/v1`.

With NVIDIA configured, a failed primary request switches immediately, including
quota/rate limits, rejected credentials, HTTP errors, timeouts, and malformed or
empty responses. The primary is skipped for `LLM_FALLBACK_COOLDOWN_SECONDS=300`,
then retried automatically. Each provider call has a total
`LLM_TIMEOUT_SECONDS=30` budget. Without NVIDIA, existing bounded rate-limit
retries remain. NVIDIA can also run alone when the primary is unconfigured.
Tool schemas and conversation/tool-result history are preserved during failover;
metrics identify NVIDIA separately. Cooldown state is per backend process.
If both providers fail, the existing safe unavailable response is returned;
failover cannot guarantee availability when both services have exhausted quotas.


Example primary Groq configuration:

```dotenv
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-120b
LLM_API_KEY=your-primary-key
NVIDIA_API_KEY=your-nvidia-key
NVIDIA_MODEL=nvidia/nemotron-3-nano-30b-a3b
LLM_TIMEOUT_SECONDS=30
LLM_FALLBACK_COOLDOWN_SECONDS=300
```

Use a primary model enabled for your account. For NVIDIA alone, leave `LLM_API_KEY`
empty and set `NVIDIA_API_KEY`. Never put credentials in frontend `VITE_*` variables.

## Browser tests and readiness

From `frontend/`:

```sh
npm ci
npx playwright install chromium
npm test
```

Browser tests mock API responses. Build the frontend before running the backend tests
to include built-page route checks. Live evaluation is a separate, quota-consuming step.

1. Check backend `/api/health`. Flags indicate configuration and index presence; they
   do not prove database connectivity or provider access.
2. Choose a student and confirm the dashboard loads.
3. Ask a course-content question to exercise hosted embeddings and FAISS.
4. Generate a small practice set and inspect the source citations.

The deployed runtime includes `backend/data/rag/chunks.json` and `index.faiss`.
These small demo assets are tracked in Git; model weights are not needed because
embeddings use Hugging Face. Keep the deployed embedding settings consistent with
the index manifest, or rebuild with `uv run python -m orbit.rag --from-existing`
from `backend/` and deploy the updated assets.
Sessions persist in PostgreSQL across backend workers and serverless restarts.
The `web_sessions` table is created automatically on first use; the database role needs
table-creation privileges. Keep `.env` at the project root and runtime assets under `backend/data/`.

On Vercel, configure backend variables in the project's Environment Variables settings
for the target deployment environment, then redeploy. These runtime values are read
directly and take precedence over the local root `.env`; no `.env` file needs to be
uploaded. Vercel's application directory is read-only, so metadata logs go to the
runtime log stream and full local chat trace files are disabled there. A local trace
write failure also cannot interrupt chat or replace the original provider error.
