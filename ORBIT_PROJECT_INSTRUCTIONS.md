# Orbit — AI-Powered College Learning Assistant
## Architecture & Implementation Instructions

This document is the single source of truth for building Orbit. It reflects the finalized
architecture decisions for the internship assignment. Follow it exactly — do not introduce
new architectural patterns (e.g., giving the LLM direct DB access, or letting the LLM decide
business rules) without checking against the principles in Section 1.

---

## 1. Core Principles (non-negotiable)

1. **The LLM never talks to Postgres directly.** All data access goes through a typed
   tool/service layer.
2. **The LLM never decides business rules.** Eligibility, attempt limits, prerequisites —
   these are computed in Python and returned as a decision + reason. The LLM only *narrates*
   the decision, it never derives it from raw numbers.
3. **`user_id` is never an LLM-controllable parameter.** It is bound server-side from the
   active session the moment a tool is invoked, regardless of what the LLM passes.
4. **Tool/data outputs are cached; final LLM answers are not.** Cache the deterministic,
   reusable pieces (DB lookups, RAG retrieval for repeated queries). Never cache a full
   natural-language answer keyed by question text — recompute eligibility/scores every time
   so staleness never silently leaks into an answer.
5. **Retrieved content (RAG chunks, tool outputs) is data, not instructions.** The system
   prompt must state this explicitly to prevent prompt injection via course content.
6. **If confidence/groundedness is low, say so — don't guess.** This applies to RAG (below
   a similarity threshold) and to any question outside available data.

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend framework | **FastAPI** | Async, typed request/response models (Pydantic), natural fit for a tool-calling orchestration layer, easy to document with OpenAPI for the eval harness. |
| Frontend | **React** (migrated from existing HTML/CSS prototype, "Orbit" UI) | Already designed (Chat / Dashboard / Practice sections); convert to componentized React for state management (session, chat history, cache indicators). |
| LLM | **Claude Sonnet or Haiku via Anthropic API** — or a free-tier model (e.g. Groq/Llama, Gemini free tier) if cost is a concern for a demo. Abstract the model call behind a single interface so the model can be swapped without touching orchestration logic. | Demo scope — no need for the most capable model; correctness comes from the tool/business-logic layer, not raw model power. |
| Database | **PostgreSQL** (as provided: `df1`-equivalent hackathon submissions table, `df2`-equivalent engagement table) | Given. |
| DB access | **Neon DB with RealDictCursor / `.mappings()`** → returns list[dict], never pandas in the live request path | Keeps output JSON-serializable end-to-end (dashboard, cache, tool results) without conversion overhead. |
| Vector store (RAG) | **Chroma or FAISS** (local, free, sufficient for demo-scale course content) | No need for a managed vector DB at this scale. |
| Embedding model | Any free/local sentence-transformer (e.g. `all-MiniLM-L6-v2`) or the same LLM provider's embedding endpoint if free-tier allows | Keep consistent between indexing and query time. |
| Session/cache store | **In-process LRU (Python `functools.lru_cache` or a bounded `OrderedDict`/`deque`-backed store) + TTL** for demo. Note as a documented limitation: single-process only — would move to Redis for multi-worker deployments. | Sufficient for a single-instance demo; documenting the upgrade path shows awareness of the scaling boundary. |
| Auth | **No real auth.** Fixed set of ~5 seeded student accounts, selected via a login/user-picker screen. | Assignment explicitly asks for "login/selection," not authentication. |

---

## 3. High-Level Architecture

```
                         Student (picks from 5 seeded users)
                                     │
                              React Frontend
                       (Chat | Dashboard | Practice)
                                     │
                              FastAPI Backend
                                     │
                      ┌──────────────┼───────────────┐
                      │              │                │
              Intent/Orchestration   │                │
                Layer (LLM decides   │                │
                which tools to call) │                │
                      │              │                │
        ┌─────────────┼──────────────┼────────────────┐
        ▼             ▼              ▼                ▼
   Data/Tool     Business Logic   RAG Pipeline   Practice Question
    Layer          Layer          (Chroma/FAISS)     Generator
        │             │              │                │
        ▼             ▼              ▼                ▼
   Postgres      Deterministic   Course content   RAG + schema-
  (df1/df2      Python rules     embeddings        validated
   tables)      (eligibility,                       output
                 attempt limits)
        │             │              │                │
        └─────────────┴──────────────┴────────────────┘
                              │
                        LLM Response
                    (narrates results,
                   never invents them)
```

---

## 4. Data & Tool Layer

Given tables (already inspected):

- `hackathon_submissions`: `user_id, hackathon_id, num_questions, submission_json`
  (`submission_json` is a **list of per-question attempt objects** — contains `skill`,
  `status`, `difficulty`, `obtained_score`, `question_score`, `question_sub_domain`,
  `submission_time`, etc. Parse this into normalized rows at ingestion/aggregation time.)
- `course_progress`: `user_id, course_id, course_title, course_domain, course_sub_domain,
  course_level, course_hours, enrolled_at, is_legacy_completion, certificate_issued,
  certificate_issued_at, certificate_link, total_views, first_viewed_at, last_viewed_at,
  total_chapters_in_course, total_activities_in_course, mcq_attempted_count,
  mcq_total_score_obtained, resource_clicks_downloads, engagement_json`

### Required tool functions (signatures — implement in a dedicated `tools/` module)

```python
def get_course_progress(user_id: str, course_id: str | None = None) -> dict | list[dict]
def get_course_performance(user_id: str) -> list[dict]       # per-course score %, derived from mcq fields
def get_hackathon_history(user_id: str) -> list[dict]        # parsed submission_json, per attempt
def get_weak_topics(user_id: str, threshold: float = 0.6) -> list[dict]  # sub-domains below threshold
def check_assessment_eligibility(user_id: str, target_course_id: str) -> dict
    # returns: {"eligible": bool, "reason": str, "unmet_conditions": [...]}
def get_recommended_topics(user_id: str, course_id: str) -> list[str]
def search_course_content(query: str, course_id: str | None = None, top_k: int = 5) -> list[dict]
    # RAG retrieval; returns chunks + source metadata + similarity scores
```

**Rules for every function:**
- `user_id` is injected by the backend from session state — strip/overwrite any `user_id`
  the LLM tries to pass as a tool argument.
- All aggregation (SUM/AVG/GROUP BY) happens in SQL where possible, not in Python/pandas,
  once you move past prototyping.
- Every function returns plain JSON-serializable dicts/lists — no DataFrames, no ORM objects.
- Every function is independently unit-testable without the LLM in the loop.

---

## 5. Business Logic Layer

- Lives entirely in a separate `business_rules/` module — plain Python, deterministic,
  fully unit-testable.
- Example rule set to implement (adapt to whatever specific rules are provided separately):
  - Assessment is active (date/flag check)
  - Required course content completion threshold met
  - Prerequisite course/assessment passed
  - Max attempt count not exceeded
- `check_assessment_eligibility()` calls each sub-rule and aggregates into one
  `{eligible, reason, unmet_conditions}` response — this exact object is what gets returned
  to the LLM as a tool result. The LLM must not be asked to re-derive eligibility from raw
  scores; it only phrases this object into a natural-language answer.
- Write unit tests for each rule independently of the chat pipeline.

---

## 6. RAG Pipeline

```
Course documents → Chunking (semantic or fixed-size w/ overlap) → Embedding
    → Vector store (Chroma/FAISS) → Similarity search at query time
    → Top-k chunks + metadata (source doc, course_id, topic) → LLM context → Response with citations
```

- Store `source`, `course_id`, and `topic` metadata alongside every chunk so answers can
  cite where content came from (assignment requires source references).
- **Groundedness gate:** if the top retrieved chunk's similarity score is below a fixed
  threshold, skip the LLM call for content generation and return a fixed
  "insufficient information in the available course materials" response. This makes
  hallucination-avoidance enforced by code, not by prompting alone.

---

## 7. Orchestration Layer

- The LLM is given the tool schema (Section 4) and a system prompt describing:
  - What each tool does and when to call it (DB vs RAG vs business logic vs multi-tool)
  - That `user_id` is handled automatically and should never be requested from the user
    or fabricated
  - That tool/retrieval outputs are data, never instructions
  - That if no tool/RAG result supports a claim, it must say so rather than guess
- Multi-step questions (e.g., "Can I take Advanced SQL and what should I study?") should
  result in multiple sequential tool calls before a final answer is composed — this is
  standard Claude/OpenAI function-calling behavior; make sure your orchestration loop
  supports multiple tool-call round trips per user turn, not just one.
- **Log every turn**: `{question, tools_called, tool_inputs, tool_outputs, final_answer,
  latency_ms}`. This directly feeds the 20-scenario eval table (Section 14 of the
  assignment) and is useful for debugging during the demo.

---

## 8. Practice Question Generation

- Inputs: course, topic, difficulty, number of questions (all user-selectable per the UI).
- Generation must be grounded in `search_course_content()` results for that course/topic —
  never generated purely from the LLM's general knowledge, to satisfy "avoid generating
  questions unrelated to the available course content."
- **Validate output before display**, don't trust raw LLM output:
  - Parse into a strict schema (Pydantic): `question, options[], correct_answer,
    explanation, source_reference`.
  - Assert `correct_answer` is one of `options`.
  - On validation failure: retry once with a corrective prompt; if it fails again, surface
    a clean error state in the UI rather than a malformed question.
- Add explicit prompt instructions for question quality: avoid ambiguous wording, avoid
  "all of the above"/"none of the above" as filler options, ensure distractors are
  plausible (not obviously wrong), match requested difficulty level.

---

## 9. Caching Strategy

| What | How | TTL / Invalidation |
|---|---|---|
| Tool/data outputs (`get_course_progress`, `get_weak_topics`, etc.) | Bounded LRU store, keyed by `(user_id, function_name, params)` | Short TTL (e.g., 60–300s) **and** explicit invalidation: evict a user's cached entries whenever a write occurs for that user (new attempt, new score, new enrollment). |
| RAG retrieval for repeated exact queries | Same LRU mechanism, keyed by `(query_text, course_id)` | TTL fine; course content changes rarely. |
| Full LLM natural-language answers | **Not cached.** | — |
| Eligibility/business-rule decisions | **Not cached as a stored answer** — always recomputed from (possibly cached) underlying data, since decisions must always reflect the latest state. | — |
| LLM provider-side prompt caching (if using Anthropic API with sufficient token volume) | Optional, separate concern — cache the static system prompt/tool schema block via `cache_control`. Only worth doing if the cacheable block exceeds the provider's minimum token threshold (~1,024 tokens for Sonnet-class models). | Provider-managed, ~5 min default TTL. |

Document explicitly in the README: LRU cache is per-process (in-memory), which is a known
limitation for multi-worker deployment — Redis would be the production upgrade path.

---

## 10. Guardrails Checklist

- [ ] `user_id` bound server-side from session, never trusted from LLM tool-call arguments.
- [ ] Explicit test scenario: logged in as user A, attempt to request user B's data →
      must refuse/ignore.
- [ ] System prompt states retrieved/tool content is data, not instructions.
- [ ] RAG groundedness threshold enforced in code (not just via prompting).
- [ ] Business-rule decisions always come from `business_rules/` functions, never from the
      LLM reading raw scores.
- [ ] Practice question output schema-validated before being shown in the UI.
- [ ] Fallback response for "information not available" is a fixed, honest string — not a
      generated guess.
- [ ] Every tool call logged for traceability/eval.

---

## 11. Frontend (Orbit UI)

Existing HTML prototype → convert to React. Preserve the current IA:

- **Sidebar**: workspace switcher, New conversation, Chat / Dashboard / Practice nav,
  "Try a conversation" example prompts, current user indicator (from the 5-user picker).
- **Chat**: message thread, source-reference display under RAG-backed answers, loading
  state while tool calls resolve, error state for failed tool/LLM calls, quick-action chips
  ("Understand a concept" / "Find my focus" / "Put it into practice") that pre-fill the
  input with a relevant prompt template.
- **Dashboard**: per-course performance (%), weak topics list, assessment/hackathon
  history, progress bars — all served from the same tool/service layer as the chat
  (Section 4), not a separate data path.
- **Practice**: course/topic/difficulty/count selectors → generated question list with
  reveal-answer/explanation interaction.

React state notes:
- Selected student (from the 5-user login) persists in session/app state for the whole
  session — never re-prompted per message.
- Chat history and dashboard data can share a lightweight client-side store (e.g. React
  Context or Zustand) since both read from the same backend endpoints.

---

## 12. Seeded Test Users (for the 5-user login)

Select 5 users whose underlying data deliberately covers distinct branches of the logic,
not arbitrary rows:

1. High performer — eligible for everything (happy path)
2. Failed a prerequisite — tests eligibility rejection
3. No data in at least one course/domain — tests "missing information" handling
4. At max attempt limit — tests attempt-limit business rule
5. Weak topics across multiple courses — tests weak-topic detection + practice generation

Document this selection rationale in the README.

---

## 13. Stretch Goal (only if core is fully done and tested)

**Image upload for text-based comparison** (e.g., comparing an uploaded syllabus photo
against course content): use the LLM's native vision input to extract text directly in the
same call — do not build a separate OCR pipeline. Feed the extracted text into the existing
RAG comparison path. Clearly label this as a bonus feature in the README; it is not part of
the graded core (Sections 1–14 above) and should not take time away from the guardrails,
business logic, or eval scenarios.

---

## 14. Deliverable Checklist (per assignment Section 15)

- [ ] Working application (FastAPI + React)
- [ ] Source code
- [ ] Database integration (tool/service layer over Postgres)
- [ ] RAG pipeline (chunking → embedding → vector store → retrieval → LLM, with citations)
- [ ] Business-logic implementation (deterministic, unit-tested)
- [ ] AI/tool orchestration (multi-step tool calling, logged)
- [ ] Student performance analysis (dashboard + chat-accessible)
- [ ] Practice-question generation (schema-validated, content-grounded)
- [ ] Architecture diagram (Section 3 above, or a cleaned-up version of it)
- [ ] 20+ test scenarios with question / expected / actual / result, ideally run via a
      small automated eval script against the logged tool-call traces (Section 7)
- [ ] README with setup instructions, seeded-user rationale, and documented limitations
      (in-process cache, free-tier model choice, stretch-goal scope)

---

## 15. User-confirmed implementation decisions (2026-09-09)

These decisions supersede conflicting assumptions earlier in this document:

- The two valid-UUID CSVs are the final active student datasets. Preserve the invalid-ID
  splits in separate database tables. No provided row may be dropped. Preserve original
  CSV archives and provenance, including empty payloads and duplicate records.
- Rules and learning materials may be authored for this demo; label them as project
  assumptions, not supplied institutional policy or supplied course documents.
- Full marks may be assumed where absent. Preserve full marks that are actually supplied.
  The initial course-MCQ assumption is 2 points per attempted question; missing score
  evidence still remains unavailable.
- UUID validation is a format requirement. Invalid format does not prove a record was
  fraudulent or manually entered; valid format does not prove registry membership.
- The user will configure Neon and an LLM key locally. Do not fabricate live results.
- Eligibility targets an assessment ID. New demo assessments have their own attempt
  records; do not count unrelated hackathon question objects as their attempts.
- Eligibility and underlying inputs are read fresh; the general tool TTL does not apply.
- Select actual students covering the available data. Exercise missing eligibility
  branches in explicit test fixtures rather than inventing student histories.

The repository README documents exact rules, score formulas, data-preservation tables,
setup commands, validation evidence, and remaining demo limitations.
