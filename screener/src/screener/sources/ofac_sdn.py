"""OFAC Specially Designated Nationals list, SDN.XML."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from screener.domain.models import SanctionEntity
from screener.sources.common import ParseResult, ParsedRecord, clean, collect_records, local_name, name_rows, unique

LIST_NAME = "OFAC SDN"


def parse_ofac_sdn(path: Path) -> ParseResult:
    return collect_records(path, "sdnEntry", _entity, "OFAC")


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
