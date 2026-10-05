"""Small helpers shared by the list parsers."""

from __future__ import annotations

from dataclasses import dataclass, field

from screener.domain.models import IndexedName, SanctionEntity


@dataclass
class ParsedRecord:
    entity: SanctionEntity
    names: list[IndexedName] = field(default_factory=list)


@dataclass
class ParseResult:
    records: list[ParsedRecord]
    skipped: int


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
