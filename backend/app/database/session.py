from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# Create synchronous engine with connection pooling and connect timeout
_connect_args = {"check_same_thread": False} if "sqlite" in settings.sync_database_url else {"connect_timeout": 15}
engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a SQLAlchemy database session per request
    and ensures proper closing after request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
