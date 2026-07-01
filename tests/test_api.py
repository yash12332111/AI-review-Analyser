import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_dashboard_summary():
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_feedback" in data
    assert "by_source" in data
    assert "by_sentiment" in data

def test_dashboard_topics():
    response = client.get("/api/dashboard/topics")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "value" in data[0]
        assert "count" in data[0]
        assert "percentage" in data[0]

def test_dashboard_complaints():
    response = client.get("/api/dashboard/complaints")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "value" in data[0]
        assert "count" in data[0]
        assert "delta_pct" in data[0]

def test_dashboard_behaviours():
    response = client.get("/api/dashboard/behaviours")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_dashboard_workarounds():
    response = client.get("/api/dashboard/workarounds")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "content" in data[0]
        assert "source" in data[0]

def test_dashboard_trends():
    response = client.get("/api/dashboard/trends")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "day" in data[0]
        assert "topic" in data[0]
        assert "count" in data[0]

def test_dashboard_quotes():
    response = client.get("/api/dashboard/quotes?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "has_more" in data
    assert isinstance(data["data"], list)

def test_dashboard_themes():
    response = client.get("/api/dashboard/themes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "cluster_type" in data[0]
        assert "label" in data[0]
        assert "member_count" in data[0]

def test_dashboard_themes_by_type():
    response = client.get("/api/dashboard/themes/core_complaint")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_dashboard_filters():
    response = client.get("/api/dashboard/summary?source=appstore&country=US&sentiment=negative")
    assert response.status_code == 200
    data = response.json()
    assert "total_feedback" in data

def test_chat_suggest():
    response = client.get("/api/chat/suggest")
    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)
    assert len(data["suggestions"]) > 0

def test_chat_returns_answer():
    # Simple check that endpoint accepts requests (uses live DB so results depend on DB)
    response = client.post("/api/chat", json={
        "message": "Why do users complain about Discover Weekly?",
        "filters": {}
    })
    # If the groq api key is not set or rate limited, it returns 200 but with an error message in answer
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "metadata" in data

