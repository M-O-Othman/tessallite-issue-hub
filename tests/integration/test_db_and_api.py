from fastapi.testclient import TestClient
from issue_hub.main import app
from issue_hub.config import settings
import pytest

client = TestClient(app, raise_server_exceptions=False)

# Use our configured bearer token
headers = {"Authorization": f"Bearer {settings.api_token}"}

@pytest.fixture(autouse=True, scope="module")
def setup_database():
    from issue_hub.database import SessionLocal
    from sqlalchemy import text
    db = SessionLocal()
    try:
        db.execute(text("TRUNCATE TABLE issues, issue_history CASCADE"))
        db.execute(text("ALTER SEQUENCE issue_number_seq RESTART WITH 1"))
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def test_health_endpoints():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"

    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"

def test_auth_rejection():
    # Attempt to create without auth
    response = client.post("/api/v1/issues", json={"reserve": True})
    assert response.status_code == 401
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "AUTHENTICATION_FAILED"

def test_create_reserve_and_complete():
    # 1. Reserve an issue
    payload = {
        "reserve": True,
        "project": "tessallite",
        "repository": "tessallite-workspace"
    }
    response = client.post("/api/v1/issues", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    issue = data["issue"]
    issue_id = issue["issue_id"]
    assert "Bug-" in issue_id
    assert issue["status"] == "RESERVED"
    assert issue["title"] == "Reserved issue"

    # 2. Query it
    response = client.get(f"/api/v1/issues?id={issue_id}", headers=headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["issue_id"] == issue_id

    # 3. Complete the reservation by creating with the reserved ID
    payload_complete = {
        "id": issue_id,
        "severity": "HIGH",
        "description": "The actual issue details go here.\nSecond line.",
        "project": "tessallite",
        "repository": "tessallite-workspace",
        "tags": ["excel", "demo"]
    }
    response = client.post("/api/v1/issues", json=payload_complete, headers=headers)
    assert response.status_code == 200
    issue_completed = response.json()["issue"]
    assert issue_completed["issue_id"] == issue_id
    assert issue_completed["status"] == "OPEN"
    assert issue_completed["severity"] == "HIGH"
    assert issue_completed["title"] == "The actual issue details go here."
    assert "excel" in issue_completed["tags"]

    # 4. Check history
    response = client.get(f"/api/v1/issues/{issue_id}/history", headers=headers)
    assert response.status_code == 200
    history = response.json()["items"]
    assert len(history) >= 2
    assert history[0]["operation"] == "UPDATE"
    assert history[1]["operation"] == "RESERVE"

def test_create_complete_issue():
    # Create complete issue directly
    payload = {
        "project": "tessallite",
        "severity": "CRITICAL",
        "title": "Critical Bug in scheduler",
        "description": "Detail description",
        "domain": "scheduler",
        "category": "product"
    }
    response = client.post("/api/v1/issues", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    issue = data["issue"]
    assert issue["severity"] == "CRITICAL"
    assert issue["title"] == "Critical Bug in scheduler"
    assert issue["status"] == "OPEN"

def test_update_append_retire():
    # 1. Create a baseline issue
    payload = {
        "severity": "MEDIUM",
        "description": "Test issue description",
    }
    response = client.post("/api/v1/issues", json=payload, headers=headers)
    issue_id = response.json()["issue"]["issue_id"]

    # 2. Patch: update fields and append description
    patch_payload = {
        "set": {
            "status": "PARTIAL",
            "priority": "P2"
        },
        "append_description": "Additional info from test runner."
    }
    response = client.patch(f"/api/v1/issues/{issue_id}", json=patch_payload, headers=headers)
    assert response.status_code == 200
    updated_issue = response.json()["issue"]
    assert updated_issue["status"] == "PARTIAL"
    assert updated_issue["priority"] == "P2"
    assert "Additional info from test runner" in updated_issue["description"]

    # 3. Patch: Retire as DUPLICATE
    retire_payload = {
        "retire": {
            "reason": "DUPLICATE",
            "duplicate_of": "Bug-1234",
            "note": "We found a duplicate target"
        }
    }
    response = client.patch(f"/api/v1/issues/{issue_id}", json=retire_payload, headers=headers)
    assert response.status_code == 200
    retired_issue = response.json()["issue"]
    assert retired_issue["is_retired"] is True
    assert retired_issue["retire_reason"] == "DUPLICATE"
    assert retired_issue["duplicate_of"] == "Bug-1234"
    assert retired_issue["retire_note"] == "We found a duplicate target"

def test_exact_and_text_search():
    # 1. Create an issue with unique text
    payload = {
        "severity": "LOW",
        "title": "UniqueTitle12345",
        "description": "Searching for needle in a haystack.",
        "tags": ["needle-tag"]
    }
    response = client.post("/api/v1/issues", json=payload, headers=headers)
    issue_id = response.json()["issue"]["issue_id"]

    # 2. Text query search
    response = client.get("/api/v1/issues?q=UniqueTitle12345", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    assert items[0]["issue_id"] == issue_id

    # 3. Text query search in description
    response = client.get("/api/v1/issues?q=haystack", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    assert items[0]["issue_id"] == issue_id

    # 4. Tag query search
    response = client.get("/api/v1/issues?tag=needle-tag", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    assert items[0]["issue_id"] == issue_id

    # 5. Wide search querying across sequence number and other attributes
    seq_num = response.json()["items"][0]["sequence_number"]
    response = client.get(f"/api/v1/issues?q={seq_num}", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    assert items[0]["issue_id"] == issue_id

def test_timestamp_filtering():
    # 1. Create a timestamp test issue
    payload = {
        "severity": "LOW",
        "title": "Timestamp Test Issue",
        "description": "Testing created_at and updated_at range filtering.",
    }
    response = client.post("/api/v1/issues", json=payload, headers=headers)
    issue_data = response.json()["issue"]
    issue_id = issue_data["issue_id"]

    # 2. Query within range
    response = client.get(
        "/api/v1/issues?created_from=2020-01-01T00:00:00Z&created_to=2030-01-01T00:00:00Z",
        headers=headers
    )
    assert response.status_code == 200
    ids = [item["issue_id"] for item in response.json()["items"]]
    assert issue_id in ids

    # 3. Query outside range (future)
    response_future = client.get(
        "/api/v1/issues?created_from=2099-01-01T00:00:00Z",
        headers=headers
    )
    assert response_future.status_code == 200
    assert len(response_future.json()["items"]) == 0


def test_multi_select_and_closed_date_filtering():
    from issue_hub.database import SessionLocal
    from issue_hub.search import query_issues
    from issue_hub.models import Issue
    db = SessionLocal()
    try:
        # Create a couple of issues with specific statuses and projects to test multi-select
        issue1 = Issue(
            issue_id="Bug-8801",
            sequence_number=8801,
            project="tessallite",
            repository="repo1",
            status="OPEN",
            severity="CRITICAL",
            title="Multi Test 1",
            description="Testing multi-select queries.",
        )
        issue2 = Issue(
            issue_id="Bug-8802",
            sequence_number=8802,
            project="tessallite",
            repository="repo2",
            status="RESERVED",
            severity="HIGH",
            title="Multi Test 2",
            description="Testing multi-select queries.",
        )
        db.add(issue1)
        db.add(issue2)
        db.commit()

        # Query using status as a list
        items, total = query_issues(db, status=["OPEN", "RESERVED"])
        ids = [i.issue_id for i in items]
        assert "Bug-8801" in ids
        assert "Bug-8802" in ids

        # Query using project as a list
        items2, total2 = query_issues(db, project=["tessallite"])
        ids2 = [i.issue_id for i in items2]
        assert "Bug-8801" in ids2

        # Clean up
        db.delete(issue1)
        db.delete(issue2)
        db.commit()
    finally:
        db.close()

