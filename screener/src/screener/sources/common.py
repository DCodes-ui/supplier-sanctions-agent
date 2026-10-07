"""Small helpers shared by the list parsers."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from screener.domain.models import IndexedName, SanctionEntity
from screener.sources.errors import ParseError


@dataclass
class ParsedRecord:
    entity: SanctionEntity
    names: list[IndexedName] = field(default_factory=list)


@dataclass
class ParseResult:
    records: list[ParsedRecord]
    skipped: int


def collect_records(
    path: Path,
    tag: str,
    build: Callable[[ET.Element], ParsedRecord | None],
    label: str,
) -> ParseResult:
    seen = 0
    skipped = 0
    records: list[ParsedRecord] = []
    known_ids: set[str] = set()
    try:
        for _event, elem in ET.iterparse(path, events=("end",)):
            if local_name(elem.tag) != tag:
                continue
            seen += 1
            record = build(elem)
            elem.clear()
            if record is None or record.entity.source_record_id in known_ids:
                skipped += 1
                continue
            known_ids.add(record.entity.source_record_id)
            records.append(record)
    except ET.ParseError as exc:
        raise ParseError(f"{label} file is not valid XML: {exc}") from exc
    if seen == 0:
        raise ParseError(f"{label} file has no {tag} records")
    if not records:
        raise ParseError(f"{label} file has no usable {tag} records")
    return ParseResult(records=records, skipped=skipped)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split())


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = clean(value)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(text)
    return ordered


def name_rows(primary: str, aliases: list[str]) -> list[IndexedName]:
    rows = [IndexedName(raw_name=primary, is_primary=True)]
    for alias in aliases:
        if alias.casefold() == primary.casefold():
            continue
        rows.append(IndexedName(raw_name=alias, is_primary=False))
    return rows
