# Decision Log — Skylark BI Agent

## Assumptions
- "This quarter" without a year → assumed current calendar quarter based on today's date context (August 7, 2026 -> Q3 2026; agent asks for confirmation or notes date assumption).
- Currency values assumed INR unless symbol present (`₹`, `$`, `Cr`, `M`, `K`). Handled shorthand notation (`Cr` = 10,000,000, `M` = 1,000,000, `K` = 1,000).
- "Leadership summary" interpreted as: pipeline health (Deals) + execution status (Work Orders) + risk flags / overdue orders + executive interpretation.
- Items beyond 100 per board fetched via cursor pagination (fully implemented in `monday_client.py`).
- Automatic fallback to sample/demo BI datasets when `MONDAY_API_TOKEN` is placeholder or missing, ensuring the application remains testable and fully functional out-of-the-box.
- Intelligent local fallback agent when neither `ANTHROPIC_API_KEY` nor `XAI_API_KEY` is valid, enabling offline testing of BI analytics, caveat injection, and clarifying questions.

## Architecture Decisions

| Decision | Choice | Reason |
|---|---|---|
| Frontend | Streamlit | Fastest to build+deploy; existing familiarity; clean support for sidebar metrics, expandable quality reports, and interactive chat loops |
| Backend | FastAPI | Clean separation of concerns; async-ready; robust Pydantic validation for `/chat`, `/health`, `/data-quality`, and `/refresh` |
| Agent framework | Tool-calling loop (no LangGraph) | LangGraph adds overhead; simple tool loop is highly reliable and sufficient for 2-board BI use case; shared loop works for both Claude (`tool_use`/`tool_result`) and Grok (`tools`/`tool_calls`) |
| LLM | Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`) **+ xAI Grok (grok-3 / grok-4) via OpenAI-compatible API** | Claude = best tool-use reliability; Grok = competitive reasoning + OpenAI-compatible endpoint at `https://api.x.ai/v1`; provider auto-routing via `LLM_PROVIDER` gives deployment flexibility and cost choice without code change |
| Grok integration | `openai` SDK with `base_url="https://api.x.ai/v1"` + translated `TOOLS_OPENAI` schemas | xAI exposes OpenAI-compatible Chat Completions with native function calling; reusing same `TOOL_FUNCTIONS` dispatch avoids duplication; identical 5-iteration loop, system prompt, and fallback behavior for parity with Claude |
| Provider routing | `LLM_PROVIDER` env (`auto`/`anthropic`/`grok`) + key-based auto-detect | `auto` picks valid key (Grok if only XAI key, Claude if only Anthropic); explicit `grok`/`xai` or `anthropic`/`claude` forces choice; both keys valid defaults to Claude for backward compat; `XAI_API_KEY`/`GROK_API_KEY` + `XAI_MODEL`/`GROK_MODEL` aliases for ergonomics |
| Caching | In-memory (`data_store.py`, refresh on startup & via `/refresh`) | Avoids API rate limits; sub-millisecond response latency; acceptable for demo/bi-reporting; restarts clear cache |
| Data storage | Pandas DataFrames | Zero database overhead; rich groupby/aggregation capabilities; sufficient for <1000 records per board |
| Resiliency & Fallback | Standalone Streamlit & Local Agent Engine | Supports both client-server FastAPI deployment and standalone Streamlit Cloud hosting (`app_standalone.py` or fallback in `app.py`) |

## Known Limitations
- Cache clears on server restart (in-memory persistence only; no external database).
- No authentication middleware on API endpoints (suitable for internal network or protected preview/deployment).
- monday.com free tier API rate limits not handled with automatic exponential backoff/retry logic (though mitigated by in-memory caching).
- Date filtering assumes standard calendar quarters (Q1: Jan–Mar, Q2: Apr–Jun, Q3: Jul–Sep, Q4: Oct–Dec).
- Very large boards (>10,000 items) would benefit from background task workers for initial cache warming.
- Grok requires `openai>=1.0` dependency even when using Claude (install stays lightweight; import is lazy in `_run_grok_agent` with graceful fallback if missing).

## What I'd Improve With More Time
- **Multi-Step Orchestration**: Introduce LangGraph for multi-step planning (e.g., cross-board client profitability analysis combining sales pipeline with actual work order invoicing).
- **Historical BI Vector Store**: Vector search over historical Q&A and quarterly board reports for deeper organizational context.
- **Persistent Caching**: Redis caching with TTL for production multi-replica environments.
- **Security & Auth**: Proper API key or OAuth2 authentication middleware for FastAPI endpoints and Streamlit UI.
- **Live Event Synchronization**: Integrate real-time monday.com webhooks so board edits automatically invalidate and reload specific cache entries.
- **Structured Output Clarifications**: Enhanced clarifying question flow using structured JSON schemas to prompt users with clickable UI buttons for ambiguous dates or metrics.
- **Streaming Responses**: Stream Grok/Claude tokens via SSE (`openai` streaming / `anthropic` streaming) for responsive chat UX.
- **Model Evaluation Harness**: A/B test Claude vs Grok on BI query suite (latency, tool-call accuracy, insight quality) to auto-select cheapest accurate provider per query.
