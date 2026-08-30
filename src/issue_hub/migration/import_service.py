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
        # Preserve original statuses (e.g. FIXED, RESOLVED, BY-DESIGN) rather than flattening to CLOSED (Gate 4 / Section 5)
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
        
    # 5. Allocate new canonical IDs for pending intakes (Gate 4 / Section 5)
    from issue_hub.issue_service import get_project_key_template
    from issue_hub.key_generation import render_issue_id
    next_id_num = report["calculated_baseline"]
    for rec in parsed_records:
        rid = rec["issue_id"]
        if rid.startswith("TMP-") or "TMP" in rid or len(rid) > 10:
            rec["sequence_number"] = next_id_num
            # Load project key template dynamically
            template = get_project_key_template(db, rec["project"])
            rec["issue_id"] = render_issue_id(template, next_id_num, project=rec["project"])
            rec["aka"] = rid # Move original TMP ID into AKA (Section 5)
            next_id_num += 1
            
    report["calculated_baseline"] = next_id_num

    # 6. Insert records inside a transaction using high-performance bulk mappings (Section 23)
    try:
        from issue_hub.models import Issue, IssueHistory
        
        issues_to_insert = []
        history_to_insert = []
        
        for rec in parsed_records:
            issues_to_insert.append({
                "issue_id": rec["issue_id"],
                "sequence_number": rec["sequence_number"],
                "project": rec.get("project") or "tessallite",
                "repository": rec.get("repository"),
                "branch": rec.get("branch", "main"),
                "status": rec["status"],
                "severity": rec.get("severity"),
                "title": rec["title"],
                "description": rec["description"],
                "area": rec.get("area"),
                "refs": rec.get("refs"),
                "domain": rec.get("domain"),
                "category": rec.get("category"),
                "owner": rec.get("owner"),
                "recommended_next_step": rec.get("recommended_next_step"),
                "aka": rec.get("aka"),
                "legacy_raw": rec.get("legacy_raw"),
                "tags": rec.get("tags", []),
            })
            
            history_to_insert.append({
                "issue_id": rec["issue_id"],
                "operation": "IMPORT",
                "note": "Administrative import"
            })
            
        db.bulk_insert_mappings(Issue, issues_to_insert)
        db.bulk_insert_mappings(IssueHistory, history_to_insert)
                
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
