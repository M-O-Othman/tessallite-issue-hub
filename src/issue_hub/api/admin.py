from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from issue_hub.database import get_db
from issue_hub.auth import verify_api_token
from issue_hub.config import settings
from issue_hub.models import Issue, IssueHistory
from issue_hub.schemas import CreateIssueRequest
from issue_hub.issue_service import create_issue

router = APIRouter(prefix="/api/v1/admin", tags=["Administration"])

class ImportRecordSchema(BaseModel):
    issue_id: str
    sequence_number: int
    project: Optional[str] = None
    repository: Optional[str] = None
    branch: str = "main"
    worktree: Optional[str] = None
    task: Optional[str] = None
    status: str = "OPEN"
    severity: Optional[str] = None
    priority: Optional[str] = None
    expected_effort: str = "UNKNOWN"
    title: str = ""
    description: str = ""
    area: Optional[str] = None
    classification: Optional[str] = None
    domain: Optional[str] = None
    category: Optional[str] = None
    refs: Optional[str] = None
    source: Optional[str] = None
    aka: Optional[str] = None
    owner: Optional[str] = None
    tags: List[str] = []
    is_retired: bool = False
    retire_reason: Optional[str] = None
    retire_note: Optional[str] = None
    legacy_raw: Optional[str] = None

class ImportRequestSchema(BaseModel):
    records: List[ImportRecordSchema]

@router.post("/import")
def api_import_issues(
    request: ImportRequestSchema,
    db: Session = Depends(get_db),
    token: str = Depends(verify_api_token)
):
    """Administrative import endpoint (Section 16.7 & Section 23.3)."""
    if not settings.import_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "ok": False,
                "error": {
                    "code": "IMPORT_DISABLED",
                    "message": "Administrative import is disabled by configuration.",
                    "details": {}
                }
            }
        )

    imported_count = 0
    errors = []
    
    # Run the import in a transaction
    try:
        for rec in request.records:
            # Check for conflict
            existing = db.query(Issue).filter(Issue.issue_id == rec.issue_id).first()
            if existing:
                errors.append(f"Conflict: Issue '{rec.issue_id}' already exists.")
                continue
                
            # Create the issue using the import-specific logic
            req = CreateIssueRequest(
                id=rec.issue_id,
                project=rec.project,
                repository=rec.repository,
                branch=rec.branch,
                worktree=rec.worktree,
                task=rec.task,
                status=rec.status,
                severity=rec.severity,
                priority=rec.priority,
                expected_effort=rec.expected_effort,
                title=rec.title,
                description=rec.description,
                area=rec.area,
                classification=rec.classification,
                domain=rec.domain,
                category=rec.category,
                refs=rec.refs,
                source=rec.source,
                aka=rec.aka,
                owner=rec.owner,
                tags=rec.tags,
                reserve=(rec.status == "RESERVED"),
            )
            
            # Call create_issue in import mode to allow custom sequence, exact ID, etc.
            issue = create_issue(db, req, import_mode=True)
            
            # Post-adjust retired state if record was imported as retired
            if rec.is_retired:
                issue.is_retired = True
                issue.retire_reason = rec.retire_reason
                issue.retire_note = rec.retire_note
                db.add(issue)
                
            if rec.legacy_raw:
                issue.legacy_raw = rec.legacy_raw
                db.add(issue)
                
            # Add an import history record
            hist = IssueHistory(
                issue_id=issue.issue_id,
                operation="IMPORT",
                before_record=None,
                after_record=issue.to_dict(),
                note="Administrative import"
            )
            db.add(hist)
            imported_count += 1
            
        if errors:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "ok": False,
                    "error": {
                        "code": "IMPORT_CONFLICT",
                        "message": "Import blocked by conflict errors.",
                        "details": {"errors": errors}
                    }
                }
            )
            
        db.commit()
        return {"ok": True, "imported": imported_count}
        
    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "ok": False,
                "error": {
                    "code": "IMPORT_INVALID_RECORD",
                    "message": str(e),
                    "details": {}
                }
            }
        )

@router.get("/export")
def api_export_issues(
    format: str = Query("json", description="Export format: 'json' or 'legacy-markdown'"),
    db: Session = Depends(get_db),
    token: str = Depends(verify_api_token)
):
    """Administrative export endpoint (Section 16.7 & Section 24.3)."""
    issues = db.query(Issue).order_by(Issue.sequence_number.asc()).all()
    
    if format == "json":
        return {
            "ok": True,
            "records": [i.to_dict() for i in issues]
        }
    elif format == "legacy-markdown":
        # Section 24.3 Legacy Markdown export format:
        # - **Bug-9627** — `[OPEN]` — AKA <aliases> — `[HIGH -- title]` description. Area: ... Refs: ... Domain: gateway. Category: product.
        lines = []
        for i in issues:
            aka_str = f" — AKA {i.aka}" if i.aka else ""
            area_str = f" Area: {i.area}." if i.area else ""
            refs_str = f" Refs: {i.refs}." if i.refs else ""
            domain_str = f" Domain: {i.domain}." if i.domain else ""
            cat_str = f" Category: {i.category}." if i.category else ""
            
            line = f"- **{i.issue_id}** — `[{i.status}]`{aka_str} — `[{i.severity or 'UNSPECIFIED'} -- {i.title}]` {i.description.splitlines()[0] if i.description else ''}.{area_str}{refs_str}{domain_str}{cat_str}"
            lines.append(line)
            
        return {
            "ok": True,
            "format": "legacy-markdown",
            "content": "\n".join(lines)
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "ok": False,
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": f"Unsupported export format '{format}'",
                    "details": {}
                }
            }
        )
