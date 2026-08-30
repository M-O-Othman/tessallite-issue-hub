from fastapi.testclient import TestClient
from issue_hub.main import app

client = TestClient(app, raise_server_exceptions=False)

def test_web_redirects_to_login_when_unauthenticated():
    """Verify that root page and other secure pages redirect to /login if unauthenticated."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    response = client.get("/issues/create", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    response = client.get("/settings", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

def test_login_validation():
    """Verify that incorrect credentials show login page with an error."""
    response = client.post("/login", data={"username": "admin", "password": "wrong_password"})
    assert response.status_code == 200
    assert "Invalid username or password" in response.text

    response = client.post("/login", data={"username": "wrong_user", "password": "admin"})
    assert response.status_code == 200
    assert "Invalid username or password" in response.text

def test_successful_login_and_secure_pages():
    """Verify that correct credentials login successfully and grant access to pages."""
    # Use TestClient with session
    # Password 'admin' matches the default bcrypt hash
    # Follow redirect to root '/'
    response = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    assert response.status_code == 200
    assert "Issue Ledger" in response.text  # present on list.html

    # Check session-restricted pages now work with the session cookies preserved by client
    response_create = client.get("/issues/create")
    assert response_create.status_code == 200
    assert "Create or Reserve Issue" in response_create.text

    response_settings = client.get("/settings")
    assert response_settings.status_code == 200
    assert "Lookup Vocabularies" in response_settings.text

    # Verify chained help pages
    for path, title_part in [
        ("/help", "Documentation & Help Center"),
        ("/help/apis", "1. REST API Specification"),
        ("/help/cli", "2. Non-Interactive CLI"),
        ("/help/frontend", "3. Interactive Web UI Portal"),
        ("/help/migration", "4. Legacy Migration Tooling"),
        ("/help/deployment", "5. Single Container Deployment")
    ]:
        res = client.get(path)
        assert res.status_code == 200
        assert title_part in res.text

    # Logout
    response_logout = client.get("/logout", follow_redirects=False)
    assert response_logout.status_code == 303
    assert response_logout.headers["location"] == "/login"
