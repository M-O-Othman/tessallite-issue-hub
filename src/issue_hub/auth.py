from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from issue_hub.config import settings
from issue_hub.issue_service import IssueHubException
import logging

logger = logging.getLogger("issue_hub.auth")

security = HTTPBearer(auto_error=False)

def verify_api_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    """Validate Bearer token against settings.api_token."""
    # If no api_token is configured on server (e.g. empty or None), we bypass auth for safety or local dev
    if not settings.api_token:
        logger.warning("Bypassing API token verification because no ISSUE_HUB_API_TOKEN is set")
        return "bypass"

    if not credentials or credentials.credentials != settings.api_token:
        # Raise IssueHubException so global handler formats it correctly
        raise IssueHubException(
            code="AUTHENTICATION_FAILED",
            message="Invalid or missing Bearer token"
        )
    return credentials.credentials
