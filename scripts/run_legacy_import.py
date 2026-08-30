from issue_hub.database import SessionLocal
from issue_hub.models import Issue
from issue_hub.migration.import_service import run_migration_import
from sqlalchemy import text
import sys

def main():
    print("Initiating production-scale legacy issue migration...")
    
    # 1. Open database session
    db = SessionLocal()
    try:
        # 2. Clear out any existing dummy/testing issue rows to prevent conflicts
        print("Clearing out existing database records to ensure a clean import state...")
        db.execute(text("TRUNCATE TABLE issues, issue_history CASCADE"))
        db.commit()
        
        # 3. Read active and closed registries
        print("Reading legacy markdown source documents...")
        with open("migration_sources/active-registry.md", "r", encoding="utf-8") as f:
            active_content = f.read()
        with open("migration_sources/closed-registry.md", "r", encoding="utf-8") as f:
            closed_content = f.read()
            
        # 4. Execute the actual migration
        print("Executing migration import transaction (parsing, validating, and inserting 3550+ records)...")
        success, errors, report = run_migration_import(
            db=db,
            active_registry_content=active_content,
            closed_registry_content=closed_content,
            intake_files=None
        )
        
        if not success:
            print("MIGRATION FAILED!")
            print("Errors encountered:")
            for err in errors:
                print(f" - {err}")
            sys.exit(1)
            
        print("MIGRATION COMPLETED SUCCESSFULLY!")
        print(f"Total Imported Records: {report['valid_count']}")
        print(f"Calculated Sequence Baseline: {report['calculated_baseline']}")
        
        # 5. Verify database counts
        db.close() # re-open to clear caches
        db = SessionLocal()
        total_issues = db.query(Issue).count()
        next_val = db.execute(text("SELECT nextval('issue_number_seq')")).scalar()
        
        print("Post-migration Verification:")
        print(f" - Verified issues in database: {total_issues}")
        print(f" - Verified next allocated sequence number: {next_val}")
        
        if next_val == report['calculated_baseline']:
            print("Post-migration baseline verification: SUCCESS!")
        else:
            print(f"Post-migration baseline verification WARNING: expected {report['calculated_baseline']} but got {next_val}")
            
    except Exception as e:
        print(f"Fatal error during migration execution: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
