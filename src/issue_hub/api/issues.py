from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List, Union
from collections import defaultdict
from datetime import datetime

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
from issue_hub.search import query_issues
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
    id: Optional[str] = Query(None, description="Exact issue ID(s) (comma-separated)"),
    q: Optional[str] = Query(None, description="Text search query"),
    project: Optional[List[str]] = Query(None),
    repository: Optional[List[str]] = Query(None),
    branch: Optional[str] = Query(None),
    worktree: Optional[str] = Query(None),
    task: Optional[str] = Query(None),
    status: Optional[List[str]] = Query(None),
    severity: Optional[List[str]] = Query(None),
    priority: Optional[List[str]] = Query(None),
    expected_effort: Optional[List[str]] = Query(None),
    area: Optional[str] = Query(None),
    domain: Optional[List[str]] = Query(None),
    category: Optional[List[str]] = Query(None),
    classification: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
    tag: Optional[str] = Query(None, description="Filter by a specific tag"),
    is_retired: Optional[str] = Query(None),
    is_terminal: Optional[str] = Query(None),
    created_from: Optional[datetime] = Query(None),
    created_to: Optional[datetime] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    closed_from: Optional[datetime] = Query(None),
    closed_to: Optional[datetime] = Query(None),
    include_history: Optional[bool] = Query(None),
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    # Read access is authenticated via verification (Section 20.1: all token-authenticated clients have read/write)
    token: str = Depends(verify_api_token)
):
    """Find, show, search, or list issues."""
    # Normalize empty strings submitted by clients/browsers to None
    def norm(v: Optional[str]) -> Optional[str]:
        return v.strip() if v and v.strip() else None

    def norm_list(v: Optional[Union[str, List[str]]]) -> Optional[Union[str, List[str]]]:
        if not v:
            return None
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",") if p.strip()]
            return parts if len(parts) > 1 else (parts[0] if parts else None)
        flattened = []
        for item in v:
            if item:
                for sub in item.split(","):
                    sub_clean = sub.strip()
                    if sub_clean:
                        flattened.append(sub_clean)
        return flattened if flattened else None

    id_norm = norm(id)
    q_norm = norm(q)
    project_norm = norm_list(project)
    repository_norm = norm_list(repository)
    branch_norm = norm(branch)
    worktree_norm = norm(worktree)
    task_norm = norm(task)
    status_norm = norm_list(status)
    severity_norm = norm_list(severity)
    priority_norm = norm_list(priority)
    expected_effort_norm = norm_list(expected_effort)
    area_norm = norm(area)
    domain_norm = norm_list(domain)
    category_norm = norm_list(category)
    classification_norm = norm(classification)
    owner_norm = norm(owner)
    tag_norm = norm(tag)

    # Safe boolean parsing of parameters
    is_retired_bool: Optional[bool] = None
    if is_retired == "true" or is_retired is True:
        is_retired_bool = True
    elif is_retired == "false" or is_retired is False:
        is_retired_bool = False
        
    is_terminal_bool: Optional[bool] = None
    if is_terminal == "true" or is_terminal is True:
        is_terminal_bool = True
    elif is_terminal == "false" or is_terminal is False:
        is_terminal_bool = False

    items, total = query_issues(
        db=db,
        id_=id_norm,
        q=q_norm,
        project=project_norm,
        repository=repository_norm,
        branch=branch_norm,
        worktree=worktree_norm,
        task=task_norm,
        status=status_norm,
        severity=severity_norm,
        priority=priority_norm,
        expected_effort=expected_effort_norm,
        area=area_norm,
        domain=domain_norm,
        category=category_norm,
        classification=classification_norm,
        owner=owner_norm,
        tag=tag_norm,
        is_retired=is_retired_bool,
        is_terminal=is_terminal_bool,
        created_from=created_from,
        created_to=created_to,
        updated_from=updated_from,
        updated_to=updated_to,
        closed_from=closed_from,
        closed_to=closed_to,
        limit=limit,
        offset=offset,
        sort=sort,
    )
    
    from issue_hub.issue_service import get_hub_setting
    db_limit = get_hub_setting(db, "search_default_limit", 100)
    resolved_limit = limit if limit is not None else db_limit

    # Process inline history in a single batch query if requested (eliminating N+1 queries)
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
        "limit": resolved_limit,
        "offset": offset,
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
