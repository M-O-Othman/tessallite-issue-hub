from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from issue_hub.database import Base

class Issue(Base):
    __tablename__ = "issues"

    issue_id = Column(String, primary_key=True)
    sequence_number = Column(BigInteger, nullable=False, unique=True)

    project = Column(String, nullable=False, server_default="tessallite", default="tessallite")
    repository = Column(String)
    branch = Column(String, nullable=False, server_default="main", default="main")
    worktree = Column(String)
    task = Column(String)

    status = Column(String, nullable=False, server_default="OPEN", default="OPEN")
    severity = Column(String)
    priority = Column(String)
    expected_effort = Column(String, server_default="UNKNOWN", default="UNKNOWN")

    title = Column(String, nullable=False, server_default="", default="")
    description = Column(String, nullable=False, server_default="", default="")
    area = Column(String)
    classification = Column(String)
    domain = Column(String)
    category = Column(String)

    refs = Column(String)
    source = Column(String)
    aka = Column(String)
    owner = Column(String)
    tags = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list)

    duplicate_of = Column(String)
    related_to = Column(String)

    is_retired = Column(Boolean, nullable=False, server_default="false", default=False)
    retire_reason = Column(String)
    retire_note = Column(String)
    retired_at = Column(DateTime(timezone=True))

    legacy_raw = Column(String)
    recommended_next_step = Column(String)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        """Serialize model into dictionary for history logging and JSON responses."""
        return {
            "issue_id": self.issue_id,
            "sequence_number": self.sequence_number,
            "project": self.project,
            "repository": self.repository,
            "branch": self.branch,
            "worktree": self.worktree,
            "task": self.task,
            "status": self.status,
            "severity": self.severity,
            "priority": self.priority,
            "expected_effort": self.expected_effort,
            "title": self.title,
            "description": self.description,
            "area": self.area,
            "classification": self.classification,
            "domain": self.domain,
            "category": self.category,
            "refs": self.refs,
            "source": self.source,
            "aka": self.aka,
            "owner": self.owner,
            "tags": self.tags,
            "duplicate_of": self.duplicate_of,
            "related_to": self.related_to,
            "is_retired": self.is_retired,
            "retire_reason": self.retire_reason,
            "retire_note": self.retire_note,
            "retired_at": self.retired_at.isoformat() if self.retired_at else None,
            "legacy_raw": self.legacy_raw,
            "recommended_next_step": self.recommended_next_step,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class IssueHistory(Base):
    __tablename__ = "issue_history"

    history_id = Column(BigInteger, primary_key=True, autoincrement=True)
    issue_id = Column(String, nullable=False)
    operation = Column(String, nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    before_record = Column(JSONB)
    after_record = Column(JSONB)
    note = Column(String)

    def to_dict(self) -> dict:
        return {
            "history_id": self.history_id,
            "issue_id": self.issue_id,
            "operation": self.operation,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
            "before_record": self.before_record,
            "after_record": self.after_record,
            "note": self.note,
        }

class LookupValue(Base):
    __tablename__ = "lookup_values"

    lookup_type = Column(String, primary_key=True, nullable=False)
    value = Column(String, primary_key=True, nullable=False)
    label = Column(String)
    display_order = Column(Integer, nullable=False, server_default="0", default=0)
    is_active = Column(Boolean, nullable=False, server_default="true", default=True)
    is_terminal = Column(Boolean)
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)

class HubSetting(Base):
    __tablename__ = "hub_settings"

    setting_key = Column(String, primary_key=True)
    setting_value = Column(JSONB, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
