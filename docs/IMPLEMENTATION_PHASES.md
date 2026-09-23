# Personal workspace implementation

The root `orbit-roadmap.md` and `orbit-build-spec.md` describe the intended
product. This file tracks delivery.

| Phase | Deliverable | Status |
| --- | --- | --- |
| 0 | Accounts, login, ownership, demo isolation | Implemented and locally verified |
| 1 | Subjects, dated marks, CSV, hackathon records, personal tools | Implemented and locally verified |
| 2 | Coding snapshots, source status, manual fallback | Implemented and locally verified |
| 3 | Paper ingestion, review, private retrieval | Implemented; local regression checks pass |
| 4 | Tools across all records and evidence-backed suggestions | Implemented; local regression checks pass |
| 5 | Saved practice attempts and feedback | Implemented and locally verified |
| 6 | Failure recovery, deletion, reconciliation, demo checks | Local hardening implemented; production verification pending |

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

## Earlier phase 0–2 validation

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
local MiniLM as assumed in the supplied documents. Personal papers retain that hosted model, store its full signature, and expose an
explicit re-index action; incompatible signatures are excluded from semantic
search. Keyword retrieval remains available without embeddings. Equal dimensions
do not make models compatible.


## Phases 5–6 and chat restoration (September 22, 2026)

Chat is the default personal workspace view. It has a full-height conversation,
a bottom multiline composer (Enter sends; Shift+Enter inserts a newline), visible
pending replies, Markdown tables/code, and expandable supporting records. Drafts
and in-flight replies survive switching workspace tabs. Failed sends restore the
draft. Clearing the session conversation requires confirmation and leaves learning
records intact. Suggestions live in Actions; academics, projects, coding, papers,
and practice remain available from navigation.

Revision `0006` adds `personal_practice`, with owner/subject foreign keys. Apply
with `python -m orbit.migrate` before running against an existing database; the
launcher already does this. No configured remote database was changed.

- Practice generates 1–10 validated questions from up to five matching confirmed
  personal questions, using keyword retrieval so embeddings are not required.
  Existing count, uniqueness, option, and citation validation runs with one retry.
  A configured model provider is required. The local demo does not fabricate quizzes.
- Sources must establish the answers. If papers only ask questions, the model is
  instructed to decline. Validation checks structure/citations, not semantic truth;
  feedback is visibly labeled AI-generated and should be checked against the source.
- Answer keys and explanations are withheld until submission, including through
  evidence and assistant tools. Scores are computed by the server. Submission is
  immutable and idempotent for identical answers; changed answers return 409.
- Sets, chosen answers, score, topic, difficulty, timestamps, and source snapshots
  persist across reloads. Changed/unconfirmed/deleted sources block submission of
  an old unfinished set. Historical completed attempts retain their snapshots after
  paper deletion; remove the practice set separately to remove those snapshots.
- `get_practice_history` is identity-bound. Missed answers in the latest completed
  subject/topic attempt support revision suggestions, explicitly separate from
  formal marks. A newer completion makes the old practice suggestion stale.
- Practice deletion is owner-scoped and confirmed in the UI. Subjects with saved
  practice sets return a useful conflict rather than a database error.
- A partially built frontend no longer prevents the backend from starting.
- Local tests cover second-account isolation, persisted attempts, source changes,
  provider failure, malformed generation, duplicate submission, deleted records,
  coding refresh recovery, confirmed-paper counts, and demo mark reconciliation.

| Endpoint | Purpose |
| --- | --- |
| GET /api/personal/practice | Owned saved sets and completed attempts |
| POST /api/personal/practice | Generate and save a validated private set |
| POST /api/personal/practice/{id}/answers | Grade and persist selected answers |
| DELETE /api/personal/practice/{id} | Delete an owned set/attempt |
| DELETE /api/personal/chat | Clear the current personal session conversation |

Backend verification: 188 passed, 5 optional tests skipped; Ruff passed.
Browser verification: 29 passed across personal (9), populated demo (3), and
legacy workspace (17) suites, including mobile and desktop layouts. The production
build passed with the existing-size bundle advisory (main bundle about 505 kB).
Production PostgreSQL/pgvector migration and live provider generation still require
verification in the deployment environment. Local tests use disposable SQLite and
synthetic provider fixtures; they do not establish live-provider semantic quality.

## Four-section workspace revision

The sidebar now has exactly Chat, Dashboard, Coding stats and Practice. Chat is
the default, with the composer at the bottom and drafts retained during navigation.
Academic management and suggested actions live inside Dashboard; hackathons live
inside Coding stats; question papers and quizzes live inside Practice.

- Dashboard starts empty. Users enter/import reported earned credits, target SGPA
  and semester SGPAs with a configurable scale. A line chart plots reported values;
  current subjects expose their marks and editable syllabus. No grades are inferred.
- Academic PDF/image imports use Gemini structured extraction. Uploads have
  processing/review/failed states, retry and removal. Review fields can be edited
  before an atomic, idempotent confirmation writes subjects, marks and reported
  values. Unmatched/incomplete marks reject the transaction instead of silently
  dropping rows. Uploads are limited to 10 MB.
- Coding stats separates DSA and development activity. Hero values come from the
  connected Codolio snapshot and manually recorded hackathons. Missing values
  prompt connection/entry. A public GitHub username saves public profile metadata;
  contribution charts still use the existing Codolio development snapshot.
- Practice projects collect selected subjects, text/Markdown or recognized PDF/image
  documents, and public GitHub source. Repository import pins a commit, selects at
  most 12 readable source files and bounds the stored snapshot to about 145k
  characters. It excludes hidden paths, symlinks and common generated directories.
  It does not clone/execute code, import private repositories or claim complete
  repository coverage. Material text is editable and removable.
- **Chat about this** selects the project in the main conversation. Tools retrieve
  query-ranked excerpts with source evidence and explicit coverage limits. The
  same saved conversation persists across sign-out; clearing chat removes that
  saved history. Concurrent conflicting saves return a reload conflict.
- Tool results are cached for 60 seconds by owner, validated arguments, database
  engine and a shared database revision. Application record writes change that
  revision in the same transaction, including background extraction/refresh writes.
  Cached citations are restored on hits; errors are not cached. Revision invalidation
  is conservative across accounts. Direct external SQL writes bypass the application
  invalidation hook and remain bounded by the cache TTL.

Migration `0007` adds the new workspace tables, durable history and cache revision.
Run the normal launcher or `alembic upgrade head` against the intended development
database. No existing production database was migrated during implementation.

Set `GEMINI_API_KEY` in the server environment to enable PDF/image recognition;
`GEMINI_MODEL` defaults to `gemini-3.8-flash` and can be overridden. The main chat
continues to use the existing configured LLM provider. Manual records and text
documents work without Gemini. API implementation follows Google's
[document processing](https://ai.google.dev/gemini-api/docs/generate-content/document-processing)
and [structured output](https://ai.google.dev/gemini-api/docs/structured-output)
documentation. Provider integrations are exercised with deterministic fixtures;
live Gemini recognition and deployment PostgreSQL behavior still need environment
verification.

Verification: backend suite 194 passed, 5 optional tests skipped; six new workspace
tests passed again after final retrieval changes; Ruff and production build passed.
The personal browser suite passed all 11 desktop/mobile flows, including empty
states, reported values, extraction review, public source import, project tool-cache
hits, account isolation and durable chat. The populated demo (3) and legacy
workspace (17) browser suites also passed, for 31 browser tests in total.
The main production bundle is about
531 kB and retains Vite's advisory to split chunks over 500 kB.
