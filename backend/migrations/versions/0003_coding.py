"""Private coding connections and durable provider/manual snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "coding_connections",
        sa.Column(
            "owner_id",
            sa.Integer,
            sa.ForeignKey("workspace_owners.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("handle", sa.String(60), nullable=False),
        sa.Column("attempted_at", sa.Float),
        sa.Column("error", sa.Text),
        sa.Column("lease", sa.String(36)),
    )
    op.create_table(
        "coding_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "owner_id",
            sa.Integer,
            sa.ForeignKey("workspace_owners.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("handle", sa.String(60)),
        sa.Column("fetched_at", sa.Float, nullable=False),
        sa.Column("raw", sa.JSON, nullable=False),
        sa.Column("normalized", sa.JSON, nullable=False),
        sa.CheckConstraint(
            "source IN ('codolio', 'manual')", name="valid_coding_source"
        ),
    )
    op.create_index("ix_coding_snapshots_owner_id", "coding_snapshots", ["owner_id"])


def downgrade():
    raise RuntimeError(
        "Downgrading would delete coding history; restore a backup instead."
    )
