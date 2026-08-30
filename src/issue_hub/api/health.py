from fastapi import APIRouter, HTTPException, status
from issue_hub.database import check_db_connection

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/live")
def health_live():
    """Liveness probe."""
    return {"status": "alive", "ok": True}

@router.get("/ready")
def health_ready():
    """Readiness probe. Checks database connectivity."""
    db_ok = check_db_connection()
    if not db_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "ok": False,
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Database is unavailable or schema is not loaded",
                    "details": {}
                }
            }
        )
    return {"status": "ready", "ok": True, "database": "connected"}
