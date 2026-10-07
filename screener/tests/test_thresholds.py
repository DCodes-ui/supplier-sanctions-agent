from datetime import datetime, timezone

import pytest

from screener.config import load_settings
from screener.db.session import init_db, session_scope
from screener.db.tables import IndexedNameRow, SanctionEntityRow, SnapshotRow
from screener.llm.adjudicate import adjudicate
from screener.matching.index import build_index
from screener.matching.retrieve import Candidate, MatchResult, _decide, match_supplier

SNAP = "test-snap"


def _candidate(score: float, **overrides) -> Candidate:
    fields = {
        "score": score,
        "source": "eu_fsf",
        "list_name": "EU",
        "programme": "IRQ",
        "source_record_id": "1",
        "name": "Example Name",
        "source_url": "https://example.test",
        "snippet": "Example Name",
        "agrees": True,
        "contradicts": False,
        "name_frequency": 1,
        "tokens_covered": True,
    }
    fields.update(overrides)
    return Candidate(**fields)


def test_score_bands():
    settings = load_settings()
    assert _decide("snap", "LT", settings, [_candidate(0.80)]).status == "review"
    assert (
        _decide(
            "snap",
            "LT",
            settings,
            [_candidate(0.90, agrees=False, contradicts=False, tokens_covered=False)],
        ).status
        == "review"
    )
    assert _decide("snap", "LT", settings, [_candidate(0.95)]).status == "likely_hit"


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    import screener.db.session as session

    session._engine = None
    init_db()
    with session_scope() as db:
        db.add(SnapshotRow(id=SNAP, created_at=datetime.now(timezone.utc), is_active=True))
        db.flush()
        identified = _entity("1", "Tariq Aziz", ["REG-9"])
        db.add(identified)
        identified.names.append(_name("Tariq Aziz"))
        for index in range(8):
            person = _entity(str(index + 2), "Abdul Aziz", [])
            db.add(person)
            person.names.append(_name("Abdul Aziz"))
    build_index(SNAP)
    yield
    session._engine = None


def test_exact_identifier_is_likely_hit(snapshot):
    result = match_supplier("Other Name", "IQ", "REG-9", snapshot_id=SNAP)
    assert result.decision.status == "likely_hit"
    assert result.decision.decision_basis == "identifier"


def test_common_name_without_id_is_not_likely_hit(snapshot):
    result = match_supplier("Abdul Aziz", "IQ", snapshot_id=SNAP)
    assert result.decision.status == "review"


def test_unknown_name_is_clear_and_skips_the_model(snapshot):
    result = match_supplier("Zqxvplat Holdings", "LT", snapshot_id=SNAP)
    assert result.decision.status == "clear"

    def fail_if_called(_messages):
        raise AssertionError("model was called")

    kind, decision = adjudicate(
        MatchResult(decision=result.decision, candidates=result.candidates),
        name="Zqxvplat Holdings",
        country="LT",
        registration_number=None,
        complete=fail_if_called,
    )
    assert kind == "rules"
    assert decision.status == "clear"


def _entity(record_id: str, name: str, identifiers: list[str]) -> SanctionEntityRow:
    return SanctionEntityRow(
        snapshot_id=SNAP,
        source="eu_fsf",
        list_name="EU",
        programme="IRQ",
        source_record_id=record_id,
        entity_type="person",
        primary_name=name,
        aliases=[],
        countries=["IQ"],
        identifiers=identifiers,
        source_url="https://example.test",
        snippet=name,
    )


def _name(raw_name: str) -> IndexedNameRow:
    return IndexedNameRow(snapshot_id=SNAP, raw_name=raw_name, normalized="", tokens=[], is_primary=True)
