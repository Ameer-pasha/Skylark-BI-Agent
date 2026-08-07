# frontend/app.py
"""
Streamlit chat UI for Skylark BI Agent.
Calls the FastAPI backend at /chat endpoint, with seamless fallback to embedded execution
if the FastAPI server is not running.
Features a modern executive KPI ribbon, gradient hero header, and interactive query chips.
"""

import streamlit as st
import requests
import os
from frontend.ui_components import (
    render_custom_css,
    render_header,
    render_kpi_cards,
    get_sample_questions
)

# ── Config ──
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Skylark BI Studio",
    page_icon="🚁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject modern CSS
render_custom_css()


# Helper functions to get data from API (or fallback to local backend functions)
def fetch_quality_summary():
    try:
        resp = requests.get(f"{BACKEND_URL}/data-quality", timeout=10)
        if resp.status_code == 200:
            return resp.json(), False
    except Exception:
        pass
    # Fallback to direct call
    from backend.data_store import get_quality_summary
    return get_quality_summary(), True


def fetch_dataframes():
    """Fetch DataFrames for KPI Ribbon."""
    try:
        from backend.data_store import get_deals_df, get_work_orders_df
        return get_deals_df(), get_work_orders_df()
    except Exception:
        return None, None


def refresh_data_source():
    try:
        resp = requests.post(f"{BACKEND_URL}/refresh", timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            return f"✅ Refreshed! Deals: {data.get('deals_quality_score')}% | Work Orders: {data.get('work_orders_quality_score')}%"
    except Exception:
        pass
    # Fallback to direct call
    from backend.data_store import refresh_data, get_quality_summary
    refresh_data()
    q = get_quality_summary()
    return f"✅ Refreshed! Deals: {q['deals']['data_quality_score']}% | Work Orders: {q['work_orders']['data_quality_score']}% (Local mode)"


def call_chat(message: str, history: list[dict]):
    try:
        resp = requests.post(
            f"{BACKEND_URL}/chat",
            json={
                "message": message,
                "conversation_history": history
            },
            timeout=60
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["response"], data["conversation_history"], False
        else:
            return f"Error {resp.status_code}: {resp.text}", history, False
    except Exception:
        # Fallback to direct call
        from backend.agent import run_agent
        response_text = run_agent(message, history)
        updated_history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": response_text}
        ]
        return response_text, updated_history, True


# ─────────────────────────────────────────────
# Sidebar — Data Quality & Controls
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🚁 **Skylark BI Studio**")
    st.caption("Powered by Claude + monday.com GraphQL")
    
    st.divider()

    # Data Quality Panel
    st.markdown("#### 📊 **Data Quality & Sync**")
    if st.button("🔄 Sync monday.com Boards", use_container_width=True):
        with st.spinner("Syncing latest board items..."):
            msg = refresh_data_source()
            st.success(msg)

    quality, is_local = fetch_quality_summary()
    if is_local:
        st.info("⚡ **Embedded Mode**: Processing via local BI engine", icon="⚡")
    else:
        st.success("🟢 **Live API**: Connected to FastAPI backend", icon="🟢")

    with st.expander("📌 Deals Board Quality", expanded=False):
        deals_q = quality.get("deals", {})
        score = deals_q.get("data_quality_score", "N/A")
        total = deals_q.get("total_rows", 0)
        st.metric("Clean Data Score", f"{score}%")
        st.metric("Total Pipeline Items", total)
        st.text(quality.get("deals_text", ""))

    with st.expander("📌 Work Orders Board Quality", expanded=False):
        wo_q = quality.get("work_orders", {})
        score = wo_q.get("data_quality_score", "N/A")
        total = wo_q.get("total_rows", 0)
        st.metric("Clean Data Score", f"{score}%")
        st.metric("Total Execution Items", total)
        st.text(quality.get("work_orders_text", ""))

    st.divider()

    st.markdown("#### 💡 **Quick Queries**")
    for idx, q in enumerate(get_sample_questions()):
        if st.button(f"👉 {q}", key=f"sidebar_sample_{idx}", use_container_width=True):
            st.session_state["prefill_question"] = q

    st.divider()
    if st.button("🗑️ Reset Chat Session", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_history = []
        st.rerun()


# ─────────────────────────────────────────────
# Main Page — Header, KPI Ribbon & Chat
# ─────────────────────────────────────────────

# 1. Render Hero Header
render_header()

# 2. Render Executive KPI Ribbon
deals_df, wo_df = fetch_dataframes()
render_kpi_cards(quality, deals_df, wo_df)

st.divider()

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "prefill_question" not in st.session_state:
    st.session_state.prefill_question = ""

# Display suggestion chips if chat is empty
if len(st.session_state.messages) == 0:
    st.markdown("#### 💡 **Select a query to get started:**")
    chip_cols = st.columns(3)
    for idx, q in enumerate(get_sample_questions()):
        with chip_cols[idx % 3]:
            if st.button(f"✨ {q}", key=f"chip_{idx}", use_container_width=True):
                st.session_state["prefill_question"] = q
    st.markdown("<br>", unsafe_allow_html=True)

# Display conversation history
for msg in st.session_state.messages:
    avatar = "🧑‍💼" if msg["role"] == "user" else "🚁"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# Handle prefilled question from buttons
prefill = st.session_state.get("prefill_question", "")
if prefill:
    st.session_state.prefill_question = ""  # Clear it

# Chat input
user_input = st.chat_input(
    "Ask about pipeline, deal values, work orders, overdue risk...",
    key="chat_input"
)

# Use prefill if no direct input
prompt = user_input or prefill

if prompt:
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(prompt)

    # Call backend
    with st.chat_message("assistant", avatar="🚁"):
        with st.spinner("Analyzing monday.com BI data..."):
            answer, updated_history, _ = call_chat(prompt, st.session_state.conversation_history)
            st.session_state.conversation_history = updated_history
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
