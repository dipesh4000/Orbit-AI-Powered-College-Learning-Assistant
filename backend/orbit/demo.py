"""Explicit local demo fixtures. Never seed a configured production database."""

import json
import re
import secrets
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from fastapi import HTTPException

from . import accounts, coding, insights, papers, personal
from . import database as db


def seed(engine):
    if engine.dialect.name != "sqlite":
        raise RuntimeError("Demo fixtures require a disposable SQLite database.")
    with engine.connect() as conn:
        if conn.scalar(select(db.owners.c.id).limit(1)):
            raise RuntimeError("Demo fixtures require an empty database.")
    fixture = json.loads(
        (Path(__file__).resolve().parents[1] / "demo_data/results.json").read_text()
    )
    owner = accounts.register(
        engine,
        accounts.Registration(
            name="Demo workspace",
            email="demo@orbit.invalid",
            password=secrets.token_urlsafe(32),
        ),
    )
    oid, ids = owner["id"], {}
    for row in fixture["subjects"]:
        subject = personal.create_subject(
            oid,
            engine,
            personal.SubjectInput(
                name=row["name"], code=row["code"], semester=row["semester"]
            ),
        )
        ids[row["code"]] = subject["id"]
        personal.save_record(
            oid,
            engine,
            "assessments",
            personal.AssessmentInput(
                subject_id=subject["id"],
                title="Reference result · declaration date",
                score=row["score"],
                max_score=100,
                assessed_on=row["declared_on"],
                kind="final",
            ),
        )
    today = datetime.now(UTC).date()
    sid = ids["CIC-210"]
    for days, score in [(14, 6), (3, 8)]:
        personal.save_record(
            oid,
            engine,
            "assessments",
            personal.AssessmentInput(
                subject_id=sid,
                title="Illustrative demo · SQL quiz",
                score=score,
                max_score=10,
                assessed_on=today - timedelta(days=days),
                kind="quiz",
                weak_topics=["Joins", "Normalization"],
            ),
        )
    for year, text in [
        (
            2024,
            "1. Explain SQL joins with an example. [5 marks]\n2. Decompose a relation using Normalization. [8 marks]\n3. Compare SQL views and tables. [5 marks]",
        ),
        (
            2025,
            "1. Compare inner and outer Joins. [6 marks]\n2. Explain Normalization up to third normal form. [8 marks]\n3. Write SQL to group student results. [5 marks]",
        ),
    ]:
        pid, _lease = papers.create(
            oid,
            engine,
            f"Illustrative DBMS questions {year}.txt",
            text.encode(),
            sid,
            year,
            "SQL,Joins,Normalization",
        )
        chunks = papers.split_questions([(1, text)], ["Joins", "Normalization", "SQL"])
        with engine.begin() as conn:
            conn.execute(
                db.paper_questions.insert(),
                [
                    {**q, "owner_id": oid, "paper_id": pid, "confirmed": True}
                    for q in chunks
                ],
            )
            conn.execute(
                db.papers.update()
                .where(db.papers.c.id == pid, db.papers.c.owner_id == oid)
                .values(
                    status="ready",
                    error="Authored demo questions; not an actual university past paper. Keyword search is ready.",
                )
            )
    for days, solved in [(14, 118), (0, 136)]:
        coding.save_manual(
            oid,
            engine,
            coding.ManualInput(
                solved=solved,
                active_days=42 + (14 - days),
                contributions=210 + (14 - days) * 3,
                commits=120,
                stars=8,
                pull_requests=12,
                note="Illustrative demo totals, not imported personal coding data.",
            ),
        )
        with engine.begin() as conn:
            key = conn.scalar(
                select(db.coding_snapshots.c.id)
                .where(db.coding_snapshots.c.owner_id == oid)
                .order_by(db.coding_snapshots.c.id.desc())
                .limit(1)
            )
            conn.execute(
                db.coding_snapshots.update()
                .where(db.coding_snapshots.c.id == key)
                .values(fetched_at=time.time() - days * 86400)
            )
    personal.save_record(
        oid,
        engine,
        "hackathons",
        personal.HackathonInput(
            name="Illustrative demo · Campus Build Weekend",
            event_date=today - timedelta(days=21),
            role="Backend developer (demo)",
            project="Study-room finder (demo)",
            summary="Illustrative project record demonstrating a booking API and availability view.",
            technologies=["Python", "React", "PostgreSQL"],
            result="Prototype submitted — illustrative",
            reflection="Demo reflection: improve validation and test simultaneous bookings before adding more features.",
        ),
    )
    insights.refresh(oid, engine)
    return owner


async def reply(message, owner_id, engine):
    """Bounded offline walkthrough, visibly distinguished from a language model."""
    from .personal_tools import PersonalRegistry

    registry = PersonalRegistry(engine)
    subjects, _ = await registry.execute("get_subjects", {}, owner_id)
    lower = message.casefold()
    subject = next(
        (
            s
            for s in subjects
            if s["name"].casefold() in lower or s["code"].casefold() in lower
        ),
        None,
    )
    if subject is None and any(
        term in lower for term in ("sql", "dbms", "database", "normalization", "joins")
    ):
        subject = next((s for s in subjects if s["code"] == "CIC-210"), None)
    sid = subject["id"] if subject else None
    calls = ["get_subjects"]

    async def read(name, args):
        calls.append(name)
        return (await registry.execute(name, args, owner_id))[0]

    if any(
        term in lower
        for term in ("plan", "focus", "revise", "review", "hours", "minutes", "friday")
    ):
        saved = await read("get_suggestions", {})
        items = [r for r in saved if not r["stale"] and r["state"] != "dismissed"]
        if sid:
            topics = await read("get_topic_frequency", {"subject_id": sid})
            marks = await read("get_assessments", {"subject_id": sid})
            questions = await read(
                "search_pyq", {"query": "SQL", "subject_id": sid, "mode": "keyword"}
            )
            allowed_ids = {eid for r in items for eid in r["evidence_ids"]}
            topics = [
                t
                for t in topics
                if any(f"question-{q}" in allowed_ids for q in t["question_ids"])
            ]
            if topics and marks and questions:
                m, topic = marks[0], topics[0]
                duration = re.search(r"(\d+)\s*(hours?|hrs?|minutes?|mins?)", lower)
                minutes = (
                    min(
                        240,
                        max(
                            15,
                            int(duration[1])
                            * (60 if duration[2].startswith(("h",)) else 1),
                        ),
                    )
                    if duration
                    else (120 if "two hours" in lower else 60)
                )
                first = minutes // 4
                second = minutes // 2
                answer = f"A suggested {minutes}-minute revision plan for {subject['name']}:\n\nYour latest saved mark is {m['score']:g}/{m['max_score']:g} on {m['assessed_on']} [{m['evidence_id']}]. {topic['topic']} appears in {topic['question_count']} confirmed questions across {topic['paper_count']} papers [{topic['evidence_ids'][0]}].\n\n1. **{first} minutes:** explain {topic['topic']} from memory and note gaps.\n2. **{second} minutes:** work through the source question: {questions[0]['content']} [{questions[0]['evidence_id']}].\n3. **{minutes - first - second} minutes:** check your course notes and record what needs another pass.\n\nThese are suggested time allocations. The demo papers are authored examples; topic frequency does not establish a weakness or predict an exam."
            else:
                answer = "There is not enough current, undismissed paper evidence for this plan. Refresh suggestions or confirm more questions. I will not re-propose an unchanged dismissed action."
        else:
            answer = (
                "\n\n".join(
                    f"**{r['title']}**\n{r['text']} "
                    + " ".join(f"[{e}]" for e in r["evidence_ids"])
                    for r in items[:3]
                )
                or "No current suggestions are available. Add confirmed paper questions and refresh suggestions."
            )
    elif any(term in lower for term in ("compare", "change", "improv", "trend")):
        pairs = await read("compare_assessments", {"subject_id": sid})
        answer = (
            "\n\n".join(
                f"**{next(s['name'] for s in subjects if s['id'] == p['subject_id'])} · {p['kind']}**: "
                + (
                    f"{p['previous']['score']:g}/{p['max_score']:g} → {p['latest']['score']:g}/{p['max_score']:g}; {p['change_percentage_points']:+g} percentage points. [{p['previous']['evidence_id']}] [{p['latest']['evidence_id']}]. "
                    if p["previous"]
                    else f"[{p['latest']['evidence_id']}] "
                )
                + p["note"]
                for p in pairs[:8]
            )
            or "No comparable marks are saved."
        )
    elif any(term in lower for term in ("coding", "solved", "github")):
        packet = await read("get_coding_snapshot", {})
        row = packet["latest"]["manual"]
        answer = (
            f"The saved manual snapshot reports {row['normalized']['solved']} problems solved and {row['normalized']['contributions']} contributions [{row['evidence_id']}]. These are illustrative demo counts, not live imported statistics or proof of skill."
            if row
            else "No manual coding snapshot is saved."
        )
    elif any(term in lower for term in ("hackathon", "project")):
        rows = await read("get_hackathons", {})
        answer = (
            "\n\n".join(
                f"**{r['project']}** · {r['role']}\n{r['reflection']} [{r['evidence_id']}]. Participation alone does not establish a skill."
                for r in rows
            )
            or "No project records are saved."
        )
    elif any(term in lower for term in ("paper", "question", "topic")):
        rows = await read("get_topic_frequency", {"subject_id": sid})
        answer = (
            "\n".join(
                f"- {r['topic']}: {r['question_count']} questions across {r['paper_count']} papers "
                + " ".join(f"[{e}]" for e in r["evidence_ids"])
                for r in rows
            )
            or "No confirmed, classified questions are saved."
        )
        answer += "\n\nThis is frequency in the confirmed library, not exam prediction."
    elif any(term in lower for term in ("mark", "score", "result", "sql", "dbms")):
        rows = await read("get_assessments", {"subject_id": sid})
        answer = (
            f"{len(rows)} saved results"
            + (f" for {subject['name']}" if subject else " across your subjects")
            + ".\n\n"
            + "\n".join(
                f"- {r['title']}: **{r['score']:g}/{r['max_score']:g}** · {r['assessed_on']} [{r['evidence_id']}]"
                for r in rows[:8]
            )
        )
        answer += "\n\nReference-result dates are declaration dates. The SQL quizzes are illustrative and kept separate from final results."
    else:
        answer = "This is a local, rule-based demo, so open-ended AI answers are unavailable. Try: ‘Show my DBMS marks’, ‘Compare my DBMS results’, ‘SQL test Friday, two hours’, ‘Show paper topics’, or ‘Show coding activity’."
    refs = set(re.findall(r"\[([a-z]+-\d+)\]", answer))
    # Suggestion reads supply stored refs but their current records remain owner-checked.
    for eid in refs - registry.evidence.keys():
        kind, key = eid.rsplit("-", 1)
        try:
            ref = insights.evidence(owner_id, engine, kind, int(key))
            registry.evidence[eid] = {
                "id": eid,
                "kind": kind,
                "record_id": int(key),
                "source": ref["label"],
                "data": ref["data"],
            }
        except (KeyError, ValueError, HTTPException):
            continue
    return {
        "answer": answer,
        "sources": [s for key, s in registry.evidence.items() if key in refs],
        "tools_called": calls,
        "cache_hits": 0,
        "demo": True,
    }
