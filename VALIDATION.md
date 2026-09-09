# Validation — 2026-09-09

Launch repairs and local checks are complete. Live AI acceptance remains incomplete; passing a tool contract does not establish factual correctness.

## Verified locally

| Check | Result |
|---|---|
| Backend tests | **63 passed**, including five real local retrieval checks |
| Python lint and formatting | Passed with Ruff 0.16.6 |
| Frontend production build | Passed |
| Launcher | Works from outside `backend/`, selects `.venv`, and propagates failures |
| Entry points | `orbit.main:app` and compatibility `orbit.app:app` import the same application |
| Direct file launch | `python backend/orbit/main.py` delegates to the virtual environment launcher |
| Missing virtual environment | Clear setup instructions and nonzero exit code |
| Development origins | Both loopback hostnames accepted on the configured port; unrelated hosts and ports rejected |
| PostgreSQL | Live connection passed; five seeded students available |
| Development proxy | Page, health, login, and dashboard passed through `localhost:5173` |
| Browser | Student picker, signed-in dashboard, second-student session, and practice course/topic form verified |
| Dataset rehearsal | All **27,456 rows** preserved; **477,138** normalized question/topic rows |
| Original CSV reconciliation | Passed for all fields, allowing documented boolean capitalization normalization |
| Diff whitespace | Passed |

Tests ran in the existing Python 3.13.9 virtual environment. The frontend used Node.js 24.20.0. Two third-party Starlette/httpx deprecation warnings remain; there were no test failures.

The full-dataset rehearsal uses a temporary SQLite database. PostgreSQL connectivity was checked separately. No original data or credentials were replaced.

## Live model evaluation

The configured provider was tested with real API calls. Its 8,000-token-per-minute limit caused HTTP 429 responses. The app now retries temporary throttling within a bound and displays an actionable error when the quota remains unavailable. Repeated tabular metadata is encoded once for model context without dropping fields or rows.

- Initial 24-scenario run: **2 contract passes, 22 failures**, predominantly provider failures.
- After payload/retry improvements: **12 of 22 contracts passed** in a paced run of scenarios 3–24. Together with the successful initial scenario 1 and progress retry (scenario 2), the recorded baseline covers **14 of 24 passing contracts across separate runs**.
- Confirmed live capabilities include course lists, progress, missing scores, history, assessment listing, inactive-assessment rejection, retrieval, grounded practice generation, and course follow-ups.
- Manual review caught an unsupported, incorrect loss-percentage formula in a response that passed its tool contract. Source-only instructions were tightened. A targeted rerun returned the fixed insufficient-information response: it avoided the formula, but did not satisfy the available-material explanation request. This is still an answer-quality issue.
- The generated practice calculation reviewed was correct: dividing 150 in the ratio 3:7 gives 45 for the first part. Its narrative citation used Unicode hyphens; the structured source ID was correct. The prompt now requests verbatim source IDs.
- Broad-question routing instructions were clarified, and unbacked answers now use the fixed insufficient-information response. Automated regression checks pass. Live retests of scenarios 6 (pending questions) and 7 (weak topics) both passed after the routing changes; these are saved separately and do not replace the historical baseline.

## Remaining acceptance work

Complete a paced 24-scenario run against the final revision with sufficient provider quota, then review every answer against its tool outputs and sources. Resolve remaining tool-selection, overly conservative retrieval, and citation-format issues before calling the AI experience complete. Prompt improvements are mitigations, not proof of groundedness.

The image-upload stretch feature is deferred until core live acceptance passes, as required by the project instructions.

## Local evidence

All reports are under `backend/data/`, which is ignored by Git because it contains student records:

- `dataset_verification.json`: preservation counts and student coverage.
- `live_evaluation.json` and `live_evaluation_remaining.json`: initial run.
- `live_evaluation_retry.json`: successful progress retry.
- `live_evaluation_paced.json`: paced scenarios 3–24.
- `live_evaluation_summary.json`: combined baseline with run provenance and selected semantic-review notes.
- `live_evaluation_grounding_retry.json`: targeted grounding rerun.
- `live_evaluation_routing_retry.json`: targeted broad-question routing checks.

Turn-level tool inputs, outputs, errors, and latency are recorded in `backend/logs/turns.jsonl`. See the [README](README.md#check-the-project) for virtual environment commands and `--interval` pacing.
