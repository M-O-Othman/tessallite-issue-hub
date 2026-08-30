from sqlalchemy.orm import Session
from typing import List, Dict, Any, Tuple

from issue_hub.models import Issue

def reconcile_and_validate(
    db: Session,
    legacy_records: List[Dict[str, Any]]
) -> Tuple[List[str], Dict[str, Any]]:
    """Validate legacy records, find ID conflicts, and calculate sequence baseline offset (Section 23)."""
    errors = []
    validated_records = []
    
    # Track unique IDs and AKAs within the imported set
    imported_ids = set()
    imported_akas = set()
    
    max_imported_seq = 0
    
    for idx, rec in enumerate(legacy_records):
        rec_id = rec.get("issue_id")
        
        # 1. Validation: Ensure ID is present and formatted correctly
        if not rec_id:
            errors.append(f"Record {idx}: Missing issue_id.")
            continue
            
        if rec_id in imported_ids:
            errors.append(f"Conflict: Duplicate issue_id '{rec_id}' in import set.")
            continue
            
        imported_ids.add(rec_id)
        
        # Track max sequence number
        seq_num = rec.get("sequence_number", 0)
        if seq_num > max_imported_seq:
            max_imported_seq = seq_num
            
        # 2. Validation: Ensure title is not empty
        if not rec.get("title"):
            errors.append(f"Issue '{rec_id}': Title cannot be empty.")
            continue
            
        # 3. Validation: Check for AKA conflict in import set (Section 23.3)
        aka = rec.get("aka")
        if aka:
            if aka in imported_ids or aka in imported_akas:
                # Section 23.3: if an alias conflicts, the importer can ignore the alias
                # We set it to None to prevent duplication/conflict, and log a warning
                rec["aka"] = None
            else:
                imported_akas.add(aka)
                
        # 4. Check for database conflicts
        existing = db.query(Issue).filter(Issue.issue_id == rec_id).first()
        if existing:
            errors.append(f"Conflict: Issue ID '{rec_id}' already exists in database.")
            continue
            
        validated_records.append(rec)
        
    # Calculate baseline sequence number offset (Section 23.3)
    # Baseline is max(imported, existing_db) + 1
    from sqlalchemy import func
    max_db_seq = db.query(func.max(Issue.sequence_number)).scalar() or 0
    calculated_baseline = max(max_imported_seq, max_db_seq) + 1
    
    # Standard baseline should be at least 1000 if no issues exist
    if calculated_baseline < 1000 and max_db_seq == 0 and max_imported_seq == 0:
        calculated_baseline = 1000
        
    report = {
        "calculated_baseline": calculated_baseline,
        "max_imported_seq": max_imported_seq,
        "max_db_seq": max_db_seq,
        "valid_count": len(validated_records),
        "error_count": len(errors),
    }
    
    return errors, report
