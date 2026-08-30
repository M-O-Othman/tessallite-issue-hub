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

def test_unreachable_database_error_handling():
    from issue_hub import database
    from sqlalchemy import create_engine
    
    # Save old engine
    old_engine = database.engine
    # Reinitialize engine with unreachable URL to force connection failure
    database.engine = create_engine("postgresql+psycopg://postgres:wrong_pw@127.0.0.1:54321/unreachable_db")
    
    try:
        response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["ok"] is False
        assert data["error"]["code"] == "DATABASE_UNAVAILABLE"
    finally:
        # Restore old engine
        database.engine = old_engine
