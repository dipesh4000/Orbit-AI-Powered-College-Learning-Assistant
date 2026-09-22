"""Owned practice sets and server-graded attempts."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "personal_practice",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "owner_id",
            sa.Integer,
            sa.ForeignKey("workspace_owners.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject_id", sa.Integer, nullable=False),
        sa.Column("topic", sa.String(120), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=False),
        sa.Column("questions", sa.JSON, nullable=False),
        sa.Column("sources", sa.JSON, nullable=False),
        sa.Column("answers", sa.JSON),
        sa.Column("correct", sa.Integer),
        sa.Column("created_at", sa.Float, nullable=False),
        sa.Column("answered_at", sa.Float),
        sa.ForeignKeyConstraint(
            ["subject_id", "owner_id"],
            ["personal_subjects.id", "personal_subjects.owner_id"],
        ),
    )
    op.create_index("ix_personal_practice_owner_id", "personal_practice", ["owner_id"])


def downgrade():
    raise RuntimeError(
        "Downgrade would delete practice history; restore a backup instead."
    )
