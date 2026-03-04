import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

def _db_url() -> str:
    db_path = os.getenv("DB_PATH", "./app.db")
    # SQLite file path
    return f"sqlite:///{db_path}"

class Base(DeclarativeBase):
    pass

engine = create_engine(
    _db_url(),
    connect_args={"check_same_thread": False},  # needed for SQLite with threads
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
