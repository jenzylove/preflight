"""destination research jobs

Researching a destination is slow and provider-dependent, so the attempt has to
outlive the request that started it. This table is that attempt: what was
asked, how far it got, what it found, and - when it found nothing usable - why.

Revision ID: a7c31d9f4e21
Revises: b20e35946380
Create Date: 2026-09-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c31d9f4e21"
down_revision: str | None = "b20e35946380"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "destination_research",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=False),
        sa.Column("query", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("progress", sa.String(length=200), nullable=True),
        sa.Column("destination_id", sa.UUID(), nullable=True),
        sa.Column("rule_pack_id", sa.UUID(), nullable=True),
        sa.Column("official_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_rules", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mandatory_rules", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('QUEUED','SEARCHING','READING','EXTRACTING','READY',"
            "'NOTHING_FOUND','FAILED')",
            name="ck_research_state",
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["destination_id"], ["destinations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["rule_pack_id"], ["rule_packs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_destination_research_requested_by"),
        "destination_research",
        ["requested_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_destination_research_requested_by"), table_name="destination_research"
    )
    op.drop_table("destination_research")
