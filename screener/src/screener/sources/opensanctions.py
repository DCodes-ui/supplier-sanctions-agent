"""OpenSanctions consolidated sanctions list, targets.simple.csv.

The CSV names a dataset by its title, not by the id used in sources.yaml.
eu_fsf and us_ofac_sdn are matched on both.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from screener.domain.models import SanctionEntity
from screener.sources.common import ParseResult, ParsedRecord, clean, name_rows, unique
from screener.sources.errors import ParseError

REQUIRED_COLUMNS = ("id", "schema", "name", "dataset")
DATASET_TITLES = {
    "eu_fsf": "EU Financial Sanctions Files (FSF)",
    "us_ofac_sdn": "US OFAC Specially Designated Nationals (SDN) List",
}


def parse_opensanctions(path: Path, skip_datasets: list[str]) -> ParseResult:
    skip = _skip_tokens(skip_datasets)
    skipped = 0
    records: list[ParsedRecord] = []
    known_ids: set[str] = set()
    csv.field_size_limit(min(sys.maxsize, 2_000_000))
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ParseError("OpenSanctions file has no header")
        missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ParseError("OpenSanctions file is missing columns: " + ", ".join(missing))
        for row in reader:
            record = _entity(row, skip)
            if record is None:
                skipped += 1
                continue
            if record.entity.source_record_id in known_ids:
                skipped += 1
                continue
            known_ids.add(record.entity.source_record_id)
            records.append(record)
    if not records:
        raise ParseError("OpenSanctions file has no usable rows")
    return ParseResult(records=records, skipped=skipped)


def _entity(row: dict[str, str | None], skip: set[str]) -> ParsedRecord | None:
    record_id = clean(row.get("id"))
    primary = clean(row.get("name"))
    datasets = _split(row.get("dataset"))
    if not record_id or not primary:
        return None
    # The CSV lists every dataset on the row. Skip it when any of those is a
    # list we already store from the official EU or OFAC file.
    if datasets and any(item.casefold() in skip for item in datasets):
        return None
    aliases = [alias for alias in _split(row.get("aliases")) if alias.casefold() != primary.casefold()]
    countries = [_country(item) for item in _split(row.get("countries"))]
    programme = "; ".join(_split(row.get("program_ids")))
    list_name = "; ".join(datasets) or "OpenSanctions"
    measure = clean(row.get("sanctions"))
    snippet = " | ".join(part for part in (primary, programme, measure) if part)[:400]
    entity = SanctionEntity(
        source=f"opensanctions:{list_name}",
        list_name=list_name,
        programme=programme,
        source_record_id=record_id,
        entity_type=clean(row.get("schema")) or "unknown",
        primary_name=primary,
        aliases=unique(aliases),
        countries=unique(countries),
        identifiers=unique(_split(row.get("identifiers"))),
        source_url=f"https://www.opensanctions.org/entities/{record_id}/",
        snippet=snippet,
    )
    return ParsedRecord(entity=entity, names=name_rows(primary, entity.aliases))


def _skip_tokens(skip_datasets: list[str]) -> set[str]:
    tokens: set[str] = set()
    for item in skip_datasets:
        text = item.strip()
        if not text:
            continue
        tokens.add(text.casefold())
        title = DATASET_TITLES.get(text)
        if title:
            tokens.add(title.casefold())
    return tokens


def _split(value: str | None) -> list[str]:
    if not value:
        return []
    parts: list[str] = []
    for part in value.split(";"):
        text = clean(part.strip().strip('"'))
        if text:
            parts.append(text)
    return parts


def _country(value: str) -> str:
    text = clean(value)
    if len(text) == 2 and text.isalpha():
        return text.upper()
    return text
