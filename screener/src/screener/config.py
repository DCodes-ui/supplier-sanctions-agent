"""Load thresholds, sources, and country risk from the config directory.

Files are read on every call so an edit is picked up without a code change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from screener.paths import screener_root


class ConfigError(Exception):
    """The screener configuration files are missing or invalid."""


class Thresholds(BaseModel):
    model_config = ConfigDict(extra="ignore")

    discard_below: float = Field(ge=0, le=1)
    likely_hit_at: float = Field(ge=0, le=1)
    high_confidence_at: float = Field(ge=0, le=1)
    common_name_min_people: int = Field(ge=1)
    candidate_rescore_limit: int = Field(ge=1)
    llm_candidate_limit: int = Field(ge=1)

    @model_validator(mode="after")
    def bands_increase(self) -> Thresholds:
        if not (self.discard_below < self.likely_hit_at <= self.high_confidence_at):
            raise ValueError(
                "thresholds must rise: discard_below < likely_hit_at <= high_confidence_at"
            )
        return self


class SourceSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    url: str = Field(min_length=1)
    required: bool = True
    enabled: bool = True
    max_bytes: int = Field(default=50_000_000, ge=1)
    skip_datasets: list[str] = Field(default_factory=list)


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    root: Path
    thresholds: Thresholds
    sources: list[SourceSpec]
    country_risk: list[str]
    prompt: str

    @field_validator("country_risk")
    @classmethod
    def iso_codes(cls, value: list[str]) -> list[str]:
        codes: list[str] = []
        for code in value:
            text = code.strip().upper()
            if len(text) != 2 or not text.isalpha():
                raise ValueError(f"country risk code must be ISO alpha-2, got {code!r}")
            codes.append(text)
        return codes

    @model_validator(mode="after")
    def unique_sources(self) -> Settings:
        seen: set[str] = set()
        for source in self.sources:
            if source.id in seen:
                raise ValueError(f"duplicate source id {source.id}")
            seen.add(source.id)
        if not self.sources:
            raise ValueError("at least one source is required")
        return self


def load_settings(root: Path | None = None) -> Settings:
    base = (root or screener_root()).resolve()
    try:
        thresholds = Thresholds.model_validate(_read_yaml(base / "config" / "thresholds.yaml"))
        sources_payload = _read_yaml(base / "config" / "sources.yaml")
        country_payload = _read_yaml(base / "config" / "country_risk.yaml")
        prompt = (base / "prompts" / "adjudicate.md").read_text(encoding="utf-8")
    except (OSError, yaml.YAMLError, ValidationError, ValueError) as exc:
        raise ConfigError(str(exc)) from exc

    if not isinstance(sources_payload, dict) or not isinstance(sources_payload.get("sources"), list):
        raise ConfigError("sources.yaml must contain a sources list")
    if not isinstance(country_payload, dict) or not isinstance(country_payload.get("countries"), list):
        raise ConfigError("country_risk.yaml must contain a countries list")

    try:
        return Settings(
            root=base,
            thresholds=thresholds,
            sources=[SourceSpec.model_validate(item) for item in sources_payload["sources"]],
            country_risk=country_payload["countries"],
            prompt=prompt,
        )
    except (ValidationError, ValueError) as exc:
        raise ConfigError(str(exc)) from exc


def _read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise ConfigError(f"missing config file: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ConfigError(f"{path.name} must be a mapping")
    return loaded
