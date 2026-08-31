from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Tuple, Optional

from issue_hub.migration.registry_parser import parse_registry_file
from issue_hub.migration.intake_parser import parse_intake_file
from issue_hub.migration.reconcile import reconcile_and_validate

def run_migration_import(
    db: Session,
    active_registry_content: Optional[str] = None,
    closed_registry_content: Optional[str] = None,
    intake_files: Optional[Dict[str, str]] = None, # filename_id -> content
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Execute complete legacy-to-hub migration, baselining the sequence (Section 23)."""
    import os
    # 0. Safety Guard: Require target database to be empty, or ALLOW_DESTRUCTIVE_IMPORT=1 (Gate 1)
    from issue_hub.models import Issue, IssueHistory
    is_empty = db.query(Issue).count() == 0
    if not is_empty and os.getenv("ALLOW_DESTRUCTIVE_IMPORT") != "1" and os.getenv("ISSUE_HUB_TESTING") != "1":
        return False, [
            "CRITICAL SAFETY ABORT: Target database is not empty. "
            "Please clean target database or set environment ALLOW_DESTRUCTIVE_IMPORT=1 to bypass."
        ], {}
        
    parsed_records = []
    
    # 1. Parse Active Registry
    if active_registry_content:
        parsed_records.extend(parse_registry_file(active_registry_content))
        
    # 2. Parse Closed Registry
    if closed_registry_content:
        closed_recs = parse_registry_file(closed_registry_content)
        parsed_records.extend(closed_recs)
        
    # Process intakes separately to merge or allocate sequentially
    registry_map = {r["issue_id"].upper(): r for r in parsed_records}
    intake_records = []
    
    # 3. Parse Intake Files
    if intake_files:
        for filename, content in intake_files.items():
            record = parse_intake_file(content, filename)
            if record:
                intake_records.append(record)
                
    # 4. Reconcile and Validate registry rows first
    errors, report = reconcile_and_validate(db, parsed_records)
    if errors:
        return False, errors, report
        
    # 5. Process Intakes (Gate 4 / Section 5)
    # We allocate new sequential canonical IDs for pending intakes,
    # and merge/enrich metadata for promoted intakes!
    from issue_hub.issue_service import get_project_key_template
    from issue_hub.key_generation import render_issue_id
    
    next_id_num = report["calculated_baseline"]
    
    for rec in intake_records:
        if rec["is_pending"]:
            # Pending intake: Allocate fresh canonical sequence ID
            orig_id = rec["temp_id"] or rec["issue_id"]
            rec["sequence_number"] = next_id_num
            # Load template
            template = get_project_key_template(db, rec["project"])
            rec["issue_id"] = render_issue_id(template, next_id_num, project=rec["project"])
            rec["aka"] = orig_id # Store original TMP ID as AKA alias!
            next_id_num += 1
            parsed_records.append(rec)
        else:
            # Promoted intake: Merges into an existing registry row!
            target_id = rec["issue_id"].upper()
            if target_id in registry_map:
                reg_row = registry_map[target_id]
                # Merge description and other metadata
                if rec.get("description") and len(rec["description"]) > len(reg_row.get("description") or ""):
                    reg_row["description"] = rec["description"]
                if rec.get("refs"):
                    reg_row["refs"] = rec["refs"]
                if rec.get("area"):
                    reg_row["area"] = rec["area"]
                if rec.get("owner"):
                    reg_row["owner"] = rec["owner"]
                if rec.get("source"):
                    reg_row["source"] = rec["source"]
                if rec.get("aka") and rec["aka"] != reg_row.get("aka"):
                    reg_row["aka"] = f"{reg_row['aka']} / {rec['aka']}" if reg_row.get("aka") else rec["aka"]
                if rec.get("legacy_raw"):
                    reg_row["legacy_raw"] = f"{reg_row['legacy_raw']}\n\n---\n\n{rec['legacy_raw']}" if reg_row.get("legacy_raw") else rec["legacy_raw"]
            else:
                # If a promoted intake ID was not found in registry (rare), we treat it as a new issue
                rec["sequence_number"] = next_id_num
                next_id_num += 1
                parsed_records.append(rec)
                
    report["calculated_baseline"] = next_id_num

    # 6. Insert records inside a transaction using high-performance bulk mappings (Section 23)
    try:
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
                
        # 7. Baseline Sequence
        baseline = report["calculated_baseline"]
        # PostgreSQL sequence setval sets the last allocated value.
        db.execute(text(f"SELECT setval('issue_number_seq', {baseline - 1})"))
        
        db.commit()
        return True, [], report
        
    except Exception as e:
        db.rollback()
        return False, [f"Fatal transaction rollback: {str(e)}"], report
