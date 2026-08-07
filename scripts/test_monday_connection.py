# scripts/test_monday_connection.py
"""
Run this FIRST to verify monday.com connection and see actual column names.
This is critical — you need real column names to configure data_store.py correctly.

Run: python scripts/test_monday_connection.py
"""

import os
import json
import sys
sys.path.append(".")  # Run from project root

from dotenv import load_dotenv
load_dotenv()

from backend.monday_client import get_board_columns, get_board_items, items_to_flat_dicts

WORK_ORDERS_BOARD_ID = os.getenv("WORK_ORDERS_BOARD_ID", "123456789")
DEALS_BOARD_ID = os.getenv("DEALS_BOARD_ID", "987654321")


def verify_board(board_id: str, board_name: str):
    print(f"\n{'='*50}")
    print(f"Testing: {board_name} (ID: {board_id})")
    print('='*50)

    # Test 1: Get columns
    print("\n📋 COLUMNS:")
    columns = get_board_columns(board_id)
    for col in columns:
        print(f"  • {col.get('title', '')!r:30} | type: {col.get('type', '')}")

    # Test 2: Get first 3 items
    print("\n📦 SAMPLE ITEMS (first 3):")
    items, name = get_board_items(board_id)
    flat = items_to_flat_dicts(items[:3])
    for i, item in enumerate(flat):
        print(f"\n  Item {i+1}:")
        for k, v in item.items():
            if v:  # Only show non-empty
                print(f"    {k}: {v!r}")

    print(f"\n✅ Total items fetched: {len(items)}")


if __name__ == "__main__":
    verify_board(DEALS_BOARD_ID, "Deals Board")
    verify_board(WORK_ORDERS_BOARD_ID, "Work Orders Board")
    print("\n\n✅ Connection test complete! Use the column names above to configure data_store.py")
