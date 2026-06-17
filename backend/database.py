"""Подключение к MySQL через SQLAlchemy. Точка входа: Base, SessionLocal, get_db()."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # лечит MySQL 
    pool_recycle=3600,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI-зависимость: открывает сессию на запрос и гарантированно закрывает."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
