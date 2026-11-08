# Architecture

## 1. System context

```mermaid
flowchart LR
    U[Employee<br/>viewer / analyst / admin] --> UI[Streamlit UI]
    UI -- "HTTPS JSON + SSE" --> API[FastAPI]
    subgraph Backend
        API --> G[LangGraph agents]
        G <--> CK[(Checkpointer<br/>SQLite)]
    end
    G -- "hybrid query + role filter" --> PC[(Pinecone)]
    G -- "chat, structured output" --> LLM[LLM provider]
    G -- "embed query" --> EMB[OpenAI embeddings]
    G -- "tools over HTTP" --> MCP[MCP server]
    G -. "traces, feedback" .-> LS[LangSmith]
```

The user only talks to the UI, and the UI only talks to the API. Login, rate limiting and roles are checked in the
API before any model call. The UI keeps nothing but the JWT and the thread id.

**Design choices**
- *Thin UI, thick backend.* All rules live in the API, so changing the UI cannot bypass them.
- *MCP is a separate process.* That is the point of MCP; it also lets the demo stop it and show graceful degradation.
- *Two model tiers.* A strong model for routing and writing, a cheap one for the many parallel research workers.

## 2. The agent graph

```mermaid
stateDiagram-v2
    [*] --> input_guard
    input_guard --> blocked_response: attack
    input_guard --> supervisor: clean
    blocked_response --> [*]

    supervisor --> retrieval: qa
    supervisor --> research_plan: research (analyst, admin)
    supervisor --> tool_agent: tool
    supervisor --> response: chitchat

    retrieval --> response

    research_plan --> research_execute
    research_execute --> research_worker: Send() per batch
    research_worker --> research_aggregate
    research_aggregate --> response

    tool_agent --> tool_executor: tool calls
    tool_executor --> tool_agent: results
    tool_agent --> validator: final answer

    response --> validator
    validator --> response: retry once
    validator --> tool_agent: retry once
    validator --> [*]
```

| Node | Job | Uses an LLM? |
|---|---|---|
| `input_guard` | Blocks injection attempts before anything else runs | no |
| `supervisor` | Picks the route, rewrites follow-ups into a full question, gives a rationale | strong (structured output) |
| `retrieval` | Hybrid search with the user's role, drops weak and poisoned chunks | no (embeddings only) |
| `research_plan` | Writes a small Python search plan from a catalog summary | strong |
| `research_execute` | Checks and runs the plan in the sandbox; safe fallback plan if rejected | no |
| `research_worker` | Reads targeted sections of one batch, fills a strict form, judges relevance | cheap, in parallel |
| `research_aggregate` | Counts root causes and builds the timeline in code, reports coverage | no |
| `tool_agent` | Chooses tools (only those the role allows), up to 3 rounds | strong |
| `tool_executor` | Re-checks roles, pauses for approval on admin actions, runs calls in parallel | no |
| `response` | Writes a cited draft from spotlighted passages | strong |
| `validator` | Brand rules + citation check; one retry, then a safe message; saves the answer to memory | no |

**Design choices**
- *Role lives in the runtime context, not in the state.* The model can write to the state; it can never change the
  frozen `RuntimeContext` that carries the user's role.
- *Draft vs. history.* Only validated answers are added to the chat history.
- *Errors are data.* A failed research worker returns "not analysed" instead of raising, so one failure does not
  stop the others (the "butterfly effect" is contained and reported as coverage).

## 3. One request, end to end

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant UI as Streamlit
    participant API as FastAPI
    participant G as LangGraph
    participant PC as Pinecone
    participant LS as LangSmith
    U->>UI: question
    UI->>API: POST /chat/stream (JWT, thread_id)
    API->>API: verify JWT, token bucket, validate body
    API->>G: astream(input, run_id, role in context)
    G-->>UI: node_end input_guard, supervisor (route + rationale)
    G->>PC: query(dense*alpha + sparse*(1-alpha), access_level filter) x namespaces in parallel
    G-->>UI: node_end retrieval (chunk ids, dropped, degraded)
    G-->>UI: token, token, token ...
    G-->>UI: node_end validator (cited, brand ok)
    API-->>UI: memory, done (answer, run_id)
    G-)LS: trace tree
    U->>UI: thumbs down
    UI->>API: POST /feedback (run_id)
    API-)LS: create_feedback(user_rating)
```

## 4. Research (RLM) flow

```mermaid
sequenceDiagram
    participant SV as supervisor
    participant PL as research_plan
    participant SB as sandbox
    participant W as workers (parallel)
    participant AG as aggregate
    participant RS as response
    SV->>PL: route=research, question
    PL->>PL: read catalog summary only (counts, tags, dates)
    PL->>SB: Python plan text
    SB->>SB: AST allow-list, no builtins, ids only from the role's catalog
    SB->>W: batches of up to 4 incident ids (Send per batch)
    W->>W: read Impact / Root cause / Follow-up sections, mark relevance
    W->>AG: findings (category, summary, fix)
    AG->>AG: Counter by cause, timeline by month, coverage n/N
    AG->>RS: analysis + citable findings
```

The planner never reads document bodies; it writes a program that decides what to read. Counting is done in code,
so the numbers are exact. Verified against `data/ground_truth.json`: 12 payment incidents in the last 12 months,
root causes 4 / 3 / 3 / 2.

## 5. Retrieval pipeline

```mermaid
flowchart LR
    subgraph Ingest[scripts/ingest.py, once]
        D[25 Markdown docs] --> C[140 chunks<br/>split at headings]
        C --> E[dense vectors<br/>OpenAI 1536-d]
        C --> B[sparse vectors<br/>own BM25 + stemming]
        E --> P[(Pinecone dotproduct<br/>namespace = department)]
        B --> P
        B --> J[bm25_params.json]
    end
    subgraph Query[every question]
        Q[question] --> QE[embed] & QB[BM25 query]
        QE & QB --> A[alpha scaling 0.7]
        R[role from JWT] --> F[access_level filter]
        A & F --> N[query all namespaces in parallel]
        N --> M[merge by score, keep >= 0.3]
        M --> GP[drop poisoned chunks]
        GP --> SL[wrap in doc markers]
    end
    P --> N
```

If Pinecone fails or times out, a circuit breaker switches to a local BM25 search over the same chunks with the same
role filter, and the answer says results may be less complete.

## 6. Roles

| Capability | Viewer | Analyst | Admin | Enforced in |
|---|:-:|:-:|:-:|---|
| Chat, memory | ✅ | ✅ | ✅ | `app/api/chat.py` |
| `public` + `internal` documents | ✅ | ✅ | ✅ | Pinecone filter, `app/knowledge/hybrid.py` |
| `confidential` documents | ❌ | ✅ | ✅ | same |
| `restricted` documents | ❌ | ❌ | ✅ | same |
| Deep research route | ❌ downgraded to Q&A | ✅ | ✅ | `app/graph/nodes/supervisor.py` |
| `knowledge_search` tool | ✅ | ✅ | ✅ | `app/core/rbac.py` + registry |
| `python_analysis` tool | ❌ | ✅ | ✅ | same |
| MCP tools | ❌ | ✅ | ✅ | same |
| Admin tools (purge, re-index) | ❌ | ❌ | ✅ + human approval | same + `interrupt()` |

## 7. Deployment

```mermaid
flowchart LR
    subgraph Compose[docker compose]
        MCPc[mcp :8001] --> APIc[api :8000]
        APIc --> UIc[ui :8501]
        ING[ingest job<br/>profile: ingest]
        VOL[(app-state volume<br/>memory + BM25 params)]
        APIc --- VOL
        ING --- VOL
    end
    APIc --> Cloud[Pinecone, OpenAI, LangSmith]
    ING --> Cloud
```

One image runs as three services. Health checks enforce the start order mcp → api → ui. Secrets come from `.env`
at runtime and are never inside the image.
