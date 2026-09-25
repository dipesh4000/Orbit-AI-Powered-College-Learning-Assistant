# Orbit

A personal learning workspace for academic marks, hackathon projects, and coding activity. Each account owns its records. The assistant reads those records through backend tools rather than inventing progress.

The personal workspace has four sections: **Chat**, **Dashboard**, **Coding stats**, and **Practice**. Chat is the default conversation view. Dashboard holds reported credits, target SGPA, semester results, subjects, syllabus and marks. Coding stats combines Codolio activity, a public GitHub profile and manually recorded hackathons. Practice holds projects, documents, public repository snapshots, question papers and quizzes; each project's **Chat about this** button selects its context in the main saved conversation.

## Landing page and navigation

Orbit already includes a public landing page at **`/`**. With `start.bat` running,
open [http://localhost:4176/](http://localhost:4176/) to view it. The normal demo
launcher opens [http://localhost:4176/demo](http://localhost:4176/demo) directly
in the preloaded workspace so it is ready to present. From the landing page, use
**Open preloaded demo** to enter that workspace, or **Create your workspace** to
reach registration in a live setup.

Once signed in, the sidebar provides **Chat**, **Dashboard**, **Coding stats**, and
**Practice**. These paths can also be opened directly: `/chat`, `/dashboard`,
`/coding`, and `/practice`. A production build served by FastAPI supports the same
paths, including `/demo`.

For backend source navigation, see [backend/orbit/README.md](backend/orbit/README.md).

Image/PDF recognition uses `GEMINI_API_KEY` on the server. Academic extraction produces an editable draft: only **Confirm and save** writes academic records. Manual entry and text documents work without Gemini. See the [phase tracker](docs/IMPLEMENTATION_PHASES.md) for delivered features and integration limits.

## Run on Windows

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js 22 or newer with npm. Open a terminal in this folder, which contains `backend/`, `frontend/`, and `start.bat`.

For a presentation-ready local demo without a database account or API keys:

```bat
start.bat
```

The launcher installs locked dependencies, starts a disposable local SQLite database, and opens **http://localhost:4176/demo** with a preloaded workspace. Chat uses local, rule-based responses; Coding stats contains clearly labeled illustrative problem solving, contest, activity, and development data. No API keys or PostgreSQL are needed. Demo records reset when the server stops.

For normal development with persistent records:

1. Copy `backend/.env.example` to **`.env` in this folder**, if `.env` does not already exist. Keep your existing credentials.
2. Set `DATABASE_URL` to your PostgreSQL / Neon connection string. Keep `COOKIE_SECURE=false`, `COOKIE_SAMESITE=lax`, and `ALLOWED_ORIGIN=http://localhost:5173` for local HTTP.
3. Run:

```bat
start.bat --live
```

Normal startup installs dependencies, applies Alembic migrations **to the database named by `DATABASE_URL`**, then opens **http://localhost:5173**. Use a development database. Existing records are preserved by the upgrades. Revision `0007` adds academic profiles/imports, learning projects/materials, and public GitHub profiles; the latest revision, `0008`, adds durable multi-chat history. No demo datasets are imported by the launcher.

Keep the launcher window open. **Ctrl+C stops both servers.** Startup checks occupied ports and reports failures instead of opening an unready app. Logs are written to `backend/logs/dev-backend.log` and `backend/logs/dev-frontend.log` and replaced on the next launch.

| Command | Purpose |
| --- | --- |
| `start.bat` | Install and open the preloaded local demo on 4176 / 8011 |
| `start.bat --live` | Install, migrate configured PostgreSQL, and run on 5173 / 8000 |
| `start.bat --demo` | Explicit form of the default local demo |
| `start.bat --sandbox` | Install and run a disposable local workspace on 4176 / 8011 |
| `start.bat --check` | Check installed dependencies and local configuration; no installs, migrations, or database connection |
| `start.bat --test` | Install dependencies and Chromium; run backend tests, production build, personal browser tests, and legacy UI tests |

First startup needs internet access for dependency downloads. Normal development needs access to PostgreSQL. An LLM key is optional for record management and coding dashboards; it is needed for assistant answers. Public Codolio imports need no key.

## Try the flow

1. **Create an account** with a password of at least 12 characters.
2. **Academics:** create a subject, add a dated mark, and reload. Edit the mark or try the downloadable CSV template. Invalid imports leave existing marks unchanged.
3. **Projects:** record a hackathon, your role, project, and reflection. Optionally preview a public GitHub repository before applying its metadata.
4. **Coding:** connect your public Codolio handle, for example `dipesh4000`, then select **Refresh** to save a snapshot. Explore **Problem solving** and **Development** for all reported breakdowns, activity calendars, totals, and language shares.
5. **Refresh and reload:** each successful refresh saves another snapshot. A provider error shows a warning and retains the last successful data. Reloading reads Orbit's database and does not call Codolio.
6. **Manual fallback:** enter totals manually, leaving unknown fields blank. Switch between Codolio and Manual to inspect each source independently. Updates save dated history; they do not add the two sources together.
7. **Assistant:** with a provider configured, ask about your marks, hackathons, or saved coding data.
8. Sign out and create a second account to verify that the workspace starts empty.

Disconnecting Codolio asks for confirmation and removes the connection and its imported history. Manual history has its own removal action. Failed refreshes and disconnected in-flight refreshes cannot replace or restore deleted snapshots.

## What the coding dashboard measures

The interface takes inspiration from the supplied [problem-solving](https://codolio.com/profile/dipesh4000/problemSolving) and [development](https://codolio.com/profile/dipesh4000/devStats) pages, while retaining Orbit's navigation and visual style.

- Problem-solving totals use `codolioCardDetails.totalQuestionsSolved` and `totalActiveDays`.
- GitHub contributions use **`githubProfileDetails.totalContributions`**, consistently. Codolio exposes another contribution figure in a separate card; Orbit does not mix these measures.
- Development metrics use reported commits, stars, pull requests (`pushRequestsCount`), and issues. The calendar displays daily activity for the 365-day window ending at the snapshot's saved date, using UTC dates. Missing days are marked as unreported, not zero.
- Language percentages are calculated from reported code bytes. They do not measure proficiency or time spent.
- Available problem-solving sections in the public provider response are saved and displayed, including difficulty, platform, contest, rating, topic, and activity details when reported. Missing fields stay unreported. The local demo shows illustrative examples of those sections.
- Every snapshot has a source and saved timestamp. Provider update time is separate because Codolio does not supply its timezone.
- Raw responses and normalized evidence are stored privately. API responses expose bounded public coding sections while excluding account details; they do not expose the raw profile payload.

Codolio's endpoint is undocumented and may change. Refresh has a bounded timeout and response-size limit. A refresh interrupted by a server restart can be retried after its 60-second lease expires. Saved dashboards work independently of the provider, but the Orbit backend and database must still be reachable; this is not a browser-only offline app.

## Manual setup and checks

For detailed configuration, optional demo import, and provider settings, see [GET_STARTED.md](GET_STARTED.md). Hosted setup is covered in [Deployment](docs/DEPLOYMENT.md).

```sh
# backend/
uv sync --frozen
uv run python -m orbit.migrate
uv run uvicorn orbit.main:app --reload --host 127.0.0.1 --port 8000

# frontend/ in another terminal
npm ci
npm run dev
```

Tests use temporary SQLite databases and synthetic external responses. They do not migrate your configured PostgreSQL database or spend LLM credits. Personal browser tests start their own API on 8011 and frontend on 4176; stop the interactive sandbox before running them.

```sh
# backend/
uv run pytest -q
uv run ruff check orbit migrations tests ../scripts/dev.py

# frontend/
npm run build
npx playwright install chromium
npx playwright test --config playwright.personal.config.js
npx playwright test --workers=2
```

For an already installed compatible Chromium, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`. Browser fixtures are enabled only by test configuration; the interactive sandbox uses the live Codolio adapter.

## Architecture and boundaries

| Layer | Implementation |
| --- | --- |
| Interface | React 19, Vite 6, React Router, Lucide, responsive CSS |
| API | FastAPI, Pydantic validation, HTTPX provider adapters |
| Persistence | PostgreSQL / Neon, SQLAlchemy, Alembic migrations |
| Identity | Argon2 passwords, opaque HttpOnly session cookies, owner-scoped records |
| Personal assistant | Bounded tool loop; subject, assessment, hackathon, and coding snapshot tools |
| Model providers | Anthropic or OpenAI-compatible primary; optional NVIDIA fallback |
| Legacy retrieval | Hosted BAAI/bge-small-en-v1.5 embeddings and FAISS; separate demo material |
| Verification | pytest, Ruff, Playwright, production build |

The supplied-data demo remains optional behind `DEMO_ENABLED=true` and uses separate routes. Personal accounts cannot access its tools or records. Demo retrieval and practice are not yet personal paper/practice features. Personal papers, reviewed questions, and private retrieval arrive in Phase 3; broader suggestions and saved personal practice follow later.

Password reset, email verification, and deployment-level authentication rate limits remain future hardening work. Use HTTPS and secure cookies for hosted deployments. Tests check migrations and ownership with SQLite; production PostgreSQL verification is separate.


### Chat and saved practice

Personal workspaces now open in chat. Use **Actions** for evidence-backed next
steps and **Practice** to generate a quiz from confirmed paper material, resume a
saved set, and review persisted feedback. Practice scores stay separate from
formal marks. Existing databases need migration `0006`; `start.bat` applies it,
or run `python -m orbit.migrate` from `backend/`.

Quiz generation needs a configured model and source text that establishes the
answers. Saved records remain usable when a provider is unavailable. See
[implementation phases](docs/IMPLEMENTATION_PHASES.md) for validation and limits.
