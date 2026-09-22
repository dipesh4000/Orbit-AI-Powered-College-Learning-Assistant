# Personal workspace implementation

The root `orbit-roadmap.md` and `orbit-build-spec.md` describe the intended
product. This file tracks delivery.

| Phase | Deliverable | Status |
| --- | --- | --- |
| 0 | Accounts, login, ownership, demo isolation | Implemented and locally verified |
| 1 | Subjects, dated marks, CSV, hackathon records, personal tools | Implemented and locally verified |
| 2 | Coding snapshots, source status, manual fallback | Implemented and locally verified |
| 3 | Paper ingestion, review, private retrieval | Next |
| 4 | Tools across all records and evidence-backed suggestions | Pending |
| 5 | Saved practice attempts and feedback | Pending |
| 6 | Failure recovery, deletion, reconciliation, demo checks | Pending |

## Setup and migrations

From `backend/`, configure `DATABASE_URL` in **Orbit/.env** (the repository root)
or the process environment, then run:

```sh
uv sync --frozen
uv run python -m orbit.migrate
uv run uvicorn orbit.main:app --reload
```

Start the frontend separately with `npm run dev` from `frontend/`, or use
`start.bat` from the repository root to install dependencies, migrate, and launch
both servers. `start.bat --sandbox` runs an isolated temporary local workspace
without touching the configured PostgreSQL database.

The Alembic upgrade adopts existing Phase 0 tables and preserves their records.
Revision `0001` creates/adopts `workspace_owners` and `personal_subjects`.
Revision `0002` adds `personal_assessments`, `personal_hackathon_events`, and an
owner/subject composite foreign key that prevents cross-account mark references.
Revision `0003` adds owner-bound `coding_connections` and `coding_snapshots`.

`uv run alembic upgrade head` is also supported from `backend/`. The Python
wrapper additionally serializes PostgreSQL upgrades with an advisory lock.
`python -m orbit.accounts` remains a compatibility setup command. Destructive
downgrade is disabled; use a database backup when rolling back data.

No remote database migration was run during development. Tests use SQLite;
production PostgreSQL verification remains pending.

## Phase 0

- Normalized unique emails, Argon2id password hashing, and password verification.
- Opaque HttpOnly sessions, eight-hour expiry, rotation on login, and database
  revocation on logout. Restoring a personal session checks the owner exists.
- Separate personal and demo endpoints. Personal accounts cannot call legacy
  demo services, and demo accounts cannot call personal services.
- Demo mode defaults off; set `DEMO_ENABLED=true` for the imported-data demo.
- Use `COOKIE_SECURE=true` on HTTPS deployments and an explicit allowed origin.
- Password reset, email verification, and deployment-level authentication rate
  limits are not implemented.

## Phase 1

- Subject create/read/edit/delete. Remove its marks before deleting a subject;
  the UI does not silently cascade-delete academic records.
- Formal marks with title, score, maximum, date, assessment type, and reported
  weak topics. Negative, nonfinite, over-maximum, and future-dated marks fail
  validation. The maximum calendar date is evaluated in UTC in both layers.
- Atomic CSV import: selected file text is sent as JSON. Limits: 1 MB in the UI,
  one million characters in the API, and 1,000 rows. Errors identify row numbers;
  any invalid row rejects the entire import. Re-importing adds new records.
- CSV subject codes resolve within the signed-in account. Include `semester`
  when the code appears more than once. The downloadable template includes it.
- Hackathon records include name, date, role, project, description, technologies,
  repository/submission links, result, and reflection.
- GitHub enrichment uses public repository metadata. Preview, apply to form,
  and save are separate actions. Failure preserves manual form values.
- Personal tools: `get_subjects`, `get_assessments`, and `get_hackathons` use the
  existing six-round chat loop and provider fallback with their own schemas and
  prompt. Identity is session-bound; model-supplied identities fail validation.
- Chat history persists in the personal session, not demo conversation tables.
  An LLM provider must be configured for factual AI responses.
- Counts and percentages are computed in Python. Subject changes compare the
  same assessment type and maximum on an earlier date. No combined score.

## API

| Endpoint | Purpose |
| --- | --- |
| POST /api/auth/register | Create account and session |
| POST /api/auth/login | Authenticate and rotate session |
| GET /api/session | Restore session |
| DELETE /api/session | Revoke session |
| GET/POST /api/subjects | List/create subjects |
| GET/PUT/DELETE /api/subjects/{id} | Read/edit/delete owned subject |
| GET/POST /api/assessments | List/create marks |
| GET/PUT/DELETE /api/assessments/{id} | Read/edit/delete owned mark |
| POST /api/assessments/import | Atomic CSV import via content field |
| GET/POST /api/hackathons | List/create events |
| GET/PUT/DELETE /api/hackathons/{id} | Read/edit/delete owned event |
| GET /api/personal/workspace | Owned records and computed summaries |
| POST /api/personal/github-preview | Public repository preview via url field |
| GET/POST /api/personal/chat | Read history/send message |

## Phase 2

The supplied [problem-solving dashboard](https://codolio.com/profile/dipesh4000/problemSolving)
and [development dashboard](https://codolio.com/profile/dipesh4000/devStats) informed
Orbit's separate coding views, metric cards, activity calendar, and language bar.
The public endpoint was verified on September 22, 2026; reference account data is
never seeded into a new Orbit account.

- One connected Codolio handle per owner. An explicit refresh starts a bounded
  background fetch; the page polls saved state and stays usable throughout.
- Successful refreshes save private raw JSON and normalized evidence, with an
  Orbit timestamp. The dashboard and assistant read only database snapshots.
- Provider failures retain the last successful snapshot and show an error.
  Source timestamps, a 24-hour age label, and a separate provider-reported
  GitHub update time make freshness visible. Provider time has no timezone.
- GitHub contribution totals consistently use `githubProfileDetails.totalContributions`.
  Calendar dates use UTC and missing days remain unknown. Language shares use
  reported bytes, not proficiency. No difficulty/topic counts are invented.
- Manual totals save separate dated snapshots; blanks remain null and known
  zeros remain zero. History shows the latest 20 snapshots per source; all
  snapshots stay stored until the owner removes that source's history.
- Disconnect deletes imported history and invalidates in-flight work. Manual
  history has a separate confirmed removal path. Backend leases prevent
  overlapping refreshes and allow retry after 60 seconds if a worker stops.
- `get_coding_snapshot` is now available to the personal assistant. It is
  owner-bound and exposes no raw profile payload. This brings one Phase 4 tool
  forward so coding data works in the existing assistant flow.
- LeetCode enrichment remains optional and deferred. The Orbit backend/database
  must still be reachable; provider independence is not browser-only offline mode.

| Endpoint | Purpose |
| --- | --- |
| GET /api/coding | Saved snapshots, history, and connection status |
| POST /api/coding/connection | Connect a public Codolio handle |
| POST /api/coding/refresh | Start background refresh (202); poll GET /api/coding |
| DELETE /api/coding/connection | Disconnect and remove imported history |
| POST /api/coding/manual | Save validated self-reported totals |
| DELETE /api/coding/manual | Remove manual history |

## Validation

Validation: 174 backend tests passed, 5 skipped; all 22 browser tests passed.
Browser checks include existing account/record flows and new coding flows at
mobile and desktop widths. Launcher startup, API proxy, snapshot persistence,
and shutdown were smoke-tested with disposable local data.
Production build and lint passed. The tests cover
ownership boundaries, CRUD, grading validation, CSV atomicity, migration of
existing Phase 0 records, database foreign keys, tool binding, GitHub failures,
and mobile/desktop flows. External model and GitHub calls use test doubles;
browser record flows use real local FastAPI endpoints and a disposable database.
Codolio browser fixtures are synthetic and restricted to the test server. The
normalizer was also checked against the live provider response. No production
PostgreSQL migration or external model call was performed.

```sh
# backend/
uv run pytest
uv run ruff check orbit migrations tests
# frontend/
npm run build
npx playwright test
npx playwright test --config playwright.personal.config.js
```

The personal browser config starts a temporary backend on 8011 and Vite on 4176.
It uses the backend virtual environment, never Neon. Install matching Playwright
Chromium or set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to a compatible executable.

## Phase 3 implementation difference

The current code uses hosted `BAAI/bge-small-en-v1.5` with a query prefix, not
local MiniLM as assumed in the supplied documents. Choose the model and
re-indexing strategy explicitly; equal dimensions do not make models compatible.
