import pytest
from sqlalchemy import text

from issue_hub.database import SessionLocal
from issue_hub.migration.registry_parser import parse_registry_line
from issue_hub.migration.intake_parser import parse_intake_file
from issue_hub.migration.import_service import run_migration_import
from issue_hub.models import Issue

@pytest.fixture(autouse=True)
def clean_migration_database():
    db = SessionLocal()
    try:
        db.execute(text("TRUNCATE TABLE issues, issue_history CASCADE"))
        db.execute(text("ALTER SEQUENCE issue_number_seq RESTART WITH 100"))
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def test_parse_legacy_registry_line():
    """Verify that registry parser correctly extracts columns and metadata from a raw list line."""
    line = "- **Bug-9627** — `[OPEN]` — AKA XMLA-9627 — `[HIGH -- XMLA hierarchy owner mismatch]` Excel cannot resolve the hierarchy owner. Area: Gateway. Refs: src/xmla.py:45. Domain: gateway. Category: product."
    record = parse_registry_line(line)
    
    assert record is not None
    assert record["issue_id"] == "Bug-9627"
    assert record["sequence_number"] == 9627
    assert record["status"] == "OPEN"
    assert record["aka"] == "XMLA-9627"
    assert record["severity"] == "HIGH"
    assert record["title"] == "XMLA hierarchy owner mismatch"
    assert record["description"] == "Excel cannot resolve the hierarchy owner. Area: Gateway. Refs: src/xmla.py:45. Domain: gateway. Category: product"
    assert record["area"] == "Gateway"
    assert record["refs"] == "src/xmla.py:45"
    assert record["domain"] == "gateway"
    assert record["category"] == "product"

def test_parse_legacy_intake_file():
    """Verify that intake parser extracts frontmatter fields and content."""
    content = """---
title: XMLA dax timeout
severity: CRITICAL
status: OPEN
area: Gateway
refs: src/dax.py:100
domain: gateway
category: product
---

## Description
This is the description.
"""
    record = parse_intake_file(content, "TESS-TMP-1234")
    assert record is not None
    assert record["issue_id"] == "TESS-TMP-1234"
    assert record["sequence_number"] == 1234
    assert record["project"] == "TESS"
    assert record["status"] == "OPEN"
    assert record["severity"] == "CRITICAL"
    assert record["title"] == "XMLA dax timeout"
    assert record["description"] == "## Description\nThis is the description."
    assert record["area"] == "Gateway"
    assert record["refs"] == "src/dax.py:100"
    assert record["domain"] == "gateway"
    assert record["category"] == "product"

def test_reconcile_and_sequence_baselining():
    """Verify migration dry-run, actual import, and proper sequence allocation baselining."""
    db = SessionLocal()
    try:
        active_content = """
- **Bug-9627** — `[OPEN]` — AKA XMLA-9627 — `[HIGH -- Title 1]` Desc 1. Area: Gateway. Domain: gateway. Category: product.
- **Bug-9628** — `[OPEN]` — `[MEDIUM -- Title 2]` Desc 2. Area: Shared. Domain: shared.
"""
        closed_content = """
- **Bug-9610** — `[CLOSED]` — `[LOW -- Title 3]` Desc 3.
"""
        intakes = {
            "TMP-9630": """---
title: Temp 4
severity: HIGH
status: OPEN
---
Desc 4."""
        }
        
        # Run import
        success, errors, report = run_migration_import(
            db=db,
            active_registry_content=active_content,
            closed_registry_content=closed_content,
            intake_files=intakes
        )
        
        assert success is True
        assert not errors
        assert report["valid_count"] == 4
        assert report["calculated_baseline"] == 9631 # max(9627, 9628, 9610, 9630) + 1
        
        # Verify database records
        bug_9627 = db.query(Issue).filter(Issue.issue_id == "Bug-9627").first()
        assert bug_9627 is not None
        assert bug_9627.status == "OPEN"
        assert bug_9627.aka == "XMLA-9627"
        
        bug_9610 = db.query(Issue).filter(Issue.issue_id == "Bug-9610").first()
        assert bug_9610 is not None
        assert bug_9610.status == "CLOSED"
        
        # Test sequence allocation baselining: creating a new issue should assign next_val = 9631
        new_val = db.execute(text("SELECT nextval('issue_number_seq')")).scalar()
        assert new_val == 9631
        
    finally:
        db.close()
