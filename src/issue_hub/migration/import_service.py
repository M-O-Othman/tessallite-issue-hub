from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Tuple, Optional

from issue_hub.migration.registry_parser import parse_registry_file
from issue_hub.migration.intake_parser import parse_intake_file
from issue_hub.migration.reconcile import reconcile_and_validate
from issue_hub.issue_service import create_issue
from issue_hub.schemas import CreateIssueRequest

def run_migration_import(
    db: Session,
    active_registry_content: Optional[str] = None,
    closed_registry_content: Optional[str] = None,
    intake_files: Optional[Dict[str, str]] = None, # filename_id -> content
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Execute complete legcy-to-hub migration, baselining the sequence (Section 23)."""
    parsed_records = []
    
    # 1. Parse Active Registry
    if active_registry_content:
        parsed_records.extend(parse_registry_file(active_registry_content))
        
    # 2. Parse Closed Registry
    if closed_registry_content:
        closed_recs = parse_registry_file(closed_registry_content)
        # Force closed status on these parsed records
        for r in closed_recs:
            r["status"] = "CLOSED"
        parsed_records.extend(closed_recs)
        
    # 3. Parse Intake Files
    if intake_files:
        for filename, content in intake_files.items():
            record = parse_intake_file(content, filename)
            if record:
                parsed_records.append(record)
                
    # 4. Reconcile and Validate
    errors, report = reconcile_and_validate(db, parsed_records)
    
    if errors:
        return False, errors, report
        
    # 5. Insert records inside a transaction
    try:
        for rec in parsed_records:
            req = CreateIssueRequest(
                id=rec["issue_id"],
                project=rec.get("project") or "tessallite",
                repository=rec.get("repository"),
                branch=rec.get("branch", "main"),
                status=rec["status"],
                severity=rec.get("severity"),
                title=rec["title"],
                description=rec["description"],
                area=rec.get("area"),
                refs=rec.get("refs"),
                domain=rec.get("domain"),
                category=rec.get("category"),
                owner=rec.get("owner"),
                recommended_next_step=rec.get("recommended_next_step"),
                tags=rec.get("tags", []),
            )
            issue = create_issue(db, req, import_mode=True)
            
            # Post-adjust tags/AKA if present
            if rec.get("aka"):
                issue.aka = rec["aka"]
                db.add(issue)
                
            if rec.get("legacy_raw"):
                issue.legacy_raw = rec["legacy_raw"]
                db.add(issue)
                
        # 6. Baseline Sequence
        baseline = report["calculated_baseline"]
        # PostgreSQL sequence setval sets the last allocated value.
        # So we set it to baseline - 1, meaning the NEXT allocated value will be baseline!
        # This is extremely precise and correct!
        db.execute(text(f"SELECT setval('issue_number_seq', {baseline - 1})"))
        
        db.commit()
        return True, [], report
        
    except Exception as e:
        db.rollback()
        return False, [f"Fatal transaction rollback: {str(e)}"], report
