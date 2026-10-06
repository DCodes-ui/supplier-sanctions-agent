"""Repeatable score-band eval. It does not call Grok."""

from __future__ import annotations

import json
from collections import Counter

from sqlalchemy import select

from screener.db.session import init_db, session_scope
from screener.db.tables import IndexedNameRow, SanctionEntityRow
from screener.matching.countries import country_codes
from screener.matching.index import active_snapshot_id
from screener.matching.normalize import name_tokens
from screener.matching.retrieve import match_supplier
from screener.paths import screener_root

CASES_PATH = screener_root() / "eval" / "cases.jsonl"
RECALL_TARGET = 0.98
PRECISION_TARGET = 0.95

_NEGATIVE_NAMES = (
    "Northwind Timber",
    "Baltic Oak Logistics",
    "Sventoji Glass",
    "Riga Linen Workshop",
    "Tallinn Paper Mill",
    "Neringa Tools",
    "Daugava Brick",
    "Saaremaa Wool",
    "Curonian Nets",
    "Zemaitija Malt",
)


def cases_path():
    return CASES_PATH


def write_cases() -> int:
    snapshot_id = active_snapshot_id()
    cases = _build_cases(snapshot_id)
    CASES_PATH.parent.mkdir(parents=True, exist_ok=True)
    CASES_PATH.write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases),
        encoding="utf-8",
    )
    return len(cases)


def evaluate() -> int:
    if not CASES_PATH.is_file():
        raise FileNotFoundError(f"Missing {CASES_PATH}. Run: python -m screener eval --write")
    cases = [json.loads(line) for line in CASES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    snapshot_id = active_snapshot_id()
    if any(case["snapshot_id"] != snapshot_id for case in cases):
        raise RuntimeError("Cases were built for a different snapshot. Run: python -m screener eval --write")

    results = []
    for case in cases:
        decision = match_supplier(
            case["name"],
            case["country"],
            case.get("registration_number"),
            snapshot_id=snapshot_id,
        ).decision
        results.append((case, decision.status))

    positives = [(case, status) for case, status in results if case["group"] == "positive"]
    likely = [(case, status) for case, status in results if case["expect"] == "likely_hit"]
    common = [(case, status) for case, status in results if case["group"] == "common"]
    recall_hits = sum(status in {"review", "likely_hit"} for _case, status in positives)
    precision_hits = sum(status == "likely_hit" for _case, status in likely)
    common_hits = sum(status == "likely_hit" for _case, status in common)
    recall = recall_hits / len(positives) if positives else 0
    precision = precision_hits / len(likely) if likely else 0

    print(f"snapshot {snapshot_id}")
    print(f"cases {len(cases)}")
    print(f"recall {recall:.2f} ({recall_hits}/{len(positives)}) target {RECALL_TARGET:.2f}")
    print(f"likely_hit precision {precision:.2f} ({precision_hits}/{len(likely)}) target {PRECISION_TARGET:.2f}")
    print(f"common-name likely_hit {common_hits} target 0")
    misses = [
        f"{case['note']}: {case['name']} -> {status}, expected {case['expect']}"
        for case, status in results
        if not _passed(case, status)
    ]
    if misses:
        print("misses:")
        for line in misses:
            print(f"- {line}")
    ok = recall >= RECALL_TARGET and precision >= PRECISION_TARGET and common_hits == 0
    if recall < RECALL_TARGET:
        print("A shortened listed name was cleared. The next change would be discard_below.")
    if precision < PRECISION_TARGET:
        print("A likely hit was wrong. The next change would be likely_hit_at.")
    return 0 if ok else 1


def _passed(case: dict, status: str) -> bool:
    expect = case["expect"]
    if expect == "flagged":
        return status in {"review", "likely_hit"}
    if expect == "not_likely_hit":
        return status != "likely_hit"
    return status == expect


def _build_cases(snapshot_id: str) -> list[dict]:
    init_db()
    with session_scope() as session:
        rows = session.execute(
            select(
                SanctionEntityRow.id,
                SanctionEntityRow.primary_name,
                SanctionEntityRow.countries,
                IndexedNameRow.normalized,
                IndexedNameRow.name_frequency,
            )
            .join(
                IndexedNameRow,
                (IndexedNameRow.entity_id == SanctionEntityRow.id) & IndexedNameRow.is_primary.is_(True),
            )
            .where(SanctionEntityRow.snapshot_id == snapshot_id)
        ).all()
        usable = []
        counts = Counter(normalized for _id, _name, _countries, normalized, _freq in rows)
        for entity_id, name, countries, normalized, frequency in rows:
            codes = _codes(countries)
            tokens = [token for token in name_tokens(normalized) if len(token) >= 4]
            if (
                codes
                and frequency < 8
                and counts[normalized] == 1
                and len(tokens) >= 2
                and len(name) <= 80
            ):
                usable.append((entity_id, name, codes[0], normalized))
        usable.sort(key=lambda item: item[3])
        chosen = usable[:30]
        alias_rows = session.execute(
            select(IndexedNameRow.entity_id, IndexedNameRow.raw_name).where(
                IndexedNameRow.entity_id.in_([item[0] for item in chosen]),
                IndexedNameRow.is_primary.is_(False),
            )
        ).all()
    aliases: dict[int, str] = {}
    for entity_id, raw_name in alias_rows:
        aliases.setdefault(entity_id, raw_name)

    cases: list[dict] = []
    for entity_id, name, country, normalized in chosen[:17]:
        cases.append(_case(snapshot_id, "positive", "likely_hit", name, country, "exact"))
    for entity_id, name, country, normalized in chosen[12:20]:
        cases.append(_case(snapshot_id, "positive", "flagged", f"{name} UAB", country, "legal-form"))
    for entity_id, name, country, normalized in chosen:
        alias = aliases.get(entity_id)
        if alias and alias.casefold() != name.casefold():
            cases.append(_case(snapshot_id, "positive", "flagged", alias, country, "alias"))
        if len([case for case in cases if case["note"] == "alias"]) >= 8:
            break
    for entity_id, name, country, normalized in chosen:
        tokens = name.split()
        if len(tokens) >= 3:
            partial = " ".join(tokens[:1] + tokens[2:])
            cases.append(_case(snapshot_id, "positive", "flagged", partial, country, "missing-middle"))
        if len([case for case in cases if case["note"] == "missing-middle"]) >= 5:
            break
    for entity_id, name, country, normalized in chosen:
        if len(name) >= 20:
            cases.append(_case(snapshot_id, "hard", "not_likely_hit", name.split()[0], country, "substring"))
        if len([case for case in cases if case["note"] == "substring"]) >= 2:
            break

    cases.extend(_common_cases(snapshot_id))
    cases.append(_case(snapshot_id, "hard", "review", "Saddam Hussein", "LT", "country-conflict"))
    for name in _NEGATIVE_NAMES:
        decision = match_supplier(name, "LT", snapshot_id=snapshot_id).decision
        if decision.status == "clear":
            cases.append(_case(snapshot_id, "negative", "clear", name, "LT", "negative"))
        if len([case for case in cases if case["note"] == "negative"]) >= 8:
            break
    return cases


def _common_cases(snapshot_id: str) -> list[dict]:
    init_db()
    with session_scope() as session:
        row = session.execute(
            select(IndexedNameRow.raw_name, SanctionEntityRow.countries)
            .join(SanctionEntityRow, SanctionEntityRow.id == IndexedNameRow.entity_id)
            .where(
                IndexedNameRow.snapshot_id == snapshot_id,
                IndexedNameRow.is_primary.is_(True),
                IndexedNameRow.name_frequency >= 8,
            )
            .limit(1)
        ).first()
    if row is None:
        return []
    name, countries = row
    country = _codes(countries)
    country_code = country[0] if country else "IQ"
    return [
        _case(snapshot_id, "common", "review", name, country_code, "common-name"),
        _case(snapshot_id, "common", "review", name, country_code, "common-name-wrong-id", "ZZZ-NOT-REAL"),
    ]


def _codes(countries: list[str] | None) -> list[str]:
    found: list[str] = []
    for value in countries or []:
        found.extend(sorted(country_codes(value)))
    return found


def _case(
    snapshot_id: str,
    group: str,
    expect: str,
    name: str,
    country: str,
    note: str,
    registration_number: str | None = None,
) -> dict:
    return {
        "snapshot_id": snapshot_id,
        "group": group,
        "expect": expect,
        "name": name,
        "country": country,
        "registration_number": registration_number,
        "note": note,
    }
