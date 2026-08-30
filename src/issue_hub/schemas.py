from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any

class CreateIssueRequest(BaseModel):
    model_config = {"extra": "forbid"}
    project: Optional[str] = None
    repository: Optional[str] = None
    branch: Optional[str] = None
    worktree: Optional[str] = None
    task: Optional[str] = None

    status: Optional[str] = None
    severity: Optional[str] = None
    priority: Optional[str] = None
    expected_effort: str = "UNKNOWN"

    title: Optional[str] = None
    description: Optional[str] = None
    area: Optional[str] = None
    classification: Optional[str] = None
    domain: Optional[str] = None
    category: Optional[str] = None

    refs: Optional[str] = None
    source: Optional[str] = None
    aka: Optional[str] = None
    owner: Optional[str] = None
    recommended_next_step: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    reserve: bool = False
    id: Optional[str] = None  # Existing reserved ID to complete

    @model_validator(mode="after")
    def validate_create_fields(self) -> "CreateIssueRequest":
        # If completing/creating with an ID, let's pass
        if self.id:
            return self

        # If reserve is False, severity and description are required
        if not self.reserve:
            if not self.severity:
                raise ValueError("severity is required when not reserving an ID")
            if not self.description:
                raise ValueError("description is required when not reserving an ID")
        return self

class UpdateIssueRequestSet(BaseModel):
    model_config = {"extra": "forbid"}
    project: Optional[str] = None
    repository: Optional[str] = None
    branch: Optional[str] = None
    worktree: Optional[str] = None
    task: Optional[str] = None
    status: Optional[str] = None
    severity: Optional[str] = None
    priority: Optional[str] = None
    expected_effort: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    area: Optional[str] = None
    classification: Optional[str] = None
    domain: Optional[str] = None
    category: Optional[str] = None
    refs: Optional[str] = None
    source: Optional[str] = None
    aka: Optional[str] = None
    owner: Optional[str] = None
    recommended_next_step: Optional[str] = None
    tags: Optional[List[str]] = None
    add_tags: Optional[List[str]] = None
    remove_tags: Optional[List[str]] = None
    duplicate_of: Optional[str] = None
    related_to: Optional[str] = None

class RetireRequest(BaseModel):
    model_config = {"extra": "forbid"}
    reason: str
    duplicate_of: Optional[str] = None
    note: Optional[str] = None

class UpdateIssueRequest(BaseModel):
    model_config = {"extra": "forbid"}
    set: Optional[UpdateIssueRequestSet] = None
    append_description: Optional[str] = None
    retire: Optional[RetireRequest] = None

class IssueResponseData(BaseModel):
    issue_id: str
    sequence_number: int
    project: Optional[str]
    repository: Optional[str]
    branch: str
    worktree: Optional[str]
    task: Optional[str]
    status: str
    severity: Optional[str]
    priority: Optional[str]
    expected_effort: str
    title: str
    description: str
    area: Optional[str]
    classification: Optional[str]
    domain: Optional[str]
    category: Optional[str]
    refs: Optional[str]
    source: Optional[str]
    aka: Optional[str]
    owner: Optional[str]
    tags: List[str]
    duplicate_of: Optional[str]
    related_to: Optional[str]
    is_retired: bool
    retire_reason: Optional[str]
    retire_note: Optional[str]
    retired_at: Optional[str]
    legacy_raw: Optional[str]
    recommended_next_step: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None
    created_at: str
    updated_at: str

class IssueResponse(BaseModel):
    ok: bool
    issue: IssueResponseData

class IssuesListResponse(BaseModel):
    ok: bool
    items: List[IssueResponseData]
    total: int
    limit: int
    offset: int

class HistoryResponseItem(BaseModel):
    history_id: int
    issue_id: str
    operation: str
    changed_at: str
    before_record: Optional[Dict[str, Any]]
    after_record: Optional[Dict[str, Any]]
    note: Optional[str]

class HistoryResponse(BaseModel):
    ok: bool
    items: List[HistoryResponseItem]
