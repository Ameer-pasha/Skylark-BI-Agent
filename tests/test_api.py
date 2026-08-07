# tests/test_api.py

from fastapi.testclient import TestClient
from backend.api import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_data_quality():
    response = client.get("/data-quality")
    assert response.status_code == 200
    data = response.json()
    assert "deals" in data
    assert "work_orders" in data
    assert "data_quality_score" in data["deals"]


def test_chat_endpoint():
    payload = {
        "message": "What is our total pipeline value?",
        "conversation_history": []
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "conversation_history" in data
    assert "Total Pipeline Value" in data["response"]


def test_refresh_endpoint():
    response = client.post("/refresh")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "refreshed"
    assert "deals_quality_score" in data
    assert "work_orders_quality_score" in data
