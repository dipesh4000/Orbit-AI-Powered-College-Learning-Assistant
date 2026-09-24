"""Replace single personal_chats row with multi-session personal_chat_sessions."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = depends_on = None


def upgrade():
    dialect = op.get_bind().dialect.name

    # Drop old single-row table (data loss is acceptable – it's chat history)
    op.drop_table("personal_chats")

    if dialect == "sqlite":
        op.execute(
            """
CREATE TABLE personal_chat_sessions (
    id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    title VARCHAR(120) NOT NULL,
    history JSON NOT NULL,
    transcript JSON NOT NULL,
    created_at FLOAT NOT NULL,
    updated_at FLOAT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(owner_id) REFERENCES workspace_owners (id) ON DELETE CASCADE
)
"""
        )
        op.execute(
            "CREATE INDEX ix_personal_chat_sessions_owner_id ON personal_chat_sessions (owner_id)"
        )
    else:
        op.execute(
            """
CREATE TABLE personal_chat_sessions (
    id SERIAL NOT NULL,
    owner_id INTEGER NOT NULL,
    title VARCHAR(120) NOT NULL,
    history JSON NOT NULL,
    transcript JSON NOT NULL,
    created_at FLOAT NOT NULL,
    updated_at FLOAT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(owner_id) REFERENCES workspace_owners (id) ON DELETE CASCADE
)
"""
        )
        op.execute(
            "CREATE INDEX ix_personal_chat_sessions_owner_id ON personal_chat_sessions (owner_id)"
        )


def downgrade():
    raise RuntimeError("Restore a backup instead of deleting personal records.")
