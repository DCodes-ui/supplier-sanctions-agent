"""One supplier screen: match first, then ask Grok only if the shortlist is non-empty."""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import select

from screener.config import Settings
from screener.db.mapping import screening_from_row, screening_row
from screener.db.session import init_db, session_scope
from screener.db.tables import ScreeningRow, SnapshotRow, SourceFileRow
from screener.domain.models import ScreeningDecision, ScreeningInput, ScreeningRecord
from screener.llm.adjudicate import adjudicate, needs_model
from screener.matching.retrieve import Candidate, match_supplier
from screener.pipeline.ingest import ingest


@dataclass(frozen=True)
class ScreenResult:
    decision: ScreeningDecision
    candidates: list[Candidate]
    adjudication: str


def screen_supplier(
    name: str,
    country: str,
    registration_number: str | None = None,
    snapshot_id: str | None = None,
    settings: Settings | None = None,
) -> ScreenResult:
    match = match_supplier(
        name,
        country,
        registration_number,
        snapshot_id=snapshot_id,
        settings=settings,
    )
    adjudication, decision = adjudicate(
        match,
        name=name,
        country=country,
        registration_number=registration_number,
        settings=settings,
    )
    return ScreenResult(decision=decision, candidates=match.candidates, adjudication=adjudication)


@dataclass(frozen=True)
class StoredScreen:
    record: ScreeningRecord
    adjudication: str


def run_screen(
    name: str,
    country: str,
    registration_number: str | None = None,
    supplier_id: str | None = None,
    settings: Settings | None = None,
) -> StoredScreen:
    supplier = ScreeningInput(
        name=name,
        country=country,
        registration_number=registration_number,
        supplier_id=supplier_id,
    )
    result = screen_supplier(
        supplier.name,
        supplier.country,
        supplier.registration_number,
        settings=settings,
    )
    record = ScreeningRecord(
        id=uuid.uuid4().hex,
        created_at=datetime.now(timezone.utc),
        supplier_id=supplier.supplier_id,
        query_name=supplier.name,
        query_country=supplier.country,
        query_registration_number=supplier.registration_number,
        decision=result.decision,
    )
    init_db()
    with session_scope() as session:
        session.add(screening_row(record))
    return StoredScreen(record=record, adjudication=result.adjudication)


def run_batch(rows: list[ScreeningInput], settings: Settings | None = None) -> list[StoredScreen]:
    return [
        run_screen(
            row.name,
            row.country,
            row.registration_number,
            row.supplier_id,
            settings=settings,
        )
        for row in rows
    ]


def parse_batch_csv(text: str) -> list[ScreeningInput]:
    reader = csv.DictReader(io.StringIO(text))
    fields = set(reader.fieldnames or [])
    required = {"supplier_id", "name", "country", "registration_number"}
    if not required <= fields:
        missing = ", ".join(sorted(required - fields))
        raise ValueError(f"CSV is missing columns: {missing}")
    rows: list[ScreeningInput] = []
    for raw in reader:
        if not (raw.get("name") or "").strip():
            continue
        try:
            rows.append(ScreeningInput.model_validate(raw))
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc
    return rows


def screenings_csv(items: list[StoredScreen]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "supplier_id",
            "name",
            "country",
            "registration_number",
            "status",
            "match_confidence",
            "matched_name",
            "list",
            "programme",
            "decision_basis",
            "snapshot_id",
            "adjudication",
        ],
    )
    writer.writeheader()
    for item in items:
        decision = item.record.decision
        matched = decision.matched_entity
        writer.writerow(
            {
                "supplier_id": item.record.supplier_id or "",
                "name": item.record.query_name,
                "country": item.record.query_country,
                "registration_number": item.record.query_registration_number or "",
                "status": decision.status,
                "match_confidence": f"{decision.match_confidence:.2f}",
                "matched_name": "" if matched is None else matched.name,
                "list": "" if matched is None else matched.list,
                "programme": "" if matched is None else matched.programme,
                "decision_basis": decision.decision_basis,
                "snapshot_id": decision.snapshot_id,
                "adjudication": item.adjudication,
            }
        )
    return buffer.getvalue()


def list_screenings(limit: int = 50) -> list[ScreeningRecord]:
    init_db()
    with session_scope() as session:
        rows = session.scalars(
            select(ScreeningRow).order_by(ScreeningRow.created_at.desc()).limit(limit)
        ).all()
        return [screening_from_row(row) for row in rows]


def get_screening(screening_id: str) -> ScreeningRecord | None:
    init_db()
    with session_scope() as session:
        row = session.get(ScreeningRow, screening_id)
        return None if row is None else screening_from_row(row)


def dataset_status(snapshot_id: str | None = None) -> dict:
    init_db()
    with session_scope() as session:
        if snapshot_id is None:
            snapshot = session.scalar(select(SnapshotRow).where(SnapshotRow.is_active.is_(True)))
            snapshot_id = None if snapshot is None else snapshot.id
            active = snapshot is not None
        else:
            snapshot = session.get(SnapshotRow, snapshot_id)
            active = bool(snapshot and snapshot.is_active)
        files = []
        if snapshot_id is not None:
            files = session.scalars(
                select(SourceFileRow).where(SourceFileRow.snapshot_id == snapshot_id)
            ).all()
        return {
            "snapshot_id": snapshot_id,
            "active": active,
            "sources": [
                {
                    "source": row.source,
                    "sha256": row.sha256,
                    "record_count": row.record_count,
                    "records_skipped": row.records_skipped,
                    "error": row.error,
                    "fetched_at": row.fetched_at.isoformat(),
                }
                for row in files
            ],
        }


def refresh_datasets() -> dict:
    result = ingest()
    status = dataset_status(result.snapshot_id)
    status["active"] = result.active
    return status


def adjudication_label(result: ScreenResult) -> str:
    if result.adjudication == "llm":
        return "llm"
    if result.adjudication == "fallback":
        return "rules (model output rejected)"
    if needs_model_result(result) and result.adjudication == "rules":
        return "rules (no XAI_API_KEY)"
    return "rules"


def needs_model_result(result: ScreenResult) -> bool:
    from screener.matching.retrieve import MatchResult

    return needs_model(MatchResult(decision=result.decision, candidates=result.candidates))
