# 🚀 Skylark BI Agent

> **Stack**: [monday.com](http://monday.com) → FastAPI → Claude Tool-Calling Agent → Streamlit → Deploy on Streamlit Cloud

Skylark BI Agent is a full-stack conversational Business Intelligence assistant built for **Skylark Drones**. It connects to live **Deals/Pipeline** and **Work Orders/Execution** boards on monday.com, normalizes and validates data quality, and uses Anthropic's Claude tool-calling API to answer executive and operational questions with actionable business insights and data quality caveats.

---

## ✨ Features

- **Live GraphQL API & Cursor Pagination**: Fetches data from monday.com boards, handling >100 items per board smoothly via cursor pagination.
- **Robust Data Cleaning & Normalization**:
  - Date normalization (`YYYY-MM-DD` fuzzy parsing)
  - Currency normalization (handles INR `₹`, USD `$`, shorthand like `Cr`, `M`, `K`)
  - Text standardization (casing, whitespace cleanup)
  - Percentage conversion (`0-100%`)
- **Automated Data Quality Reporting**: Evaluates missing/invalid data per column and injects a real-time caveat score (`data_quality_score`) into every BI response.
- **Conversational BI Tools**:
  - `query_deals`: Analyze pipeline health, win rates, sector distribution, deal stages, and revenue forecasts.
  - `query_work_orders`: Monitor execution status, overdue milestones, client distribution, contract values, and collection gaps.
  - `generate_leadership_summary`: Produce structured executive reports combining both boards.
- **Out-of-the-Box Sample & Offline Fallback Mode**:
  - Automatically falls back to a realistic sample dataset when monday.com credentials are not configured.
  - Includes a smart local BI fallback agent so you can test and explore queries even without an Anthropic API key.
- **Dual Deployment Modes**:
  - Client-Server: FastAPI backend (`backend/api.py`) + Streamlit frontend (`frontend/app.py`).
  - Standalone: Zero-backend Streamlit deployment (`frontend/app_standalone.py`) suitable for free hosting on Streamlit Community Cloud.

---

## 📁 Project Structure

```
skylark-bi-agent/
│
├── .env                          # API keys and environment configuration
├── .env.example                  # Template for environment variables
├── .gitignore                    # Ignored files and directories
├── requirements.txt              # Python dependencies
├── README.md                     # Project documentation
├── Decision_Log.md               # Architecture decisions, assumptions, and future plans
│
├── backend/
│   ├── __init__.py               # Package initializer
│   ├── monday_client.py          # monday.com GraphQL API layer + pagination + sample fallback
│   ├── data_cleaner.py           # Normalization + data quality score calculation
│   ├── data_store.py             # In-memory cache + manual/startup refresh logic
│   ├── tools.py                  # BI Tool functions (query_deals, query_work_orders, summary)
│   ├── agent.py                  # Claude tool-calling conversational agent + fallback engine
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

### 2. Configure Environment

Copy the example configuration file and add your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```env
MONDAY_API_TOKEN=your_monday_personal_api_token_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
WORK_ORDERS_BOARD_ID=123456789
DEALS_BOARD_ID=987654321
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
BACKEND_URL=http://localhost:8000
```
*(Note: If you leave `MONDAY_API_TOKEN` or `ANTHROPIC_API_KEY` unchanged, the app will run in sample/offline fallback mode automatically.)*

### 3. Test Monday.com Connection

Verify connection and check board columns:

```bash
python scripts/test_monday_connection.py
```

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

---

## 📡 API Reference (`backend/api.py`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check endpoint (`{"status": "ok"}`) |
| `GET` | `/data-quality` | Returns quality metrics and caveats for Deals & Work Orders |
| `POST` | `/chat` | Main conversational endpoint (`{"message": "...", "conversation_history": [...]}`) |
| `POST` | `/refresh` | Manually reload and normalize fresh data from monday.com |

---

## 💡 Example Queries

- *"What's our total pipeline value?"*
- *"Show me Q3 2026 deals in Energy sector"*
- *"Which sector has the most deals?"*
- *"How many work orders are overdue?"*
- *"What's our collection gap on work orders?"*
- *"Generate a leadership summary"*

---

## 🚀 Deployment

### Streamlit Community Cloud (Recommended — Free)
1. Push this repository to GitHub.
2. Log into [Streamlit Community Cloud](https://share.streamlit.io/) and create a new app.
3. Select your repository and set **Main file path** to `frontend/app_standalone.py`.
4. In Advanced Settings -> Secrets, add:
   ```toml
   MONDAY_API_TOKEN = "your_token_here"
   ANTHROPIC_API_KEY = "your_key_here"
   WORK_ORDERS_BOARD_ID = "123456789"
   DEALS_BOARD_ID = "987654321"
   ```

### Render + Streamlit Cloud
1. Deploy `backend.api:app` on Render using start command:
   ```bash
   uvicorn backend.api:app --host 0.0.0.0 --port $PORT
   ```
2. In Streamlit Cloud, deploy `frontend/app.py` and set secret `BACKEND_URL` to your Render service URL.

---

## 📄 Decision Log
For detailed architecture decisions, assumptions, known limitations, and future improvements, see [`Decision_Log.md`](./Decision_Log.md).
