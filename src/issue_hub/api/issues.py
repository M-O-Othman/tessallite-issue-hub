from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from collections import defaultdict

from issue_hub.database import get_db
from issue_hub.auth import verify_api_token
from issue_hub.schemas import (
    CreateIssueRequest,
    UpdateIssueRequest,
    IssueResponse,
    IssuesListResponse,
    HistoryResponse,
)
from issue_hub.issue_service import create_issue, update_issue, IssueNotFound, IssueHubException
from issue_hub.search import query_issues, resolve_limit
from issue_hub.filters import IssueFilterParams, issue_filters
from issue_hub.models import Issue, IssueHistory

router = APIRouter(prefix="/api/v1/issues", tags=["Issues"])

@router.post("", response_model=IssueResponse)
def api_create_issue(
    request: CreateIssueRequest,
    db: Session = Depends(get_db),
    token: str = Depends(verify_api_token)
):
    """Create a complete issue or reserve an ID."""
    try:
        issue = create_issue(db, request)
        return {"ok": True, "issue": issue.to_dict()}
    except IssueHubException as e:
        # Re-raise to be caught by global handler
        raise e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "ok": False,
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": str(e),
                    "details": {}
                }
            }
        )

@router.get("", response_model=IssuesListResponse)
def api_list_issues(
    filters: IssueFilterParams = Depends(issue_filters),
    include_history: Optional[bool] = Query(None, description="Embed each issue's change history"),
    db: Session = Depends(get_db),
    # Read access is authenticated via verification (Section 20.1: all token-authenticated clients have read/write)
    token: str = Depends(verify_api_token)
):
    """Find, show, search, or list issues.

    Binds to the same filter dependency as the web issue list and the analytics
    dashboard, so an identical query string yields an identical result set on
    all three surfaces.
    """
    effective_limit = resolve_limit(db, filters.limit)

    items, total = query_issues(
        db,
        limit=effective_limit,
        offset=filters.offset,
        sort=filters.sort,
        **filters.to_query_kwargs(),
    )

    # Embed history in a single batch query when asked, avoiding N+1 round-trips.
    res_items = []
    if include_history and items:
        issue_ids = [item.issue_id for item in items]
        histories = db.query(IssueHistory).filter(
            IssueHistory.issue_id.in_(issue_ids)
        ).order_by(IssueHistory.history_id.desc()).all()

        hist_by_id = defaultdict(list)
        for h in histories:
            hist_by_id[h.issue_id].append(h.to_dict())

        for item in items:
            issue_dict = item.to_dict()
            issue_dict["history"] = hist_by_id[item.issue_id]
            res_items.append(issue_dict)
    else:
        for item in items:
            res_items.append(item.to_dict())

    return {
        "ok": True,
        "items": res_items,
        "total": total,
        # The limit actually applied, not the one requested.
        "limit": effective_limit,
        "offset": filters.offset,
    }

@router.patch("/{issue_id}", response_model=IssueResponse)
def api_update_issue(
    issue_id: str,
    request: UpdateIssueRequest,
    db: Session = Depends(get_db),
    token: str = Depends(verify_api_token)
):
    """Update fields, append description text, relate, or retire an issue."""
    try:
        issue = update_issue(db, issue_id, request)
        return {"ok": True, "issue": issue.to_dict()}
    except IssueHubException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "ok": False,
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": str(e),
                    "details": {}
                }
            }
        )

@router.get("/{issue_id}/history", response_model=HistoryResponse)
def api_issue_history(
    issue_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_api_token)
):
    """Read the mutation and audit history of a specific issue."""
    # Check if issue exists
    exists = db.query(Issue.issue_id).filter(func.lower(Issue.issue_id) == func.lower(issue_id)).first()
    if not exists:
        raise IssueNotFound(issue_id)
        
    history_records = db.query(IssueHistory).filter(
        func.lower(IssueHistory.issue_id) == func.lower(issue_id)
    ).order_by(IssueHistory.history_id.desc()).all()
    
    items = []
    for r in history_records:
        items.append({
            "history_id": r.history_id,
            "issue_id": r.issue_id,
            "operation": r.operation,
            "changed_at": r.changed_at.isoformat() if r.changed_at else None,
            "before_record": r.before_record,
            "after_record": r.after_record,
            "note": r.note,
        })
        
    return {"ok": True, "items": items}
