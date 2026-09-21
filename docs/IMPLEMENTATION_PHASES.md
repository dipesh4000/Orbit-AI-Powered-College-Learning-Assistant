# Personal workspace implementation

The root `orbit-roadmap.md` and `orbit-build-spec.md` describe the intended
product. This file tracks delivery.

| Phase | Deliverable | Status |
| --- | --- | --- |
| 0 | Accounts, login, ownership, demo isolation | Implemented and locally verified |
| 1 | Subjects, dated marks, CSV, hackathon records, personal tools | Implemented and locally verified |
| 2 | Coding snapshots, source status, manual fallback | Next |
| 3 | Paper ingestion, review, private retrieval | Pending |
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

Start the frontend separately with `npm run dev` from `frontend/`.

The Alembic upgrade adopts existing Phase 0 tables and preserves their records.
Revision `0001` creates/adopts `workspace_owners` and `personal_subjects`.
Revision `0002` adds `personal_assessments`, `personal_hackathon_events`, and an
owner/subject composite foreign key that prevents cross-account mark references.

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

## Interface references and Phase 2

The supplied [problem-solving dashboard](https://codolio.com/profile/dipesh4000/problemSolving)
and [development dashboard](https://codolio.com/profile/dipesh4000/devStats) were
inspected on September 21, 2026. Orbit uses a profile/navigation sidebar,
separate metric cards, and Academics, Projects, Assistant, and Coding sections.
The Coding section explicitly has no source connected yet.

Next: Codolio snapshots, refresh timestamps, manual fallback, problem-solving
totals, activity heatmaps, and development/language panels. Verify each provider
field, label its source, preserve snapshots on failure, and keep unrelated
measures separate. Do not seed reference-page statistics as live data.

## Validation

Validation: 154 backend tests passed, 5 skipped; all 20 browser tests passed.
Production build and lint passed. The tests cover
ownership boundaries, CRUD, grading validation, CSV atomicity, migration of
existing Phase 0 records, database foreign keys, tool binding, GitHub failures,
and mobile/desktop flows. External model and GitHub calls use test doubles;
browser record flows use real local FastAPI endpoints and a disposable database.

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
