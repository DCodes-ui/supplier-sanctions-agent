import json

from screener.config import load_settings
from screener.llm.adjudicate import adjudicate
from screener.matching.retrieve import Candidate, MatchResult, _decide


def _match() -> MatchResult:
    settings = load_settings()
    candidate = Candidate(
        score=0.8,
        source="eu_fsf",
        list_name="EU",
        programme="IRQ",
        source_record_id="1",
        name="Example Name",
        source_url="https://example.test/1",
        snippet="Example Name",
        agrees=True,
        contradicts=False,
        name_frequency=1,
        tokens_covered=True,
    )
    return MatchResult(decision=_decide("snap", "LT", settings, [candidate]), candidates=[candidate])


def test_extra_field_is_dropped_and_review_is_kept():
    def complete(_messages):
        return json.dumps(
            {
                "status": "review",
                "matched_entity": {
                    "name": "ignored",
                    "list": "ignored",
                    "programme": "ignored",
                    "source_record_id": "1",
                },
                "match_confidence": 0.4,
                "evidence": [],
                "recommended_action": "nope",
                "rationale": "Needs a person.",
                "hallucinated": True,
            }
        )

    kind, decision = adjudicate(
        _match(),
        name="Example Name",
        country="LT",
        registration_number=None,
        complete=complete,
    )
    assert kind == "llm"
    assert decision.status == "review"
    assert decision.matched_entity is not None
    assert decision.matched_entity.name == "Example Name"
    assert decision.evidence[0].url == "https://example.test/1"


def test_invalid_payload_falls_back_to_rules():
    match = _match()

    def complete(payload):
        return json.dumps(payload)

    for payload in ({"status": "blocked"}, {"rationale": "no status"}):
        kind, decision = adjudicate(
            match,
            name="Example Name",
            country="LT",
            registration_number=None,
            complete=lambda _messages, payload=payload: complete(payload),
        )
        assert kind == "fallback"
        assert decision.decision_basis == "fallback_rules"
        assert decision.status == match.decision.status
