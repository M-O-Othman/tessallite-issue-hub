import subprocess
import json
import os
import pytest
from issue_hub.config import settings

# Setup environment variables for CLI execution
env = os.environ.copy()
env["ISSUE_HUB_URL"] = "http://localhost:8080"
env["ISSUE_HUB_TOKEN"] = settings.api_token

@pytest.fixture(autouse=True, scope="module")
def setup_cli_test_database():
    from issue_hub.database import SessionLocal
    from sqlalchemy import text
    db = SessionLocal()
    try:
        db.execute(text("TRUNCATE TABLE issues, issue_history CASCADE"))
        db.execute(text("ALTER SEQUENCE issue_number_seq RESTART WITH 10"))
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def test_cli_create_reserve():
    """Verify issue create --reserve allocates a sequence number and returns JSON."""
    result = subprocess.run(
        ["issue", "create", "--reserve"],
        capture_output=True,
        text=True,
        env=env
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert "issue_id" in data["issue"]
    assert data["issue"]["issue_id"] == "Bug-10"
    assert data["issue"]["status"] == "RESERVED"

def test_cli_create_complete():
    """Verify creating a complete issue from CLI works."""
    result = subprocess.run([
        "issue", "create",
        "--severity", "HIGH",
        "--title", "CLI Created Issue",
        "--description", "This was created via CLI.",
        "--domain", "shared",
        "--category", "ci"
    ], capture_output=True, text=True, env=env)
    
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["issue"]["issue_id"] == "Bug-11"
    assert data["issue"]["status"] == "OPEN"
    assert data["issue"]["severity"] == "HIGH"
    assert data["issue"]["domain"] == "shared"

def test_cli_find_by_id():
    """Verify finding an issue by ID works."""
    result = subprocess.run(
        ["issue", "find", "Bug-11"],
        capture_output=True,
        text=True,
        env=env
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert len(data["items"]) == 1
    assert data["items"][0]["issue_id"] == "Bug-11"

def test_cli_find_text_query():
    """Verify searching by text query works."""
    result = subprocess.run(
        ["issue", "find", "CLI Created"],
        capture_output=True,
        text=True,
        env=env
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert len(data["items"]) >= 1
    assert data["items"][0]["issue_id"] == "Bug-11"

def test_cli_update_fields():
    """Verify updating issue fields works."""
    result = subprocess.run([
        "issue", "update", "Bug-11",
        "--set", "status=FIXED-PENDING-VERIFICATION",
        "--set", "expected_effort=S"
    ], capture_output=True, text=True, env=env)
    
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["issue"]["status"] == "FIXED-PENDING-VERIFICATION"
    assert data["issue"]["expected_effort"] == "S"

def test_cli_retire():
    """Verify retiring an issue works."""
    result = subprocess.run([
        "issue", "update", "Bug-11",
        "--retire", "DUPLICATE",
        "--duplicate-of", "Bug-10",
        "--retire-note", "Duplicate of Bug-10"
    ], capture_output=True, text=True, env=env)
    
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["issue"]["is_retired"] is True
    assert data["issue"]["retire_reason"] == "DUPLICATE"
    assert data["issue"]["duplicate_of"] == "Bug-10"

def test_cli_issue_not_found():
    """Verify that exit code 4 is returned when issue is not found."""
    result = subprocess.run(
        ["issue", "find", "Bug-999"],
        capture_output=True,
        text=True,
        env=env
    )
    assert result.returncode == 0 # Wait, find of query of non-existent ID just returns empty list!
    # Let's test update of non-existent ID
    result_update = subprocess.run(
        ["issue", "update", "Bug-999", "--set", "status=OPEN"],
        capture_output=True,
        text=True,
        env=env
    )
    assert result_update.returncode == 4
    data = json.loads(result_update.stdout)
    assert data["ok"] is False
    assert data["error"]["code"] == "ISSUE_NOT_FOUND"

def test_cli_auth_error():
    """Verify exit code 3 is returned on auth failure."""
    bad_env = env.copy()
    bad_env["ISSUE_HUB_TOKEN"] = "bad_token"
    result = subprocess.run(
        ["issue", "create", "--reserve"],
        capture_output=True,
        text=True,
        env=bad_env
    )
    assert result.returncode == 3
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["error"]["code"] == "AUTHENTICATION_FAILED"

def test_cli_update_description_and_tags():
    """Verify updating description and managing tags via --add-tag and --remove-tag."""
    # 1. Update description and add tags
    result = subprocess.run([
        "issue", "update", "Bug-11",
        "--description", "Updated description text via CLI.",
        "--add-tag", "tag1",
        "--add-tag", "tag2"
    ], capture_output=True, text=True, env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["issue"]["description"] == "Updated description text via CLI."
    assert "tag1" in data["issue"]["tags"]
    assert "tag2" in data["issue"]["tags"]

    # 2. Remove a tag
    result_remove = subprocess.run([
        "issue", "update", "Bug-11",
        "--remove-tag", "tag1"
    ], capture_output=True, text=True, env=env)
    assert result_remove.returncode == 0
    data_remove = json.loads(result_remove.stdout)
    assert data_remove["ok"] is True
    assert "tag1" not in data_remove["issue"]["tags"]
    assert "tag2" in data_remove["issue"]["tags"]

