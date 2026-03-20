from fastapi import Depends
from sqlalchemy.orm import Session
from core.database.engine import get_session


def get_db(session: Session = Depends(get_session)) -> Session:
    """FastAPI dependency to get a database session."""
    return session
