from functools import lru_cache
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    JSON,
    UniqueConstraint,
    LargeBinary,
)
from .config import settings

metadata = MetaData()
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
            "Configure DATABASE_URL in backend/.env, then run the importer."
        )
    if not settings.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise RuntimeError(
            "Orbit requires PostgreSQL. Use a postgresql+psycopg:// URL."
        )
    url = settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, hide_parameters=True)
