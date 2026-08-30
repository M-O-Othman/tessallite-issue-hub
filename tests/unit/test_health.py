from fastapi.testclient import TestClient
from issue_hub.main import app

client = TestClient(app)

def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive", "ok": True}

def test_health_ready_skeleton():
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["ok"] is True
    assert "database" in data

def test_api_root():
    response = client.get("/api/v1")
    assert response.status_code == 200
    assert response.json()["ok"] is True
