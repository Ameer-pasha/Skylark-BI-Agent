# backend/agent.py
"""
Conversational agent with tool-calling support for both Anthropic Claude and xAI Grok.
- Uses Anthropic's tool_use API when LLM_PROVIDER=anthropic / claude
- Uses xAI Grok via OpenAI-compatible API (https://api.x.ai/v1) when LLM_PROVIDER=grok / xai
- Auto-detects provider based on available API keys if LLM_PROVIDER=auto
- Includes an intelligent fallback mode when running without an API key or offline.

Grok tool-calling is implemented via the `openai` SDK with `base_url="https://api.x.ai/v1"`,
matching xAI's OpenAI-compatible endpoint. Tool schemas are translated to OpenAI function
format while reusing the same TOOL_FUNCTIONS dispatch map.
"""

import os
import json
import re
from anthropic import Anthropic
from dotenv import load_dotenv
from backend.tools import TOOL_FUNCTIONS

load_dotenv()

# ─────────────────────────────────────────────
# Tool schemas - Anthropic Claude format
# ─────────────────────────────────────────────

TOOLS_CLAUDE = [
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

# Backward-compat alias
TOOLS = TOOLS_CLAUDE

# ─────────────────────────────────────────────
# Tool schemas - OpenAI / xAI Grok format
# ─────────────────────────────────────────────

TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "query_deals",
            "description": (
                "Query and analyze the Deals/Pipeline board from monday.com. "
                "Use this for questions about sales pipeline, deal values, sectors, "
                "win rates, deal stages, or revenue forecasts."
            ),
            "parameters": {
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
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_work_orders",
            "description": (
                "Query and analyze the Work Orders / Execution board from monday.com. "
                "Use this for questions about operational work, project status, delivery timelines, "
                "overdue orders, invoicing, or client-level execution data."
            ),
            "parameters": {
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
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_leadership_summary",
            "description": (
                "Generate a structured executive/leadership summary combining pipeline "
                "and execution data. Use when user asks for 'weekly summary', 'leadership update', "
                "'board report', or an overview of the full business."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
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


# ─────────────────────────────────────────────
# Provider helpers
# ─────────────────────────────────────────────

_PLACEHOLDER_KEYS = {"", "your_anthropic_api_key_here", "your_xai_api_key_here", "mock", "test", "placeholder"}


def _is_valid_key(value: str) -> bool:
    if not value:
        return False
    v = value.strip()
    if not v or v.lower() in _PLACEHOLDER_KEYS:
        return False
    # xAI keys typically start with xai- ; Anthropic with sk-ant-
    # but accept any non-placeholder lengthy string
    return len(v) > 10


def _get_anthropic_key() -> str:
    return (os.getenv("ANTHROPIC_API_KEY") or "").strip()


def _get_xai_key() -> str:
    # Support XAI_API_KEY, GROK_API_KEY, XAI_KEY for flexibility
    for env_key in ["XAI_API_KEY", "GROK_API_KEY", "XAI_KEY"]:
        val = os.getenv(env_key, "").strip()
        if _is_valid_key(val):
            return val
    # Fallback to raw fetch to allow placeholder detection
    return (os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY") or "").strip()


def _get_llm_provider() -> str:
    """
    Resolve LLM provider.

    Env LLM_PROVIDER values:
      - anthropic / claude -> force Claude
      - grok / xai / x-ai -> force Grok
      - auto (default) -> auto-detect based on available valid keys

    Auto-detect precedence:
      1. If only one provider has a valid key, use it
      2. If both have valid keys, respect explicit LLM_PROVIDER, else default to anthropic
      3. If none, return 'mock'
    """
    raw = (os.getenv("LLM_PROVIDER") or "auto").strip().lower()
    has_anthropic = _is_valid_key(_get_anthropic_key())
    has_xai = _is_valid_key(_get_xai_key())

    # Explicit forced providers
    if raw in ("grok", "xai", "x-ai", "xai_grok"):
        return "grok" if has_xai else ("mock" if not has_anthropic else "anthropic")
    if raw in ("anthropic", "claude"):
        return "anthropic" if has_anthropic else ("mock" if not has_xai else "grok")
    if raw in ("openai",):
        # Treat openai as grok-compatible via xAI endpoint if XAI key present
        return "grok" if has_xai else "mock"

    # Auto mode
    if has_xai and not has_anthropic:
        return "grok"
    if has_anthropic and not has_xai:
        return "anthropic"
    if has_xai and has_anthropic:
        # Both present -> default to anthropic unless provider explicitly says grok
        # but if LLM_PROVIDER is auto, prefer anthropic for backward compat
        return "anthropic"
    return "mock"


def _is_mock_ai_mode() -> bool:
    """Check if we should use local fallback agent instead of live LLM API."""
    return _get_llm_provider() == "mock"


def _local_fallback_agent(user_message: str, conversation_history: list[dict]) -> str:
    """
    Intelligent rule-based fallback agent that invokes tools and formats high-quality BI responses
    with insights, caveats, and clarifying questions when no LLM API key is present.
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
# Claude runner
# ─────────────────────────────────────────────

def _run_claude_agent(user_message: str, conversation_history: list[dict]) -> str:
    api_key = _get_anthropic_key()
    client = Anthropic(api_key=api_key)
    model_name = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    messages = conversation_history + [{"role": "user", "content": user_message}]
    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        try:
            response = client.messages.create(
                model=model_name,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOLS_CLAUDE,
                messages=messages
            )
        except Exception as e:
            print(f"[agent:claude] Anthropic API call failed: {e}. Falling back to local BI agent.")
            return _local_fallback_agent(user_message, conversation_history)

        if response.stop_reason == "end_turn":
            text_blocks = [block.text for block in response.content if hasattr(block, "text")]
            return "\n".join(text_blocks)

        elif response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    print(f"[agent:claude] Tool called: {tool_name} with input: {tool_input}")
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
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            return f"Agent stopped unexpectedly: {response.stop_reason}"

    return "I reached the maximum reasoning steps. Please try a more specific question."


# ─────────────────────────────────────────────
# Grok (xAI) runner - OpenAI-compatible
# ─────────────────────────────────────────────

def _run_grok_agent(user_message: str, conversation_history: list[dict]) -> str:
    """
    Run Grok via xAI's OpenAI-compatible API.

    Uses `openai` SDK with base_url="https://api.x.ai/v1".
    Implements the same tool-calling loop as Claude but with OpenAI semantics:
      - tools -> `tools` with `type: function`
      - tool_calls -> execute -> append `tool` role messages -> loop
    """
    try:
        from openai import OpenAI
    except ImportError:
        print("[agent:grok] openai package not installed. Falling back to local BI agent. Install with `pip install openai`.")
        return _local_fallback_agent(user_message, conversation_history)

    api_key = _get_xai_key()
    # XAI_MODEL / GROK_MODEL / ANTHROPIC_MODEL fallback chain
    model_name = (
        os.getenv("XAI_MODEL")
        or os.getenv("GROK_MODEL")
        or os.getenv("ANTHROPIC_MODEL")  # allow reusing generic var
        or "grok-3"
    )
    # Allow overriding base URL (useful for testing / mocks)
    base_url = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")

    client = OpenAI(api_key=api_key, base_url=base_url)

    # Build OpenAI messages: system + history + new user message
    # conversation_history is list of {"role": "...", "content": "..."}
    # Normalize roles: OpenAI supports system/user/assistant/tool
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in conversation_history:
        # Pass through tool messages if present (for multi-turn)
        if m.get("role") in ("user", "assistant", "system", "tool"):
            messages.append(m)
        else:
            # Coerce unknown roles to user
            messages.append({"role": "user", "content": m.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=TOOLS_OPENAI,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=2048,
            )
        except Exception as e:
            print(f"[agent:grok] xAI API call failed (model={model_name} base_url={base_url}): {e}. Falling back to local BI agent.")
            return _local_fallback_agent(user_message, conversation_history)

        choice = response.choices[0]
        message = choice.message

        # If no tool calls, return content directly
        if not message.tool_calls:
            # Handle None content gracefully
            content = message.content or ""
            # Append to history for completeness
            messages.append({"role": "assistant", "content": content})
            return content

        # Tool calls requested -> execute each
        # First, append the assistant message with tool_calls
        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in message.tool_calls
            ]
        })

        for tc in message.tool_calls:
            tool_name = tc.function.name
            raw_args = tc.function.arguments or "{}"
            try:
                tool_input = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                if not isinstance(tool_input, dict):
                    tool_input = {}
            except json.JSONDecodeError:
                print(f"[agent:grok] Failed to parse tool arguments: {raw_args}")
                tool_input = {}

            print(f"[agent:grok] Tool called: {tool_name} with input: {tool_input}")

            if tool_name in TOOL_FUNCTIONS:
                try:
                    tool_result = TOOL_FUNCTIONS[tool_name](**tool_input)
                except Exception as e:
                    tool_result = f"Error executing {tool_name}: {str(e)}"
            else:
                tool_result = f"Unknown tool: {tool_name}"

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result
            })

        # Loop will make next completion with tool results injected
        # If finish_reason is stop after tool handling, loop continues

    return "I reached the maximum reasoning steps. Please try a more specific question."


# ─────────────────────────────────────────────
# Main Agent Dispatcher
# ─────────────────────────────────────────────

def run_agent(user_message: str, conversation_history: list[dict]) -> str:
    """
    Run the tool-calling agent loop with automatic LLM provider routing.

    - If LLM_PROVIDER=grok/xai -> use xAI Grok via OpenAI-compatible API
    - If LLM_PROVIDER=anthropic/claude -> use Anthropic Claude
    - If LLM_PROVIDER=auto (default) -> auto-detect based on available keys
    - If no valid keys -> use intelligent local fallback BI agent

    conversation_history: list of {"role": "user"/"assistant", "content": "..."}
    Returns final text response as string.

    Flow:
    1. Detect provider
    2. Send user message + history to LLM
    3. If LLM returns tool_use / tool_calls → execute tool → feed result back → repeat
    4. When LLM returns final text → return it
    """
    provider = _get_llm_provider()

    if provider == "mock":
        print("[agent] Mock AI mode active (no valid ANTHROPIC_API_KEY / XAI_API_KEY). Using local fallback BI agent.")
        return _local_fallback_agent(user_message, conversation_history)

    if provider == "grok":
        print(f"[agent] Using xAI Grok (model={os.getenv('XAI_MODEL') or os.getenv('GROK_MODEL') or 'grok-3'})")
        return _run_grok_agent(user_message, conversation_history)

    # Default: anthropic
    print(f"[agent] Using Anthropic Claude (model={os.getenv('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022')})")
    return _run_claude_agent(user_message, conversation_history)

