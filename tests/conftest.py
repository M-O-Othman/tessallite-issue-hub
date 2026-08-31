import os
from sqlalchemy.engine.url import make_url

# 1. Force development and testing environment profiles (Gate 5 / Section 12)
os.environ["ISSUE_HUB_ENV"] = "development"
os.environ["ISSUE_HUB_TESTING"] = "1"

# Load DATABASE_URL, forcing a dedicated separate test database name!
# This prevents any possibility of ever pointing to or truncating the live 'issue_hub' database!
db_url = os.getenv(
    "DATABASE_URL", 
    "postgresql+psycopg://issue_hub:secret_password@localhost:5432/issue_hub_test"
)

# If the database URL is set but points to the live dev DB "issue_hub", force it to "issue_hub_test"!
parsed = make_url(db_url)
if parsed.database == "issue_hub":
    db_url = "postgresql+psycopg://issue_hub:secret_password@localhost:5432/issue_hub_test"
    parsed = make_url(db_url)
    
os.environ["DATABASE_URL"] = db_url

# 2. Positive Whitelist Safety Gate (Gate 5 / Section 12)
try:
    db_name = parsed.database or ""
    # Whitelist database names to ensure they MUST explicitly contain "test"!
    # The live development DB "issue_hub" is STRICTLY forbidden and rejected!
    if "test" not in db_name.lower():
        raise ValueError(
            f"CRITICAL SAFETY ABORT: pytest is whitelisted ONLY for database names containing 'test'. "
            f"The normal 'issue_hub' database is strictly forbidden in tests to prevent data loss. "
            f"Attempted database: '{db_name}'."
        )
except Exception as e:
    raise ValueError(f"CRITICAL SAFETY ABORT: Failed database safety validation: {e}")
