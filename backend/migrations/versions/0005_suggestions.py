"""Evidence-backed personal suggestions and durable decisions."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "personal_suggestions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "owner_id",
            sa.Integer,
            sa.ForeignKey("workspace_owners.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("evidence", sa.JSON, nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("created_at", sa.Float, nullable=False),
        sa.UniqueConstraint("owner_id", "fingerprint"),
        sa.CheckConstraint(
            "state IN ('proposed', 'accepted', 'dismissed')",
            name="valid_suggestion_state",
        ),
    )
    op.create_index(
        "ix_personal_suggestions_owner_id", "personal_suggestions", ["owner_id"]
    )


def downgrade():
    raise RuntimeError(
        "Downgrade would delete suggestion decisions; restore a backup instead."
    )
