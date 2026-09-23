"""Reported academic values and review-before-save document import."""

import time
from datetime import date
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from . import database as db
from . import gemini, personal


class Input(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, allow_inf_nan=False
    )


class Profile(Input):
    program: str = Field(default="", max_length=100)
    current_semester: str = Field(default="", max_length=40)
    total_credits: float | None = Field(default=None, ge=0, le=10000)
    target_sgpa: float | None = Field(default=None, ge=0)
    sgpa_scale: float = Field(default=10, gt=0, le=100)

    @model_validator(mode="after")
    def scale(self):
        if self.target_sgpa is not None and self.target_sgpa > self.sgpa_scale:
            raise ValueError("Target SGPA exceeds the grading scale.")
        return self


class Semester(Input):
    semester: str = Field(min_length=1, max_length=40)
    sgpa: float = Field(ge=0, le=100)


class Syllabus(Input):
    content: str = Field(max_length=100000)


class ImportSubject(Input):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(default="", max_length=40)
    semester: str = Field(default="", max_length=40)
    syllabus: str = Field(default="", max_length=100000)


class ImportMark(Input):
    subject_code: str = Field(default="", max_length=40)
    semester: str = Field(default="", max_length=40)
    title: str = Field(default="", max_length=200)
    score: float | None = Field(default=None, ge=0, le=1000000)
    max_score: float | None = Field(default=None, gt=0, le=1000000)
    assessed_on: date | None = None
    kind: str = Field(default="final", max_length=20)


class Draft(Input):
    profile: Profile | None = None
    semesters: list[Semester] = Field(default_factory=list, max_length=30)
    subjects: list[ImportSubject] = Field(default_factory=list, max_length=200)
    marks: list[ImportMark] = Field(default_factory=list, max_length=1000)


def packet(owner_id, engine):
    with engine.connect() as conn:
        profile = (
            conn.execute(
                select(db.academic_profiles).where(
                    db.academic_profiles.c.owner_id == owner_id
                )
            )
            .mappings()
            .first()
        )
        semesters = [
            dict(r)
            for r in conn.execute(
                select(db.semester_results).where(
                    db.semester_results.c.owner_id == owner_id
                )
            ).mappings()
        ]
        syllabi = [
            dict(r)
            for r in conn.execute(
                select(db.subject_syllabi).where(
                    db.subject_syllabi.c.owner_id == owner_id
                )
            ).mappings()
        ]
    return {
        "profile": dict(profile) if profile else None,
        "semesters": sorted(
            semesters,
            key=lambda r: (
                (0, int(r["semester"]))
                if r["semester"].isdigit()
                else (1, r["semester"])
            ),
        ),
        "syllabi": syllabi,
    }


def save_profile(owner_id, engine, body):
    with engine.begin() as conn:
        if conn.scalar(
            select(db.semester_results.c.id)
            .where(
                db.semester_results.c.owner_id == owner_id,
                db.semester_results.c.sgpa > body.sgpa_scale,
            )
            .limit(1)
        ):
            raise HTTPException(
                422,
                "A saved SGPA exceeds this scale. Correct it before changing the scale.",
            )
        upsert(conn, db.academic_profiles, {"owner_id": owner_id}, body.model_dump())
    return packet(owner_id, engine)


def upsert(conn, table, keys, values):
    where = [table.c[k] == v for k, v in keys.items()]
    if conn.execute(select(table).where(*where)).first():
        conn.execute(table.update().where(*where).values(**values))
    else:
        conn.execute(table.insert().values(**keys, **values))


def save_semester(owner_id, engine, body):
    with engine.begin() as conn:
        scale = conn.scalar(
            select(db.academic_profiles.c.sgpa_scale).where(
                db.academic_profiles.c.owner_id == owner_id
            )
        )
        if body.sgpa > (scale or 10):
            raise HTTPException(422, "SGPA exceeds the configured scale.")
        upsert(
            conn,
            db.semester_results,
            {"owner_id": owner_id, "semester": body.semester},
            {"sgpa": body.sgpa},
        )
    return packet(owner_id, engine)


def save_syllabus(owner_id, engine, key, body):
    with engine.begin() as conn:
        personal._owned(owner_id, conn, db.subjects, key)
        upsert(
            conn,
            db.subject_syllabi,
            {"owner_id": owner_id, "subject_id": key},
            {"content": body.content},
        )
    return {"ok": True}


def imports(owner_id, engine):
    with engine.connect() as conn:
        rows = conn.execute(
            select(db.academic_imports)
            .where(db.academic_imports.c.owner_id == owner_id)
            .order_by(db.academic_imports.c.id.desc())
        ).mappings()
        return [
            {
                **{k: v for k, v in r.items() if k not in {"source", "lease"}},
                "retryable": r["status"] == "failed"
                or (
                    r["status"] == "processing" and time.time() - r["started_at"] > 120
                ),
            }
            for r in rows
        ]


def create_import(owner_id, engine, filename, data):
    mime = gemini.media(filename, data)
    lease = str(uuid4())
    with engine.begin() as conn:
        key = conn.execute(
            db.academic_imports.insert().values(
                owner_id=owner_id,
                filename=filename.replace("\\", "/").split("/")[-1][:200],
                mime=mime,
                source=data,
                status="processing",
                draft=None,
                error=None,
                started_at=time.time(),
                lease=lease,
            )
        ).inserted_primary_key[0]
    return key, lease


async def extract(owner_id, engine, key, lease):
    try:
        with engine.connect() as conn:
            row = personal._owned(owner_id, conn, db.academic_imports, key)
        raw = await gemini.recognize(
            row["source"],
            row["mime"],
            Draft.model_json_schema(),
            "Read subject lists, syllabus, dated marks, semester SGPA and total credits. Keep missing dates null. Never derive SGPA or credits from marks. Do not confuse a declaration date with an assessment date.",
        )
        draft = Draft.model_validate(raw).model_dump(mode="json")
        values = {"status": "review", "draft": draft, "error": None}
    except (HTTPException, ValueError, TypeError, KeyError):
        values = {
            "status": "failed",
            "error": "Recognition failed. Check GEMINI_API_KEY/model configuration or retry with a clearer document. Manual entry is still available.",
        }
    with engine.begin() as conn:
        conn.execute(
            db.academic_imports.update()
            .where(
                db.academic_imports.c.id == key,
                db.academic_imports.c.owner_id == owner_id,
                db.academic_imports.c.lease == lease,
            )
            .values(**values)
        )


def retry_import(owner_id, engine, key):
    with engine.begin() as conn:
        row = personal._owned(owner_id, conn, db.academic_imports, key, lock=True)
        if row["status"] not in {"failed", "processing"} or (
            row["status"] == "processing" and time.time() - row["started_at"] < 120
        ):
            raise HTTPException(409, "This import is not ready to retry.")
        lease = str(uuid4())
        conn.execute(
            db.academic_imports.update()
            .where(
                db.academic_imports.c.id == key,
                db.academic_imports.c.owner_id == owner_id,
            )
            .values(
                status="processing", error=None, started_at=time.time(), lease=lease
            )
        )
    return lease


def confirm(owner_id, engine, key, body):
    with engine.begin() as conn:
        row = personal._owned(owner_id, conn, db.academic_imports, key, lock=True)
        if row["status"] == "saved":
            return {"ok": True}
        if row["status"] != "review":
            raise HTTPException(409, "Wait for extraction before saving.")
        if body.profile:
            max_existing = conn.scalar(
                select(db.semester_results.c.sgpa)
                .where(db.semester_results.c.owner_id == owner_id)
                .order_by(db.semester_results.c.sgpa.desc())
                .limit(1)
            )
            if max_existing is not None and max_existing > body.profile.sgpa_scale:
                raise HTTPException(422, "A saved SGPA exceeds the new scale.")
            upsert(
                conn,
                db.academic_profiles,
                {"owner_id": owner_id},
                body.profile.model_dump(),
            )
        scale = (
            conn.scalar(
                select(db.academic_profiles.c.sgpa_scale).where(
                    db.academic_profiles.c.owner_id == owner_id
                )
            )
            or 10
        )
        for sem in body.semesters:
            if sem.sgpa > scale:
                raise HTTPException(
                    422, "A semester SGPA exceeds the configured scale."
                )
            upsert(
                conn,
                db.semester_results,
                {"owner_id": owner_id, "semester": sem.semester},
                {"sgpa": sem.sgpa},
            )
        for sub in body.subjects:
            if not sub.code or not sub.semester:
                raise HTTPException(
                    422, "Fill each subject code and semester before saving."
                )
            upsert(
                conn,
                db.subjects,
                {"owner_id": owner_id, "code": sub.code, "semester": sub.semester},
                {"name": sub.name},
            )
            sid = conn.scalar(
                select(db.subjects.c.id).where(
                    db.subjects.c.owner_id == owner_id,
                    db.subjects.c.code == sub.code,
                    db.subjects.c.semester == sub.semester,
                )
            )
            if sub.syllabus:
                upsert(
                    conn,
                    db.subject_syllabi,
                    {"owner_id": owner_id, "subject_id": sid},
                    {"content": sub.syllabus},
                )
        for mark in body.marks:
            sid = conn.scalar(
                select(db.subjects.c.id).where(
                    db.subjects.c.owner_id == owner_id,
                    db.subjects.c.code == mark.subject_code,
                    db.subjects.c.semester == mark.semester,
                )
            )
            if (
                not sid
                or mark.score is None
                or mark.max_score is None
                or mark.assessed_on is None
                or not mark.title
            ):
                raise HTTPException(
                    422,
                    "Fill each mark's matching subject code, semester, title, score, maximum and date.",
                )
            try:
                validated = personal.AssessmentInput(
                    subject_id=sid,
                    **mark.model_dump(exclude={"subject_code", "semester"}),
                )
            except ValueError as exc:
                raise HTTPException(
                    422, "Check mark values, assessment type, and dates."
                ) from exc
            conn.execute(
                db.personal_assessments.insert().values(
                    owner_id=owner_id, **validated.model_dump()
                )
            )
        conn.execute(
            db.academic_imports.update()
            .where(
                db.academic_imports.c.id == key,
                db.academic_imports.c.owner_id == owner_id,
            )
            .values(status="saved", draft=body.model_dump(mode="json"))
        )
    return {"ok": True}
