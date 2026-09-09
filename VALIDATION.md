# Validation — 2026-09-09

| Check | Actual result | Scope |
|---|---|---|
| Automated backend tests | **43 passed** | Rules, identity isolation, session switching, fresh eligibility, lossless imports, caching, tool-loop limits, follow-ups, practice validation/retry, and real local retrieval |
| Python lint | **Passed** | `ruff check backend/orbit backend/tests backend/scripts` |
| React production build | **Passed** | Vite production bundle |
| Original-to-split reconciliation | **Passed: 27,456 rows** | Multiset comparison of all fields, allowing only boolean capitalization changes; duplicates included |
| Full importer rehearsal | **Passed** | Temporary SQLite verification database; 8,710 + 447 engagement rows, 17,689 + 610 submission rows preserved |
| Normalized question/topic records | **477,138** | Valid-ID source payloads; multiple topic tags expand records |
| Original-byte archive round trip | **Passed in importer fixture** | Gzip decompression reproduces original CSV bytes |
| Local embedding index | **9 lessons, 107 linked courses** | Sentence-transformer + FAISS; no LLM service involved |
| Relevant retrieval | **Passed** | Normalization cosine score 0.5678; Python tuple top score 0.5002 |
| Unrelated retrieval | **Passed** | Secret parking policy and chocolate-cake questions returned no chunks |
| Browser check | **Passed for setup screen** | Built React app loads; unconfigured service displays a clear message |
| Neon/PostgreSQL live connection | **Pending user configuration** | SQLite verification is not a substitute for a live PostgreSQL check |
| Live LLM / 24-scenario evaluation | **Pending user configuration** | No actual model answers or paid API evaluations claimed |
| Authenticated browser flow | **Pending Neon import** | Endpoint behavior tested with isolated fixtures; populated screens not yet browser-verified |

Two third-party deprecation warnings were emitted by the installed Starlette/httpx test integration; no test failures remained.

Detailed local audits are in `backend/data/import_report.json` and `backend/data/dataset_verification.json` (ignored by Git because they include dataset identifiers). Live evaluation will write `backend/data/live_evaluation.json`, with each answer requiring semantic review even when tool-contract checks pass.
