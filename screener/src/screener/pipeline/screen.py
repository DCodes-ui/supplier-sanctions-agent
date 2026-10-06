"""One supplier screen: match first, then ask Grok only if the shortlist is non-empty."""

from __future__ import annotations

from dataclasses import dataclass

from screener.config import Settings
from screener.domain.models import ScreeningDecision
from screener.llm.adjudicate import adjudicate, needs_model
from screener.matching.retrieve import Candidate, match_supplier


@dataclass(frozen=True)
class ScreenResult:
    decision: ScreeningDecision
    candidates: list[Candidate]
    adjudication: str


def screen_supplier(
    name: str,
    country: str,
    registration_number: str | None = None,
    snapshot_id: str | None = None,
    settings: Settings | None = None,
) -> ScreenResult:
    match = match_supplier(
        name,
        country,
        registration_number,
        snapshot_id=snapshot_id,
        settings=settings,
    )
    adjudication, decision = adjudicate(
        match,
        name=name,
        country=country,
        registration_number=registration_number,
        settings=settings,
    )
    return ScreenResult(decision=decision, candidates=match.candidates, adjudication=adjudication)


def adjudication_label(result: ScreenResult) -> str:
    if result.adjudication == "llm":
        return "llm"
    if result.adjudication == "fallback":
        return "rules (model output rejected)"
    if needs_model_result(result) and result.adjudication == "rules":
        return "rules (no XAI_API_KEY)"
    return "rules"


def needs_model_result(result: ScreenResult) -> bool:
    from screener.matching.retrieve import MatchResult

    return needs_model(MatchResult(decision=result.decision, candidates=result.candidates))
