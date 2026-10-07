"""EU Financial Sanctions Files, XML format 1.1."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from screener.domain.models import SanctionEntity
from screener.sources.common import ParseResult, ParsedRecord, clean, collect_records, local_name, name_rows, unique

LIST_NAME = "EU Financial Sanctions Files"


def parse_eu_fsf(path: Path) -> ParseResult:
    return collect_records(path, "sanctionEntity", _entity, "EU")


def _entity(elem: ET.Element) -> ParsedRecord | None:
    record_id = clean(elem.attrib.get("logicalId"))
    names = _names(elem)
    if not record_id or not names:
        return None
    primary = names[0]
    aliases = names[1:]
    programmes = unique(
        [node.attrib.get("programme", "") for node in _children(elem, "regulation")]
    )
    countries = unique(
        [node.attrib.get("countryIso2Code", "") for node in _children(elem, "citizenship")]
        + [node.attrib.get("countryIso2Code", "") for node in _children(elem, "address")]
    )
    identifiers = unique(
        [node.attrib.get("number", "") for node in _children(elem, "identification")]
    )
    un_id = clean(elem.attrib.get("unitedNationId"))
    if un_id:
        identifiers = unique([un_id, *identifiers])
    url = ""
    for node in _children(elem, "regulation"):
        url = _child_text(node, "publicationUrl")
        if url:
            break
    subject = _children(elem, "subjectType")
    entity_type = clean(subject[0].attrib.get("code")) if subject else "unknown"
    programme = "; ".join(programmes)
    remark = _child_text(elem, "remark")
    snippet = " | ".join(part for part in (primary, programme, remark) if part)[:400]
    entity = SanctionEntity(
        source="eu_fsf",
        list_name=LIST_NAME,
        programme=programme,
        source_record_id=record_id,
        entity_type=entity_type or "unknown",
        primary_name=primary,
        aliases=aliases,
        countries=[code.upper() for code in countries],
        identifiers=identifiers,
        source_url=url,
        snippet=snippet,
    )
    return ParsedRecord(entity=entity, names=name_rows(primary, aliases))


def _names(elem: ET.Element) -> list[str]:
    strong: list[str] = []
    other: list[str] = []
    for node in _children(elem, "nameAlias"):
        name = clean(node.attrib.get("wholeName"))
        if not name:
            name = clean(
                " ".join(
                    clean(node.attrib.get(part))
                    for part in ("firstName", "middleName", "lastName")
                )
            )
        if not name:
            continue
        if node.attrib.get("strong", "").lower() == "true":
            strong.append(name)
        else:
            other.append(name)
    return unique([*strong, *other])


def _children(elem: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(elem) if local_name(child.tag) == name]


def _child_text(elem: ET.Element, name: str) -> str:
    for child in _children(elem, name):
        text = clean(child.text)
        if text:
            return text
    return ""
