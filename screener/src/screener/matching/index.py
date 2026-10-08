"""Fill normalized names, blocking tokens, and identifier keys for one snapshot."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable

from sqlalchemy import delete, func, select

from screener.db.session import init_db, session_scope
from screener.db.tables import (
    EntityIdentifierRow,
    IndexedNameRow,
    NameTokenRow,
    SanctionEntityRow,
)
from screener.matching.normalize import name_tokens, normalize_identifier, normalize_name
from screener.paths import data_dir

Log = Callable[[str], None]
_BATCH = 2000
_PERSON_TYPES = ("person", "individual")


class SnapshotNotReady(RuntimeError):
    """The active snapshot is missing, or its names have not been indexed."""


def active_snapshot_id() -> str:
    path = data_dir() / "current_snapshot.txt"
    if not path.is_file():
        raise SnapshotNotReady("No sanctions snapshot is loaded.")
    snapshot_id = path.read_text(encoding="utf-8").strip()
    if not snapshot_id:
        raise SnapshotNotReady("The snapshot pointer is empty.")
    return snapshot_id


def build_index(snapshot_id: str, log: Log | None = None) -> None:
    write = log or (lambda _message: None)
    init_db()
    with session_scope() as session:
        session.execute(delete(NameTokenRow).where(NameTokenRow.snapshot_id == snapshot_id))
        session.execute(delete(EntityIdentifierRow).where(EntityIdentifierRow.snapshot_id == snapshot_id))
        people = set(
            session.scalars(
                select(SanctionEntityRow.id).where(
                    SanctionEntityRow.snapshot_id == snapshot_id,
                    func.lower(SanctionEntityRow.entity_type).in_(_PERSON_TYPES),
                )
            )
        )
        rows = session.execute(
            select(IndexedNameRow.id, IndexedNameRow.entity_id, IndexedNameRow.raw_name).where(
                IndexedNameRow.snapshot_id == snapshot_id
            )
        ).all()
        prepared: list[tuple[int, int, str, list[str]]] = []
        people_with_name: dict[str, set[int]] = defaultdict(set)
        for name_id, entity_id, raw_name in rows:
            normalized = normalize_name(raw_name)
            tokens = name_tokens(normalized)
            prepared.append((name_id, entity_id, normalized, tokens))
            if normalized and entity_id in people:
                people_with_name[normalized].add(entity_id)
        frequency = {name: len(entity_ids) for name, entity_ids in people_with_name.items()}
        _update_names(session, prepared, frequency)
        _insert_tokens(session, snapshot_id, prepared)
        _insert_identifiers(session, snapshot_id)
    write(f"indexed {len(prepared)} names")


def _update_names(session, prepared: list[tuple[int, int, str, list[str]]], frequency: dict[str, int]) -> None:  # noqa: ANN001
    statement = "UPDATE indexed_names SET normalized = ?, tokens = ?, name_frequency = ? WHERE id = ?"
    connection = session.connection()
    payload = [
        (normalized, json.dumps(tokens), frequency.get(normalized, 0), name_id)
        for name_id, _entity_id, normalized, tokens in prepared
    ]
    for start in range(0, len(payload), _BATCH):
        connection.exec_driver_sql(statement, payload[start : start + _BATCH])


def _insert_tokens(session, snapshot_id: str, prepared: list[tuple[int, int, str, list[str]]]) -> None:  # noqa: ANN001
    statement = (
        "INSERT INTO name_tokens (snapshot_id, token, entity_id, indexed_name_id) VALUES (?, ?, ?, ?)"
    )
    payload = [
        (snapshot_id, token[:64], entity_id, name_id)
        for name_id, entity_id, _normalized, tokens in prepared
        for token in tokens
    ]
    connection = session.connection()
    for start in range(0, len(payload), _BATCH):
        connection.exec_driver_sql(statement, payload[start : start + _BATCH])


def _insert_identifiers(session, snapshot_id: str) -> None:  # noqa: ANN001
    rows = session.execute(
        select(SanctionEntityRow.id, SanctionEntityRow.identifiers).where(
            SanctionEntityRow.snapshot_id == snapshot_id
        )
    ).all()
    payload: list[tuple[str, int, str]] = []
    seen: set[tuple[int, str]] = set()
    for entity_id, identifiers in rows:
        for value in identifiers or []:
            key = normalize_identifier(str(value))
            if not key or (entity_id, key) in seen:
                continue
            seen.add((entity_id, key))
            payload.append((snapshot_id, entity_id, key[:128]))
    statement = "INSERT INTO entity_identifiers (snapshot_id, entity_id, key) VALUES (?, ?, ?)"
    connection = session.connection()
    for start in range(0, len(payload), _BATCH):
        connection.exec_driver_sql(statement, payload[start : start + _BATCH])
