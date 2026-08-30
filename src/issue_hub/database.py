from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from issue_hub.config import settings
import logging

logger = logging.getLogger("issue_hub.database")

engine = create_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    """FastAPI DB dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_connection() -> bool:
    """Check database health, schema tables, and sequences (Gate 1)."""
    try:
        with engine.connect() as conn:
            # 1. Connectivity check
            conn.execute(text("SELECT 1"))
            
            # 2. Check if tables exist in the current schema
            tables = ["alembic_version", "issues", "issue_history", "lookup_values", "hub_settings"]
            for table in tables:
                exists = conn.execute(text(
                    f"SELECT EXISTS (SELECT FROM information_schema.tables "
                    f"WHERE table_name = '{table}' AND table_schema = CURRENT_SCHEMA())"
                )).scalar()
                if not exists:
                    logger.error(f"Readiness check failed: required table '{table}' does not exist.")
                    return False
            
            # 3. Check if sequence exists
            seq_exists = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.sequences "
                "WHERE sequence_name = 'issue_number_seq' AND sequence_schema = CURRENT_SCHEMA())"
            )).scalar()
            if not seq_exists:
                logger.error("Readiness check failed: sequence 'issue_number_seq' does not exist.")
                return False
                
            return True
    except Exception as e:
        logger.error(f"Database readiness check failed: {e}")
        return False
