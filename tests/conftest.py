import os
from sqlalchemy.engine.url import make_url

# 1. Force development and testing environment profiles (Gate 5 / Section 12)
os.environ["ISSUE_HUB_ENV"] = "development"
os.environ["ISSUE_HUB_TESTING"] = "1"

# Load DATABASE_URL
db_url = os.getenv(
    "DATABASE_URL", 
    "postgresql+psycopg://issue_hub:secret_password@localhost:5432/issue_hub"
)
os.environ["DATABASE_URL"] = db_url

# 2. Positive Whitelist Safety Gate (Gate 5 / Section 12)
try:
    parsed = make_url(db_url)
    db_name = parsed.database or ""
    # Whitelist database names to ensure they must explicitly contain "test" or equal local dev "issue_hub"
    if "test" not in db_name.lower() and db_name != "issue_hub":
        raise ValueError(
            f"CRITICAL SAFETY ABORT: pytest is whitelisted ONLY for database names containing 'test' "
            f"or equaling local development 'issue_hub'. Attempted database: '{db_name}'."
        )
except Exception as e:
    raise ValueError(f"CRITICAL SAFETY ABORT: Failed database safety validation: {e}")
