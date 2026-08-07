# backend/tools.py
"""
Actual implementations of the tools the AI agent can call.
Each function receives structured params from Claude's tool call,
queries the cached DataFrames, and returns a result string.
"""

import pandas as pd
from backend.data_store import get_deals_df, get_work_orders_df, get_quality_summary


def _safe_filter(df: pd.DataFrame, col: str, value: str) -> pd.DataFrame:
    """Case-insensitive partial string match filter."""
    if not value or col not in df.columns:
        return df
    return df[df[col].astype(str).str.contains(str(value), case=False, na=False)]


# ─────────────────────────────────────────────
# TOOL 1: Query Deals
# ─────────────────────────────────────────────

def query_deals(
    sector: str = None,
    stage: str = None,
    quarter: str = None,
    year: int = None,
    metric: str = "summary"
) -> str:
    """
    Query and analyze the Deals/Pipeline data.
    
    metric options: 'summary' | 'by_sector' | 'by_stage' | 'total_value' | 'win_rate'
    """
    df = get_deals_df()
    quality = get_quality_summary()
    caveat = quality["deals_text"]

    # ── Apply filters ──
    if sector:
        df = _safe_filter(df, "Sector", sector)
    if stage:
        df = _safe_filter(df, "Stage", stage)

    # ── Date filtering (quarter + year) ──
    if "Close Date" in df.columns:
        df_close_date = pd.to_datetime(df["Close Date"], errors="coerce")
        if year is not None:
            try:
                df = df[df_close_date.dt.year == int(year)]
                df_close_date = pd.to_datetime(df["Close Date"], errors="coerce")
            except (ValueError, TypeError):
                pass

        if quarter:
            q_map = {"Q1": [1, 2, 3], "Q2": [4, 5, 6], "Q3": [7, 8, 9], "Q4": [10, 11, 12]}
            q_upper = str(quarter).upper().strip()
            if q_upper in q_map:
                df = df[df_close_date.dt.month.isin(q_map[q_upper])]

    if df.empty:
        return f"No deals found matching your filters (sector={sector}, stage={stage}, quarter={quarter}, year={year}).\n\n{caveat}"

    # ── Compute metrics ──
    total_rows = len(df)
    result_lines = [f"**Deals Analysis** ({total_rows} deals matched)\n"]

    if metric == "by_sector" and "Sector" in df.columns:
        grouped = df.groupby("Sector")
        for sec, group in grouped:
            val = group["Deal Value"].sum() if "Deal Value" in group.columns else 0
            result_lines.append(f"  • **{sec}**: {len(group)} deals | Value: ₹{val:,.0f}")

    elif metric == "by_stage" and "Stage" in df.columns:
        if "Deal Value" in df.columns:
            stage_stats = df.groupby("Stage").agg(
                Count=("Name", "count"),
                Total_Value=("Deal Value", "sum")
            ).reset_index()
            for _, row in stage_stats.iterrows():
                result_lines.append(f"  • **{row['Stage']}**: {row['Count']} deals | Value: ₹{row['Total_Value']:,.0f}")
        else:
            grouped = df.groupby("Stage").size()
            for stg, cnt in grouped.items():
                result_lines.append(f"  • **{stg}**: {cnt} deals")

    elif metric == "total_value" and "Deal Value" in df.columns:
        clean_vals = df["Deal Value"].dropna()
        result_lines.append(f"  • Total Pipeline Value: ₹{clean_vals.sum():,.0f}")
        result_lines.append(f"  • Average Deal Size: ₹{clean_vals.mean():,.0f}")
        result_lines.append(f"  • Deals with valid value: {len(clean_vals)}/{total_rows}")

    elif metric == "win_rate":
        won_deals = 0
        if "Stage" in df.columns:
            won_deals = len(df[df["Stage"].astype(str).str.lower().str.contains("won", na=False)])
        elif "Status" in df.columns:
            won_deals = len(df[df["Status"].astype(str).str.lower().str.contains("won", na=False)])
        win_rate_pct = (won_deals / total_rows * 100) if total_rows > 0 else 0
        result_lines.append(f"  • Closed Won Deals: {won_deals}/{total_rows}")
        result_lines.append(f"  • Win Rate: {win_rate_pct:.1f}%")
        if "Win Probability" in df.columns:
            mean_prob = df["Win Probability"].dropna().mean()
            if pd.notna(mean_prob):
                result_lines.append(f"  • Average Win Probability Across Pipeline: {mean_prob:.1f}%")

    else:  # default summary
        if "Deal Value" in df.columns:
            clean_vals = df["Deal Value"].dropna()
            result_lines.append(f"  • Total Value: ₹{clean_vals.sum():,.0f}")
            result_lines.append(f"  • Count: {total_rows} deals ({len(clean_vals)} with valid amounts)")

        if "Stage" in df.columns:
            stage_counts = df["Stage"].value_counts().head(5).to_dict()
            result_lines.append(f"  • Top Stages: {stage_counts}")

        if "Sector" in df.columns:
            sector_counts = df["Sector"].value_counts().head(5).to_dict()
            result_lines.append(f"  • Top Sectors: {sector_counts}")

    result_lines.append(f"\n---\n⚠️ *Data Caveats:*\n{caveat}")
    return "\n".join(result_lines)


# ─────────────────────────────────────────────
# TOOL 2: Query Work Orders
# ─────────────────────────────────────────────

def query_work_orders(
    status: str = None,
    sector: str = None,
    client: str = None,
    metric: str = "summary"
) -> str:
    """
    Query and analyze Work Orders / Execution data.
    
    metric options: 'summary' | 'by_status' | 'by_sector' | 'overdue' | 'revenue'
    """
    df = get_work_orders_df()
    quality = get_quality_summary()
    caveat = quality["work_orders_text"]

    # ── Apply filters ──
    if status:
        df = _safe_filter(df, "Status", status)
    if sector:
        df = _safe_filter(df, "Sector", sector)
    if client:
        df = _safe_filter(df, "Client", client)

    if df.empty:
        return f"No work orders found matching filters (status={status}, sector={sector}, client={client}).\n\n{caveat}"

    total_rows = len(df)
    result_lines = [f"**Work Orders Analysis** ({total_rows} records matched)\n"]

    if metric == "overdue" and "End Date" in df.columns:
        # Flag overdue: End Date in past + status not 'completed'/'done'
        df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")
        today = pd.Timestamp.today()
        done_keywords = ["completed", "done", "closed", "delivered"]
        if "Status" in df.columns:
            not_done = ~df["Status"].astype(str).str.lower().isin(done_keywords)
            overdue = df[not_done & (df["End Date"] < today) & df["End Date"].notna()]
        else:
            overdue = df[(df["End Date"] < today) & df["End Date"].notna()]

        result_lines.append(f"  • **Overdue Orders**: {len(overdue)} of {total_rows}")
        if not overdue.empty and "Client" in overdue.columns:
            result_lines.append(f"  • Affected Clients: {overdue['Client'].dropna().unique().tolist()[:5]}")
        if not overdue.empty and "Name" in overdue.columns:
            result_lines.append(f"  • Overdue Work Orders: {overdue['Name'].dropna().tolist()[:5]}")

    elif metric == "by_status" and "Status" in df.columns:
        status_counts = df["Status"].value_counts()
        for s, c in status_counts.items():
            result_lines.append(f"  • **{s}**: {c} orders")

    elif metric == "by_sector" and "Sector" in df.columns:
        if "Contract Value" in df.columns:
            sec_stats = df.groupby("Sector").agg(
                Count=("Name", "count"),
                Total_Value=("Contract Value", "sum")
            ).reset_index()
            for _, row in sec_stats.iterrows():
                result_lines.append(f"  • **{row['Sector']}**: {row['Count']} orders | Contract Value: ₹{row['Total_Value']:,.0f}")
        else:
            grouped = df.groupby("Sector").size()
            for sec, cnt in grouped.items():
                result_lines.append(f"  • **{sec}**: {cnt} orders")

    elif metric == "revenue" and "Contract Value" in df.columns:
        clean_vals = df["Contract Value"].dropna()
        result_lines.append(f"  • Total Contract Value: ₹{clean_vals.sum():,.0f}")
        result_lines.append(f"  • Average Contract: ₹{clean_vals.mean():,.0f}")
        if "Invoiced Amount" in df.columns:
            invoiced = df["Invoiced Amount"].dropna().sum()
            result_lines.append(f"  • Total Invoiced: ₹{invoiced:,.0f}")
            result_lines.append(f"  • Collection Gap: ₹{clean_vals.sum() - invoiced:,.0f}")

    else:  # default summary
        if "Status" in df.columns:
            status_dist = df["Status"].value_counts().to_dict()
            result_lines.append(f"  • Status Breakdown: {status_dist}")
        if "Sector" in df.columns:
            top_sectors = df["Sector"].value_counts().head(5).to_dict()
            result_lines.append(f"  • Top Sectors: {top_sectors}")
        if "Contract Value" in df.columns:
            clean_vals = df["Contract Value"].dropna()
            result_lines.append(f"  • Total Value: ₹{clean_vals.sum():,.0f} ({len(clean_vals)}/{total_rows} valid)")

    result_lines.append(f"\n---\n⚠️ *Data Caveats:*\n{caveat}")
    return "\n".join(result_lines)


# ─────────────────────────────────────────────
# TOOL 3: Generate Leadership Summary
# ─────────────────────────────────────────────

def generate_leadership_summary() -> str:
    """
    Generate a structured executive summary combining both boards.
    """
    deals_summary = query_deals(metric="summary")
    wo_summary = query_work_orders(metric="summary")
    overdue = query_work_orders(metric="overdue")

    return f"""
# 📋 Skylark Drones — BI Summary

## 🎯 Pipeline Health
{deals_summary}

## 🏗️ Execution / Work Orders
{wo_summary}

## ⚠️ Overdue / At-Risk
{overdue}

*Generated automatically. Review data quality caveats above before sharing externally.*
"""


# ─────────────────────────────────────────────
# Tool dispatch map (used by agent)
# ─────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "query_deals": query_deals,
    "query_work_orders": query_work_orders,
    "generate_leadership_summary": generate_leadership_summary
}
