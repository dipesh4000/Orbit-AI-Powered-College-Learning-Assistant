from functools import lru_cache

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
)

from .config import settings

metadata = MetaData()
personal_practice = Table(
    "personal_practice",
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
    Column("topic", String(120), nullable=False),
    Column("difficulty", String(20), nullable=False),
    Column("questions", JSON, nullable=False),
    Column("sources", JSON, nullable=False),
    Column("answers", JSON),
    Column("correct", Integer),
    Column("created_at", Float, nullable=False),
    Column("answered_at", Float),
    ForeignKeyConstraint(
        ["subject_id", "owner_id"],
        ["personal_subjects.id", "personal_subjects.owner_id"],
    ),
)
suggestions = Table(
    "personal_suggestions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "owner_id",
        Integer,
        ForeignKey("workspace_owners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("fingerprint", String(64), nullable=False),
    Column("title", String(200), nullable=False),
    Column("text", Text, nullable=False),
    Column("evidence", JSON, nullable=False),
    Column("state", String(20), nullable=False),
    Column("created_at", Float, nullable=False),
    UniqueConstraint("owner_id", "fingerprint"),
    CheckConstraint(
        "state IN ('proposed', 'accepted', 'dismissed')", name="valid_suggestion_state"
    ),
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
owners = Table(
    "workspace_owners",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("name", String(100), nullable=False),
    Column("password_hash", Text, nullable=False),
)
subjects = Table(
    "personal_subjects",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "owner_id",
        Integer,
        ForeignKey("workspace_owners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("name", String(100), nullable=False),
    Column("code", String(40), nullable=False),
    Column("semester", String(40), nullable=False),
    UniqueConstraint("owner_id", "code", "semester"),
    Index("uq_personal_subject_owner", "id", "owner_id", unique=True),
)
personal_assessments = Table(
    "personal_assessments",
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
    Column("title", String(200), nullable=False),
    Column("score", Float, nullable=False),
    Column("max_score", Float, nullable=False),
    Column("assessed_on", Date, nullable=False),
    Column("kind", String(20), nullable=False),
    Column("weak_topics", JSON, nullable=False),
    ForeignKeyConstraint(
        ["subject_id", "owner_id"],
        ["personal_subjects.id", "personal_subjects.owner_id"],
        ondelete="CASCADE",
    ),
    CheckConstraint(
        "max_score > 0 AND score >= 0 AND score <= max_score",
        name="valid_personal_score",
    ),
    CheckConstraint(
        "kind IN ('quiz', 'midterm', 'final', 'assignment', 'lab')",
        name="valid_personal_kind",
    ),
)
hackathon_events = Table(
    "personal_hackathon_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "owner_id",
        Integer,
        ForeignKey("workspace_owners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("name", String(200), nullable=False),
    Column("event_date", Date, nullable=False),
    Column("role", String(120), nullable=False),
    Column("project", String(200), nullable=False),
    Column("summary", Text, nullable=False),
    Column("technologies", JSON, nullable=False),
    Column("repo_url", String(500), nullable=False),
    Column("submission_url", String(500), nullable=False),
    Column("result", String(200), nullable=False),
    Column("reflection", Text, nullable=False),
)

coding_connections = Table(
    "coding_connections",
    metadata,
    Column(
        "owner_id",
        Integer,
        ForeignKey("workspace_owners.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("handle", String(60), nullable=False),
    Column("attempted_at", Float),
    Column("error", Text),
    Column("lease", String(36)),
)
coding_snapshots = Table(
    "coding_snapshots",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "owner_id",
        Integer,
        ForeignKey("workspace_owners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("source", String(20), nullable=False),
    Column("handle", String(60)),
    Column("fetched_at", Float, nullable=False),
    Column("raw", JSON, nullable=False),
    Column("normalized", JSON, nullable=False),
    CheckConstraint("source IN ('codolio', 'manual')", name="valid_coding_source"),
)

source_archives = Table(
    "source_file_archives",
    metadata,
    Column("filename", String, primary_key=True),
    Column("sha256", String),
    Column("gzip_bytes", LargeBinary, nullable=False),
)


# Every CSV row survives verbatim as a dictionary of CSV string fields. Identical
# business records at different source row numbers are deliberately preserved.
def raw_table(name):
    return Table(
        name,
        metadata,
        Column("id", Integer, primary_key=True),
        Column("source_file", String, nullable=False),
        Column("source_row", Integer, nullable=False),
        Column("source_sha256", String, nullable=False),
        Column("user_id", Text),
        Column("raw_record", JSON, nullable=False),
        Column("issue", Text),
        UniqueConstraint("source_file", "source_row"),
    )


raw_engagement = raw_table("raw_course_engagement")
raw_submissions = raw_table("raw_hackathon_submissions")
invalid_engagement = raw_table("invalid_user_id_engagement")
invalid_submissions = raw_table("invalid_user_id_submissions")
imports = Table(
    "import_manifest",
    metadata,
    Column("filename", String, primary_key=True),
    Column("sha256", String),
    Column("row_count", Integer),
    Column("completed", Boolean),
)
courses = Table(
    "courses",
    metadata,
    Column("course_id", String, primary_key=True),
    Column("title", Text),
    Column("subject", Text),
)
progress = Table(
    "course_progress",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("raw_id", Integer, unique=True),
    Column("user_id", String, index=True),
    Column("course_id", String, index=True),
    Column("mcq_attempted", Integer),
    Column("mcq_score", Float),
    Column("total_activities", Integer),
    Column("observed_activities", Integer),
    Column("certificate", Boolean),
    Column("legacy_completion", Boolean),
    Column("total_views", Integer),
)
questions = Table(
    "question_attempts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("raw_id", Integer, index=True),
    Column("question_index", Integer),
    Column("user_id", String, index=True),
    Column("hackathon_id", String),
    Column("round_id", String),
    Column("attempt_id", String),
    Column("question_id", String),
    Column("skill", Text),
    Column("topic", Text),
    Column("status", String),
    Column("obtained", Float),
    Column("maximum", Float),
    Column("assumed_maximum", Boolean),
    Column("submitted_at", String),
    UniqueConstraint("raw_id", "question_index", "topic"),
)
students = Table(
    "demo_students",
    metadata,
    Column("user_id", String, primary_key=True),
    Column("label", String),
    Column("rationale", Text),
)
sessions = Table(
    "web_sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("expires_at", Float, nullable=False, index=True),
    Column("data", JSON, nullable=False),
)
conversations = Table(
    "chat_conversations",
    metadata,
    Column("id", String, primary_key=True),
    Column("user_id", String, index=True, nullable=False),
    Column("title", String(80), nullable=False),
    Column("messages", JSON, nullable=False),
    Column("updated_at", String, index=True, nullable=False),
)
assessments = Table(
    "assessments",
    metadata,
    Column("assessment_id", String, primary_key=True),
    Column("course_id", String),
    Column("title", Text),
    Column("active", Boolean),
    Column("max_attempts", Integer),
    Column("completion_threshold", Float),
    Column("prerequisite_course_id", String),
    Column("pass_percent", Float),
    Column("demo_rule", Boolean),
)
practice_history = Table(
    "practice_history",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", String, index=True),
    Column("course_id", String),
    Column("topic", String),
    Column("difficulty", String),
    Column("questions", JSON),
    Column("created_at", String),
)
assessment_attempts = Table(
    "assessment_attempts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", String, index=True),
    Column("assessment_id", String, index=True),
    Column("score_percent", Float),
)


@lru_cache
def get_engine():
    if not settings.database_url:
        raise RuntimeError(
            "Configure DATABASE_URL in Orbit/.env, then run python -m orbit.migrate."
        )
    if not settings.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise RuntimeError(
            "Orbit requires PostgreSQL. Use a postgresql+psycopg:// URL."
        )
    url = settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(
        url, pool_pre_ping=True, pool_size=5, max_overflow=5, hide_parameters=True
    )
