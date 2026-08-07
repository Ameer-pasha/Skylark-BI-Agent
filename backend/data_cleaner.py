# backend/data_cleaner.py

import pandas as pd
from dateutil import parser as date_parser
import re


# ─────────────────────────────────────────────
# Individual field normalizers
# ─────────────────────────────────────────────

def normalize_date(date_str) -> str | None:
    """
    Parse messy date strings into standard YYYY-MM-DD format.
    Returns None (and doesn't crash) if unparseable.
    Handles: '15-Jun-24', 'June 15 2024', '2024/06/15', empty strings, None.
    """
    if not date_str or str(date_str).strip() in ("", "None", "nan", "null"):
        return None
    try:
        return date_parser.parse(str(date_str), fuzzy=True).strftime("%Y-%m-%d")
    except Exception:
        return None


def normalize_currency(val) -> float | None:
    """
    Parse currency strings to float.
    Handles: '₹1,25,000', '$250,000', '1.5M', '250000.00', None.
    """
    if val is None or str(val).strip() in ("", "None", "nan", "null"):
        return None

    val_str = str(val).strip()

    # Handle shorthand like '1.5M', '2.3K', '1.2Cr'
    multiplier = 1
    val_upper = val_str.upper()
    if val_upper.endswith("M"):
        multiplier = 1_000_000
        val_str = val_str[:-1]
    elif val_upper.endswith("CR"):
        multiplier = 10_000_000
        val_str = val_str[:-2]
    elif val_upper.endswith("K"):
        multiplier = 1_000
        val_str = val_str[:-1]

    # Strip currency symbols and commas
    cleaned = re.sub(r"[₹$€£,\s]", "", val_str)

    try:
        return float(cleaned) * multiplier
    except ValueError:
        return None


def normalize_text(val) -> str | None:
    """
    Standardize text fields: strip whitespace, fix casing.
    'ENERGY ', ' energy', 'Energy' → 'Energy'
    """
    if not val or str(val).strip() in ("", "None", "nan", "null"):
        return None
    return str(val).strip().title()


def normalize_percentage(val) -> float | None:
    """
    Parse percentage strings to float 0-100.
    '75%' → 75.0, '0.75' → 75.0 (auto-detect decimal format)
    """
    if not val or str(val).strip() in ("", "None", "nan", "null"):
        return None
    val_str = str(val).replace("%", "").strip()
    try:
        result = float(val_str)
        # If someone stored 0.75 instead of 75, convert
        if result <= 1.0 and "." in val_str and result > 0:
            result *= 100
        return result
    except ValueError:
        return None


# ─────────────────────────────────────────────
# Main DataFrame cleaner
# ─────────────────────────────────────────────

def clean_dataframe(
    df: pd.DataFrame,
    date_cols: list[str] = None,
    currency_cols: list[str] = None,
    text_cols: list[str] = None,
    percentage_cols: list[str] = None
) -> tuple[pd.DataFrame, dict]:
    """
    Apply normalizers to specified columns.
    Returns cleaned DataFrame + quality_report dict.
    
    quality_report = {
        "total_rows": 85,
        "missing_dates": {"Close Date": 12, "Start Date": 3},
        "missing_amounts": {"Deal Value": 5},
        "missing_text": {"Sector": 2},
        "data_quality_score": 91.2   # % of total cells that are clean
    }
    """
    date_cols = date_cols or []
    currency_cols = currency_cols or []
    text_cols = text_cols or []
    percentage_cols = percentage_cols or []

    quality_report = {
        "total_rows": len(df),
        "missing_dates": {},
        "missing_amounts": {},
        "missing_text": {}
    }

    # --- Date columns ---
    for col in date_cols:
        if col not in df.columns:
            continue
        df[col] = df[col].apply(normalize_date)
        missing = int(df[col].isna().sum())
        if missing > 0:
            quality_report["missing_dates"][col] = missing

    # --- Currency columns ---
    for col in currency_cols:
        if col not in df.columns:
            continue
        df[col] = df[col].apply(normalize_currency)
        missing = int(df[col].isna().sum())
        if missing > 0:
            quality_report["missing_amounts"][col] = missing

    # --- Text columns ---
    for col in text_cols:
        if col not in df.columns:
            continue
        df[col] = df[col].apply(normalize_text)
        missing = int(df[col].isna().sum())
        if missing > 0:
            quality_report["missing_text"][col] = missing

    # --- Percentage columns ---
    for col in percentage_cols:
        if col not in df.columns:
            continue
        df[col] = df[col].apply(normalize_percentage)

    # --- Compute overall data quality score ---
    total_cells = len(df) * len(df.columns)
    total_missing = (
        sum(quality_report["missing_dates"].values()) +
        sum(quality_report["missing_amounts"].values()) +
        sum(quality_report["missing_text"].values())
    )
    quality_report["data_quality_score"] = round(
        ((total_cells - total_missing) / total_cells * 100) if total_cells > 0 else 100.0,
        1
    )

    return df, quality_report


def quality_report_to_text(report: dict, board_name: str) -> str:
    """
    Convert quality report dict to human-readable caveat string.
    Agent will inject this into its responses.
    """
    lines = [f"📊 **{board_name} Data Quality** ({report['data_quality_score']}% clean, {report['total_rows']} rows)"]

    for col, count in report.get("missing_dates", {}).items():
        lines.append(f"  • {count} rows have missing/unparseable values in '{col}'")

    for col, count in report.get("missing_amounts", {}).items():
        lines.append(f"  • {count} rows have missing/invalid amounts in '{col}'")

    for col, count in report.get("missing_text", {}).items():
        lines.append(f"  • {count} rows have missing values in '{col}'")

    if len(lines) == 1:
        lines.append("  • No significant data quality issues detected ✅")

    return "\n".join(lines)
