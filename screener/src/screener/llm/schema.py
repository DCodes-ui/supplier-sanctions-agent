"""JSON schema sent to Grok, and the checks applied to its answer."""

from __future__ import annotations

from screener.domain.models import MatchedEntity, Status, parse_model
from screener.matching.retrieve import Candidate, MatchResult, ceiling_status

MODEL_NAME = "grok-4.7"
API_BASE = "https://api.x.ai/v1"

DECISION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "status",
        "matched_entity",
        "match_confidence",
        "evidence",
        "recommended_action",
        "rationale",
    ],
    "properties": {
        "status": {"type": "string", "enum": ["clear", "review", "likely_hit"]},
        "matched_entity": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "list", "programme", "source_record_id"],
                    "properties": {
                        "name": {"type": "string"},
                        "list": {"type": "string"},
                        "programme": {"type": "string"},
                        "source_record_id": {"type": "string"},
                    },
                },
            ]
        },
        "match_confidence": {"type": "number"},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source", "url", "snippet", "kind"],
                "properties": {
                    "source": {"type": "string"},
                    "url": {"type": "string"},
                    "snippet": {"type": "string"},
                    "kind": {"type": "string", "enum": ["list_match", "country_risk"]},
                },
            },
        },
        "recommended_action": {"type": "string"},
        "rationale": {"type": "string"},
    },
}


class AdjudicationError(Exception):
    """The model output could not be accepted."""


def ceilings(match: MatchResult, settings) -> dict[str, str]:  # noqa: ANN001
    """Strongest status allowed for each shortlisted record."""

    if match.decision.decision_basis == "identifier" and match.decision.status == "review":
        return {candidate.source_record_id: "review" for candidate in match.candidates}
    return {
        candidate.source_record_id: ceiling_status(candidate, settings) for candidate in match.candidates
    }


def validate_adjudication(payload: object, match: MatchResult, settings) -> tuple[Status, MatchedEntity | None, float, str, Candidate | None]:  # noqa: ANN001
    """Drop unknown fields, then reject a status the score rules do not allow."""

    from screener.llm.models import ModelDecision

    try:
        parsed = parse_model(ModelDecision, payload)
    except Exception as exc:
        raise AdjudicationError(str(exc)) from exc
    allowed = ceilings(match, settings)
    by_id = {candidate.source_record_id: candidate for candidate in match.candidates}
    if parsed.status == "clear":
        if parsed.matched_entity is not None:
            raise AdjudicationError("clear cannot name a matched entity")
        if "likely_hit" in allowed.values():
            raise AdjudicationError("a likely_hit candidate cannot be cleared; return review")
        return "clear", None, parsed.match_confidence, parsed.rationale, None
    if parsed.matched_entity is None:
        if parsed.status == "likely_hit":
            raise AdjudicationError("likely_hit requires a matched entity from the shortlist")
        return "review", None, parsed.match_confidence, parsed.rationale, None
    chosen = by_id.get(parsed.matched_entity.source_record_id)
    if chosen is None:
        raise AdjudicationError("matched_entity is not one of the supplied candidates")
    ceiling = allowed[chosen.source_record_id]
    if parsed.status == "likely_hit" and ceiling != "likely_hit":
        raise AdjudicationError(
            f"candidate {chosen.source_record_id} has ceiling review and cannot be a likely_hit"
        )
    matched = MatchedEntity(
        name=chosen.name,
        list=chosen.list_name,
        programme=chosen.programme,
        source_record_id=chosen.source_record_id,
    )
    return parsed.status, matched, parsed.match_confidence, parsed.rationale, chosen
