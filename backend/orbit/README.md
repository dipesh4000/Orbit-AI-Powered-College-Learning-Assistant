# Orbit backend layout

The backend is grouped by responsibility. Root-level Python files with an existing
name remain as compatibility modules, so existing imports and commands such as
`python -m orbit.migrate` continue to work. Put new implementation in the folders
below rather than adding new root modules.

```text
orbit/
├── api/        HTTP routers and request dependencies
├── features/   Academic, coding, project, paper, and practice workflows
├── core/       Configuration, database, sessions, cache, telemetry, migrations
├── ai/         Gemini, LLM, retrieval, embeddings, ingestion, orchestration
├── demo/       Disposable demo server and seeded demo data
├── main.py     FastAPI application entry point
└── personal_tools.py  Cross-feature assistant tool registry
```

## Common destinations

| Change | Folder |
| --- | --- |
| Add or change an HTTP endpoint | `api/` |
| Change a dashboard feature or its stored records | `features/` |
| Change database tables, sessions, settings, or telemetry | `core/` |
| Change model calls, document extraction, or retrieval | `ai/` |
| Change preloaded local-demo data | `demo/` |

Run the backend from `backend/` with `uv run uvicorn orbit.main:app --reload`.
See [../readme.md](../readme.md) for commands and [../../GET_STARTED.md](../../GET_STARTED.md)
for the full local setup and landing-page navigation.
