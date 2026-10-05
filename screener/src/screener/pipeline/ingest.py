"""Download the configured lists and store them as one snapshot.

The snapshot becomes active, and data/current_snapshot.txt is updated, only
after every required source has been downloaded and parsed.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import update

from screener.config import Settings, SourceSpec, load_settings
from screener.db.mapping import entity_row, name_row
from screener.db.session import init_db, session_scope
from screener.db.tables import SnapshotRow, SourceFileRow
from screener.paths import data_dir
from screener.sources.common import ParseResult
from screener.sources.errors import FetchError, ParseError
from screener.sources.eu_fsf import parse_eu_fsf
from screener.sources.fetch import download
from screener.sources.ofac_sdn import parse_ofac_sdn
from screener.sources.opensanctions import parse_opensanctions

Log = Callable[[str], None]
BATCH = 1000


@dataclass
class SourceOutcome:
    source_id: str
    url: str
    ok: bool
    http_status: int
    sha256: str
    path: str
    record_count: int | None
    records_skipped: int | None
    error: str | None
    parsed: ParseResult | None


@dataclass
class IngestResult:
    snapshot_id: str
    active: bool
    sources: list[SourceOutcome]


def ingest(settings: Settings | None = None, log: Log | None = None) -> IngestResult:
    loaded = settings or load_settings()
    write = log or (lambda _message: None)
    snapshot_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = data_dir() / "snapshots" / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    enabled = [source for source in loaded.sources if source.enabled]
    if not enabled:
        raise ValueError("no sources are enabled")

    outcomes = [_fetch_and_parse(source, snapshot_dir, write) for source in enabled]
    required_ok = all(outcome.ok for outcome in outcomes if _required(loaded, outcome.source_id))
    active = required_ok and any(outcome.ok for outcome in outcomes)
    _store(snapshot_id, outcomes, active=active)
    if active:
        _write_pointer(snapshot_id)
        write(f"active snapshot {snapshot_id}")
    else:
        write(f"snapshot {snapshot_id} was not activated")
    return IngestResult(snapshot_id=snapshot_id, active=active, sources=outcomes)


def _fetch_and_parse(source: SourceSpec, snapshot_dir: Path, log: Log) -> SourceOutcome:
    suffix = ".csv" if source.kind == "opensanctions_csv" else ".xml"
    dest = snapshot_dir / f"{source.id}{suffix}"
    log(f"downloading {source.id}")
    try:
        status, digest = download(source.url, dest, max_bytes=source.max_bytes)
    except FetchError as exc:
        log(f"{source.id} failed: {exc}")
        return _failed(source, str(exc), http_status=exc.http_status)
    log(f"parsing {source.id}")
    try:
        parsed = _parse(source, dest)
    except (ParseError, OSError, ValueError) as exc:
        log(f"{source.id} failed: {exc}")
        return _failed(
            source,
            str(exc),
            http_status=status,
            sha256=digest,
            path=str(dest),
        )
    except Exception as exc:
        log(f"{source.id} failed: {exc}")
        traceback.print_exc()
        return _failed(
            source,
            str(exc),
            http_status=status,
            sha256=digest,
            path=str(dest),
        )
    log(f"{source.id}: {len(parsed.records)} kept, {parsed.skipped} skipped")
    return SourceOutcome(
        source_id=source.id,
        url=source.url,
        ok=True,
        http_status=status,
        sha256=digest,
        path=str(dest),
        record_count=len(parsed.records),
        records_skipped=parsed.skipped,
        error=None,
        parsed=parsed,
    )


def _parse(source: SourceSpec, path: Path) -> ParseResult:
    if source.kind == "eu_fsf":
        return parse_eu_fsf(path)
    if source.kind == "ofac_sdn":
        return parse_ofac_sdn(path)
    if source.kind == "opensanctions_csv":
        return parse_opensanctions(path, source.skip_datasets)
    raise ParseError(f"no parser for kind {source.kind}")


def _store(snapshot_id: str, outcomes: list[SourceOutcome], *, active: bool) -> None:
    init_db()
    created_at = datetime.now(timezone.utc)
    with session_scope() as session:
        session.add(SnapshotRow(id=snapshot_id, created_at=created_at, is_active=False))
        session.flush()
        for outcome in outcomes:
            session.add(
                SourceFileRow(
                    snapshot_id=snapshot_id,
                    source=outcome.source_id,
                    url=outcome.url,
                    path=outcome.path,
                    sha256=outcome.sha256,
                    http_status=outcome.http_status,
                    fetched_at=created_at,
                    record_count=outcome.record_count,
                    records_skipped=outcome.records_skipped,
                    error=outcome.error,
                )
            )
        if active:
            for outcome in outcomes:
                if outcome.parsed is not None:
                    _insert_records(session, snapshot_id, outcome.parsed)
            session.execute(update(SnapshotRow).values(is_active=False))
            session.execute(
                update(SnapshotRow).where(SnapshotRow.id == snapshot_id).values(is_active=True)
            )


def _insert_records(session, snapshot_id: str, parsed: ParseResult) -> None:  # noqa: ANN001
    records = parsed.records
    for start in range(0, len(records), BATCH):
        chunk = records[start : start + BATCH]
        rows = [entity_row(snapshot_id, record.entity) for record in chunk]
        session.add_all(rows)
        session.flush()
        names = []
        for row, record in zip(rows, chunk, strict=True):
            for name in record.names:
                mapped = name_row(snapshot_id, name)
                mapped.entity_id = row.id
                names.append(mapped)
        session.add_all(names)


def _write_pointer(snapshot_id: str) -> None:
    target = data_dir() / "current_snapshot.txt"
    temporary = target.with_suffix(".txt.tmp")
    temporary.write_text(snapshot_id + "\n", encoding="utf-8")
    temporary.replace(target)


def _required(settings: Settings, source_id: str) -> bool:
    for source in settings.sources:
        if source.id == source_id:
            return source.required
    return True


def _failed(
    source: SourceSpec,
    message: str,
    *,
    http_status: int = 0,
    sha256: str = "",
    path: str = "",
) -> SourceOutcome:
    return SourceOutcome(
        source_id=source.id,
        url=source.url,
        ok=False,
        http_status=http_status,
        sha256=sha256,
        path=path,
        record_count=None,
        records_skipped=None,
        error=message[:2000],
        parsed=None,
    )
