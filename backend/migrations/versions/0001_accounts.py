"""Adopt existing Phase 0 tables without changing their data."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = depends_on = None


def upgrade():
    metadata = sa.MetaData()
    owners = sa.Table(
        "workspace_owners",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
    )
    subjects = sa.Table(
        "personal_subjects",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "owner_id",
            sa.Integer,
            sa.ForeignKey("workspace_owners.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("semester", sa.String(40), nullable=False),
        sa.UniqueConstraint("owner_id", "code", "semester"),
    )
    owners.create(op.get_bind(), checkfirst=True)
    subjects.create(op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError(
        "Downgrading would delete personal accounts; restore a backup instead."
    )
