from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from core.config import settings

# Create engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


def create_db_tables() -> None:
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)


def get_session():
    """Get a new database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
