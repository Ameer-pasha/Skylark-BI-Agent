# tests/test_tools.py

from backend.tools import query_deals, query_work_orders, generate_leadership_summary


def test_query_deals_summary():
    res = query_deals(metric="summary")
    assert "Deals Analysis" in res
    assert "Total Value" in res
    assert "Data Caveats" in res


def test_query_deals_total_value():
    res = query_deals(metric="total_value")
    assert "Total Pipeline Value" in res
    assert "Average Deal Size" in res


def test_query_deals_win_rate():
    res = query_deals(metric="win_rate")
    assert "Closed Won Deals" in res
    assert "Win Rate:" in res


def test_query_deals_filters():
    res = query_deals(sector="Defence", metric="summary")
    assert "Deals Analysis" in res
    res_q3 = query_deals(quarter="Q3", year=2026, metric="summary")
    assert "Deals Analysis" in res_q3


def test_query_work_orders_summary():
    res = query_work_orders(metric="summary")
    assert "Work Orders Analysis" in res
    assert "Status Breakdown" in res


def test_query_work_orders_overdue():
    res = query_work_orders(metric="overdue")
    assert "Overdue Orders" in res


def test_query_work_orders_revenue():
    res = query_work_orders(metric="revenue")
    assert "Total Contract Value" in res
    assert "Collection Gap" in res


def test_generate_leadership_summary():
    res = generate_leadership_summary()
    assert "Skylark Drones — BI Summary" in res
    assert "Pipeline Health" in res
    assert "Execution / Work Orders" in res
    assert "Overdue / At-Risk" in res
