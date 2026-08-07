# backend/api.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from backend.data_store import refresh_data, get_quality_summary
from backend.agent import run_agent


# ── Startup: load data when server starts ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[startup] Loading data from monday.com...")
    refresh_data()
    yield
    print("[shutdown] Cleaning up...")


app = FastAPI(
    title="Skylark BI Agent API",
    description="Business Intelligence conversational agent for Skylark Drones",
    version="1.0.0",
    lifespan=lifespan
)

# Allow Streamlit frontend and any browser preview host to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ── Request/Response models ──
class ChatRequest(BaseModel):
    message: str
    conversation_history: list[dict] = []


class ChatResponse(BaseModel):
    response: str
    conversation_history: list[dict]


# ── Endpoints ──

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Skylark BI Agent is running"}


@app.get("/data-quality")
def data_quality():
    """Return data quality report for both boards."""
    try:
        return get_quality_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data quality: {str(e)}")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Main conversational endpoint.
    Receives user message + conversation history,
    returns agent response + updated history.
    """
    try:
        response_text = run_agent(
            user_message=request.message,
            conversation_history=request.conversation_history
        )

        # Update conversation history
        updated_history = request.conversation_history + [
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": response_text}
        ]

        return ChatResponse(
            response=response_text,
            conversation_history=updated_history
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.post("/refresh")
def refresh():
    """Manually refresh data from monday.com."""
    try:
        refresh_data()
        quality = get_quality_summary()
        return {
            "status": "refreshed",
            "deals_quality_score": quality["deals"]["data_quality_score"],
            "work_orders_quality_score": quality["work_orders"]["data_quality_score"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {str(e)}")
