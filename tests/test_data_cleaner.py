# tests/test_data_cleaner.py

import pytest
import pandas as pd
from backend.data_cleaner import (
    normalize_date,
    normalize_currency,
    normalize_text,
    normalize_percentage,
    clean_dataframe,
    quality_report_to_text
)


def test_normalize_date():
    assert normalize_date("2026-08-15") == "2026-08-15"
    assert normalize_date("15-Jun-26") == "2026-06-15"
    assert normalize_date("June 15 2026") == "2026-06-15"
    assert normalize_date("") is None
    assert normalize_date(None) is None


def test_normalize_currency():
    assert normalize_currency("₹1,25,000") == 125000.0
    assert normalize_currency("$250,000") == 250000.0
    assert normalize_currency("1.5M") == 1500000.0
    assert normalize_currency("2.5Cr") == 25000000.0
    assert normalize_currency("250000.00") == 250000.0
    assert normalize_currency("") is None
    assert normalize_currency(None) is None


def test_normalize_text():
    assert normalize_text("ENERGY ") == "Energy"
    assert normalize_text(" energy") == "Energy"
    assert normalize_text("Energy") == "Energy"
    assert normalize_text("") is None
    assert normalize_text(None) is None


def test_normalize_percentage():
    assert normalize_percentage("75%") == 75.0
    assert normalize_percentage("0.75") == 75.0
    assert normalize_percentage("100%") == 100.0
    assert normalize_percentage("") is None
    assert normalize_percentage(None) is None


def test_clean_dataframe():
    data = [
        {
            "Name": "Deal 1",
            "Close Date": "15-Aug-26",
            "Deal Value": "1.5M",
            "Sector": " ENERGY "
        },
        {
            "Name": "Deal 2",
            "Close Date": None,
            "Deal Value": "₹50,00,000",
            "Sector": "Defence"
        }
    ]
    df = pd.DataFrame(data)
    cleaned_df, report = clean_dataframe(
        df,
        date_cols=["Close Date"],
        currency_cols=["Deal Value"],
        text_cols=["Sector"]
    )
    assert cleaned_df.loc[0, "Close Date"] == "2026-08-15"
    assert cleaned_df.loc[0, "Deal Value"] == 1500000.0
    assert cleaned_df.loc[0, "Sector"] == "Energy"
    assert report["missing_dates"].get("Close Date") == 1
    assert report["total_rows"] == 2
    assert report["data_quality_score"] < 100.0


def test_quality_report_to_text():
    report = {
        "total_rows": 10,
        "missing_dates": {"Close Date": 1},
        "missing_amounts": {},
        "missing_text": {},
        "data_quality_score": 95.0
    }
    txt = quality_report_to_text(report, "Deals Board")
    assert "95.0% clean" in txt
    assert "Close Date" in txt
