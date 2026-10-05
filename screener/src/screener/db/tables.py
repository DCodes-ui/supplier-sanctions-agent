"""Tables for snapshots, canonical entities, the name index, and decisions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from screener.db.base import Base


class SnapshotRow(Base):
    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    source_files: Mapped[list[SourceFileRow]] = relationship(back_populates="snapshot")
    entities: Mapped[list[SanctionEntityRow]] = relationship(back_populates="snapshot")
    screenings: Mapped[list[ScreeningRow]] = relationship(back_populates="snapshot")


class SourceFileRow(Base):
    __tablename__ = "source_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    record_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    records_skipped: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    snapshot: Mapped[SnapshotRow] = relationship(back_populates="source_files")


class SanctionEntityRow(Base):
    __tablename__ = "sanction_entities"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "source",
            "source_record_id",
            name="uq_sanction_entities_natural_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    list_name: Mapped[str] = mapped_column(Text, nullable=False)
    programme: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_record_id: Mapped[str] = mapped_column(String(256), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    primary_name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    countries: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    identifiers: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")

    snapshot: Mapped[SnapshotRow] = relationship(back_populates="entities")
    names: Mapped[list[IndexedNameRow]] = relationship(
        back_populates="entity",
        cascade="all, delete-orphan",
    )


class IndexedNameRow(Base):
    __tablename__ = "indexed_names"
    __table_args__ = (Index("ix_indexed_names_snapshot_normalized", "snapshot_id", "normalized"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("sanction_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tokens: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    phonetic_key: Mapped[str] = mapped_column(String(128), nullable=False, default="", index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    name_frequency: Mapped[int | None] = mapped_column(Integer, nullable=True)

    entity: Mapped[SanctionEntityRow] = relationship(back_populates="names")


class NameTokenRow(Base):
    """One blocking token for a normalized name."""

    __tablename__ = "name_tokens"
    __table_args__ = (Index("ix_name_tokens_snapshot_token", "snapshot_id", "token"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int] = mapped_column(ForeignKey("sanction_entities.id"), nullable=False, index=True)
    indexed_name_id: Mapped[int] = mapped_column(ForeignKey("indexed_names.id"), nullable=False)


class EntityIdentifierRow(Base):
    """Registration and document numbers, reduced to letters and digits."""

    __tablename__ = "entity_identifiers"
    __table_args__ = (Index("ix_entity_identifiers_snapshot_key", "snapshot_id", "key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int] = mapped_column(ForeignKey("sanction_entities.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)


class ScreeningRow(Base):
    __tablename__ = "screenings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"), nullable=False, index=True)
    supplier_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    query_name: Mapped[str] = mapped_column(Text, nullable=False)
    query_country: Mapped[str] = mapped_column(String(64), nullable=False)
    query_registration_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    match_confidence: Mapped[float] = mapped_column(nullable=False)
    matched_entity: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    decision_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")

    snapshot: Mapped[SnapshotRow] = relationship(back_populates="screenings")
