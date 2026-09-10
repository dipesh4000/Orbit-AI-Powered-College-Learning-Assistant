# Orbit

### Find your focus. Build your momentum.

Orbit is a college learning workspace combining student progress, course-grounded AI chat, assessment eligibility, and practice. It turns supplied learning records into useful next steps while keeping identity, data access, and assessment decisions under backend control.

[Get started](GET_STARTED.md) · [Deployment](docs/DEPLOYMENT.md) · [Data and demo assumptions](docs/ARCHITECTURE.md)

## The learning workspace

| Experience | What Orbit provides |
| --- | --- |
| Student selection | Demo profiles drawn from supplied student records |
| Dashboard | Course progress, performance, weak topics, and assessment history |
| AI chat | Multi-step tool use, course references, and persistent conversations |
| Eligibility | Deterministic decisions with reasons and unmet requirements |
| Practice | Course-grounded questions with validated options, answers, and citations |
| Provider resilience | Primary LLM with automatic NVIDIA fallback and recovery cooldown |

## System architecture

```mermaid
flowchart TB
    student([Student]) --> ui["React workspace"]
    ui --> api["FastAPI routes and session checks"]
    api --> services["Student data services"]
    api --> agent["AI orchestration loop"]
    api --> practice["Practice generation"]
    agent --> tools["Typed tool registry"]
    tools --> services
    tools --> rules["Deterministic eligibility rules"]
    tools --> rag["Course retrieval"]
    tools --> practice
    rules --> services
    services --> database[("PostgreSQL / Neon")]
    practice --> rag
    agent --> model["Shared model interface"]
    practice --> model
    model --> primary["Primary LLM API"]
    model -.-> fallback["NVIDIA Nemotron fallback"]
    rag --> embeddings["Local MiniLM embeddings"]
    rag --> index[("FAISS index and source chunks")]
    api --> conversations["Conversation persistence"]
    conversations --> database
    agent -.-> traces["Turn traces and latency metrics"]
    classDef app fill:#e9f2ec,stroke:#476b56,color:#203b2b;
    classDef data fill:#eef0fa,stroke:#65739d,color:#27334f;
    class ui,api,agent,tools,practice,model app;
    class database,index data;
```

The LLM selects tools and narrates their outputs. Typed services query the database, Python computes eligibility, and retrieval supplies course passages. The model has no direct database connection.

## AI flow: a LangGraph-style view

Nodes, conditional routing, and a tool loop describe the existing implementation. Orbit implements this flow in async Python; **LangGraph and LangChain are not runtime dependencies**.

A turn carries messages, tool results, source references, and a trace. The backend binds student identity before executing tools. Chat retains the latest 20 history messages and permits six model rounds, with at most eight tool calls per response.

```mermaid
flowchart TD
    startNode(["START: student message"]) --> guards{"Identity restriction or greeting?"}
    guards -->|Yes| fixed["Return the appropriate fixed response"]
    guards -->|No| context["System rules plus recent history"]
    context --> model["Call model with tool schemas"]
    model --> route{"Tool calls returned?"}
    route -->|Yes| execute["Validate arguments and execute tools with bound identity"]
    execute --> state["Append tool results and collect sources"]
    state --> evidence{"Course search returned no passages?"}
    evidence -->|Yes| insufficient["Insufficient information plus any eligibility reasons"]
    evidence -->|No| budget{"Model rounds remaining?"}
    budget -->|Yes| model
    budget -->|No| limit["Ask the student to narrow the request"]
    route -->|No| used{"Any tools used this turn?"}
    used -->|Yes| answer["Return model answer with collected sources"]
    used -->|No| insufficient
    fixed --> finish["Update history and record trace"]
    insufficient --> finish
    limit --> finish
    answer --> finish
    finish --> endNode([END])
    classDef action fill:#e9f2ec,stroke:#476b56,color:#203b2b;
    classDef gate fill:#fff3d9,stroke:#a88a45,color:#54451f;
    class context,model,execute,state,finish action;
    class guards,route,evidence,budget,used gate;
```

Missing retrieval evidence stops further course-content generation. System instructions treat tool outputs and retrieved text as untrusted data. Citations and tool-use checks support grounded answers; they do not formally verify every generated claim.

## Model fallback and recovery

Chat and practice share a model interface. NVIDIA defaults to `nvidia/nemotron-3-nano-30b-a3b`, with thinking disabled for lower latency. `nvidia/nemotron-3-super-120b-a12b` is an optional model setting.

```mermaid
flowchart TD
    requestNode(["Model request"]) --> available{"Primary configured and eligible?"}
    available -->|Yes| primary["Call primary provider"]
    available -->|No| fallbackReady{"NVIDIA configured?"}
    primary --> outcome{"Usable response?"}
    outcome -->|Yes| success["Return content or tool calls"]
    outcome -->|No| configured{"NVIDIA configured?"}
    configured -->|Yes| cooldown["Skip primary for 300 seconds"]
    cooldown --> nvidia["Call NVIDIA with the same history and tools"]
    fallbackReady -->|Yes| nvidia
    fallbackReady -->|No| unavailable["Safe unavailable error"]
    configured -->|No| unavailable
    nvidia --> fallbackResult{"Usable response?"}
    fallbackResult -->|Yes| success
    fallbackResult -->|No| unavailable
    cooldown -.-> probe["Later request after cooldown retries primary"]
```

With fallback enabled, quota errors, rejected access, HTTP failures, timeouts, and unusable responses trigger failover. Each provider call has a default 30-second total budget. Without NVIDIA, the primary retains bounded rate-limit retries before returning an error. Cooldown state is process-local, and both providers can still become unavailable.

## Course retrieval

Demo-authored materials are split into overlapping chunks, embedded locally with `all-MiniLM-L6-v2`, and stored in FAISS with source and course metadata. Search filters by course and similarity threshold before returning evidence.

```mermaid
flowchart LR
    materials["Demo course materials"] --> chunks["Overlapping source chunks"]
    chunks --> embed["MiniLM embeddings"]
    embed --> index[("FAISS and chunk metadata")]
    question["Course question"] --> search["Semantic search and course filter"]
    index --> search
    search --> threshold{"Relevant evidence?"}
    threshold -->|Yes| context["Passages and source IDs for chat"]
    threshold -->|No| stopNode["Insufficient information"]
```

## Validated practice generation

Known catalog topics use direct passage lookup, with semantic search as a fallback. Generated questions pass schema and citation checks before being saved or displayed.

```mermaid
flowchart TD
    inputNode(["Course, topic, difficulty, count"]) --> enrolled{"Enrolled course?"}
    enrolled -->|No| reject["Reject request"]
    enrolled -->|Yes| sources["Retrieve topic passages"]
    sources --> found{"Passages available?"}
    found -->|No| insufficient["Return no questions and explain missing evidence"]
    found -->|Yes| generate["Generate JSON through shared model interface"]
    generate --> validate{"Count, uniqueness, options, answer and citations valid?"}
    validate -->|Yes| persist["Save practice history in PostgreSQL"]
    persist --> display(["Display validated questions"])
    validate -->|No| retry{"Correction already attempted?"}
    retry -->|No| correct["Add validation feedback"]
    correct --> generate
    retry -->|Yes| errorNode["Return validation error"]
```

## Technology stack

| Layer | Technologies | Role |
| --- | --- | --- |
| Interface | React 19, React Router 7, Vite 6, CSS, Lucide | Responsive workspace and navigation |
| Chat rendering | React Markdown, remark-gfm | Markdown answers and tables |
| API | Python 3.13, FastAPI, Uvicorn, Pydantic | Routes, validation, sessions, and error handling |
| Data | PostgreSQL / Neon, SQLAlchemy, Psycopg | Student records, conversations, practice history |
| AI orchestration | Async Python, HTTPX | Tool loop, provider adapters, timeout and failover |
| LLM providers | Anthropic or an OpenAI-compatible primary; NVIDIA NIM fallback | Tool-capable chat and question generation |
| Retrieval | Sentence Transformers, MiniLM, PyTorch, NumPy, FAISS CPU | Local embeddings and course search |
| State | Process-local sessions and bounded TTL caches | Session context and reusable tool/retrieval results |
| Observability | JSON traces, rotating metrics logs | Tool execution, provider usage, latency, and failures |
| Tooling | uv, pytest, Ruff, Playwright, Prettier | Dependencies, backend checks, browser validation, formatting |

## Data and trust boundaries

Orbit preserves all **27,456 supplied source rows**, including raw records, source archives, duplicate rows, and separate invalid-UUID splits. Missing scores remain unavailable instead of becoming zero. Eligibility and its inputs are read fresh. Reusable tool data can be cached; final AI answers are not cached.

The student picker is a demo selector. Learning materials and assessment rules are labeled demo assumptions. Sessions and caches are process-local; conversations and practice history persist in PostgreSQL. The current design uses one backend worker and instance.
