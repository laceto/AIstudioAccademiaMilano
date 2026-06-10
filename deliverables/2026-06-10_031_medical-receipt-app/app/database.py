from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

_DB_DIR = Path(__file__).parent.parent / "data"
_DB_DIR.mkdir(exist_ok=True)
DATABASE_URL = f"sqlite:///{_DB_DIR / 'receipts.db'}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
