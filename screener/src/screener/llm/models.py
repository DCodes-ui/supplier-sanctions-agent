"""The object Grok is asked to return. Snapshot id and evidence links are filled in afterwards."""

from __future__ import annotations

from pydantic import Field

from screener.domain.models import EvidenceKind, MatchedEntity, Status, StrictModel


class ModelEvidence(StrictModel):
    source: str = ""
    url: str = ""
    snippet: str = ""
    kind: EvidenceKind = "list_match"


class ModelDecision(StrictModel):
    status: Status
    matched_entity: MatchedEntity | None = None
    match_confidence: float = Field(ge=0, le=1)
    evidence: list[ModelEvidence] = Field(default_factory=list)
    recommended_action: str = ""
    rationale: str = Field(default="", max_length=1000)
