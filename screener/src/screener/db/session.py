"""Engine and session. The URL selects SQLite or Postgres; the tables stay the same."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from screener.db.base import Base
from screener.paths import data_dir, database_url

_engine: Engine | None = None


def make_engine(url: str | None = None) -> Engine:
    target = url or database_url()
    if target.startswith("sqlite:///"):
        path = Path(target.removeprefix("sqlite:///"))
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(target, connect_args={"check_same_thread": False})
        _enable_sqlite_foreign_keys(engine)
        return engine
    return create_engine(target)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = make_engine()
    return _engine


def init_db(engine: Engine | None = None) -> Engine:
    """Create tables if they are missing. Does not download sanctions data."""

    from screener.db import tables as tables  # noqa: F401

    bound = engine or get_engine()
    if bound.dialect.name == "sqlite":
        data_dir().mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bound)
    return bound


def session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or get_engine(), expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    factory = session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
