import os
import sqlite3
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

def _resolve_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        # Railway/Heroku Postgres URLs use postgres:// — SQLAlchemy needs postgresql://
        return url.replace("postgres://", "postgresql://", 1)
    # Default: SQLite next to this package
    db_dir = Path(__file__).parent.parent / "data"
    db_dir.mkdir(exist_ok=True)
    return f"sqlite:///{db_dir / 'receipts.db'}"

DATABASE_URL = _resolve_database_url()

_is_sqlite = DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(Engine, "connect")
def _set_wal_mode(dbapi_conn, _record):
    if isinstance(dbapi_conn, sqlite3.Connection):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import Receipt  # noqa: F401 — registers the table
    Base.metadata.create_all(bind=engine)


def check_db_health() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
