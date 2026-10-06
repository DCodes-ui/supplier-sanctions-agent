"""Ask Grok 4.7 to accept or lower the shortlist. It cannot raise a score band."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

from screener.config import Settings, load_settings
from screener.domain.models import Evidence, ScreeningDecision, parse_model
from screener.llm.schema import (
    API_BASE,
    DECISION_SCHEMA,
    MODEL_NAME,
    AdjudicationError,
    validate_adjudication,
)
from screener.matching.retrieve import Candidate, MatchResult
from screener.paths import load_project_env

Complete = Callable[[list[dict[str, str]]], str]


def needs_model(match: MatchResult) -> bool:
    if not match.candidates:
        return False
    if match.decision.decision_basis == "identifier" and match.decision.status == "likely_hit":
        return False
    return True


def adjudicate(
    match: MatchResult,
    *,
    name: str,
    country: str,
    registration_number: str | None,
    settings: Settings | None = None,
    complete: Complete | None = None,
) -> tuple[str, ScreeningDecision]:
    """Return (adjudication, decision).

    adjudication is llm, rules, or fallback. rules means the model was not called.
    """

    loaded = settings or load_settings()
    if not needs_model(match):
        return "rules", match.decision
    if complete is None:
        load_project_env()
    if complete is None and not os.environ.get("XAI_API_KEY"):
        return "rules", match.decision
    caller = complete or _complete_with_grok
    messages = [
        {"role": "system", "content": loaded.prompt},
        {"role": "user", "content": _user_payload(match, loaded, name, country, registration_number)},
    ]
    try:
        raw = caller(messages)
        return "llm", _accept(raw, match, loaded)
    except (AdjudicationError, OSError, ValueError, TimeoutError) as first_error:
        previous = raw if "raw" in locals() else ""
        messages.append({"role": "assistant", "content": previous or "{}"})
        messages.append(
            {
                "role": "user",
                "content": f"That response was rejected: {first_error}. Return a corrected object.",
            }
        )
        try:
            repaired = caller(messages)
            return "llm", _accept(repaired, match, loaded)
        except (AdjudicationError, OSError, ValueError, TimeoutError):
            return "fallback", _fallback(match.decision)


def _accept(raw: str, match: MatchResult, settings: Settings) -> ScreeningDecision:
    payload = _load_json(raw)
    status, matched, confidence, rationale, chosen = validate_adjudication(payload, match, settings)
    evidence: list[Evidence] = []
    if chosen is not None:
        evidence.append(
            Evidence(
                source=chosen.source,
                url=chosen.source_url,
                snippet=chosen.snippet or chosen.name,
                kind="list_match",
            )
        )
    return ScreeningDecision(
        status=status,
        matched_entity=matched,
        match_confidence=confidence,
        evidence=evidence,
        snapshot_id=match.decision.snapshot_id,
        decision_basis="llm",
        rationale=rationale.strip() or "The model accepted a candidate from the shortlist.",
    )


def _fallback(decision: ScreeningDecision) -> ScreeningDecision:
    payload = decision.model_dump()
    payload["decision_basis"] = "fallback_rules"
    return parse_model(ScreeningDecision, payload)


def _load_json(raw: str) -> Any:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AdjudicationError("response was not JSON") from exc
    if not isinstance(payload, dict):
        raise AdjudicationError("response JSON must be an object")
    return payload


def _user_payload(
    match: MatchResult,
    settings: Settings,
    name: str,
    country: str,
    registration_number: str | None,
) -> str:
    from screener.llm.schema import ceilings

    allowed = ceilings(match, settings)
    candidates = [
        {
            "source_record_id": candidate.source_record_id,
            "name": candidate.name,
            "list": candidate.list_name,
            "programme": candidate.programme,
            "score": round(candidate.score, 4),
            "url": candidate.source_url,
            "snippet": candidate.snippet,
            "ceiling": allowed[candidate.source_record_id],
            "country_agrees": candidate.agrees,
            "country_contradicts": candidate.contradicts,
        }
        for candidate in match.candidates
    ]
    return json.dumps(
        {
            "supplier": {
                "name": name,
                "country": country,
                "registration_number": registration_number,
            },
            "snapshot_id": match.decision.snapshot_id,
            "candidates": candidates,
        },
        ensure_ascii=False,
    )


def _complete_with_grok(messages: list[dict[str, str]]) -> str:
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ["XAI_API_KEY"],
        base_url=API_BASE,
        timeout=90,
        max_retries=1,
    )
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,  # type: ignore[arg-type]
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "screening_decision",
                    "strict": True,
                    "schema": DECISION_SCHEMA,
                },
            },
        )
    except Exception as exc:
        raise AdjudicationError(str(exc)) from exc
    content = response.choices[0].message.content if response.choices else None
    if not content:
        raise AdjudicationError("the model returned an empty response")
    return content
