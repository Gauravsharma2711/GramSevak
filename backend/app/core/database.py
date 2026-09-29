import logging
from typing import Generator, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine with connection pooling settings suitable for cloud Postgres / Supabase
engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
    echo=settings.DEBUG and settings.ENVIRONMENT == "development",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request
    and ensures it is properly closed when the request is done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> Dict[str, Any]:
    """
    Check if the PostgreSQL database is reachable and fetch diagnostic metrics.
    Returns a dictionary with status, message, table details, and row counts.
    """
    try:
        with engine.connect() as conn:
            # 1. Test live PostgreSQL query
            conn.execute(text("SELECT 1"))
            
            # 2. Check table row counts
            panchayat_rows = conn.execute(text("SELECT count(*) FROM panchayat_weather_data;")).scalar()
            forecast_rows = conn.execute(text("SELECT count(*) FROM downscaled_forecasts;")).scalar()
            
        return {
            "connected": True,
            "status": "healthy",
            "database_type": "PostgreSQL (Supabase)",
            "tables": {
                "panchayat_weather_data": {
                    "exists": True,
                    "rows": panchayat_rows
                },
                "downscaled_forecasts": {
                    "exists": True,
                    "rows": forecast_rows
                }
            },
            "message": "Successfully connected to Supabase PostgreSQL database."
        }
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return {
            "connected": False,
            "status": "unhealthy",
            "database_type": "PostgreSQL (Supabase)",
            "tables": {},
            "error": "Database service is unreachable or encountering connection errors.",
            "message": "Database connection failed."
        }
