"""Private paper sources and reviewed, model-versioned questions."""

from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)

revision = "0004"
down_revision = "0003"
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    metadata = MetaData()
    Table("workspace_owners", metadata, Column("id", Integer, primary_key=True))
    Table(
        "personal_subjects",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("owner_id", Integer),
    )
    papers = Table(
        "personal_papers",
        metadata,
        Column("id", Integer, primary_key=True),
        Column(
            "owner_id",
            Integer,
            ForeignKey("workspace_owners.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column("subject_id", Integer, nullable=False),
        Column("filename", String(200), nullable=False),
        Column("year", Integer, nullable=False),
        Column("topics", JSON, nullable=False),
        Column("source", LargeBinary, nullable=False),
        Column("status", String(30), nullable=False),
        Column("error", Text),
        Column("started_at", Float, nullable=False),
        Column("lease", String(36), nullable=False),
        ForeignKeyConstraint(
            ["subject_id", "owner_id"],
            ["personal_subjects.id", "personal_subjects.owner_id"],
        ),
        UniqueConstraint("id", "owner_id"),
    )
    paper_questions = Table(
        "personal_questions",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("owner_id", Integer, nullable=False, index=True),
        Column("paper_id", Integer, nullable=False),
        Column("page", Integer, nullable=False),
        Column("content", Text, nullable=False),
        Column("topic", String(100), nullable=False),
        Column("marks", Integer),
        Column("confirmed", Boolean, nullable=False),
        Column("embedding", Vector(384).with_variant(JSON(), "sqlite")),
        Column("signature", Text),
        Column("revision", Integer, nullable=False, default=1),
        ForeignKeyConstraint(
            ["paper_id", "owner_id"],
            ["personal_papers.id", "personal_papers.owner_id"],
            ondelete="CASCADE",
        ),
    )
    papers.create(bind)
    paper_questions.create(bind)


def downgrade():
    raise RuntimeError("Downgrade would delete papers; restore a backup instead.")
