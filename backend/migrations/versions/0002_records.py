"""Owner-bound marks and hackathon records."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = depends_on = None


def upgrade():
    op.create_index(
        "uq_personal_subject_owner",
        "personal_subjects",
        ["id", "owner_id"],
        unique=True,
    )
    op.create_table(
        "personal_assessments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "owner_id",
            sa.Integer,
            sa.ForeignKey("workspace_owners.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject_id", sa.Integer, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("max_score", sa.Float, nullable=False),
        sa.Column("assessed_on", sa.Date, nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("weak_topics", sa.JSON, nullable=False),
        sa.ForeignKeyConstraint(
            ["subject_id", "owner_id"],
            ["personal_subjects.id", "personal_subjects.owner_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "max_score > 0 AND score >= 0 AND score <= max_score",
            name="valid_personal_score",
        ),
        sa.CheckConstraint(
            "kind IN ('quiz', 'midterm', 'final', 'assignment', 'lab')",
            name="valid_personal_kind",
        ),
    )
    op.create_index(
        "ix_personal_assessments_owner_id", "personal_assessments", ["owner_id"]
    )
    op.create_table(
        "personal_hackathon_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "owner_id",
            sa.Integer,
            sa.ForeignKey("workspace_owners.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("event_date", sa.Date, nullable=False),
        sa.Column("role", sa.String(120), nullable=False),
        sa.Column("project", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("technologies", sa.JSON, nullable=False),
        sa.Column("repo_url", sa.String(500), nullable=False),
        sa.Column("submission_url", sa.String(500), nullable=False),
        sa.Column("result", sa.String(200), nullable=False),
        sa.Column("reflection", sa.Text, nullable=False),
    )
    op.create_index(
        "ix_personal_hackathon_events_owner_id",
        "personal_hackathon_events",
        ["owner_id"],
    )


def downgrade():
    raise RuntimeError(
        "Downgrading would delete student records; restore a backup instead."
    )
