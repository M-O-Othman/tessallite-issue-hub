import os

# 1. Safe Test Database Guard (Gate 5 / Section 12)
db_url = os.getenv("DATABASE_URL", "")
if "tessallite_system" in db_url or "34.82.232.232" in db_url or "sql.tessallite.io" in db_url:
    raise ValueError(
        f"CRITICAL SAFETY WARNING: pytest attempted to run against a production-like database: '{db_url}'. "
        f"Execution aborted to prevent accidental data loss or truncation."
    )

# 2. Force development environment profile for all test suites (Gate 2)
os.environ["ISSUE_HUB_ENV"] = "development"
os.environ["DATABASE_URL"] = os.getenv(
    "DATABASE_URL", 
    "postgresql+psycopg://issue_hub:secret_password@localhost:5432/issue_hub"
)
