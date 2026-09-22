"""Compute evidence in Python; the assistant may explain it, not invent it."""

import hashlib
import json
import time
from collections import defaultdict
from typing import Literal

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from . import database as db
from . import personal


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["accepted", "dismissed"]


def digest(value):
    return hashlib.sha256(
        json.dumps(jsonable_encoder(value), sort_keys=True).encode()
    ).hexdigest()


def topic_frequency(owner_id, engine, subject_id=None):
    q, p = db.paper_questions, db.papers
    if subject_id:
        personal.get_subject(owner_id, engine, subject_id)
    query = (
        select(q.c.id, q.c.topic, q.c.paper_id, p.c.subject_id, p.c.year)
        .join(p, (q.c.paper_id == p.c.id) & (q.c.owner_id == p.c.owner_id))
        .where(q.c.owner_id == owner_id, q.c.confirmed.is_(True))
    )
    if subject_id:
        query = query.where(p.c.subject_id == subject_id)
    groups = defaultdict(list)
    with engine.connect() as conn:
        for row in conn.execute(query).mappings():
            if row["topic"].casefold() != "unclassified":
                groups[(row["subject_id"], row["topic"].casefold())].append(dict(row))
    return sorted(
        [
            {
                "subject_id": sid,
                "topic": rows[0]["topic"],
                "question_count": len(rows),
                "paper_count": len({r["paper_id"] for r in rows}),
                "years": sorted({r["year"] for r in rows}),
                "question_ids": [r["id"] for r in rows],
                "note": "Frequency in your confirmed library, not a prediction of exams or evidence of weakness.",
            }
            for (sid, _), rows in groups.items()
        ],
        key=lambda r: (-r["question_count"], r["topic"]),
    )


def compare_assessments(owner_id, engine, subject_id=None):
    marks = personal.list_records(owner_id, engine, "assessments", subject_id)
    groups = defaultdict(list)
    for mark in marks:
        groups[(mark["subject_id"], mark["kind"], mark["max_score"])].append(mark)
    results = []
    for (sid, kind, scale), rows in groups.items():
        latest = rows[0]
        previous = next(
            (r for r in rows[1:] if r["assessed_on"] < latest["assessed_on"]), None
        )
        same_day = sum(r["assessed_on"] == latest["assessed_on"] for r in rows) > 1
        reason = "Two results show a change, not a reliable long-term trend."
        if not previous:
            reason = "Insufficient evidence: only one dated result in this subject, assessment type and scale."
        if same_day:
            previous = None
            reason = "Multiple results share the latest date; there is no unambiguous latest comparison."
        results.append(
            {
                "subject_id": sid,
                "kind": kind,
                "max_score": scale,
                "latest": latest,
                "previous": previous,
                "change_percentage_points": round(
                    latest["percent"] - previous["percent"], 1
                )
                if previous
                else None,
                "note": reason,
            }
        )
    return results


TABLES = {
    "assessment": db.personal_assessments,
    "question": db.paper_questions,
    "subject": db.subjects,
    "coding": db.coding_snapshots,
    "hackathon": db.hackathon_events,
}


def source(owner_id, conn, kind, key):
    table = TABLES[kind]
    row = personal._owned(owner_id, conn, table, key)
    if kind == "question":
        if not row["confirmed"]:
            raise HTTPException(404, "Question is no longer confirmed.")
        paper = personal._owned(owner_id, conn, db.papers, row["paper_id"])
        row = {
            k: v
            for k, v in row.items()
            if k not in {"embedding", "signature", "revision"}
        }
        row.update(
            filename=paper["filename"],
            year=paper["year"],
            subject_id=paper["subject_id"],
        )
    elif kind == "coding":
        row.pop("raw", None)
    label = {
        "assessment": row.get("title"),
        "question": row.get("topic"),
        "subject": row.get("name"),
        "coding": f"{row.get('source', '')} coding snapshot",
        "hackathon": row.get("project"),
    }[kind]
    data = jsonable_encoder(row)
    return {
        "kind": kind,
        "id": key,
        "label": label,
        "data": data,
        "version": digest(data),
    }


def evidence(owner_id, engine, kind, key):
    if kind not in TABLES:
        raise HTTPException(404, "Unknown evidence type.")
    with engine.connect() as conn:
        return source(owner_id, conn, kind, key)


def current(owner_id, conn, refs):
    for ref in refs:
        try:
            if (
                source(owner_id, conn, ref["kind"], ref["id"])["version"]
                != ref["version"]
            ):
                return False
        except HTTPException:
            return False
    return True


def listing(owner_id, engine):
    with engine.connect() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                select(db.suggestions)
                .where(db.suggestions.c.owner_id == owner_id)
                .order_by(db.suggestions.c.id.desc())
            ).mappings()
        ]
        for row in rows:
            row["stale"] = not current(owner_id, conn, row["evidence"])
    return rows


def refresh(owner_id, engine):
    marks = personal.list_records(owner_id, engine, "assessments")
    topics = topic_frequency(owner_id, engine)
    candidates, used = [], set()
    for topic in topics:
        sid = topic["subject_id"]
        if sid in used:
            continue
        used.add(sid)
        mark = next((m for m in marks if m["subject_id"] == sid), None)
        with engine.connect() as conn:
            refs = [source(owner_id, conn, "subject", sid)] + [
                source(owner_id, conn, "question", key) for key in topic["question_ids"]
            ]
            if mark:
                refs.append(source(owner_id, conn, "assessment", mark["id"]))
        text = f"Revisit {topic['topic']} in {refs[0]['label']}: {topic['question_count']} confirmed questions across {topic['paper_count']} papers."
        if mark:
            text += f" Your recorded {mark['title']} result is {mark['score']:g}/{mark['max_score']:g} on {mark['assessed_on']}."
        text += " Start with one source question. Frequency is a revision cue, not evidence that you are weak at this topic."
        candidates.append((f"Revisit {topic['topic']}", text, refs))
        if len(candidates) >= 4:
            break
    # A self-reported topic may support an action, but the mark alone cannot.
    for mark in marks:
        if mark["subject_id"] in used or not mark["weak_topics"]:
            continue
        with engine.connect() as conn:
            refs = [
                source(owner_id, conn, "assessment", mark["id"]),
                source(owner_id, conn, "subject", mark["subject_id"]),
            ]
        topic = mark["weak_topics"][0]
        candidates.append(
            (
                f"Review your note on {topic}"[:200],
                f"You reported {topic} as a weak topic on {mark['title']} ({mark['assessed_on']}). Try explaining it from memory, then check your notes. This is your own report, not a weakness inferred from the score.",
                refs,
            )
        )
        used.add(mark["subject_id"])
        if len(candidates) >= 6:
            break
    with engine.begin() as conn:
        # Serialize refreshes per owner so duplicate requests cannot repeat suggestions.
        conn.execute(
            select(db.owners.c.id).where(db.owners.c.id == owner_id).with_for_update()
        ).first()
        existing = set(
            conn.execute(
                select(db.suggestions.c.fingerprint).where(
                    db.suggestions.c.owner_id == owner_id
                )
            ).scalars()
        )
        for title, text, refs in candidates:
            fingerprint = digest({"title": title, "text": text, "refs": refs})
            if fingerprint not in existing and current(owner_id, conn, refs):
                conn.execute(
                    db.suggestions.insert().values(
                        owner_id=owner_id,
                        fingerprint=fingerprint,
                        title=title,
                        text=text,
                        evidence=refs,
                        state="proposed",
                        created_at=time.time(),
                    )
                )
                existing.add(fingerprint)
    return listing(owner_id, engine)


def decide(owner_id, engine, key, state):
    with engine.begin() as conn:
        row = personal._owned(owner_id, conn, db.suggestions, key, lock=True)
        if state == "accepted" and not current(owner_id, conn, row["evidence"]):
            raise HTTPException(
                409, "Supporting records changed. Refresh suggestions before accepting."
            )
        if row["state"] != "proposed":
            if row["state"] == state:
                return {"ok": True}
            raise HTTPException(409, "This suggestion already has a saved decision.")
        conn.execute(
            db.suggestions.update()
            .where(db.suggestions.c.id == key, db.suggestions.c.owner_id == owner_id)
            .values(state=state)
        )
    return {"ok": True}
