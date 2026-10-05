"""OFAC Specially Designated Nationals list, SDN.XML."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from screener.domain.models import SanctionEntity
from screener.sources.common import ParseResult, ParsedRecord, clean, local_name, name_rows, unique
from screener.sources.errors import ParseError

LIST_NAME = "OFAC SDN"


def parse_ofac_sdn(path: Path) -> ParseResult:
    seen = 0
    skipped = 0
    records: list[ParsedRecord] = []
    known_ids: set[str] = set()
    try:
        for _event, elem in ET.iterparse(path, events=("end",)):
            if local_name(elem.tag) != "sdnEntry":
                continue
            seen += 1
            record = _entity(elem)
            elem.clear()
            if record is None:
                skipped += 1
                continue
            if record.entity.source_record_id in known_ids:
                skipped += 1
                continue
            known_ids.add(record.entity.source_record_id)
            records.append(record)
    except ET.ParseError as exc:
        raise ParseError(f"OFAC file is not valid XML: {exc}") from exc
    if seen == 0:
        raise ParseError("OFAC file has no sdnEntry records")
    if not records:
        raise ParseError("OFAC file has no usable sdnEntry records")
    return ParseResult(records=records, skipped=skipped)


def _entity(elem: ET.Element) -> ParsedRecord | None:
    record_id = _text(elem, "uid")
    primary = _join_name(_text(elem, "firstName"), _text(elem, "lastName"))
    if not record_id or not primary:
        return None
    aliases: list[str] = []
    for aka in _descendants(elem, "aka"):
        alias = _join_name(_text(aka, "firstName"), _text(aka, "lastName"))
        if alias:
            aliases.append(alias)
    aliases = unique(aliases)
    programmes = unique(_texts(elem, "program"))
    countries = unique(_texts(elem, "country") + _texts(elem, "idCountry"))
    identifiers = unique(_texts(elem, "idNumber"))
    programme = "; ".join(programmes)
    entity_type = _text(elem, "sdnType") or "unknown"
    entity = SanctionEntity(
        source="ofac_sdn",
        list_name=LIST_NAME,
        programme=programme,
        source_record_id=record_id,
        entity_type=entity_type,
        primary_name=primary,
        aliases=[alias for alias in aliases if alias.casefold() != primary.casefold()],
        countries=countries,
        identifiers=identifiers,
        source_url=f"https://sanctionssearch.ofac.treas.gov/Details.aspx?id={record_id}",
        snippet=" | ".join(part for part in (primary, programme) if part)[:400],
    )
    return ParsedRecord(entity=entity, names=name_rows(entity.primary_name, entity.aliases))


def _join_name(first: str, last: str) -> str:
    return clean(" ".join(part for part in (first, last) if part))


def _text(elem: ET.Element, name: str) -> str:
    for child in list(elem):
        if local_name(child.tag) == name:
            return clean(child.text)
    return ""


def _texts(elem: ET.Element, name: str) -> list[str]:
    return [clean(node.text) for node in elem.iter() if local_name(node.tag) == name]


def _descendants(elem: ET.Element, name: str) -> list[ET.Element]:
    return [node for node in elem.iter() if local_name(node.tag) == name]
