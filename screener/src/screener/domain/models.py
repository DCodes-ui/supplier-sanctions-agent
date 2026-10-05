"""Domain contracts for a sanctions entity and a screening decision.

Untrusted payloads, including model output, go through parse_model. That drops
unknown fields and validates the remaining object a second time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Status = Literal["clear", "review", "likely_hit"]
EvidenceKind = Literal["list_match", "country_risk"]
DecisionBasis = Literal[
    "no_candidates",
    "below_threshold",
    "llm",
    "fallback_rules",
    "identifier",
    "country_risk",
]

RECOMMENDED_ACTIONS: dict[Status, str] = {
    "clear": "Proceed and record the screening against the snapshot.",
    "review": "Do not onboard or pay until a compliance analyst confirms or rejects the candidates.",
    "likely_hit": "Stop. Do not transact. Escalate to compliance with the evidence pack.",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


def parse_model[ModelT: StrictModel](model: type[ModelT], payload: Any) -> ModelT:
    """Drop unknown fields, then validate the cleaned object again."""

    first = model.model_validate(payload)
    return model.model_validate(first.model_dump())


class ScreeningInput(StrictModel):
    name: str = Field(min_length=1)
    country: str = Field(min_length=2, max_length=64)
    registration_number: str | None = None
    supplier_id: str | None = None

    @field_validator("registration_number", "supplier_id", mode="before")
    @classmethod
    def blank_to_none(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("name", "country", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value


class SanctionEntity(StrictModel):
    source: str = Field(min_length=1)
    list_name: str = Field(min_length=1)
    programme: str = ""
    source_record_id: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    primary_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    identifiers: list[str] = Field(default_factory=list)
    source_url: str = ""
    snippet: str = ""


class IndexedName(StrictModel):
    """One name row in the search index. Normalization fills the empty fields later."""

    raw_name: str = Field(min_length=1)
    normalized: str = ""
    tokens: list[str] = Field(default_factory=list)
    phonetic_key: str = ""
    is_primary: bool = False
    name_frequency: int | None = Field(default=None, ge=0)


class MatchedEntity(StrictModel):
    name: str = Field(min_length=1)
    list: str = Field(min_length=1)
    programme: str = ""
    source_record_id: str = Field(min_length=1)


class Evidence(StrictModel):
    source: str = Field(min_length=1)
    url: str = ""
    snippet: str = ""
    kind: EvidenceKind


class ScreeningDecision(StrictModel):
    status: Status
    matched_entity: MatchedEntity | None = None
    match_confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list)
    recommended_action: str = ""
    snapshot_id: str = Field(min_length=1)
    decision_basis: DecisionBasis
    rationale: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def apply_decision_rules(self) -> ScreeningDecision:
        self.recommended_action = RECOMMENDED_ACTIONS[self.status]
        if self.status == "likely_hit" and self.matched_entity is None:
            raise ValueError("likely_hit requires a matched entity")
        if self.status == "clear" and self.matched_entity is not None:
            raise ValueError("clear does not carry a matched entity")
        return self


class ScreeningRecord(StrictModel):
    """One stored screening: the supplier we were asked about, and the decision."""

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    id: str = Field(min_length=1)
    created_at: datetime
    supplier_id: str | None = None
    query_name: str = Field(min_length=1)
    query_country: str = Field(min_length=2)
    query_registration_number: str | None = None
    decision: ScreeningDecision
