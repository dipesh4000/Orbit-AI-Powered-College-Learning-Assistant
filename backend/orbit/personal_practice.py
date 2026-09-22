"""Private practice; answer keys never leave the server before submission."""

import json
import time
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from . import database as db
from . import insights, papers, personal
from .practice import QUIZ_INSTRUCTIONS, QuestionSet, validate_questions


class Generate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    subject_id: int = Field(gt=0)
    topic: str = Field(min_length=2, max_length=120)
    difficulty: Literal["foundation", "intermediate", "advanced"] = "foundation"
    count: int = Field(default=3, ge=1, le=10)


class Answers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: list[str] = Field(min_length=1, max_length=10)


def public(row):
    row = dict(row)
    if row["answered_at"] is None:
        row["questions"] = [
            {k: v for k, v in q.items() if k not in {"correct_answer", "explanation"}}
            for q in row["questions"]
        ]
    return row


def listing(owner_id, engine, subject_id=None):
    query = select(db.personal_practice).where(
        db.personal_practice.c.owner_id == owner_id
    )
    if subject_id:
        personal.get_subject(owner_id, engine, subject_id)
        query = query.where(db.personal_practice.c.subject_id == subject_id)
    with engine.connect() as conn:
        return [
            public(r)
            for r in conn.execute(
                query.order_by(db.personal_practice.c.id.desc())
            ).mappings()
        ]


async def generate(owner_id, engine, body, model):
    rows = await run_in_threadpool(
        papers.search,
        owner_id,
        engine,
        papers.Search(query=body.topic, subject_id=body.subject_id),
    )
    if not rows:
        raise HTTPException(
            422,
            "No confirmed questions match this topic. Review a paper first or try its exact topic label.",
        )
    refs = [
        await run_in_threadpool(
            insights.evidence, owner_id, engine, "question", r["id"]
        )
        for r in rows[:5]
    ]
    passages = [
        {"id": f"question-{r['id']}", "content": r["data"]["content"]} for r in refs
    ]
    messages = [
        {
            "role": "system",
            "content": QUIZ_INSTRUCTIONS
            + '\nPaper questions may not contain answers. Only generate answerable questions when the supplied text establishes the answer. If insufficient, return {"questions": []}. Never solve a source question using outside knowledge.',
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "request": body.model_dump(),
                    "passages": passages,
                    "schema": QuestionSet.model_json_schema(),
                }
            ),
        },
    ]
    for attempt in range(2):
        answer = await model.complete(messages)
        text = answer.get("content") or ""
        try:
            if json.loads(text) == {"questions": []}:
                raise HTTPException(
                    422,
                    "These papers contain questions but insufficient answer evidence. Add and confirm material containing explanations before generating a quiz.",
                )
            questions = validate_questions(
                text, body.count, {p["id"] for p in passages}
            )
            break
        except ValueError as exc:
            if attempt:
                raise HTTPException(
                    422,
                    "Generated questions failed validation. Try another topic or fewer questions.",
                ) from exc
            messages.extend(
                [
                    {"role": "assistant", "content": text},
                    {
                        "role": "user",
                        "content": f"Correct the JSON under the original rules: {str(exc)[:1000]}",
                    },
                ]
            )

    def save():
        with engine.begin() as conn:
            if not insights.current(owner_id, conn, refs):
                raise HTTPException(
                    409, "Source questions changed. Generate a fresh set."
                )
            key = conn.execute(
                db.personal_practice.insert().values(
                    owner_id=owner_id,
                    subject_id=body.subject_id,
                    topic=body.topic,
                    difficulty=body.difficulty,
                    questions=questions,
                    sources=refs,
                    created_at=time.time(),
                )
            ).inserted_primary_key[0]
            return public(personal._owned(owner_id, conn, db.personal_practice, key))

    return await run_in_threadpool(save)


def submit(owner_id, engine, key, body):
    with engine.begin() as conn:
        row = personal._owned(owner_id, conn, db.personal_practice, key, lock=True)
        if row["answered_at"] is not None:
            if row["answers"] != body.answers:
                raise HTTPException(
                    409,
                    "This attempt already has saved answers. Generate another set to practise again.",
                )
            return public(row)
        if len(body.answers) != len(row["questions"]) or any(
            a not in q["options"] for a, q in zip(body.answers, row["questions"])
        ):
            raise HTTPException(422, "Choose one listed answer for every question.")
        if not insights.current(owner_id, conn, row["sources"]):
            raise HTTPException(
                409, "Source questions changed or were removed. Generate a fresh set."
            )
        values = {
            "answers": body.answers,
            "correct": sum(
                a == q["correct_answer"] for a, q in zip(body.answers, row["questions"])
            ),
            "answered_at": time.time(),
        }
        conn.execute(
            db.personal_practice.update()
            .where(
                db.personal_practice.c.id == key,
                db.personal_practice.c.owner_id == owner_id,
            )
            .values(**values)
        )
        return public({**row, **values})


def remove(owner_id, engine, key):
    with engine.begin() as conn:
        personal._owned(owner_id, conn, db.personal_practice, key)
        conn.execute(
            db.personal_practice.delete().where(
                db.personal_practice.c.id == key,
                db.personal_practice.c.owner_id == owner_id,
            )
        )
    return {"ok": True}
