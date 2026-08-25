"""Database schema.

Two invariants are enforced by the database rather than by application code,
because application code is where mistakes live:

  * Everything hangs off an owner. Assets, rule packs, jobs, packages and
    delivery rooms all reach a user through ``projects.owner_id``, and queries
    are always filtered by it.
  * Idempotency and approval binding are unique constraints, not conventions.
    A repeated execute request cannot create a second job, and an approval is
    bound to the exact plan digest it was granted for.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _pk()
    #: Firebase / Identity Platform subject. Never accepted from a request body.
    auth_subject: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = _created()

    projects: Mapped[list[Project]] = relationship(back_populates="owner")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = _pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    project_type: Mapped[str] = mapped_column(String(50), nullable=False)
    primary_language: Mapped[str | None] = mapped_column(String(20))
    runtime_seconds: Mapped[int | None] = mapped_column(Integer)
    country_of_origin: Mapped[str | None] = mapped_column(String(2))
    internal_code: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT")
    created_at: Mapped[datetime] = _created()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[User] = relationship(back_populates="projects")
    assets: Mapped[list[Asset]] = relationship(back_populates="project")


class Asset(Base):
    """An uploaded file. Originals are immutable — enforced by ``immutable``.

    ``custody_state`` records where the bytes currently live, so the deletion
    lifecycle can be honest about what has actually been removed.
    """

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(700), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    custody_state: Mapped[str] = mapped_column(String(40), nullable=False, default="STORED")
    derived_from_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _created()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="assets")

    __table_args__ = (
        CheckConstraint("byte_size >= 0", name="ck_assets_byte_size_non_negative"),
        Index("ix_assets_project_role", "project_id", "role"),
    )


class AssetEvidence(Base):
    """A measurement, with the identity of whatever produced it."""

    __tablename__ = "asset_evidence"

    id: Mapped[uuid.UUID] = _pk()
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    inspector: Mapped[str] = mapped_column(String(80), nullable=False)
    inspector_version: Mapped[str] = mapped_column(String(80), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    measured_properties_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    #: Raw tool output is kept private for debugging and never served to clients.
    raw_private_evidence_key: Mapped[str | None] = mapped_column(String(700))
    created_at: Mapped[datetime] = _created()


class Destination(Base):
    __tablename__ = "destinations"

    id: Mapped[uuid.UUID] = _pk()
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    official_domain: Mapped[str | None] = mapped_column(String(255))
    public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: Set when a destination's requirements are not publicly retrievable, so
    #: the UI can ask for a private specification instead of failing opaquely.
    requires_private_spec: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = _created()


class SourceEvidenceRow(Base):
    """Where a requirement was published, and what it said at the time.

    ``source_hash`` is what makes drift detection possible: the same URL
    retrieved later with a different hash means the destination changed its
    requirements, which is a thing users need told.
    """

    __tablename__ = "source_evidence"

    id: Mapped[uuid.UUID] = _pk()
    destination_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    quoted_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    trust_tier: Mapped[str] = mapped_column(String(1), nullable=False)
    private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        CheckConstraint("trust_tier IN ('A','B','C','D')", name="ck_source_evidence_tier"),
        # A private specification must belong to someone and must not carry a
        # public URL. This is the leak the schema refuses to allow.
        CheckConstraint(
            "(private = false) OR (owner_id IS NOT NULL AND url IS NULL)",
            name="ck_private_spec_is_owned_and_unpublished",
        ),
        Index("ix_source_evidence_dest_hash", "destination_id", "source_hash"),
    )


class RulePackRow(Base):
    __tablename__ = "rule_packs"

    id: Mapped[uuid.UUID] = _pk()
    destination_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_model: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = _created()

    rules: Mapped[list[RuleRow]] = relationship(back_populates="rule_pack")

    __table_args__ = (
        UniqueConstraint("destination_id", "version", "owner_id", name="uq_rule_pack_version"),
    )


class RuleRow(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = _pk()
    rule_pack_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rule_packs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(30), nullable=False)
    field: Mapped[str] = mapped_column(String(60), nullable=False)
    operator: Mapped[str] = mapped_column(String(20), nullable=False)
    expected_value_json: Mapped[dict | list | str | int | float | None] = mapped_column(JSONB)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    source_evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_evidence.id", ondelete="RESTRICT"), nullable=False
    )
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    rule_pack: Mapped[RulePackRow] = relationship(back_populates="rules")

    __table_args__ = (
        CheckConstraint(
            "severity IN ('required','recommended','context')", name="ck_rules_severity"
        ),
        CheckConstraint("confidence IN ('high','medium','low')", name="ck_rules_confidence"),
        # No rule may exist without evidence. RESTRICT on the foreign key above
        # means evidence cannot be deleted out from under a live rule either.
    )


class PreflightRun(Base):
    __tablename__ = "preflight_runs"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_pack_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    comparison_digest: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="RUNNING")
    created_at: Mapped[datetime] = _created()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Assertion(Base):
    __tablename__ = "assertions"

    id: Mapped[uuid.UUID] = _pk()
    preflight_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("preflight_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    destination_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"))
    rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rules.id", ondelete="CASCADE"))
    measured_value_json: Mapped[dict | list | str | int | float | None] = mapped_column(JSONB)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("asset_evidence.id", ondelete="SET NULL")
    )
    #: False for the preflight pass, True when re-measured against a built
    #: package. A package cannot verify on assertions where this is False.
    is_output_validation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint(
            "result IN ('PASS','REPAIRABLE','REVIEW_REQUIRED','UNSUPPORTED',"
            "'AMBIGUOUS','NOT_MEASURED')",
            name="ck_assertions_result",
        ),
    )


class RepairPlan(Base):
    __tablename__ = "repair_plans"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    preflight_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("preflight_runs.id", ondelete="CASCADE"), nullable=False
    )
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    estimated_seconds: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(3))
    created_at: Mapped[datetime] = _created()

    steps: Mapped[list[RepairStep]] = relationship(back_populates="plan")

    __table_args__ = (
        UniqueConstraint("project_id", "digest", name="uq_repair_plan_digest"),
    )


class RepairStep(Base):
    __tablename__ = "repair_steps"

    id: Mapped[uuid.UUID] = _pk()
    repair_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repair_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(String(60), nullable=False)
    safety_level: Mapped[str] = mapped_column(String(10), nullable=False)
    input_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL")
    )
    output_role: Mapped[str] = mapped_column(String(40), nullable=False)
    parameters_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    dependency_ids_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="PLANNED")

    plan: Mapped[RepairPlan] = relationship(back_populates="steps")

    __table_args__ = (
        CheckConstraint("safety_level IN ('green','yellow','red')", name="ck_repair_safety"),
        # Only green operations are ever executed automatically. Yellow and red
        # steps may be planned and displayed, never run.
    )


class Approval(Base):
    """Immutable record binding a user's consent to an exact plan.

    The unique constraint is the whole point: if any parameter of the plan
    changes, its digest changes, and the previous approval no longer matches.
    """

    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    repair_plan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_step_ids_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("project_id", "repair_plan_digest", name="uq_approval_plan_digest"),
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        # AC-9: a repeated execute request returns the existing job rather than
        # creating a duplicate. The database is what guarantees it.
        UniqueConstraint("project_id", "idempotency_key", name="uq_job_idempotency"),
    )


class Package(Base):
    __tablename__ = "packages"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    destination_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=False
    )
    rule_pack_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rule_packs.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="PLANNED")
    storage_key: Mapped[str | None] = mapped_column(String(700))
    sha256: Mapped[str | None] = mapped_column(String(64))
    manifest_json: Mapped[dict | None] = mapped_column(JSONB)
    validated_against_output: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        # A package cannot be verified without a hash, a manifest, and
        # validation performed against what was actually produced.
        CheckConstraint(
            "state <> 'VERIFIED' OR ("
            "sha256 IS NOT NULL AND manifest_json IS NOT NULL "
            "AND validated_against_output = true)",
            name="ck_verified_requires_proof",
        ),
    )


class Passport(Base):
    __tablename__ = "passports"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    passport_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_passport_version"),
    )


class DeliveryRoom(Base):
    """A recipient-specific, expiring view of one package.

    Only the hash of the token is stored. A leaked database does not yield
    working delivery links.
    """

    __tablename__ = "delivery_rooms"

    id: Mapped[uuid.UUID] = _pk()
    package_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    recipient_label: Mapped[str | None] = mapped_column(String(200))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class DeliveryEvent(Base):
    __tablename__ = "delivery_events"

    id: Mapped[uuid.UUID] = _pk()
    delivery_room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_at: Mapped[datetime] = _created()
    #: Deliberately narrow. Never a filename, never a media URL, never an IP.
    safe_metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('OPENED','DOWNLOAD_STARTED','DOWNLOAD_COMPLETED','DENIED')",
            name="ck_delivery_event_type",
        ),
        # Note what is absent: there is no ACCEPTED event. Preflight cannot
        # observe whether a recipient accepted a film, so it does not pretend to.
    )


class DeletionRequest(Base):
    __tablename__ = "deletion_requests"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    objects_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    objects_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    requested_at: Mapped[datetime] = _created()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectDestination(Base):
    """Which destinations a project is being prepared for.

    Without this, preflight would measure a project against every rule pack in
    the database. The rule pack version is pinned at selection time so a
    destination revising its requirements next week does not silently change
    what an in-flight project is being judged against — a new preflight run
    adopts the newer version deliberately.
    """

    __tablename__ = "project_destinations"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    destination_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=False
    )
    rule_pack_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rule_packs.id", ondelete="RESTRICT")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("project_id", "destination_id", name="uq_project_destination"),
    )
