# frontend/ui_components.py
"""
Shared modern UI components and CSS styling for Skylark BI Agent Streamlit apps.
"""

import streamlit as st
import pandas as pd


def render_custom_css():
    """Inject modern, responsive CSS styling for Streamlit UI."""
    st.markdown("""
    <style>
        /* Main page spacing & font polish */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1200px;
        }

        /* Hero Header Container */
        .hero-container {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 28px 32px;
            margin-bottom: 24px;
            box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.3);
            position: relative;
            overflow: hidden;
        }
        
        .hero-badge {
            display: inline-block;
            background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
            color: #ffffff;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 4px 12px;
            border-radius: 9999px;
            margin-bottom: 12px;
            box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
        }

        .hero-title {
            font-size: 2.25rem;
            font-weight: 800;
            margin: 0 0 8px 0;
            background: linear-gradient(90deg, #ffffff 0%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .accent-text {
            background: linear-gradient(90deg, #60a5fa 0%, #3b82f6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero-subtitle {
            font-size: 1rem;
            color: #94a3b8;
            margin: 0;
            line-height: 1.5;
        }

        /* Modern KPI Cards */
        .kpi-card {
            background: rgba(30, 41, 59, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            padding: 18px 20px;
            transition: all 0.2s ease-in-out;
            height: 100%;
        }
        
        .kpi-card:hover {
            transform: translateY(-2px);
            border-color: rgba(96, 165, 250, 0.3);
            box-shadow: 0 8px 20px -6px rgba(0, 0, 0, 0.3);
        }

        .kpi-label {
            font-size: 0.8rem;
            font-weight: 600;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 6px;
        }

        .kpi-value {
            font-size: 1.6rem;
            font-weight: 700;
            color: #f8fafc;
            margin-bottom: 4px;
        }

        .kpi-subtext {
            font-size: 0.8rem;
            color: #64748b;
        }
        
        .kpi-badge-green {
            color: #34d399;
            font-weight: 600;
        }
        
        .kpi-badge-amber {
            color: #fbbf24;
            font-weight: 600;
        }

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: #0f172a !important;
            border-right: 1px solid rgba(255, 255, 255, 0.05);
        }

        /* Custom buttons styling */
        div.stButton > button {
            border-radius: 10px;
            font-weight: 600;
            transition: all 0.2s ease;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        div.stButton > button:hover {
            border-color: #3b82f6;
            color: #3b82f6;
            transform: translateY(-1px);
        }

        /* Chat bubbles */
        div[data-testid="stChatMessage"] {
            background: rgba(30, 41, 59, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 16px;
            padding: 16px 20px;
            margin-bottom: 16px;
        }
    </style>
    """, unsafe_allow_html=True)


def format_inr(val: float) -> str:
    """Format float into clean Indian shorthand notation (Cr / L / raw)."""
    if val is None or pd.isna(val) or val == 0:
        return "₹0"
    try:
        val = float(val)
        if val >= 10_000_000:
            return f"₹{val/10_000_000:.2f} Cr"
        elif val >= 100_000:
            return f"₹{val/100_000:.2f} L"
        else:
            return f"₹{val:,.0f}"
    except Exception:
        return f"₹{val}"


def render_header():
    """Render modern hero header banner."""
    st.markdown("""
    <div class="hero-container">
        <div class="hero-badge">🚁 LIVE BI AGENT</div>
        <h1 class="hero-title">Skylark Drones <span class="accent-text">BI Studio</span></h1>
        <p class="hero-subtitle">Conversational Intelligence for Sales Pipeline & Operational Execution on monday.com</p>
    </div>
    """, unsafe_allow_html=True)


def render_kpi_cards(quality_summary: dict, deals_df: pd.DataFrame, wo_df: pd.DataFrame):
    """Render 4 interactive KPI summary cards above the chat interface."""
    # Compute metrics
    total_pipeline = 0
    deals_count = len(deals_df) if deals_df is not None else 0
    if deals_df is not None and "Deal Value" in deals_df.columns:
        total_pipeline = deals_df["Deal Value"].dropna().sum()

    wo_count = len(wo_df) if wo_df is not None else 0
    total_wo_val = 0
    overdue_count = 0
    if wo_df is not None:
        if "Contract Value" in wo_df.columns:
            total_wo_val = wo_df["Contract Value"].dropna().sum()
        if "End Date" in wo_df.columns and "Status" in wo_df.columns:
            try:
                df_end = pd.to_datetime(wo_df["End Date"], errors="coerce")
                today = pd.Timestamp.today()
                not_done = ~wo_df["Status"].astype(str).str.lower().isin(["completed", "done", "closed", "delivered"])
                overdue_count = int((not_done & (df_end < today) & df_end.notna()).sum())
            except Exception:
                overdue_count = 0

    deals_score = quality_summary.get("deals", {}).get("data_quality_score", 100.0)
    wo_score = quality_summary.get("work_orders", {}).get("data_quality_score", 100.0)
    avg_quality = round((deals_score + wo_score) / 2.0, 1)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">🎯 Pipeline Health</div>
            <div class="kpi-value">{format_inr(total_pipeline)}</div>
            <div class="kpi-subtext">Across <b>{deals_count}</b> Active Deals</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">🏗️ Execution Orders</div>
            <div class="kpi-value">{format_inr(total_wo_val)}</div>
            <div class="kpi-subtext"><b>{wo_count}</b> Work Orders Assigned</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        overdue_badge = f'<span class="kpi-badge-amber">⚠️ {overdue_count} Overdue</span>' if overdue_count > 0 else '<span class="kpi-badge-green">✅ On Schedule</span>'
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">🚨 Delivery Risk</div>
            <div class="kpi-value">{overdue_count} Orders</div>
            <div class="kpi-subtext">{overdue_badge}</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        qual_badge = f'<span class="kpi-badge-green">{avg_quality}% Clean</span>' if avg_quality >= 90 else f'<span class="kpi-badge-amber">{avg_quality}% Clean</span>'
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">📊 Data Quality</div>
            <div class="kpi-value">{avg_quality}%</div>
            <div class="kpi-subtext">monday.com {qual_badge}</div>
        </div>
        """, unsafe_allow_html=True)


def get_sample_questions() -> list[str]:
    return [
        "What's our total pipeline value?",
        "Which sector has the most deals?",
        "How many work orders are overdue?",
        "Show me Q3 2026 deals in Energy sector",
        "Generate a leadership summary",
        "What's our collection gap on work orders?"
    ]
