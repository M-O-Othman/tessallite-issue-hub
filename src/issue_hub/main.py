from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
import logging

from issue_hub.database import SessionLocal
from issue_hub.models import LookupValue, HubSetting
from issue_hub.issue_service import IssueHubException
from issue_hub.config import settings
from issue_hub.api import health, issues, config, admin
from issue_hub.web import routes as web_routes

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler to perform idempotent startup seeding."""
    db = SessionLocal()
    try:
        seed_lookups(db)
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
    finally:
        db.close()
    yield

app = FastAPI(
    title="Tessallite Issue Hub",
    description="Authoritative issue ledger and numeric identifier sequence allocator.",
    version="1.0.0",
    lifespan=lifespan,
)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("issue_hub")

# Global exception handler for custom IssueHubException (Section 16.8)
@app.exception_handler(IssueHubException)
def issue_hub_exception_handler(request, exc: IssueHubException):
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code == "ISSUE_NOT_FOUND":
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code == "AUTHENTICATION_FAILED" or exc.code == "AUTHENTICATION_REQUIRED":
        status_code = status.HTTP_401_UNAUTHORIZED
    elif exc.code == "IMPORT_CONFLICT":
        status_code = status.HTTP_409_CONFLICT
        
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )

# Add session middleware for administrative web UI access (Section 20.1)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="issue_hub_session"
)

# Include API, health, and Web UI routers
app.include_router(health.router)
app.include_router(issues.router)
app.include_router(config.router)
app.include_router(admin.router)
app.include_router(web_routes.router)

def seed_lookups(db: Session):
    """Seed lookup and settings tables with specifications defined in Section 13 (Idempotent check)."""
    logger.info("Checking database lookup vocabularies and settings...")
    
    # Statuses
    if not db.query(LookupValue).filter(LookupValue.lookup_type == "STATUS").first():
        logger.info("Pre-seeding STATUS values...")
        statuses = [
            ("OPEN", "Open", False),
            ("FIXED-PENDING-VERIFICATION", "Fixed - Pending Verification", False),
            ("DEFERRED", "Deferred", False),
            ("DESCOPED", "Descoped", True),
            ("PARTIAL", "Partial", False),
            ("MITIGATED", "Mitigated", False),
            ("SHELVED", "Shelved", False),
            ("FLAGGED", "Flagged", False),
            ("RESERVED", "Reserved", False),
            ("PARKED", "Parked", False),
            ("BY-DESIGN", "By Design", True),
            ("INFO", "Info", False),
            ("NOTED", "Noted", False),
            ("ACCEPTED", "Accepted", False),
            ("ACCEPTED-RISK", "Accepted Risk", True),
            ("ACCEPTED-FOR-DEMO", "Accepted for Demo", False),
            ("CLIENT-OPS", "Client Ops", False),
            ("FIXED", "Fixed", True),
            ("CLOSED", "Closed", True),
            ("DONE", "Done", True),
            ("RESOLVED", "Resolved", True),
            ("VERIFIED", "Verified", True),
            ("SUPERSEDED", "Superseded", True),
            ("REMOVED", "Removed", True),
            ("OBSOLETE", "Obsolete", True),
            ("DUPLICATE", "Duplicate", True),
            ("POSSIBLY DUPLICATE", "Possibly Duplicate", False),
            ("REOPENED", "Reopened", False),
            ("WONTFIX", "Wontfix", True),
            ("MOVED-TO-ENHANCEMENT-PLAN", "Moved to Enhancement Plan", True),
            ("FIXED_IN_REPLAY", "Fixed in Replay", True),
            ("FIXED_IN_INTEGRATION", "Fixed in Integration", True),
        ]
        for idx, (val, label, term) in enumerate(statuses):
            db.add(LookupValue(lookup_type="STATUS", value=val, label=label, is_terminal=term, display_order=idx))

    # Severities
    if not db.query(LookupValue).filter(LookupValue.lookup_type == "SEVERITY").first():
        logger.info("Pre-seeding SEVERITY values...")
        severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "ENHANCEMENT", "PERF", "QUESTION", "UNSPECIFIED"]
        for idx, val in enumerate(severities):
            db.add(LookupValue(lookup_type="SEVERITY", value=val, label=val.capitalize(), display_order=idx))

    # Priorities
    if not db.query(LookupValue).filter(LookupValue.lookup_type == "PRIORITY").first():
        logger.info("Pre-seeding PRIORITY values...")
        priorities = ["P0", "P1", "P2", "P3", "P4", "UNSCHEDULED"]
        for idx, val in enumerate(priorities):
            db.add(LookupValue(lookup_type="PRIORITY", value=val, label=val, display_order=idx))

    # Effort
    if not db.query(LookupValue).filter(LookupValue.lookup_type == "EFFORT").first():
        logger.info("Pre-seeding EFFORT values...")
        efforts = ["XS", "S", "M", "L", "XL", "XXL", "UNKNOWN"]
        for idx, val in enumerate(efforts):
            db.add(LookupValue(lookup_type="EFFORT", value=val, label=val, display_order=idx))

    # Domains
    if not db.query(LookupValue).filter(LookupValue.lookup_type == "DOMAIN").first():
        logger.info("Pre-seeding DOMAIN values...")
        domains = [
            "gateway", "query-router", "model-service", "optimizer", "scheduler", 
            "agent-service", "front-end", "shared", "seed", "deploy", 
            "release-tooling", "ci", "uat", "website", "community-edition", 
            "documentation", "cross-cutting"
        ]
        for idx, val in enumerate(domains):
            db.add(LookupValue(lookup_type="DOMAIN", value=val, label=val.replace("-", " ").capitalize(), display_order=idx))

    # Categories
    if not db.query(LookupValue).filter(LookupValue.lookup_type == "CATEGORY").first():
        logger.info("Pre-seeding CATEGORY values...")
        categories = ["product", "ci", "security", "documentation", "tessallite-website", "community-edition"]
        for idx, val in enumerate(categories):
            db.add(LookupValue(lookup_type="CATEGORY", value=val, label=val.replace("-", " ").capitalize(), display_order=idx))

    # Retirement Reasons
    if not db.query(LookupValue).filter(LookupValue.lookup_type == "RETIRE_REASON").first():
        logger.info("Pre-seeding RETIRE_REASON values...")
        reasons = ["DUPLICATE", "NOT_AN_ISSUE", "CREATED_IN_ERROR", "SUPERSEDED", "OTHER"]
        for idx, val in enumerate(reasons):
            db.add(LookupValue(lookup_type="RETIRE_REASON", value=val, label=val.replace("_", " ").capitalize(), display_order=idx))

    # Projects
    if not db.query(LookupValue).filter(LookupValue.lookup_type == "PROJECT").first():
        logger.info("Pre-seeding PROJECT values...")
        db.add(LookupValue(lookup_type="PROJECT", value="tessallite", label="Tessallite", display_order=0))

    # Repositories
    if not db.query(LookupValue).filter(LookupValue.lookup_type == "REPOSITORY").first():
        logger.info("Pre-seeding REPOSITORY values...")
        db.add(LookupValue(lookup_type="REPOSITORY", value="tessallite-workspace", label="Tessallite Workspace", display_order=0))

    # Preseed settings if empty
    if not db.query(HubSetting).filter(HubSetting.setting_key == "issue_key_template").first():
        logger.info("Pre-seeding default settings...")
        db.add(HubSetting(setting_key="issue_key_template", setting_value={"template": "Bug-{number}"}))
        db.add(HubSetting(setting_key="default_project", setting_value={"value": "tessallite"}))
        db.add(HubSetting(setting_key="default_repository", setting_value={"value": "tessallite-workspace"}))
        db.add(HubSetting(setting_key="default_branch", setting_value={"value": "main"}))
        db.add(HubSetting(setting_key="search_default_limit", setting_value={"value": 100}))
        db.add(HubSetting(setting_key="title_max_length", setting_value={"value": 500}))
        db.add(HubSetting(setting_key="web_title", setting_value={"value": "Tessallite Issue Hub"}))

    db.commit()
@app.get("/api/v1", tags=["API"])
def api_root():
    return {"message": "Welcome to Tessallite Issue Hub API v1", "ok": True}
