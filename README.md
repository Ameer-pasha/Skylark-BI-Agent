# 🚀 Skylark BI Agent


> **Stack**: [monday.com](http://monday.com) → FastAPI → Claude **/ Grok (xAI)** Tool-Calling Agent → Streamlit → Deploy on Streamlit Cloud

Skylark BI Agent is a full-stack conversational Business Intelligence assistant built for **Skylark Drones**. It connects to live **Deals/Pipeline** and **Work Orders/Execution** boards on monday.com, normalizes and validates data quality, and uses **Anthropic Claude** *or* **xAI Grok** tool-calling APIs to answer executive and operational questions with actionable business insights and data quality caveats.

Both LLM providers share the same BI toolset — the agent automatically routes to whichever key you configure, with identical tool-calling loops and fallback behavior.

---

## ✨ Features

- **Live GraphQL API & Cursor Pagination**: Fetches data from monday.com boards, handling >100 items per board smoothly via cursor pagination.
- **Robust Data Cleaning & Normalization**:
  - Date normalization (`YYYY-MM-DD` fuzzy parsing)
  - Currency normalization (handles INR `₹`, USD `$`, shorthand like `Cr`, `M`, `K`)
  - Text standardization (casing, whitespace cleanup)
  - Percentage conversion (`0-100%`)
- **Automated Data Quality Reporting**: Evaluates missing/invalid data per column and injects a real-time caveat score (`data_quality_score`) into every BI response.
- **Conversational BI Tools** (shared across Claude & Grok):
  - `query_deals`: Analyze pipeline health, win rates, sector distribution, deal stages, and revenue forecasts.
  - `query_work_orders`: Monitor execution status, overdue milestones, client distribution, contract values, and collection gaps.
  - `generate_leadership_summary`: Produce structured executive reports combining both boards.
- **Dual LLM Provider — Claude + Grok (xAI) Tool-Calling**:
  - **Anthropic Claude** via `anthropic` SDK (`claude-3-5-sonnet-20241022` default) using native `tool_use` / `tool_result` loop.
  - **xAI Grok** via OpenAI-compatible API (`https://api.x.ai/v1`) using `openai` SDK with `tools` / `tool_calls` (supports `grok-3`, `grok-3-mini`, `grok-4`, `grok-4-fast`). Tool schemas are auto-translated to OpenAI function format — same BI tools, same prompting, same fallback logic.
  - Auto-detect provider from env keys (`LLM_PROVIDER=auto`) or force via `LLM_PROVIDER=grok | anthropic`.
- **Out-of-the-Box Sample & Offline Fallback Mode**:
  - Automatically falls back to a realistic sample dataset when monday.com credentials are not configured.
  - Includes a smart local BI fallback agent so you can test and explore queries even without any LLM API key.
- **Dual Deployment Modes**:
  - Client-Server: FastAPI backend (`backend/api.py`) + Streamlit frontend (`frontend/app.py`).
  - Standalone: Zero-backend Streamlit deployment (`frontend/app_standalone.py`) suitable for free hosting on Streamlit Community Cloud.

---

## 📁 Project Structure

```
skylark-bi-agent/
│
├── .env                          # API keys and environment configuration
├── .env.example                  # Template for environment variables (Claude + Grok)
├── .gitignore                    # Ignored files and directories
├── requirements.txt              # Python dependencies (anthropic + openai)
├── README.md                     # Project documentation
├── Decision_Log.md               # Architecture decisions, assumptions, and future plans
│
├── backend/
│   ├── __init__.py               # Package initializer
│   ├── monday_client.py          # monday.com GraphQL API layer + pagination + sample fallback
│   ├── data_cleaner.py           # Normalization + data quality score calculation
│   ├── data_store.py             # In-memory cache + manual/startup refresh logic
│   ├── tools.py                  # BI Tool functions (query_deals, query_work_orders, summary)
│   ├── agent.py                  # Claude + Grok tool-calling agent + fallback engine (auto-routing)
│   └── api.py                    # FastAPI application (/health, /data-quality, /chat, /refresh)
│
├── frontend/
│   ├── app.py                    # Streamlit UI (Client-Server with auto-fallback)
│   └── app_standalone.py         # Standalone Streamlit UI (for Streamlit Community Cloud)
│
├── scripts/
│   └── test_monday_connection.py # Connection and column sanity check script
│
└── tests/
    ├── test_data_cleaner.py      # Unit tests for field normalizers & DataFrame cleaner
    ├── test_tools.py             # Unit tests for BI tool functions & filters
    └── test_api.py               # API endpoint tests using FastAPI TestClient
```

---

## ⚙️ Quick Start

### 1. Install Dependencies

Requires Python 3.10+:

```bash
pip install -r requirements.txt
```

Extras: `openai>=1.0` is required for Grok support (already in `requirements.txt`); `anthropic` for Claude.

### 2. Configure Environment

Copy the example configuration file and add your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# monday.com
MONDAY_API_TOKEN=your_monday_personal_api_token_here
WORK_ORDERS_BOARD_ID=123456789
DEALS_BOARD_ID=987654321

# LLM provider selection: auto | anthropic | claude | grok | xai
LLM_PROVIDER=auto

# Anthropic Claude
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# xAI Grok (OpenAI-compatible at https://api.x.ai/v1)
XAI_API_KEY=your_xai_api_key_here
XAI_MODEL=grok-3
# GROK_API_KEY, GROK_MODEL and XAI_BASE_URL are also accepted as aliases

# Backend
BACKEND_URL=http://localhost:8000
```

**Environment variables:**

| Variable | Required | Description |
|---|---|---|
| `MONDAY_API_TOKEN` | No (fallback to sample) | monday.com personal API token |
| `LLM_PROVIDER` | No | `auto` (default) auto-detects; `anthropic`/`claude` forces Claude; `grok`/`xai` forces Grok |
| `ANTHROPIC_API_KEY` | For Claude | Anthropic console key (`sk-ant-...`) |
| `ANTHROPIC_MODEL` | No | Claude model, default `claude-3-5-sonnet-20241022` |
| `XAI_API_KEY` | For Grok | xAI console key (`xai-...`) — also accepts `GROK_API_KEY`, `XAI_KEY` |
| `XAI_MODEL` | No | Grok model, default `grok-3` (`grok-3-mini`, `grok-4`, `grok-4-fast` also valid) |
| `GROK_MODEL` | No | Alias for `XAI_MODEL` |
| `XAI_BASE_URL` | No | Override Grok endpoint, default `https://api.x.ai/v1` |
| `BACKEND_URL` | No | FastAPI URL for Streamlit frontend |

*(Note: If you leave `MONDAY_API_TOKEN` or both `ANTHROPIC_API_KEY` / `XAI_API_KEY` as placeholders, the app runs in sample/offline fallback mode automatically — fully functional without external keys.)*

### 3. Test Monday.com Connection

Verify connection and check board columns:

```bash
python scripts/test_monday_connection.py
```

---

## 🤖 LLM Providers — Claude vs Grok Tool-Calling

Both providers expose the **same three BI tools** with identical business logic (`backend/tools.py` → `TOOL_FUNCTIONS`). The agent (`backend/agent.py`) translates the schemas and runs a 5-iteration tool loop for either:

| Aspect | Claude (Anthropic) | Grok (xAI) |
|---|---|---|
| SDK | `anthropic` | `openai` with `base_url="https://api.x.ai/v1"` |
| Schema format | `TOOLS_CLAUDE` → `{"name", "description", "input_schema"}` | `TOOLS_OPENAI` → `{"type":"function","function":{"name","parameters"}}` |
| Loop | `response.stop_reason=="tool_use"` → `tool_result` → next turn | `message.tool_calls` → `tool` role messages → next `chat.completions.create` |
| System prompt | Same `SYSTEM_PROMPT` injected as `system` | Same prompt injected as `system` message |
| Fallback | On API error → local rule-based BI agent | Same |

**Usage:**

```bash
# Use Claude (default if ANTHROPIC_API_KEY is set and LLM_PROVIDER=auto)
LLM_PROVIDER=anthropic uvicorn backend.api:app --reload

# Use Grok with xAI key
export XAI_API_KEY="xai-..."
export XAI_MODEL="grok-3"   # or grok-4, grok-3-mini
export LLM_PROVIDER=grok
uvicorn backend.api:app --reload

# Auto-detect (picks Grok if only XAI key is valid)
LLM_PROVIDER=auto
```

Get your xAI key at **https://console.x.ai** → API Keys. Grok models support native function calling / tool use — no prompt hacks needed.

**Programmatic example (Grok directly):**

```python
from openai import OpenAI
client = OpenAI(api_key="xai-...", base_url="https://api.x.ai/v1")
resp = client.chat.completions.create(
    model="grok-3",
    messages=[{"role": "user", "content": "What's our pipeline value?"}],
    tools=TOOLS_OPENAI,
)
```

The backend does this loop for you via `run_agent()` — see `backend/agent.py::_run_grok_agent` and `_run_claude_agent`.

---

## 🖥️ Running the Application

### Option 1: Full-Stack Mode (FastAPI + Streamlit)

1. Start the FastAPI backend server:
   ```bash
   uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
   ```
2. In a separate terminal, start the Streamlit UI:
   ```bash
   streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0
   ```
3. Open your browser to `http://localhost:8501`.

### Option 2: Standalone Mode (Streamlit Only)

If deploying to Streamlit Community Cloud without a separate server:
```bash
streamlit run frontend/app_standalone.py --server.port 8501 --server.address 0.0.0.0
```

---

## 🧪 Running Automated Tests

We include a full pytest test suite verifying normalization, caching, BI tool queries, and API endpoints:

```bash
pytest -v
```

Tests run against the fallback/sample dataset and mock LLM mode — no external keys required.

---

## 📡 API Reference (`backend/api.py`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check endpoint (`{"status": "ok"}`) |
| `GET` | `/data-quality` | Returns quality metrics and caveats for Deals & Work Orders |
| `POST` | `/chat` | Main conversational endpoint (`{"message": "...", "conversation_history": [...]}`) — routes to Claude or Grok based on `LLM_PROVIDER` |
| `POST` | `/refresh` | Manually reload and normalize fresh data from monday.com |

---

## 💡 Example Queries

- *"What's our total pipeline value?"*
- *"Show me Q3 2026 deals in Energy sector"*
- *"Which sector has the most deals?"*
- *"How many work orders are overdue?"*
- *"What's our collection gap on work orders?"*
- *"Generate a leadership summary"*

Works identically with Claude or Grok — just switch `LLM_PROVIDER` / key.

---

## 🚀 Deployment

### Streamlit Community Cloud (Recommended — Free)
1. Push this repository to GitHub.
2. Log into [Streamlit Community Cloud](https://share.streamlit.io/) and create a new app.
3. Select your repository and set **Main file path** to `frontend/app_standalone.py`.
4. In Advanced Settings -> Secrets, add:
   ```toml
   MONDAY_API_TOKEN = "your_token_here"
   # Pick ONE LLM provider (or both):
   ANTHROPIC_API_KEY = "your_anthropic_key_here"
   XAI_API_KEY = "your_xai_key_here"
   XAI_MODEL = "grok-3"
   LLM_PROVIDER = "auto"
   WORK_ORDERS_BOARD_ID = "123456789"
   DEALS_BOARD_ID = "987654321"
   ```

### Render + Streamlit Cloud
1. Deploy `backend.api:app` on Render using start command:
   ```bash
   uvicorn backend.api:app --host 0.0.0.0 --port $PORT
   ```
2. In Streamlit Cloud, deploy `frontend/app.py` and set secret `BACKEND_URL` to your Render service URL. Set `XAI_API_KEY` / `ANTHROPIC_API_KEY` and `LLM_PROVIDER` as Render env vars.

---

## 📄 Decision Log
For detailed architecture decisions, assumptions, known limitations, and future improvements, see [`Decision_Log.md`](./Decision_Log.md).
