from sqlalchemy.orm import Session
from sqlalchemy import text, func
from datetime import datetime, timezone
from typing import Optional, List
import re

from issue_hub.models import Issue, IssueHistory, LookupValue, HubSetting
from issue_hub.schemas import CreateIssueRequest, UpdateIssueRequest
from issue_hub.config import settings
from issue_hub.key_generation import render_issue_id
from typing import Any

def get_hub_setting(db: Session, key: str, default: Any) -> Any:
    """Dynamically load active configuration overrides from the database (Gate 3)."""
    try:
        setting = db.query(HubSetting).filter(HubSetting.setting_key == key).first()
        if setting and setting.setting_value:
            return setting.setting_value.get("value", default)
    except Exception:
        pass
    return default

class IssueHubException(Exception):
    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

class CallerSuppliedIdNotAllowed(IssueHubException):
    def __init__(self, issue_id: str):
        super().__init__(
            code="CALLER_SUPPLIED_ID_NOT_ALLOWED",
            message=f"Caller-supplied issue_id '{issue_id}' must identify an existing reserved issue",
        )

class IssueNotFound(IssueHubException):
    def __init__(self, issue_id: str):
        super().__init__(
            code="ISSUE_NOT_FOUND",
            message=f"Issue '{issue_id}' was not found",
        )

class ImportConflict(IssueHubException):
    def __init__(self, message: str):
        super().__init__(code="IMPORT_CONFLICT", message=message)

class ImportInvalidRecord(IssueHubException):
    def __init__(self, message: str):
        super().__init__(code="IMPORT_INVALID_RECORD", message=message)


def get_project_key_template(db: Session, project: Optional[str]) -> str:
    """Retrieve key template for a project or the global setting or system default."""
    if project:
        # Check lookup_values for PROJECT metadata
        proj_lookup = db.query(LookupValue).filter(
            LookupValue.lookup_type == "PROJECT",
            LookupValue.value == project
        ).first()
        if proj_lookup and proj_lookup.metadata_ and "key_template" in proj_lookup.metadata_:
            return proj_lookup.metadata_["key_template"]

    # Check hub_settings
    setting = db.query(HubSetting).filter(HubSetting.setting_key == "issue_key_template").first()
    if setting and setting.setting_value and "template" in setting.setting_value:
        return setting.setting_value["template"]

    return "Bug-{number}"


def derive_title(description: Optional[str], db: Optional[Session] = None, default_title: str = "Reserved issue") -> str:
    """Derive title from first non-empty description line, truncated to title_max_length (Gate 3 / Section 8)."""
    if not description:
        return default_title
    
    # Load dynamic limit if db context exists
    max_len = settings.title_max_length
    if db is not None:
        max_len = get_hub_setting(db, "title_max_length", settings.title_max_length)
    
    # Find first non-empty line
    for line in description.splitlines():
        trimmed = line.strip()
        if trimmed:
            # Remove Markdown headings like '# ', '## ', etc.
            clean_line = re.sub(r"^#+\s+", "", trimmed)
            # Truncate
            return clean_line[:max_len]
            
    return default_title


def clean_tags(tags: List[str]) -> List[str]:
    """Remove duplicates case-insensitively, remove empty strings, preserve original casing of first occurrence."""
    seen = set()
    cleaned = []
    for tag in tags:
        if not tag:
            continue
        trimmed = tag.strip()
        if not trimmed:
            continue
        lower_tag = trimmed.lower()
        if lower_tag not in seen:
            seen.add(lower_tag)
            cleaned.append(trimmed)
    return cleaned

def validate_state_invariants(issue: Issue):
    """Enforce strict RESERVED state-invariants centrally before any write (Gate 3 / Section 7)."""
    if issue.status == "RESERVED":
        # Incomplete fields permitted during RESERVED status
        pass
    else:
        # Active status requires nonblank severity and description! (Section 7)
        if not issue.description or not issue.description.strip():
            raise IssueHubException(
                "INVALID_STATUS_TRANSITION", 
                f"Description is required to transition issue '{issue.issue_id}' to active status '{issue.status}'."
            )
        if not issue.severity or not issue.severity.strip():
            raise IssueHubException(
                "INVALID_STATUS_TRANSITION", 
                f"Severity is required to transition issue '{issue.issue_id}' to active status '{issue.status}'."
            )


def create_issue(db: Session, request: CreateIssueRequest, import_mode: bool = False) -> Issue:
    """Core transaction logic for creating or reserving an issue (Section 34.1)."""
    # If Caller supplies an ID
    if request.id:
        reserved = db.query(Issue).filter(func.lower(Issue.issue_id) == func.lower(request.id)).first()
        if not reserved:
            if not import_mode:
                raise CallerSuppliedIdNotAllowed(request.id)
            # If import mode is active, we let it proceed to normal creation with the specified ID
        elif not import_mode and reserved.status != "RESERVED":
            raise CallerSuppliedIdNotAllowed(request.id)
        
        if reserved:
            before = reserved.to_dict()
            
            # Update fields on the reserved issue ONLY if explicitly supplied (Gate 3 / Section 7)
            supplied = request.model_fields_set
            
            if "project" in supplied:
                reserved.project = request.project
            if "repository" in supplied:
                reserved.repository = request.repository
            if "branch" in supplied:
                reserved.branch = request.branch
            if "worktree" in supplied:
                reserved.worktree = request.worktree
            if "task" in supplied:
                reserved.task = request.task
            
            # Default status transitions from RESERVED to request.status or OPEN
            if "status" in supplied and request.status != "RESERVED":
                reserved.status = request.status
            elif reserved.status == "RESERVED" and not request.reserve:
                reserved.status = "OPEN"
                
            if "severity" in supplied:
                reserved.severity = request.severity
            if "priority" in supplied:
                reserved.priority = request.priority
            if "expected_effort" in supplied:
                reserved.expected_effort = request.expected_effort
                
            if "description" in supplied:
                reserved.description = request.description
                
            # Title handling
            if "title" in supplied:
                reserved.title = request.title
            elif (not reserved.title or reserved.title == "Reserved issue") and reserved.description:
                reserved.title = derive_title(reserved.description)
            
            if "area" in supplied:
                reserved.area = request.area
            if "classification" in supplied:
                reserved.classification = request.classification
            if "domain" in supplied:
                reserved.domain = request.domain
            if "category" in supplied:
                reserved.category = request.category
                
            if "refs" in supplied:
                reserved.refs = request.refs
            if "source" in supplied:
                reserved.source = request.source
            if "aka" in supplied:
                reserved.aka = request.aka
            if "owner" in supplied:
                reserved.owner = request.owner
            if "recommended_next_step" in supplied:
                reserved.recommended_next_step = request.recommended_next_step
            if "tags" in supplied:
                reserved.tags = clean_tags(request.tags)
                
            # Perform centralized schema state-invariant validation (Gate 3 / Section 7)
            validate_state_invariants(reserved)
                
            reserved.updated_at = datetime.now(timezone.utc)
            db.add(reserved)
            
            # Write History
            history = IssueHistory(
                issue_id=reserved.issue_id,
                operation="UPDATE",
                before_record=before,
                after_record=reserved.to_dict(),
                note="Completed reservation fields"
            )
            db.add(history)
            if not import_mode:
                db.commit()
                db.refresh(reserved)
            return reserved

    # Resolve dynamic defaults from database settings (Gate 3 / Section 8)
    def_project = get_hub_setting(db, "default_project", settings.default_project)
    def_repository = get_hub_setting(db, "default_repository", settings.default_repository)
    def_branch = get_hub_setting(db, "default_branch", settings.default_branch)

    # If Caller supplied an ID and import mode is active, we use the supplied ID and bypass sequence/template DB calls (Section 23)
    if request.id and import_mode:
        issue_id = request.id
        # Extract sequence number from the supplied ID if possible
        match = re.search(r"-(\d+)$", request.id)
        number = int(match.group(1)) if match else 0
        proj = request.project or def_project
    else:
        # Normal creation/reservation (generate new sequence number)
        number = db.execute(text("SELECT nextval('issue_number_seq')")).scalar()
        
        # Template selection
        proj = request.project or def_project
        template = get_project_key_template(db, proj)
        
        issue_id = render_issue_id(
            template=template,
            number=number,
            project=proj,
            repository=request.repository or def_repository,
            branch=request.branch or def_branch,
            task=request.task,
        )

    # Derive title (Gate 3 / Section 8)
    derived_t = request.title or derive_title(request.description, db=db, default_title="Reserved issue" if request.reserve else "")

    status = request.status or ("RESERVED" if request.reserve else "OPEN")
    
    issue = Issue(
        issue_id=issue_id,
        sequence_number=number,
        project=proj,
        repository=request.repository or def_repository,
        branch=request.branch or def_branch,
        worktree=request.worktree,
        task=request.task,
        status=status,
        severity=request.severity,
        priority=request.priority,
        expected_effort=request.expected_effort,
        title=derived_t,
        description=request.description or "",
        area=request.area,
        classification=request.classification,
        domain=request.domain,
        category=request.category,
        refs=request.refs,
        source=request.source,
        aka=request.aka,
        owner=request.owner,
        recommended_next_step=request.recommended_next_step,
        tags=clean_tags(request.tags),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    # Enforce centralized state-invariants (Gate 3 / Section 7)
    validate_state_invariants(issue)
    
    db.add(issue)
    
    # Write history
    history = IssueHistory(
        issue_id=issue_id,
        operation="RESERVE" if request.reserve else "CREATE",
        before_record=None,
        after_record=issue.to_dict(),
    )
    db.add(history)
    if not import_mode:
        db.commit()
        db.refresh(issue)
    return issue


def update_issue(db: Session, issue_id: str, request: UpdateIssueRequest) -> Issue:
    """Core transaction logic for modifying, appending to, or retiring an issue (Section 34.2)."""
    current = db.query(Issue).filter(func.lower(Issue.issue_id) == func.lower(issue_id)).first()
    if not current:
        raise IssueNotFound(issue_id)
        
    before = current.to_dict()
    operation = "UPDATE"
    
    if request.set:
        # Update set fields
        for field, value in request.set.model_dump(exclude_unset=True).items():
            if field == "tags" and value is not None:
                current.tags = clean_tags(value)
            elif field == "add_tags" and value is not None:
                current.tags = clean_tags(current.tags + value)
            elif field == "remove_tags" and value is not None:
                remove_set = {rt.lower() for rt in value}
                current.tags = [t for t in current.tags if t.lower() not in remove_set]
            elif value is not None:
                # Support explicit field-clearing contract (Gate 3 / Section 9)
                if isinstance(value, str) and value.strip() in ("", "null", "NULL", "none", "NONE"):
                    setattr(current, field, None)
                else:
                    setattr(current, field, value)
                
    if request.append_description is not None:
        operation = "APPEND" if not request.set else "UPDATE"
        # Append logic (Section 15)
        utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        append_block = f"\n\n---\n\n**Appended {utc_now}**\n\n{request.append_description}"
        current.description = current.description + append_block
        
    if request.retire:
        operation = "RETIRE"
        current.is_retired = True
        current.retire_reason = request.retire.reason
        current.retire_note = request.retire.note
        current.retired_at = datetime.now(timezone.utc)
        if request.retire.duplicate_of:
            current.duplicate_of = request.retire.duplicate_of
            
    current.updated_at = datetime.now(timezone.utc)
    
    # Enforce centralized state-invariants (Gate 3 / Section 7)
    validate_state_invariants(current)
    
    db.add(current)
    
    # Insert history (Gate 3 / Section 9)
    history = IssueHistory(
        issue_id=current.issue_id,
        operation=operation,
        before_record=before,
        after_record=current.to_dict(),
        note=request.retire.note if request.retire else None
    )
    db.add(history)
    db.commit()
    db.refresh(current)
    return current
