# backend/data_store.py
"""
In-memory data store. Loads data once at startup (or on manual refresh).
This avoids hitting monday.com API on every single chat message.
"""

import os
import pandas as pd
from dotenv import load_dotenv
from backend.monday_client import get_board_items, items_to_flat_dicts
from backend.data_cleaner import clean_dataframe, quality_report_to_text

load_dotenv()

WORK_ORDERS_BOARD_ID = os.getenv("WORK_ORDERS_BOARD_ID", "123456789")
DEALS_BOARD_ID = os.getenv("DEALS_BOARD_ID", "987654321")


# ─── Global in-memory store ───
_store = {
    "deals_df": None,
    "work_orders_df": None,
    "deals_quality": None,
    "work_orders_quality": None,
    "deals_quality_text": "",
    "work_orders_quality_text": "",
    "deals_name": "Deals Board",
    "work_orders_name": "Work Orders Board",
    "loaded": False
}


def refresh_data():
    """
    Fetch fresh data from monday.com and normalize it.
    Call once at startup and expose a /refresh endpoint for manual reload.
    """
    global _store

    print("[data_store] Fetching Deals board...")
    deals_items, deals_name = get_board_items(DEALS_BOARD_ID)
    deals_flat = items_to_flat_dicts(deals_items)
    deals_df = pd.DataFrame(deals_flat)

    deals_df, deals_quality = clean_dataframe(
        deals_df,
        date_cols=["Close Date", "Created Date"],          # adjust to your column names
        currency_cols=["Deal Value", "Expected Revenue"],   # adjust to your column names
        text_cols=["Sector", "Stage", "Owner", "Status"],  # adjust to your column names
        percentage_cols=["Win Probability"]                 # adjust to your column names
    )
    _store["deals_df"] = deals_df
    _store["deals_quality"] = deals_quality
    _store["deals_quality_text"] = quality_report_to_text(deals_quality, deals_name)
    _store["deals_name"] = deals_name

    print("[data_store] Fetching Work Orders board...")
    wo_items, wo_name = get_board_items(WORK_ORDERS_BOARD_ID)
    wo_flat = items_to_flat_dicts(wo_items)
    wo_df = pd.DataFrame(wo_flat)

    wo_df, wo_quality = clean_dataframe(
        wo_df,
        date_cols=["Start Date", "End Date", "Delivery Date"],   # adjust to your column names
        currency_cols=["Contract Value", "Invoiced Amount"],      # adjust to your column names
        text_cols=["Status", "Sector", "Client", "Assigned To"]  # adjust to your column names
    )
    _store["work_orders_df"] = wo_df
    _store["work_orders_quality"] = wo_quality
    _store["work_orders_quality_text"] = quality_report_to_text(wo_quality, wo_name)
    _store["work_orders_name"] = wo_name

    _store["loaded"] = True
    print("[data_store] ✅ Data loaded and normalized successfully.")


def get_deals_df() -> pd.DataFrame:
    if not _store["loaded"] or _store["deals_df"] is None:
        refresh_data()
    return _store["deals_df"].copy()


def get_work_orders_df() -> pd.DataFrame:
    if not _store["loaded"] or _store["work_orders_df"] is None:
        refresh_data()
    return _store["work_orders_df"].copy()


def get_quality_summary() -> dict:
    if not _store["loaded"]:
        refresh_data()
    return {
        "deals": _store["deals_quality"],
        "work_orders": _store["work_orders_quality"],
        "deals_text": _store["deals_quality_text"],
        "work_orders_text": _store["work_orders_quality_text"],
        "deals_name": _store["deals_name"],
        "work_orders_name": _store["work_orders_name"]
    }
