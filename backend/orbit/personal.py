"""Owner-scoped Phase 1 services. Identity always comes from the session."""

import csv
import io
from datetime import UTC, date, datetime
from typing import Literal
from urllib.parse import urlsplit

from fastapi import HTTPException
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from . import database as db


class SubjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=40)
    semester: str = Field(min_length=1, max_length=40)


def list_subjects(owner_id, engine):
    with engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                select(db.subjects)
                .where(db.subjects.c.owner_id == owner_id)
                .order_by(db.subjects.c.id)
            ).mappings()
        ]


def get_subject(owner_id, engine, subject_id):
    with engine.connect() as conn:
        row = (
            conn.execute(
                select(db.subjects).where(
                    db.subjects.c.owner_id == owner_id, db.subjects.c.id == subject_id
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise HTTPException(404, "Subject not found.")
    return dict(row)


def create_subject(owner_id, engine, body):
    try:
        with engine.begin() as conn:
            key = conn.execute(
                db.subjects.insert().values(owner_id=owner_id, **body.model_dump())
            ).inserted_primary_key[0]
    except IntegrityError as exc:
        raise HTTPException(
            409, "This subject code already exists in this semester."
        ) from exc
    return get_subject(owner_id, engine, key)


class AssessmentInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, allow_inf_nan=False
    )
    subject_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    score: float = Field(ge=0, le=1000000)
    max_score: float = Field(gt=0, le=1000000)
    assessed_on: date
    kind: Literal["quiz", "midterm", "final", "assignment", "lab"]
    weak_topics: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def valid_mark(self):
        if self.score > self.max_score:
            raise ValueError("Score cannot exceed the maximum")
        if self.assessed_on > datetime.now(UTC).date():
            raise ValueError("Assessment date cannot be in the future")
        return self

    @field_validator("weak_topics")
    @classmethod
    def topics(cls, values):
        if any(not value.strip() or len(value) > 100 for value in values):
            raise ValueError("Topics must contain 1–100 characters")
        return list(dict.fromkeys(value.strip() for value in values))


class HackathonInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    event_date: date
    role: str = Field(min_length=1, max_length=120)
    project: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=4000)
    technologies: list[str] = Field(default_factory=list, max_length=30)
    repo_url: str = Field(default="", max_length=500)
    submission_url: str = Field(default="", max_length=500)
    result: str = Field(default="", max_length=200)
    reflection: str = Field(default="", max_length=4000)

    @field_validator("repo_url", "submission_url")
    @classmethod
    def safe_link(cls, value):
        parsed = urlsplit(value)
        if value and (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Use a complete http or https URL")
        return value

    @field_validator("technologies")
    @classmethod
    def techs(cls, values):
        return AssessmentInput.topics(values)


TABLES = {"assessments": db.personal_assessments, "hackathons": db.hackathon_events}


def _owned(owner_id, connection, table, key, lock=False):
    query = select(table).where(table.c.owner_id == owner_id, table.c.id == key)
    if lock:
        query = query.with_for_update()
    row = connection.execute(query).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, "Record not found.")
    return dict(row)


def update_subject(owner_id, engine, key, body):
    try:
        with engine.begin() as conn:
            _owned(owner_id, conn, db.subjects, key, lock=True)
            conn.execute(
                db.subjects.update()
                .where(db.subjects.c.owner_id == owner_id, db.subjects.c.id == key)
                .values(**body.model_dump())
            )
    except IntegrityError as exc:
        raise HTTPException(
            409, "This subject code already exists in this semester."
        ) from exc
    return get_subject(owner_id, engine, key)


def delete_subject(owner_id, engine, key):
    with engine.begin() as conn:
        _owned(owner_id, conn, db.subjects, key, lock=True)
        if conn.scalar(
            select(db.personal_assessments.c.id)
            .where(
                db.personal_assessments.c.owner_id == owner_id,
                db.personal_assessments.c.subject_id == key,
            )
            .limit(1)
        ):
            raise HTTPException(
                409, "Delete this subject's marks before deleting the subject."
            )
        conn.execute(
            db.subjects.delete().where(
                db.subjects.c.owner_id == owner_id, db.subjects.c.id == key
            )
        )
    return {"ok": True}


def list_records(owner_id, engine, resource, subject_id=None):
    table = TABLES[resource]
    query = select(table).where(table.c.owner_id == owner_id)
    if resource == "assessments":
        if subject_id is not None:
            get_subject(owner_id, engine, subject_id)
            query = query.where(table.c.subject_id == subject_id)
        query = query.order_by(table.c.assessed_on.desc(), table.c.id.desc())
    else:
        query = query.order_by(table.c.event_date.desc(), table.c.id.desc())
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(query).mappings()]
    if resource == "assessments":
        for row in rows:
            row["percent"] = round(row["score"] / row["max_score"] * 100, 1)
    return rows


def get_record(owner_id, engine, resource, key):
    with engine.connect() as conn:
        return _owned(owner_id, conn, TABLES[resource], key)


def save_record(owner_id, engine, resource, body, key=None):
    table = TABLES[resource]
    with engine.begin() as conn:
        if key is not None:
            _owned(owner_id, conn, table, key, lock=True)
        if resource == "assessments":
            _owned(owner_id, conn, db.subjects, body.subject_id, lock=True)
        if key is None:
            key = conn.execute(
                table.insert().values(owner_id=owner_id, **body.model_dump())
            ).inserted_primary_key[0]
        else:
            conn.execute(
                table.update()
                .where(table.c.owner_id == owner_id, table.c.id == key)
                .values(**body.model_dump())
            )
        return _owned(owner_id, conn, table, key)


def delete_record(owner_id, engine, resource, key):
    table = TABLES[resource]
    with engine.begin() as conn:
        result = conn.execute(
            table.delete().where(table.c.owner_id == owner_id, table.c.id == key)
        )
        if not result.rowcount:
            raise HTTPException(404, "Record not found.")
    return {"ok": True}


class CsvInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=1000000)


def import_marks(owner_id, engine, content):
    """Validate the entire CSV before any insert; commit all rows together."""
    required = {
        "subject_code",
        "title",
        "score",
        "max_score",
        "assessed_on",
        "kind",
        "weak_topics",
    }
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")), strict=True)
    try:
        fields = reader.fieldnames or []
    except csv.Error as exc:
        raise HTTPException(
            422, "CSV header is malformed. Use the template headers."
        ) from exc
    if (
        not required.issubset(fields)
        or set(fields) - required - {"semester"}
        or len(set(fields)) != len(fields)
    ):
        raise HTTPException(422, "Use the CSV template headers; semester is optional.")
    errors, pending = [], []
    with engine.begin() as conn:
        subjects = [
            dict(row)
            for row in conn.execute(
                select(db.subjects)
                .where(db.subjects.c.owner_id == owner_id)
                .with_for_update()
            ).mappings()
        ]
        try:
            for row in reader:
                row_number = reader.line_num
                if len(pending) + len(errors) >= 1000:
                    raise HTTPException(422, "Import at most 1000 marks at a time.")
                try:
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError("Row has missing or extra columns")
                    candidates = [
                        s
                        for s in subjects
                        if s["code"] == row["subject_code"].strip()
                        and (
                            not row.get("semester", "").strip()
                            or s["semester"] == row["semester"].strip()
                        )
                    ]
                    if len(candidates) != 1:
                        raise ValueError(
                            "Subject code is unknown or ambiguous; add the subject or specify semester"
                        )
                    data = {
                        k: row[k] for k in required - {"subject_code", "weak_topics"}
                    }
                    mark = AssessmentInput(
                        subject_id=candidates[0]["id"],
                        weak_topics=[
                            v.strip()
                            for v in row["weak_topics"].split(";")
                            if v.strip()
                        ],
                        **data,
                    )
                    pending.append({"owner_id": owner_id, **mark.model_dump()})
                except (ValidationError, ValueError) as exc:
                    message = (
                        "; ".join(e["msg"] for e in exc.errors())
                        if isinstance(exc, ValidationError)
                        else str(exc)
                    )
                    errors.append({"row": row_number, "message": message})
        except csv.Error as exc:
            errors.append({"row": reader.line_num, "message": str(exc)})
        if errors:
            raise HTTPException(
                422,
                {
                    "message": "Nothing imported. Fix these rows and retry.",
                    "errors": errors,
                },
            )
        if not pending:
            raise HTTPException(422, "CSV contains no marks.")
        conn.execute(db.personal_assessments.insert(), pending)
    return {"imported": len(pending)}


def workspace(owner_id, engine):
    subjects = list_subjects(owner_id, engine)
    marks = list_records(owner_id, engine, "assessments")
    events = list_records(owner_id, engine, "hackathons")
    for subject in subjects:
        history = [row for row in marks if row["subject_id"] == subject["id"]]
        latest = history[0] if history else None
        previous = next(
            (
                row
                for row in history[1:]
                if latest
                and row["kind"] == latest["kind"]
                and row["max_score"] == latest["max_score"]
                and row["assessed_on"] < latest["assessed_on"]
            ),
            None,
        )
        subject["latest"] = latest
        subject["change"] = (
            round(latest["percent"] - previous["percent"], 1) if previous else None
        )
        subject["previous_id"] = previous["id"] if previous else None
    return {
        "subjects": subjects,
        "assessments": marks,
        "hackathons": events,
        "counts": {
            "subjects": len(subjects),
            "assessments": len(marks),
            "hackathons": len(events),
        },
    }
