# Orbit deployment

Local installation and data preparation live in [GET_STARTED.md](../GET_STARTED.md).

## Why the full Vercel deployment exceeds 500 MB

The reported 5,646.89 MB is the function bundle, not the frontend build. Vercel's
Python function limit is **500 MB uncompressed**, including dependencies. Increasing
request memory or splitting routes does not remove libraries shared by each function.
See [Vercel function limits](https://vercel.com/docs/functions/limitations).

This repository's root `vercel.json` declares both frontend and backend services.
The backend depends on `sentence-transformers`, which brings in PyTorch. The current
Linux lockfile also resolves CUDA libraries and Triton. Those are a likely major
contributor to the multi-gigabyte build; the exact Vercel artifact has not been inspected.
Local virtual environments and model caches can add more if uploaded with a project.

The NVIDIA chat API is remote HTTPS inference and does not require local CUDA.
Local PyTorch is used for MiniLM embeddings, independently of the chat provider.

## Where to deploy

| Setup | Recommendation for Orbit |
| --- | --- |
| Paid Render web service, serving React and FastAPI together; Neon database | Simplest full-project setup: one origin, one service, no cross-site session cookies |
| Vercel static frontend; paid Render backend; Neon database | Keep Vercel for the UI and route API requests to the backend |
| Railway service with a volume; Neon database | Alternative for a persistent Python service with usage-based billing |
| Entire current backend in Vercel Functions | Poor fit for the local ML dependency footprint and process-local sessions |

Start evaluation with approximately **2 GB RAM for the backend**, then measure loaded
model memory and concurrent requests before choosing a smaller plan. This is a sizing
estimate, not a measured minimum. A GPU is not needed for the small embedding model.
Paid persistent storage is useful for the index and downloaded embedding weights.
Render free services sleep after inactivity and cannot attach a persistent disk.

References: [Render FastAPI](https://render.com/docs/deploy-fastapi),
[Render free-service restrictions](https://render.com/docs/free),
[Render disks](https://render.com/docs/disks),
[Railway pricing](https://docs.railway.com/pricing),
[Railway volumes](https://docs.railway.com/volumes/reference).

## Option A: full project on Render

Use the repository directory containing both `frontend/` and `backend/` as the service
root. The build environment must provide Node.js/npm and Python/uv. For a native
Python service, verify Node is available in its build environment; a Docker service
with both runtimes is an alternative if your environment does not provide them.

Build command, from that root:

```sh
npm --prefix frontend ci && npm --prefix frontend run build && pip install uv && uv sync --directory backend --frozen --no-dev
```

Start command:

```sh
uv run --directory backend --no-sync uvicorn orbit.main:app --host 0.0.0.0 --port "$PORT" --workers 1
```

Use one instance. Set `VITE_API_BASE_URL=/api` before the frontend build, and configure
the backend variables from `backend/.env.example` in Render's environment settings.
Set `ALLOWED_ORIGIN` to the exact public app origin, `COOKIE_SECURE=true`, and
`COOKIE_SAMESITE=lax`. Configure `/api/health` as the health-check path.

Before testing course chat or practice:

1. Prepare the Neon database using the local ingestion commands in GET_STARTED.md.
   Do not import student CSVs during every deployment.
2. Build the course index locally with `uv run python -m orbit.rag` from `backend/`.
3. Provision both `backend/data/rag/` and `backend/data/models/` on the service,
   using a private transfer or a controlled setup step. The model cache must include
   the actual weight files, not broken symlinks. Do not copy `.venv` between systems.
4. On Render, attach a disk at the absolute `backend/data` directory inside the
   deployed checkout. With the standard repository-root checkout this is
   `/opt/render/project/src/backend/data`; verify the path in the service shell.
5. Populate the disk at runtime: Render disks are not available during build steps.
   Mounting an empty disk over files created at build time hides those files.

Alternatively, rebuild the index and model cache during each build, with the required
dataset securely available to that build. Never commit student CSVs or API keys just
to make a deployment succeed. Requests require pre-provisioned weights because the
retriever loads with `local_files_only=True`.

## Option B: keep the frontend on Vercel

Create or reconfigure the Vercel project with **Root Directory = `frontend`**, framework
**Vite**, build command `npm run build`, and output directory **`dist`**. Disable inclusion
of files outside the root when not needed. Do not reuse the repository-root multi-service
configuration: it explicitly deploys the oversized backend.

Deploy FastAPI separately using the Render backend instructions below. For reliable
same-origin sessions, add a `frontend/vercel.json` like this after replacing the
example hostname with the actual backend URL:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "rewrites": [
    { "source": "/api/:path*", "destination": "https://YOUR-BACKEND.onrender.com/api/:path*" },
    { "source": "/:path*", "destination": "/index.html" }
  ]
}
```

Set frontend `VITE_API_BASE_URL=/api`. On the backend set `ALLOWED_ORIGIN` to the
Vercel frontend's exact HTTPS origin, `COOKIE_SECURE=true`, and `COOKIE_SAMESITE=lax`.
Keep API responses uncached. Verify login, logout, a page reload, and a long chat request
through the deployed proxy; host proxy timeouts still apply and cannot be changed by
the browser's timeout setting. An always-on backend avoids routing a long cold start
through the proxy. See [Vercel external rewrites](https://vercel.com/docs/routing/rewrites).

## Reducing the backend footprint

For CPU hosting, use the CPU-only PyTorch index rather than shipping unused GPU
libraries. The following is an optional dependency change to make in `backend/pyproject.toml`
and validate before deployment; it has not been applied automatically:

```toml
[tool.uv.sources]
torch = [{ index = "pytorch-cpu" }]

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true
```

Declare `torch` as a direct dependency as well (for example, add `"torch>=2.2,<3"`
to the existing `project.dependencies` list) so its source is explicit. Then run
`uv lock`, `uv sync`, and the backend tests, and exercise an actual course search.
Commit the updated lockfile together with the dependency configuration. Follow
[uv's PyTorch guide](https://docs.astral.sh/uv/guides/integration/pytorch/) for platform-specific
wheel availability. Build deployments with `uv sync --frozen --no-dev`.

Exclude `.venv`, local caches, logs, datasets, and `node_modules` from source uploads.
Required model weights and the index must still be provisioned separately. CPU-only
PyTorch reduces size but does **not** guarantee this backend fits Vercel's 500 MB limit.
Fitting serverless would require a larger redesign, such as remote embeddings and
external session storage; merely moving routes into separate functions is insufficient.

## Route contract

| Browser page | API operations |
| --- | --- |
| `/login` | `GET /api/health`, `GET /api/students`, `POST /api/login` |
| `/chat` | `POST /api/chat`, `GET /api/conversations`, conversation open/reset operations |
| `/dashboard` | `GET /api/dashboard`, `GET /api/eligibility/{assessment_id}` |
| `/practice` | `GET /api/courses`, `GET /api/topics/{course_id}`, `POST /api/practice` |

`GET /api/session` restores a session and `DELETE /api/session` ends it. The older `POST /api/session` remains a compatible alias for login. Browser routes support refresh and back/forward navigation. A protected deep link returns to the requested page after profile selection. Unknown browser paths redirect to the default page in the SPA; unknown API paths remain JSON 404s. The combined FastAPI host only serves the five explicit browser paths.

## Recommended hosting for cold starts

Serve `frontend/dist` from an always-available static host, with a same-origin reverse proxy forwarding `/api/*` to the Render backend. Set the proxy timeout to at least 120 seconds and preserve request cookies, response `Set-Cookie` headers, and the original browser Origin. Set `ALLOWED_ORIGIN` to the exact public frontend origin. Keep API responses uncached. Set an SPA rewrite for browser requests to `/index.html`, after the API rule.

This lets the login screen load while the backend sleeps. Serving both frontend and backend from one sleeping Render service delays the HTML itself, so the app cannot display its wake-up screen until that service responds.

Frontend build, from `frontend/`:

```sh
npm ci
npm run build
```

Publish `frontend/dist`. Use `VITE_API_BASE_URL=/api` for a same-origin proxy. Vite embeds this value at build time; rebuild after changing it. No secrets belong in `VITE_*` variables.

For a directly addressed separate backend, set `VITE_API_BASE_URL` to its full HTTPS origin plus `/api`. Set `ALLOWED_ORIGIN` to the frontend's exact HTTPS origin, `COOKIE_SECURE=true`, and, if the origins are cross-site, `COOKIE_SAMESITE=none`. Browser third-party-cookie restrictions can still prevent cross-site sessions; use the same-origin proxy or custom domains on the same site for reliable login. Local development defaults remain `COOKIE_SECURE=false`, `COOKIE_SAMESITE=lax`.

## Render backend

Use `backend/` as the service root and Python 3.11–3.13. Build with:

```sh
pip install uv
uv sync --frozen --no-dev
```

Start with:

```sh
uv run uvicorn orbit.main:app --host 0.0.0.0 --port "$PORT" --workers 1
```

Configure the environment values described in `backend/.env.example`, including the database and model provider. Set `COOKIE_SECURE=true` for HTTPS deployments. Use `/api/health` as the Render health-check path. This is a lightweight liveness check with configuration flags, not a database/model readiness guarantee; the UI separately loads the student catalog and reports failures.

Before accepting users, provision the imported database and course retrieval index using the existing backend setup instructions. Do not rely on a free service's ephemeral filesystem for durable records. Sessions currently live in process memory: deploy one worker and expect users to select their profile again after a restart. Conversations persist in the configured database.

The app remains a **demo student selector, not identity authentication**. An authenticated identity provider and authorization policy are necessary before exposing private student data to real users.

## Connection behavior

The login page pings immediately. After three seconds it explains the typical 60–90-second wake-up delay. Only health GETs retry automatically, with 12-second request bounds, two-second pauses, and a total two-minute budget. Failed startup displays a retry button. Navigation/unmount cancels startup work. Login, chat, and practice mutations are never automatically replayed. A 401 from a protected request clears the local session and returns to login.

## Verification

```sh
cd frontend
npm ci
npx playwright install chromium
npm test
npm run build
cd ../backend
uv run pytest -q
uv run ruff check orbit tests scripts
uv run ruff format --check orbit tests scripts
```

Browser tests use synthetic API responses and cover deep links, login/logout, session expiry, slow startup/recovery, failures/retry, and 360px/768px/1440px layouts including wide Markdown tables. Screenshots are written to `frontend/test-results/`. To use an existing Chromium installation, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to the browser executable.

The built frontend route tests require `npm run build` before starting pytest. Actual Render wake-up duration, proxy configuration, and production cookies must also be checked against the deployed URLs.

Hosting references: [Render free services](https://render.com/docs/free), [Render health checks](https://render.com/docs/health-checks).
