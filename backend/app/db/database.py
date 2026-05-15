from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# Railway (and Heroku) supply postgres:// — SQLAlchemy 2.x requires postgresql://
_url = settings.database_url.replace("postgres://", "postgresql://", 1)

# check_same_thread is SQLite-only; omit it for PostgreSQL
_connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}

engine = create_engine(_url, connect_args=_connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()