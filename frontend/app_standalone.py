# frontend/app_standalone.py
"""
Standalone Streamlit chat UI for Skylark BI Agent (Streamlit Community Cloud deployment).
Directly imports and executes backend functions without requiring a separate FastAPI server.
Features a modern executive KPI ribbon, gradient hero header, and interactive query chips.
"""

import streamlit as st
import os
from backend.data_store import (
    refresh_data,
    get_quality_summary,
    get_deals_df,
    get_work_orders_df
)
from backend.agent import run_agent
from frontend.ui_components import (
    render_custom_css,
    render_header,
    render_kpi_cards,
    get_sample_questions
)

st.set_page_config(
    page_title="Skylark BI Studio (Standalone)",
    page_icon="🚁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject modern CSS
render_custom_css()

# Initialize data store in session state
if "data_loaded" not in st.session_state:
    with st.spinner("Loading Monday.com BI data..."):
        refresh_data()
        st.session_state.data_loaded = True


# ─────────────────────────────────────────────
# Sidebar — Data Quality & Controls
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🚁 **Skylark BI Studio**")
    st.caption("Powered by Claude + monday.com (Standalone Mode)")

    st.divider()

    # Data Quality Panel
    st.markdown("#### 📊 **Data Quality & Sync**")
    if st.button("🔄 Sync monday.com Boards", use_container_width=True):
        with st.spinner("Syncing latest board items..."):
            refresh_data()
            q = get_quality_summary()
            st.success(f"✅ Refreshed! Deals: {q['deals']['data_quality_score']}% | Work Orders: {q['work_orders']['data_quality_score']}%")

    st.info("⚡ **Standalone Mode**: Direct embedded execution", icon="⚡")
    quality = get_quality_summary()

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
deals_df = get_deals_df()
wo_df = get_work_orders_df()
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

    # Call agent directly
    with st.chat_message("assistant", avatar="🚁"):
        with st.spinner("Analyzing monday.com BI data..."):
            response_text = run_agent(
                user_message=prompt,
                conversation_history=st.session_state.conversation_history
            )

            # Update conversation history
            updated_history = st.session_state.conversation_history + [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response_text}
            ]

            st.session_state.conversation_history = updated_history
            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})
