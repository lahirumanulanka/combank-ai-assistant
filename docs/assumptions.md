# Assumptions, trade-offs and known limits

## Assumptions

1. **Deadline.** The brief's "8th October" is read as a typo for Sunday 8 November 2026, 17:00 (Asia/Colombo).
2. **Data.** The corpus is mock data written for this project (25 documents, all fictional). "Commercial Bank" is used
   only because the brief asks for it.
3. **Authentication.** Option A from the brief: three hard-coded users with bcrypt-hashed passwords and JWT tokens.
4. **"Last year"** in research questions means the trailing 12 months from today.
5. **One instance.** Rate limits, the circuit breaker and run ownership are kept in memory of a single API process.
6. **English Markdown** documents only; no PDF or OCR parsing.
7. **Models.** The defaults are Claude Sonnet (strong) and Claude Haiku (workers); the recorded demo uses
   `openai:gpt-5.4-mini` for all LLM settings because that key was available. Switching is configuration only.

## Trade-offs (what was chosen and why)

| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| Hybrid scoring | One Pinecone index, alpha-weighted dense + sparse | Two indexes + reciprocal rank fusion | One query per namespace, scores combined by Pinecone; alpha is easy to explain and tune |
| Sparse encoder | Own 60-line BM25 with light stemming | `pinecone-text` library | Fully explainable, no runtime downloads; stemming added after testing showed "rotated" ≠ "rotation" |
| Chunking | Split at `##` headings, long sections into 250 words with 40 overlap | Fixed token windows | Keeps sections like "Root cause" whole, which the research workers rely on |
| Research code | Small Python language checked by an AST allow-list, no built-ins | Full sandbox (container, gVisor) | Safe and explainable for a POC; a real sandbox is the production answer |
| Research depth | One level of workers | Workers that split again | Reliable within the time box; the worker is the same callable and could `Send()` again |
| Counting | Python `Counter` in code | Ask the model to count | Exact and repeatable numbers |
| Injection defence | Patterns + spotlighting + RBAC in code + approval | Dedicated classifier model | Fast and testable; a paraphrased attack is still stopped by the later layers |
| Memory | Thread memory via SQLite checkpointer | Postgres; long-term per-user store | Zero setup; same LangGraph interface, so Postgres is a config change |
| Rate limit | In-memory token bucket | Redis | Correct for one instance; Redis needed for several replicas |
| Citation check | Cited ids must be retrieved ids | LLM judge of faithfulness | Cheap and deterministic; proves the source exists, not that every sentence is faithful |
| UI | Streamlit with a synchronous SSE reader | React | Required by the brief; good enough for a POC |
| Approval | One decision covers all admin calls in a tool round | One prompt per call | Simpler UI; admin rounds rarely contain more than one action |
| Python analysis | Fixed operations with validated arguments, role-filtered data | Model writes and runs pandas code | No code from the model is executed; numbers are exact and testable |

## Known limits

- **Not implemented (bonus items):** reranking layer, long-term memory across conversations, Keycloak (Option B),
  Postgres in Compose, an LLM-based injection classifier, an evaluation dataset.
- **MCP tools load at API start.** If the MCP server starts later, restart the API (Compose handles the order).
- **Brand check** allows a sentence that both names another bank and refuses to compare.
- **Docker image** is about 1.8 GB because UI, API and MCP share one image.
- **Python analysis tool** runs fixed operations (count, timeline, list) chosen from a list, not free-form Python
  written by the model. Safer and explainable; less flexible than a real code interpreter.

## With one more week

1. LangSmith evaluation dataset (20 questions with expected chunk ids) to measure citation precision and recall.
2. Reranker (Pinecone inference or a cross-encoder) and an A/B comparison in LangSmith.
3. Long-term memory per user (LangGraph Store) and Postgres for checkpoints.
4. Keycloak login (OIDC) instead of hard-coded users.
5. Redis-backed rate limiting and circuit breaker for multiple API replicas.
6. A faithfulness judge in the validator and a dedicated injection classifier.
