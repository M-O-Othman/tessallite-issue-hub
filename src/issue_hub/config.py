import os
from pydantic import BaseModel, Field

class Settings(BaseModel):
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", 
            "postgresql+psycopg://issue_hub:secret_password@localhost:5432/issue_hub"
        )
    )
    api_token: str = Field(default_factory=lambda: os.getenv("ISSUE_HUB_API_TOKEN", "api_bearer_token_123"))
    web_username: str = Field(default_factory=lambda: os.getenv("ISSUE_HUB_WEB_USERNAME", "admin"))
    # Default bcrypt hash for 'admin'
    web_password_hash: str = Field(
        default_factory=lambda: os.getenv(
            "ISSUE_HUB_WEB_PASSWORD_HASH", 
            "$2b$12$aFi5o69Jva.w9qOPi952mOsdCA3kSt7QprLhhicsNJTBrQSdEaa8O"
        )
    )
    session_secret: str = Field(default_factory=lambda: os.getenv("ISSUE_HUB_SESSION_SECRET", "super_secret_session_key_9999"))
    default_project: str = Field(default_factory=lambda: os.getenv("ISSUE_HUB_DEFAULT_PROJECT", "tessallite"))
    default_repository: str = Field(default_factory=lambda: os.getenv("ISSUE_HUB_DEFAULT_REPOSITORY", "tessallite-workspace"))
    default_branch: str = Field(default_factory=lambda: os.getenv("ISSUE_HUB_DEFAULT_BRANCH", "main"))
    import_enabled: bool = Field(default_factory=lambda: os.getenv("ISSUE_HUB_IMPORT_ENABLED", "true").lower() in ("true", "1", "yes"))
    title_max_length: int = 500

settings = Settings()
