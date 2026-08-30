from sqlalchemy.orm import Session
from sqlalchemy import or_, text, desc, asc, cast, String
from typing import Optional, List, Tuple
from datetime import datetime

from issue_hub.models import Issue, LookupValue

def query_issues(
    db: Session,
    id_: Optional[str] = None,
    q: Optional[str] = None,
    project: Optional[str] = None,
    repository: Optional[str] = None,
    branch: Optional[str] = None,
    worktree: Optional[str] = None,
    task: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    priority: Optional[str] = None,
    expected_effort: Optional[str] = None,
    area: Optional[str] = None,
    domain: Optional[str] = None,
    category: Optional[str] = None,
    classification: Optional[str] = None,
    owner: Optional[str] = None,
    tag: Optional[str] = None,
    is_retired: Optional[bool] = None,
    is_terminal: Optional[bool] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    updated_from: Optional[datetime] = None,
    updated_to: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    sort: Optional[str] = None,
) -> Tuple[List[Issue], int]:
    """Search, filter, and paginate issues with custom scoring (Section 21.3)."""
    query = db.query(Issue)
    
    # Exact ID filter (comma-separated or single)
    if id_:
        id_list = [i.strip() for i in id_.split(",") if i.strip()]
        if len(id_list) == 1:
            query = query.filter(or_(Issue.issue_id == id_list[0], Issue.aka == id_list[0]))
        else:
            query = query.filter(or_(Issue.issue_id.in_(id_list), Issue.aka.in_(id_list)))

    # Exact field filters
    if project:
        query = query.filter(Issue.project == project)
    if repository:
        query = query.filter(Issue.repository == repository)
    if branch:
        query = query.filter(Issue.branch == branch)
    if worktree:
        query = query.filter(Issue.worktree == worktree)
    if task:
        query = query.filter(Issue.task == task)
    if status:
        query = query.filter(Issue.status == status)
    if severity:
        query = query.filter(Issue.severity == severity)
    if priority:
        query = query.filter(Issue.priority == priority)
    if expected_effort:
        query = query.filter(Issue.expected_effort == expected_effort)
    if area:
        query = query.filter(Issue.area == area)
    if domain:
        query = query.filter(Issue.domain == domain)
    if category:
        query = query.filter(Issue.category == category)
    if classification:
        query = query.filter(Issue.classification == classification)
    if owner:
        query = query.filter(Issue.owner == owner)
        
    # Tag array containment filter (JSONB)
    if tag:
        # Cast our string tag into a JSON array, e.g. ["excel"]
        query = query.filter(Issue.tags.contains([tag]))
        
    # Retired filter (only filter if explicitly requested)
    if is_retired is not None:
        query = query.filter(Issue.is_retired == is_retired)

    # Terminal filter handling
    if is_terminal is not None:
        # Fetch terminal statuses from lookup_values
        terminal_lookups = db.query(LookupValue.value).filter(
            LookupValue.lookup_type == "STATUS",
            LookupValue.is_terminal.is_(True)
        ).all()
        terminal_statuses = [r[0] for r in terminal_lookups]
        
        if is_terminal:
            query = query.filter(Issue.status.in_(terminal_statuses))
        else:
            query = query.filter(~Issue.status.in_(terminal_statuses))

    # Timestamp Range Filters (Section 16.3)
    if created_from is not None:
        query = query.filter(Issue.created_at >= created_from)
    if created_to is not None:
        query = query.filter(Issue.created_at <= created_to)
    if updated_from is not None:
        query = query.filter(Issue.updated_at >= updated_from)
    if updated_to is not None:
        query = query.filter(Issue.updated_at <= updated_to)

    # Text Search q and custom scoring/ranking
    if q:
        q_clean = q.strip()
        q_like = f"%{q_clean}%"
        q_prefix = f"{q_clean}%"
        
        # Apply the filters across every single attribute (wide search)
        query = query.filter(
            or_(
                Issue.issue_id.ilike(q_like),
                Issue.aka.ilike(q_like),
                Issue.title.ilike(q_like),
                Issue.description.ilike(q_like),
                Issue.area.ilike(q_like),
                Issue.classification.ilike(q_like),
                Issue.domain.ilike(q_like),
                Issue.category.ilike(q_like),
                Issue.refs.ilike(q_like),
                Issue.source.ilike(q_like),
                Issue.owner.ilike(q_like),
                Issue.status.ilike(q_like),
                Issue.severity.ilike(q_like),
                Issue.priority.ilike(q_like),
                Issue.expected_effort.ilike(q_like),
                Issue.project.ilike(q_like),
                Issue.repository.ilike(q_like),
                Issue.branch.ilike(q_like),
                Issue.worktree.ilike(q_like),
                Issue.task.ilike(q_like),
                Issue.duplicate_of.ilike(q_like),
                Issue.related_to.ilike(q_like),
                Issue.retire_reason.ilike(q_like),
                Issue.retire_note.ilike(q_like),
                Issue.legacy_raw.ilike(q_like),
                Issue.recommended_next_step.ilike(q_like),
                cast(Issue.sequence_number, String).ilike(q_like),
                cast(Issue.tags, String).ilike(q_like)
            )
        )
        
        # Scoring expression based on Section 21.3
        score_expr = text(
            """
            CASE
                WHEN LOWER(issues.issue_id) = LOWER(:q_clean) THEN 100
                WHEN LOWER(issues.aka) = LOWER(:q_clean) THEN 90
                WHEN LOWER(issues.issue_id) LIKE LOWER(:q_prefix) THEN 80
                WHEN LOWER(issues.title) ILIKE LOWER(:q_like) THEN 70
                WHEN LOWER(issues.description) ILIKE LOWER(:q_like) THEN 60
                WHEN LOWER(issues.area) ILIKE LOWER(:q_like) 
                     OR LOWER(issues.classification) ILIKE LOWER(:q_like) 
                     OR LOWER(issues.domain) ILIKE LOWER(:q_like) 
                     OR LOWER(issues.category) ILIKE LOWER(:q_like) 
                     OR LOWER(issues.refs) ILIKE LOWER(:q_like) 
                     OR LOWER(issues.source) ILIKE LOWER(:q_like) 
                     OR LOWER(issues.owner) ILIKE LOWER(:q_like) THEN 50
                ELSE 1
            END
            """
        ).bindparams(q_clean=q_clean, q_prefix=q_prefix, q_like=q_like)
        
        # Add search score select and sort by score desc first, then sort
        query = query.order_by(desc(score_expr))

    # General Sorting
    sort_by = None
    if sort:
        parts = sort.strip().split()
        field = parts[0].lower()
        direction = parts[1].upper() if len(parts) > 1 else "ASC"
        
        column = getattr(Issue, field, None)
        if column:
            sort_by = desc(column) if direction == "DESC" else asc(column)
            
    if sort_by is not None:
        query = query.order_by(sort_by)
    elif not q:
        # Default sort (descending sequence_number) when no text search active
        query = query.order_by(desc(Issue.sequence_number))

    # Get total count before pagination
    total = query.count()
    
    # Apply limit/offset
    limit = max(1, min(limit, 1000))
    query = query.limit(limit).offset(offset)
    
    return query.all(), total
