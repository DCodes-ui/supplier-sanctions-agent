"""Convert domain objects to rows and back, revalidating on the way out."""

from __future__ import annotations

from datetime import datetime, timezone

from screener.db.tables import IndexedNameRow, SanctionEntityRow, ScreeningRow
from screener.domain.models import (
    IndexedName,
    SanctionEntity,
    ScreeningDecision,
    ScreeningRecord,
    parse_model,
)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def entity_row(snapshot_id: str, entity: SanctionEntity) -> SanctionEntityRow:
    return SanctionEntityRow(
        snapshot_id=snapshot_id,
        source=entity.source,
        list_name=entity.list_name,
        programme=entity.programme,
        source_record_id=entity.source_record_id,
        entity_type=entity.entity_type,
        primary_name=entity.primary_name,
        aliases=list(entity.aliases),
        countries=list(entity.countries),
        identifiers=list(entity.identifiers),
        source_url=entity.source_url,
        snippet=entity.snippet,
    )


def name_row(snapshot_id: str, name: IndexedName) -> IndexedNameRow:
    return IndexedNameRow(
        snapshot_id=snapshot_id,
        raw_name=name.raw_name,
        normalized=name.normalized,
        tokens=list(name.tokens),
        is_primary=name.is_primary,
        name_frequency=name.name_frequency,
    )


def screening_row(record: ScreeningRecord) -> ScreeningRow:
    decision = record.decision
    matched = None if decision.matched_entity is None else decision.matched_entity.model_dump()
    return ScreeningRow(
        id=record.id,
        created_at=as_utc(record.created_at),
        snapshot_id=decision.snapshot_id,
        supplier_id=record.supplier_id,
        query_name=record.query_name,
        query_country=record.query_country,
        query_registration_number=record.query_registration_number,
        status=decision.status,
        match_confidence=decision.match_confidence,
        matched_entity=matched,
        evidence=[item.model_dump() for item in decision.evidence],
        recommended_action=decision.recommended_action,
        decision_basis=decision.decision_basis,
        rationale=decision.rationale,
        adjudication=record.adjudication,
    )


def screening_from_row(row: ScreeningRow) -> ScreeningRecord:
    decision = parse_model(
        ScreeningDecision,
        {
            "status": row.status,
            "matched_entity": row.matched_entity,
            "match_confidence": row.match_confidence,
            "evidence": row.evidence,
            "recommended_action": row.recommended_action,
            "snapshot_id": row.snapshot_id,
            "decision_basis": row.decision_basis,
            "rationale": row.rationale,
        },
    )
    return ScreeningRecord(
        id=row.id,
        created_at=as_utc(row.created_at),
        supplier_id=row.supplier_id,
        query_name=row.query_name,
        query_country=row.query_country,
        query_registration_number=row.query_registration_number,
        decision=decision,
        adjudication=row.adjudication,
    )
