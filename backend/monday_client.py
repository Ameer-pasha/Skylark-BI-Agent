# backend/monday_client.py

import os
import requests
from dotenv import load_dotenv

load_dotenv()

MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN")

HEADERS = {
    "Authorization": MONDAY_API_TOKEN or "",
    "Content-Type": "application/json",
    "API-Version": "2024-01"  # pin the API version for stability
}


def _is_mock_mode() -> bool:
    """
    Check if we should use mock data (missing token, placeholder token, or explicitly enabled).
    """
    token = os.getenv("MONDAY_API_TOKEN", "")
    if not token or token in ["your_monday_personal_api_token_here", "mock", "test", ""]:
        return True
    return False


def run_query(query: str, variables: dict = None) -> dict:
    """
    Core function to execute any GraphQL query against monday.com API.
    Raises on HTTP errors. Returns parsed JSON.
    """
    if _is_mock_mode():
        raise ValueError("Mock mode active: no valid MONDAY_API_TOKEN provided.")

    headers = {
        "Authorization": os.getenv("MONDAY_API_TOKEN", ""),
        "Content-Type": "application/json",
        "API-Version": "2024-01"
    }
    payload = {"query": query, "variables": variables or {}}
    resp = requests.post(MONDAY_API_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # monday.com returns errors inside JSON body, not as HTTP errors
    if "errors" in data:
        raise ValueError(f"monday.com API error: {data['errors']}")

    return data


def get_board_items(board_id: str) -> tuple[list[dict], str]:
    """
    Fetch ALL items from a board using cursor-based pagination.
    Handles boards with more than 100 items.
    Returns a flat list of item dicts with {name, column_values} and board_name.
    """
    query_template = """
    query ($boardId: [ID!], $cursor: String) {
      boards(ids: $boardId) {
        name
        columns {
          id
          title
          type
        }
        items_page(limit: 100, cursor: $cursor) {
          cursor
          items {
            id
            name
            column_values {
              id
              text
              value
              column {
                title
                type
              }
            }
          }
        }
      }
    }
    """

    if not _is_mock_mode():
        try:
            all_items = []
            cursor = None
            board_name = None

            while True:
                variables = {"boardId": [board_id], "cursor": cursor}
                result = run_query(query_template, variables)

                boards = result.get("data", {}).get("boards", [])
                if not boards:
                    break
                board_data = boards[0]
                board_name = board_data.get("name", f"Board {board_id}")
                page = board_data.get("items_page", {})
                items = page.get("items", [])
                all_items.extend(items)

                cursor = page.get("cursor")
                if not cursor:  # No more pages
                    break

            print(f"[monday_client] Fetched {len(all_items)} items from board '{board_name}'")
            return all_items, board_name
        except Exception as e:
            print(f"[monday_client] API call failed ({e}). Falling back to mock data.")

    # Mock Data Fallback
    items, board_name = _get_mock_board_items(str(board_id))
    print(f"[monday_client] Using sample data: Fetched {len(items)} items from board '{board_name}'")
    return items, board_name


def get_board_columns(board_id: str) -> list[dict]:
    """
    Fetch column metadata for a board.
    Useful for understanding column types before normalization.
    """
    query = """
    query ($boardId: [ID!]) {
      boards(ids: $boardId) {
        columns {
          id
          title
          type
        }
      }
    }
    """
    if not _is_mock_mode():
        try:
            result = run_query(query, {"boardId": [board_id]})
            boards = result.get("data", {}).get("boards", [])
            if boards:
                return boards[0].get("columns", [])
        except Exception as e:
            print(f"[monday_client] get_board_columns API call failed ({e}). Using mock columns.")

    return _get_mock_columns(str(board_id))


def items_to_flat_dicts(items: list[dict]) -> list[dict]:
    """
    Convert monday.com's nested column_values structure into flat dicts.
    
    monday.com returns items like:
    {
      "name": "Deal A",
      "column_values": [
        {"column": {"title": "Status"}, "text": "In Progress"},
        {"column": {"title": "Close Date"}, "text": "2026-08-15"},
        ...
      ]
    }
    
    We convert to: {"Name": "Deal A", "Status": "In Progress", "Close Date": "2026-08-15"}
    """
    flat_records = []

    for item in items:
        record = {"Name": item.get("name", "")}
        for cv in item.get("column_values", []):
            col_info = cv.get("column", {})
            col_title = col_info.get("title", cv.get("id", ""))
            # Use 'text' field — it's the human-readable string version
            # 'value' is raw JSON (e.g., '{"date":"2026-08-15"}') — harder to parse
            record[col_title] = cv.get("text") or None
        flat_records.append(record)

    return flat_records


# ─────────────────────────────────────────────
# MOCK / SAMPLE DATA GENERATOR
# ─────────────────────────────────────────────

def _get_mock_board_items(board_id: str) -> tuple[list[dict], str]:
    """
    Return realistic sample data for Deals and Work Orders boards.
    """
    deals_board_id = os.getenv("DEALS_BOARD_ID", "987654321")
    # Identify if it's deals or work orders
    if str(board_id) == str(deals_board_id) or "deal" in str(board_id).lower():
        board_name = "Deals Board"
        raw_rows = [
            {
                "Name": "Project Alpha Drone Deployment",
                "Close Date": "2026-08-15",
                "Created Date": "2026-05-10",
                "Deal Value": "₹45,00,000",
                "Expected Revenue": "₹40,00,000",
                "Sector": "Defence",
                "Stage": "Negotiation",
                "Owner": "Ameer Pasha",
                "Status": "Active",
                "Win Probability": "75%"
            },
            {
                "Name": "Border Surveillance Grid",
                "Close Date": "2026-09-30",
                "Created Date": "2026-06-01",
                "Deal Value": "1.5Cr",
                "Expected Revenue": "1.4Cr",
                "Sector": "Defence ",
                "Stage": "Proposal",
                "Owner": "Ameer Pasha",
                "Status": "Active",
                "Win Probability": "60%"
            },
            {
                "Name": "Wind Farm Thermal Inspection",
                "Close Date": "15-Aug-26",
                "Created Date": "2026-06-15",
                "Deal Value": "₹28,50,000",
                "Expected Revenue": "₹25,00,000",
                "Sector": "Energy",
                "Stage": "Closed Won",
                "Owner": "Priya Sharma",
                "Status": "Won",
                "Win Probability": "95%"
            },
            {
                "Name": "Agri-Spray Fleet Contract",
                "Close Date": "2026-07-10",
                "Created Date": "2026-04-20",
                "Deal Value": "₹18,00,000",
                "Expected Revenue": "₹18,00,000",
                "Sector": "Agriculture",
                "Stage": "Closed Won",
                "Owner": "Rohan Mehta",
                "Status": "Won",
                "Win Probability": "100%"
            },
            {
                "Name": "Mining Pit Volume Mapping",
                "Close Date": "2026-08-25",
                "Created Date": "2026-07-01",
                "Deal Value": "₹32,00,000",
                "Expected Revenue": "₹30,00,000",
                "Sector": "Mining",
                "Stage": "Proposal",
                "Owner": "Priya Sharma",
                "Status": "Active",
                "Win Probability": "50%"
            },
            {
                "Name": "Highway Corridor Survey",
                "Close Date": "2026-10-15",
                "Created Date": "2026-07-15",
                "Deal Value": "₹55,00,000",
                "Expected Revenue": "₹50,00,000",
                "Sector": "Infrastructure",
                "Stage": "Discovery",
                "Owner": "Rohan Mehta",
                "Status": "Active",
                "Win Probability": "30%"
            },
            {
                "Name": "Solar Plant Infrared Mapping",
                "Close Date": "2026-08-20",
                "Created Date": "2026-06-10",
                "Deal Value": "₹22,00,000",
                "Expected Revenue": "₹20,00,000",
                "Sector": " energy",
                "Stage": "Negotiation",
                "Owner": "Priya Sharma",
                "Status": "Active",
                "Win Probability": "80%"
            },
            {
                "Name": "Naval Coastal Reconnaissance",
                "Close Date": "2026-11-01",
                "Created Date": "2026-07-05",
                "Deal Value": "2.2Cr",
                "Expected Revenue": "2.0Cr",
                "Sector": "Defence",
                "Stage": "Qualified",
                "Owner": "Ameer Pasha",
                "Status": "Active",
                "Win Probability": "40%"
            },
            {
                "Name": "Crop Yield Monitoring Program",
                "Close Date": None,  # Intentionally missing date for quality report testing
                "Created Date": "2026-07-01",
                "Deal Value": "₹15,00,000",
                "Expected Revenue": "₹15,00,000",
                "Sector": "Agriculture",
                "Stage": "Proposal",
                "Owner": "Rohan Mehta",
                "Status": "Active",
                "Win Probability": "50%"
            },
            {
                "Name": "Railway Track LiDAR Scan",
                "Close Date": "2026-09-15",
                "Created Date": "2026-06-20",
                "Deal Value": "₹65,00,000",
                "Expected Revenue": "₹60,00,000",
                "Sector": "Infrastructure",
                "Stage": "Negotiation",
                "Owner": "Ameer Pasha",
                "Status": "Active",
                "Win Probability": "70%"
            },
            {
                "Name": "Oil Pipeline Patrol Contract",
                "Close Date": "2026-08-30",
                "Created Date": "2026-05-15",
                "Deal Value": "₹40,00,000",
                "Expected Revenue": "₹38,00,000",
                "Sector": "Energy",
                "Stage": "Proposal",
                "Owner": "Priya Sharma",
                "Status": "Active",
                "Win Probability": "60%"
            },
            {
                "Name": "Forestry Canopy Health Study",
                "Close Date": "2026-09-10",
                "Created Date": "2026-07-01",
                "Deal Value": None,  # Intentionally missing amount for quality report testing
                "Expected Revenue": None,
                "Sector": None,      # Intentionally missing text for quality report testing
                "Stage": "Discovery",
                "Owner": "Rohan Mehta",
                "Status": "Active",
                "Win Probability": "25%"
            }
        ]
    else:
        board_name = "Work Orders Board"
        raw_rows = [
            {
                "Name": "WO-101 Thermal Inspection - Phase 1",
                "Start Date": "2026-06-01",
                "End Date": "2026-07-20",  # Overdue (past end date, today is 2026-08-07)
                "Delivery Date": "2026-07-25",
                "Contract Value": "₹28,50,000",
                "Invoiced Amount": "₹15,00,000",
                "Status": "In Progress",
                "Sector": "Energy",
                "Client": "Tata Power",
                "Assigned To": "Team Alpha"
            },
            {
                "Name": "WO-102 Border Grid Deployment",
                "Start Date": "2026-06-15",
                "End Date": "2026-08-01",  # Overdue
                "Delivery Date": "2026-08-05",
                "Contract Value": "₹65,00,000",
                "Invoiced Amount": "₹30,00,000",
                "Status": "In Progress",
                "Sector": "Defence",
                "Client": "DRDO",
                "Assigned To": "Team Beta"
            },
            {
                "Name": "WO-103 Punjab Wheat Spray",
                "Start Date": "2026-07-01",
                "End Date": "2026-07-25",  # Completed
                "Delivery Date": "2026-07-28",
                "Contract Value": "₹18,00,000",
                "Invoiced Amount": "₹18,00,000",
                "Status": "Completed",
                "Sector": "Agriculture",
                "Client": "Mahindra Agri",
                "Assigned To": "Team Gamma"
            },
            {
                "Name": "WO-104 Rajasthan Solar Farm Audit",
                "Start Date": "2026-07-10",
                "End Date": "2026-08-25",
                "Delivery Date": "2026-08-30",
                "Contract Value": "₹22,00,000",
                "Invoiced Amount": "₹10,00,000",
                "Status": "In Progress",
                "Sector": "Energy",
                "Client": "Adani Green",
                "Assigned To": "Team Alpha"
            },
            {
                "Name": "WO-105 Dhanbad Coal Pit Volumetrics",
                "Start Date": "2026-07-15",
                "End Date": "2026-09-01",
                "Delivery Date": "2026-09-05",
                "Contract Value": "₹32,00,000",
                "Invoiced Amount": "₹0",
                "Status": "In Progress",
                "Sector": "Mining",
                "Client": "Coal India",
                "Assigned To": "Team Delta"
            },
            {
                "Name": "WO-106 Expressway Bridge Scan",
                "Start Date": "2026-07-01",
                "End Date": "2026-07-30",  # Overdue
                "Delivery Date": "2026-08-05",
                "Contract Value": "₹40,00,000",
                "Invoiced Amount": "₹20,00,000",
                "Status": "In Progress",
                "Sector": "Infrastructure",
                "Client": "L&T Construction",
                "Assigned To": "Team Gamma"
            },
            {
                "Name": "WO-107 Naval Base Perimeter Drone",
                "Start Date": "2026-07-20",
                "End Date": "2026-09-30",
                "Delivery Date": "2026-10-05",
                "Contract Value": "1.2Cr",
                "Invoiced Amount": "₹40,00,000",
                "Status": "In Progress",
                "Sector": "Defence",
                "Client": "HAL",
                "Assigned To": "Team Beta"
            },
            {
                "Name": "WO-108 Tamil Nadu Wind Turbine Inspection",
                "Start Date": "2026-06-10",
                "End Date": "2026-07-15",
                "Delivery Date": "2026-07-18",
                "Contract Value": "₹15,00,000",
                "Invoiced Amount": "₹15,00,000",
                "Status": "Completed",
                "Sector": "Energy",
                "Client": "Tata Power",
                "Assigned To": "Team Alpha"
            },
            {
                "Name": "WO-109 Madhya Pradesh Soybean Mapping",
                "Start Date": "2026-07-05",
                "End Date": "2026-08-15",
                "Delivery Date": "2026-08-20",
                "Contract Value": "₹12,00,000",
                "Invoiced Amount": "₹6,00,000",
                "Status": "In Progress",
                "Sector": "Agriculture",
                "Client": "ITC Agri",
                "Assigned To": "Team Gamma"
            },
            {
                "Name": "WO-110 Odisha Bauxite Pit Survey",
                "Start Date": "2026-06-25",
                "End Date": "2026-07-28",  # Overdue
                "Delivery Date": "2026-08-02",
                "Contract Value": "₹25,00,000",
                "Invoiced Amount": "₹10,00,000",
                "Status": "In Progress",
                "Sector": "Mining",
                "Client": "Vedanta",
                "Assigned To": "Team Delta"
            },
            {
                "Name": "WO-111 Dedicated Freight Corridor Survey",
                "Start Date": "2026-07-15",
                "End Date": "2026-09-15",
                "Delivery Date": "2026-09-20",
                "Contract Value": "₹50,00,000",
                "Invoiced Amount": "₹15,00,000",
                "Status": "In Progress",
                "Sector": "Infrastructure",
                "Client": "L&T Construction",
                "Assigned To": "Team Alpha"
            }
        ]

    # Build Monday-style nested column_values structure
    mock_items = []
    for idx, row in enumerate(raw_rows):
        cv_list = []
        for k, v in row.items():
            if k == "Name":
                continue
            cv_list.append({
                "id": k.lower().replace(" ", "_"),
                "text": str(v) if v is not None else None,
                "value": None,
                "column": {
                    "title": k,
                    "type": "text"
                }
            })
        mock_items.append({
            "id": str(idx + 100),
            "name": row["Name"],
            "column_values": cv_list
        })

    return mock_items, board_name


def _get_mock_columns(board_id: str) -> list[dict]:
    """
    Return column metadata for mock boards.
    """
    deals_board_id = os.getenv("DEALS_BOARD_ID", "987654321")
    if str(board_id) == str(deals_board_id) or "deal" in str(board_id).lower():
        titles = ["Close Date", "Created Date", "Deal Value", "Expected Revenue", "Sector", "Stage", "Owner", "Status", "Win Probability"]
    else:
        titles = ["Start Date", "End Date", "Delivery Date", "Contract Value", "Invoiced Amount", "Status", "Sector", "Client", "Assigned To"]

    cols = []
    for t in titles:
        cols.append({
            "id": t.lower().replace(" ", "_"),
            "title": t,
            "type": "text"
        })
    return cols
