# Orbit deployment

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
