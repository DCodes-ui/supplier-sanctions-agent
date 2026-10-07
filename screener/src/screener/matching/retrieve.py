"""Find list candidates for one supplier and apply the score bands.

The model is not called here. A later step may lower a likely hit to review.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler
from sqlalchemy import func, select

from screener.config import Settings, load_settings
from screener.db.session import session_scope
from screener.db.tables import (
    EntityIdentifierRow,
    IndexedNameRow,
    NameTokenRow,
    SanctionEntityRow,
)
from screener.domain.models import Evidence, MatchedEntity, ScreeningDecision
from screener.matching.countries import country_codes, country_relation
from screener.matching.index import SnapshotNotReady, active_snapshot_id
from screener.matching.normalize import name_tokens, normalize_identifier, normalize_name

# A token shared by more names than this is too common to block on.
_MAX_BLOCK_DF = 2000
# Company words. They are not enough on their own to make two names look alike.
_GENERIC_TOKENS = {
    "holdings",
    "holding",
    "group",
    "company",
    "international",
    "trading",
    "enterprises",
    "enterprise",
    "limited",
    "services",
    "corp",
    "corporation",
}


@dataclass(frozen=True)
class Candidate:
    score: float
    source: str
    list_name: str
    programme: str
    source_record_id: str
    name: str
    source_url: str
    snippet: str
    agrees: bool
    contradicts: bool
    name_frequency: int
    tokens_covered: bool


@dataclass(frozen=True)
class MatchResult:
    decision: ScreeningDecision
    candidates: list[Candidate]


def match_supplier(
    name: str,
    country: str,
    registration_number: str | None = None,
    snapshot_id: str | None = None,
    settings: Settings | None = None,
    source: str | None = None,
) -> MatchResult:
    loaded = settings or load_settings()
    current = snapshot_id or active_snapshot_id()
    normalized = normalize_name(name)
    with session_scope() as session:
        _require_index(session, current)
        identifier_ids = _identifier_hits(session, current, registration_number)
        if len(identifier_ids) == 1:
            identified = _identifier_decision(session, current, identifier_ids[0], normalized, country)
            if _on_list(identified.candidates[0].source, source):
                return identified
        blocked = _block(
            session,
            current,
            normalized,
            name_tokens(normalized),
            loaded.thresholds.candidate_rescore_limit,
        )
        if identifier_ids:
            blocked = _merge(identifier_ids, blocked, loaded.thresholds.candidate_rescore_limit)
        scored = _score_entities(session, normalized, country, blocked)
    if source:
        scored = [candidate for candidate in scored if _on_list(candidate.source, source)]
    kept = [candidate for candidate in scored if candidate.score >= loaded.thresholds.discard_below]
    kept.sort(key=lambda candidate: candidate.score, reverse=True)
    shortlist = kept[: loaded.thresholds.llm_candidate_limit]
    if len(identifier_ids) > 1 and shortlist:
        return MatchResult(decision=_many_identifiers(current, shortlist[0]), candidates=shortlist)
    decision = _decide(current, country, loaded, shortlist)
    return MatchResult(decision=decision, candidates=shortlist)


def _decide(snapshot_id: str, country: str, settings: Settings, candidates: list[Candidate]) -> ScreeningDecision:
    thresholds = settings.thresholds
    if not candidates:
        if _country_is_elevated(country, settings):
            return _decision(
                snapshot_id,
                status="review",
                basis="country_risk",
                confidence=0,
                rationale=f"{country.strip().upper()} is on the elevated-risk country list. This is not a sanctions designation.",
                evidence=[
                    Evidence(
                        source="country_risk",
                        url="",
                        snippet=f"{country.strip().upper()} is configured as an elevated-risk country.",
                        kind="country_risk",
                    )
                ],
            )
        return _decision(
            snapshot_id,
            status="clear",
            basis="no_candidates",
            confidence=0,
            rationale=f"No listed name scored at or above {thresholds.discard_below:.2f}.",
        )
    best = candidates[0]
    if best.score < thresholds.likely_hit_at or not _corroborated(best, settings):
        return _from_candidate(
            snapshot_id,
            best,
            status="review",
            basis="below_threshold",
            rationale=_review_reason(best, settings),
        )
    return _from_candidate(
        snapshot_id,
        best,
        status="likely_hit",
        basis="fallback_rules",
        rationale=(
            f"The closest listed name scored {best.score:.2f}, and the country or the rarity of the name supports it."
        ),
    )


def _on_list(candidate_source: str, selected: str | None) -> bool:
    if not selected:
        return True
    if selected == "opensanctions":
        return candidate_source.startswith("opensanctions:")
    return candidate_source == selected


def ceiling_status(candidate: Candidate, settings: Settings) -> str:
    """The strongest status the score rules allow for this candidate."""

    if candidate.score >= settings.thresholds.likely_hit_at and _corroborated(candidate, settings):
        return "likely_hit"
    return "review"


def _corroborated(candidate: Candidate, settings: Settings) -> bool:
    if candidate.contradicts:
        return False
    thresholds = settings.thresholds
    if candidate.name_frequency >= thresholds.common_name_min_people:
        return False
    high = candidate.score >= thresholds.high_confidence_at
    covered = candidate.score >= thresholds.likely_hit_at and candidate.agrees and candidate.tokens_covered
    return high or covered


def _review_reason(candidate: Candidate, settings: Settings) -> str:
    thresholds = settings.thresholds
    if candidate.name_frequency >= thresholds.common_name_min_people and candidate.score >= thresholds.likely_hit_at:
        return (
            f"The closest name scored {candidate.score:.2f}, but that name is shared by "
            f"{candidate.name_frequency} listed people and there is no matching identifier."
        )
    if candidate.contradicts and candidate.score >= thresholds.likely_hit_at:
        return f"The closest name scored {candidate.score:.2f}, but the countries do not agree."
    if candidate.score >= thresholds.likely_hit_at:
        return f"The closest name scored {candidate.score:.2f}, without a second fact to support a likely hit."
    return (
        f"The closest listed name scored {candidate.score:.2f}, which is below "
        f"{thresholds.likely_hit_at:.2f}."
    )


def _identifier_decision(session, snapshot_id: str, entity_id: int, normalized: str, country: str) -> MatchResult:  # noqa: ANN001
    entity = session.get(SanctionEntityRow, entity_id)
    if entity is None:
        raise SnapshotNotReady("The identifier index points at a missing entity.")
    found = _candidate_for_entity(entity, _names_for(session, [entity_id]).get(entity_id, []), normalized, country)
    candidate = replace(found, score=1, tokens_covered=True)
    decision = _from_candidate(
        snapshot_id,
        candidate,
        status="likely_hit",
        basis="identifier",
        rationale="The registration number matches one listed identifier.",
        confidence=1,
    )
    return MatchResult(decision=decision, candidates=[candidate])


def _many_identifiers(snapshot_id: str, best: Candidate) -> ScreeningDecision:
    return _from_candidate(
        snapshot_id,
        best,
        status="review",
        basis="identifier",
        rationale="The registration number matches more than one listed record.",
        confidence=min(best.score, 0.9),
    )


def _from_candidate(
    snapshot_id: str,
    candidate: Candidate,
    *,
    status: str,
    basis: str,
    rationale: str,
    confidence: float | None = None,
) -> ScreeningDecision:
    return _decision(
        snapshot_id,
        status=status,
        basis=basis,
        confidence=candidate.score if confidence is None else confidence,
        rationale=rationale,
        matched=MatchedEntity(
            name=candidate.name,
            list=candidate.list_name,
            programme=candidate.programme,
            source_record_id=candidate.source_record_id,
        ),
        evidence=[
            Evidence(
                source=candidate.source,
                url=candidate.source_url,
                snippet=candidate.snippet or candidate.name,
                kind="list_match",
            )
        ],
    )


def _decision(
    snapshot_id: str,
    *,
    status: str,
    basis: str,
    confidence: float,
    rationale: str,
    matched: MatchedEntity | None = None,
    evidence: list[Evidence] | None = None,
) -> ScreeningDecision:
    return ScreeningDecision(
        status=status,  # type: ignore[arg-type]
        matched_entity=matched,
        match_confidence=confidence,
        evidence=evidence or [],
        snapshot_id=snapshot_id,
        decision_basis=basis,  # type: ignore[arg-type]
        rationale=rationale[:1000],
    )


def _country_is_elevated(country: str, settings: Settings) -> bool:
    return bool(country_codes(country) & set(settings.country_risk))


def _block(session, snapshot_id: str, normalized: str, tokens: list[str], limit: int) -> list[int]:  # noqa: ANN001
    """Exact normalized names, plus entities that share the rarest useful token."""

    exact = list(
        session.scalars(
            select(IndexedNameRow.entity_id).where(
                IndexedNameRow.snapshot_id == snapshot_id,
                IndexedNameRow.normalized == normalized,
            )
        )
    )
    distinctive = [token for token in tokens if token not in _GENERIC_TOKENS]
    found: list[int] = []
    for token in sorted(distinctive, key=len, reverse=True):
        count = (
            session.scalar(
                select(func.count(func.distinct(NameTokenRow.entity_id))).where(
                    NameTokenRow.snapshot_id == snapshot_id,
                    NameTokenRow.token == token,
                )
            )
            or 0
        )
        if count == 0 or count > _MAX_BLOCK_DF:
            continue
        found = list(
            session.scalars(
                select(NameTokenRow.entity_id)
                .where(NameTokenRow.snapshot_id == snapshot_id, NameTokenRow.token == token)
                .limit(limit)
            )
        )
        break
    return _merge(exact, found, limit)


def _score_entities(session, normalized: str, country: str, entity_ids: list[int]) -> list[Candidate]:  # noqa: ANN001
    if not entity_ids or not normalized:
        return []
    names = _names_for(session, entity_ids)
    entities = session.scalars(select(SanctionEntityRow).where(SanctionEntityRow.id.in_(entity_ids))).all()
    scored: list[Candidate] = []
    for entity in entities:
        scored.append(_candidate_for_entity(entity, names.get(entity.id, []), normalized, country))
    return scored


def _candidate_for_entity(entity: SanctionEntityRow, names: list[tuple[str, int]], normalized: str, country: str) -> Candidate:
    best_score = 0.0
    best_frequency = names[0][1] if names else 0
    for candidate_name, frequency in names:
        score = _name_score(normalized, candidate_name)
        if score >= best_score:
            best_score = score
            best_frequency = frequency
    agrees, contradicts = country_relation(country, list(entity.countries or []))
    query_tokens = set(name_tokens(normalized))
    listed_tokens: set[str] = set()
    for candidate_name, _frequency in names:
        listed_tokens.update(name_tokens(candidate_name))
    covered = bool(query_tokens) and query_tokens <= listed_tokens
    return Candidate(
        score=best_score,
        source=entity.source,
        list_name=entity.list_name,
        programme=entity.programme,
        source_record_id=entity.source_record_id,
        name=entity.primary_name,
        source_url=entity.source_url,
        snippet=entity.snippet or entity.primary_name,
        agrees=agrees,
        contradicts=contradicts,
        name_frequency=best_frequency,
        tokens_covered=covered,
    )


def _names_for(session, entity_ids: list[int]) -> dict[int, list[tuple[str, int]]]:  # noqa: ANN001
    rows = session.execute(
        select(IndexedNameRow.entity_id, IndexedNameRow.normalized, IndexedNameRow.name_frequency).where(
            IndexedNameRow.entity_id.in_(entity_ids)
        )
    ).all()
    grouped: dict[int, list[tuple[str, int]]] = {}
    for entity_id, normalized, frequency in rows:
        grouped.setdefault(entity_id, []).append((normalized or "", frequency or 0))
    return grouped


def _identifier_hits(session, snapshot_id: str, registration_number: str | None) -> list[int]:  # noqa: ANN001
    key = normalize_identifier(registration_number or "")
    if not key:
        return []
    return list(
        session.scalars(
            select(EntityIdentifierRow.entity_id).where(
                EntityIdentifierRow.snapshot_id == snapshot_id,
                EntityIdentifierRow.key == key,
            )
        )
    )


def _require_index(session, snapshot_id: str) -> None:  # noqa: ANN001
    indexed = session.scalar(
        select(func.count())
        .select_from(IndexedNameRow)
        .where(IndexedNameRow.snapshot_id == snapshot_id, IndexedNameRow.normalized != "")
    )
    if not indexed:
        raise SnapshotNotReady("Names are not indexed. Run: python -m screener index")


def _merge(first: list[int], second: list[int], limit: int) -> list[int]:
    ordered: list[int] = []
    seen: set[int] = set()
    for entity_id in [*first, *second]:
        if entity_id in seen:
            continue
        seen.add(entity_id)
        ordered.append(entity_id)
        if len(ordered) >= limit:
            break
    return ordered


def _name_score(query: str, candidate: str) -> float:
    if not query or not candidate:
        return 0.0
    left = _distinctive(query)
    right = _distinctive(candidate)
    if left and right and (left != query or right != candidate):
        return _pair_score(left, right)
    return _pair_score(query, candidate)


def _distinctive(normalized: str) -> str:
    tokens = [token for token in normalized.split() if token not in _GENERIC_TOKENS]
    return " ".join(tokens) if tokens else normalized


def _pair_score(query: str, candidate: str) -> float:
    if not query or not candidate:
        return 0.0
    jaro = JaroWinkler.normalized_similarity(query, candidate)
    tokens = fuzz.token_sort_ratio(query, candidate) / 100
    return max(jaro, tokens)
