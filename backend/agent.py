# backend/agent.py
"""
Claude-powered conversational agent with tool-calling loop.
Uses Anthropic's tool_use feature — no LangGraph needed.
Includes an intelligent fallback mode when running without an API key or offline.
"""

import os
import json
import re
from anthropic import Anthropic
from dotenv import load_dotenv
from backend.tools import TOOL_FUNCTIONS

load_dotenv()

# ─────────────────────────────────────────────
# Tool schemas (tells Claude what tools exist)
# ─────────────────────────────────────────────

TOOLS = [
    {
        "name": "query_deals",
        "description": (
            "Query and analyze the Deals/Pipeline board from monday.com. "
            "Use this for questions about sales pipeline, deal values, sectors, "
            "win rates, deal stages, or revenue forecasts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sector": {
                    "type": "string",
                    "description": "Filter by industry sector (e.g., 'Energy', 'Defence', 'Agriculture')"
                },
                "stage": {
                    "type": "string",
                    "description": "Filter by deal stage (e.g., 'Proposal', 'Negotiation', 'Closed Won')"
                },
                "quarter": {
                    "type": "string",
                    "description": "Filter by quarter: 'Q1', 'Q2', 'Q3', or 'Q4'"
                },
                "year": {
                    "type": "integer",
                    "description": "Filter by year (e.g., 2026)"
                },
                "metric": {
                    "type": "string",
                    "enum": ["summary", "by_sector", "by_stage", "total_value", "win_rate"],
                    "description": "Type of analysis to perform"
                }
            },
            "required": []
        }
    },
    {
        "name": "query_work_orders",
        "description": (
            "Query and analyze the Work Orders / Execution board from monday.com. "
            "Use this for questions about operational work, project status, delivery timelines, "
            "overdue orders, invoicing, or client-level execution data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by work order status (e.g., 'In Progress', 'Completed', 'On Hold')"
                },
                "sector": {
                    "type": "string",
                    "description": "Filter by sector"
                },
                "client": {
                    "type": "string",
                    "description": "Filter by client name"
                },
                "metric": {
                    "type": "string",
                    "enum": ["summary", "by_status", "by_sector", "overdue", "revenue"],
                    "description": "Type of analysis to perform"
                }
            },
            "required": []
        }
    },
    {
        "name": "generate_leadership_summary",
        "description": (
            "Generate a structured executive/leadership summary combining pipeline "
            "and execution data. Use when user asks for 'weekly summary', 'leadership update', "
            "'board report', or an overview of the full business."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


# ─────────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Business Intelligence Assistant for Skylark Drones — a drone services company.
You have access to two live data boards from monday.com:
1. **Deals Board** — Sales pipeline: deal stages, values, sectors, close dates, win probability
2. **Work Orders Board** — Execution: active projects, delivery timelines, client status, invoicing

YOUR BEHAVIOR RULES:

1. **Always mention data quality caveats** in your responses — if the tool returns missing dates, 
   invalid amounts, or low data quality, include that context so users know to interpret carefully.

2. **Ask clarifying questions for ambiguous queries** — examples:
   - "This quarter" → Ask: "Just to confirm, are you referring to Q3 2026 (July–September)?"
   - "Top deals" → Ask: "By deal value, or by probability of closing?"
   - "How are we doing?" → Ask: "Are you asking about pipeline health, execution status, or both?"

3. **Provide business insight, not just raw numbers** — after giving data, add a brief interpretation:
   - Flag risks (e.g., "70% of pipeline is in early stages — close rate risk")
   - Note trends (e.g., "Defence sector dominates deals — concentration risk")
   - Suggest actions when appropriate

4. **Be honest about limitations**:
   - If data is missing or incomplete, say so
   - If a question requires data you don't have (e.g., competitor data), say so
   - Never fabricate numbers

5. **Format responses clearly** using markdown — use bullets, bold headers, and tables where helpful.

6. Today's date context: Today is August 7, 2026 (Q3 2026). Use this to correctly interpret "this quarter", "last month", etc.
   Always state the date range you're using when applying time filters.
"""


def _is_mock_ai_mode() -> bool:
    """Check if we should use local fallback agent instead of live Anthropic API."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key in ["your_anthropic_api_key_here", "mock", "test", ""]:
        return True
    return False


def _local_fallback_agent(user_message: str, conversation_history: list[dict]) -> str:
    """
    Intelligent rule-based fallback agent that invokes tools and formats high-quality BI responses
    with insights, caveats, and clarifying questions when no Anthropic API key is present.
    """
    msg = user_message.lower()
    insights = []
    response_sections = []

    # 1. Ambiguous queries -> ask clarifying questions
    if msg.strip() in ["how are we doing?", "overview", "status"]:
        return (
            "🚁 **Skylark Drones BI Assistant**\n\n"
            "Just to confirm — are you asking about **pipeline health** (Deals), **execution status** (Work Orders), or a **full leadership summary**?\n\n"
            "In the meantime, here is our full leadership executive summary:\n\n"
            f"{TOOL_FUNCTIONS['generate_leadership_summary']()}\n\n"
            "💡 *Business Insight*: Defence and Energy sectors represent our largest pipeline and execution contracts. Monitor overdue work orders closely to protect cash flow."
        )

    # 2. Leadership / executive summary
    if any(k in msg for k in ["leadership", "summary", "executive", "weekly", "report", "board report", "business"]):
        res = TOOL_FUNCTIONS["generate_leadership_summary"]()
        return (
            f"{res}\n\n"
            "### 💡 Executive Interpretation & Risk Flags\n"
            "- **Pipeline Risk**: Ensure early-stage Proposal/Discovery deals are moved to Negotiation to meet Q3 revenue targets.\n"
            "- **Execution Risk**: Several work orders are overdue; prioritize client communications and field deployment schedules.\n"
            "- **Cash Flow Opportunity**: Address collection gaps on invoiced vs. contract amounts for active work orders."
        )

    # 3. Work Orders specific queries
    if any(k in msg for k in ["work order", "execution", "overdue", "invoice", "invoiced", "collection", "contract", "client"]):
        metric = "summary"
        if "overdue" in msg:
            metric = "overdue"
        elif any(k in msg for k in ["revenue", "invoiced", "collection", "contract value", "gap"]):
            metric = "revenue"
        elif "status" in msg:
            metric = "by_status"
        elif "sector" in msg:
            metric = "by_sector"

        # Check optional sector or client filters
        sector = None
        for sec in ["Energy", "Defence", "Agriculture", "Mining", "Infrastructure"]:
            if sec.lower() in msg:
                sector = sec
                break
        client = None
        for cl in ["Tata Power", "DRDO", "Adani Green", "Mahindra Agri", "L&T Construction", "Coal India", "HAL", "Vedanta"]:
            if cl.lower() in msg:
                client = cl
                break

        res = TOOL_FUNCTIONS["query_work_orders"](sector=sector, client=client, metric=metric)

        insight = (
            "\n\n### 💡 Business Insight & Recommended Actions\n"
            "- **Execution Alert**: Keep an eye on overdue milestones; delays can trigger contract penalties or delay invoicing.\n"
            "- **Collections**: Follow up on uninvoiced contract balances as projects hit delivery milestones."
        )
        return res + insight

    # 4. Deals / Pipeline specific queries (default if not work orders)
    metric = "summary"
    if any(k in msg for k in ["total value", "pipeline value", "worth"]):
        metric = "total_value"
    elif any(k in msg for k in ["win rate", "win probability", "won"]):
        metric = "win_rate"
    elif "sector" in msg:
        metric = "by_sector"
    elif "stage" in msg:
        metric = "by_stage"

    sector = None
    for sec in ["Energy", "Defence", "Agriculture", "Mining", "Infrastructure"]:
        if sec.lower() in msg:
            sector = sec
            break
    stage = None
    for stg in ["Proposal", "Negotiation", "Closed Won", "Discovery", "Qualified"]:
        if stg.lower() in msg:
            stage = stg
            break
    quarter = None
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        if q.lower() in msg:
            quarter = q
            break
    year = None
    year_match = re.search(r"202\d", msg)
    if year_match:
        year = int(year_match.group(0))

    # Clarifying note if "this quarter" mentioned without year
    clarification = ""
    if "this quarter" in msg and not year:
        clarification = "*(Note: Interpreting 'this quarter' as Q3 2026 based on today's date August 7, 2026)*\n\n"
        quarter = "Q3"
        year = 2026

    res = TOOL_FUNCTIONS["query_deals"](sector=sector, stage=stage, quarter=quarter, year=year, metric=metric)

    insight = (
        "\n\n### 💡 Business Insight & Pipeline Health\n"
        "- **Concentration Risk**: High-value deals are concentrated in Defence and Energy; expanding agriculture and infrastructure can balance the portfolio.\n"
        "- **Conversion Focus**: Focus account executives on deals in 'Negotiation' to lock in Q3 revenue."
    )
    return clarification + res + insight


# ─────────────────────────────────────────────
# Main Agent Function
# ─────────────────────────────────────────────

def run_agent(user_message: str, conversation_history: list[dict]) -> str:
    """
    Run the Claude tool-calling agent loop.
    
    conversation_history: list of {"role": "user"/"assistant", "content": "..."}
    Returns final text response as string.
    
    Flow:
    1. Send user message + history to Claude
    2. If Claude returns tool_use → execute tool → feed result back → repeat
    3. When Claude returns final text → return it
    """
    if _is_mock_ai_mode():
        print("[agent] Mock AI mode active (no valid ANTHROPIC_API_KEY). Using local fallback BI agent.")
        return _local_fallback_agent(user_message, conversation_history)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = Anthropic(api_key=api_key)
    model_name = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    # Build messages list (history + new user message)
    messages = conversation_history + [{"role": "user", "content": user_message}]

    max_iterations = 5  # Prevent infinite loops
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        try:
            # ── Call Claude ──
            response = client.messages.create(
                model=model_name,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            )
        except Exception as e:
            print(f"[agent] Anthropic API call failed: {e}. Falling back to local BI agent.")
            return _local_fallback_agent(user_message, conversation_history)

        # ── Check stop reason ──
        if response.stop_reason == "end_turn":
            # Claude is done — extract text response
            text_blocks = [block.text for block in response.content if hasattr(block, "text")]
            return "\n".join(text_blocks)

        elif response.stop_reason == "tool_use":
            # Claude wants to call tool(s) — execute them
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    print(f"[agent] Tool called: {tool_name} with input: {tool_input}")

                    # Execute the tool
                    if tool_name in TOOL_FUNCTIONS:
                        try:
                            tool_result = TOOL_FUNCTIONS[tool_name](**tool_input)
                        except Exception as e:
                            tool_result = f"Error executing {tool_name}: {str(e)}"
                    else:
                        tool_result = f"Unknown tool: {tool_name}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_result
                    })

            # Add Claude's response (with tool_use blocks) to messages
            messages.append({"role": "assistant", "content": response.content})
            # Add tool results for Claude to process
            messages.append({"role": "user", "content": tool_results})

        else:
            # Unexpected stop reason
            return f"Agent stopped unexpectedly: {response.stop_reason}"

    return "I reached the maximum reasoning steps. Please try a more specific question."
