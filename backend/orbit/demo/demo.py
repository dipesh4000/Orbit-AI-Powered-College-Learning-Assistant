"""Explicit local demo fixtures. Never seed a configured production database."""

import json
import re
import secrets
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select

from ..core import accounts
from ..core import database as db
from ..features import academics, coding, insights, papers, personal, personal_practice


def seed(engine):
    if engine.dialect.name != "sqlite":
        raise RuntimeError("Demo fixtures require a disposable SQLite database.")
    with engine.connect() as conn:
        if conn.scalar(select(db.owners.c.id).limit(1)):
            raise RuntimeError("Demo fixtures require an empty database.")
    fixture = json.loads(
        (Path(__file__).resolve().parents[2] / "demo_data/results.json").read_text()
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
    academics.save_profile(
        oid,
        engine,
        academics.Profile(
            program="CSE · demo reference",
            current_semester="3",
            total_credits=82,
            target_sgpa=9,
            sgpa_scale=10,
        ),
    )
    for index, value in enumerate(fixture["reported_sgpa"][:2], 1):
        academics.save_semester(
            oid, engine, academics.Semester(semester=str(index), sgpa=value)
        )
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
    quiz_questions = [
        {
            "question": "Which SQL clause filters groups after aggregation?",
            "options": ["WHERE", "HAVING", "ORDER BY", "SELECT"],
            "correct_answer": "HAVING",
            "explanation": "HAVING filters grouped results; WHERE filters individual rows before grouping.",
        },
        {
            "question": "Which join keeps every row from the left table, even without a match?",
            "options": ["INNER JOIN", "LEFT JOIN", "CROSS JOIN", "SELF JOIN"],
            "correct_answer": "LEFT JOIN",
            "explanation": "A LEFT JOIN retains all left-table rows and uses NULL for unmatched right-table columns.",
        },
        {
            "question": "What is a primary goal of database normalization?",
            "options": ["Duplicate every row", "Remove all keys", "Reduce redundant data", "Sort every table"],
            "correct_answer": "Reduce redundant data",
            "explanation": "Normalization organizes relations to reduce redundancy and insertion, update, and deletion anomalies.",
        },
    ]
    # Authored fixtures use the same persistence, answer hiding and grading as real sets.
    for completed in (True, False):
        with engine.begin() as conn:
            quiz_id = conn.execute(
                db.personal_practice.insert().values(
                    owner_id=oid,
                    subject_id=sid,
                    topic="DBMS fundamentals · demo" if not completed else "SQL revision · demo",
                    difficulty="foundation",
                    questions=quiz_questions,
                    sources=[],
                    created_at=time.time() - (86400 if completed else 3600),
                )
            ).inserted_primary_key[0]
        if completed:
            personal_practice.submit(
                oid, engine, quiz_id,
                personal_practice.Answers(answers=["WHERE", "LEFT JOIN", "Reduce redundant data"]),
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
    def demo_activity(day_offset, problem=False):
        """Deterministic, irregular demo activity with breaks and study sprints."""
        day = datetime.now(UTC) - timedelta(days=day_offset)
        pulse = (day_offset * 37 + day.month * 11 + day.day * 7) % 101
        # Exam breaks, holidays, and naturally quieter weekends create real gaps.
        if 72 <= day_offset <= 88 or 201 <= day_offset <= 219:
            return 0
        if day.weekday() >= 5 and pulse < 72:
            return 0
        # A few multi-week build/revision windows produce clustered activity.
        sprint = any(start <= day_offset <= start + width for start, width in ((4, 18), (112, 27), (286, 22)))
        threshold = 70 if sprint else (48 if problem else 42)
        if pulse > threshold:
            return 0
        base = 1 + ((pulse * 13 + day_offset) % (7 if problem else 11))
        return base + (3 if sprint and pulse < 28 else 0)

    sample = {
        "status": {"success": True},
        "data": {
            "codolioCardDetails": {
                "totalQuestionsSolved": 326,
                "totalActiveDays": 181,
                "totalSubmissions": 395,
                "maxStreak": 24,
                "currentStreak": 4,
                "totalContestAttended": 16,
            },
            "questionDistribution": {
                "Fundamentals": {"GFG Basic": 6, "HackerRank": 9},
                "DSA": {"Easy": 119, "Medium": 145, "Hard": 19},
                "Competitive Programming": {"CodeChef": 21, "AtCoder": 7},
            },
            "contestDetails": {
                "LeetCode": {"attended": 7, "rating": 1585},
                "CodeChef": {"attended": 2},
                "AtCoder": {"attended": 5},
                "CodeChef DSA": {"attended": 2},
            },
            "problemSolvingActivity": {
                str(
                    int(
                        (datetime.now(UTC) - timedelta(days=i))
                        .replace(hour=0, minute=0, second=0, microsecond=0)
                        .timestamp()
                    )
                ): demo_activity(i, problem=True)
                for i in range(365)
            },
            "githubProfileDetails": {
                "totalContributions": 412,
                "commitCounts": 284,
                "pushRequestsCount": 12,
                "stars": 8,
                "issues": 5,
                "totalActiveDays": 126,
                "developmentActivity": {
                    str(
                        int(
                            (datetime.now(UTC) - timedelta(days=i))
                            .replace(hour=0, minute=0, second=0, microsecond=0)
                            .timestamp()
                        )
                    ): demo_activity(i)
                    for i in range(365)
                },
                "languageDistributions": {
                    "TypeScript": 470,
                    "Python": 310,
                    "CSS": 140,
                    "SQL": 80,
                },
            },
        },
    }
    with engine.begin() as conn:
        conn.execute(
            db.coding_snapshots.insert().values(
                owner_id=oid,
                source="codolio",
                handle="illustrative-demo",
                fetched_at=time.time(),
                raw=sample,
                normalized=coding.normalize(sample, time.time()),
            )
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
    from ..personal_tools import PersonalRegistry

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
        answer += (
            "\n\n## Turn this into a focused study session\n\n"
            "### 1. Start with recall\n\n"
            "Pick one topic from the records above. Close your notes and explain the main idea in a few sentences. "
            "Write down the exact step you cannot explain; that gives the session a concrete target. "
            "If no current suggestion is available, choose a topic from your own syllabus instead.\n\n"
            "### 2. Work through one example\n\n"
            "Use a confirmed paper question or an example from your notes. Attempt it before checking the explanation. "
            "For a database question, use a tiny table and trace which rows survive each operation. "
            "Record your reasoning as well as the final answer.\n\n"
            "### 3. Check understanding\n\n"
            "- Explain why your answer works.\n"
            "- Change one assumption and predict how the result changes.\n"
            "- Identify one common mistake and show how you would detect it.\n\n"
            "### 4. Finish with a next step\n\n"
            "Save a short note: **what I understood, what I missed, and what I will practise next**. "
            "Try a saved quiz in Practice when you want feedback. A quiz result helps you choose another exercise; "
            "it remains separate from your formal marks.\n\n"
            "This is a suggested study method, not an assessment of weaknesses beyond the available records."
        )
        if "focus" in lower:
            answer += (
                "\n\n## Decide what deserves attention first\n\n"
                "Use three questions to order your work: **What is due soon? What can I currently explain without help? "
                "What source material can I use to check my answer?** Start with a nearby deadline when you have one, "
                "then choose a manageable topic with a clear exercise. The workspace does not establish your deadlines, "
                "so this ordering is a decision rule you can apply, rather than a claim about your schedule.\n\n"
                "Keep the session narrow. Finishing one worked example, explaining the mistake you made, and trying a variation "
                "usually gives you a more useful checkpoint than opening several subjects and reading a little of each. "
                "If you can already solve the example independently, move on to a harder variation or another topic. "
                "If you need the solution throughout, revisit the prerequisite concept and try again later.\n\n"
                "**Your stopping point:** one completed exercise, a short explanation in your own words, and a specific next action. "
                "That makes the next study session easier to start and gives you something concrete to compare over time."
            )
        else:
            answer += (
                "\n\n## A practical 60-minute session template\n\n"
                "| Time | Activity | What to produce |\n|---|---|---|\n"
                "| 0–10 minutes | Recall the concept without notes | A short explanation and one uncertainty |\n"
                "| 10–35 minutes | Attempt one question | A worked solution with reasoning |\n"
                "| 35–50 minutes | Check and retry the difficult step | A corrected explanation |\n"
                "| 50–60 minutes | Try a variation and record the next task | A concrete follow-up |\n\n"
                "Use this as a default template when you have not specified a duration; if a tailored allocation appears above, "
                "follow that allocation instead. Put your notes out of sight for the first attempt. When you get stuck, "
                "identify the exact step before looking up the explanation, then close the notes and reproduce it independently. "
                "The aim is to practise retrieval and reasoning, rather than simply recognize a familiar solution.\n\n"
                "At the end, write a two-line handoff to yourself: what you can now do, and the first exercise to attempt next time."
            )
    elif any(term in lower for term in ("practice", "practise")):
        rows = await read("get_practice_history", {"subject_id": sid})
        completed = [r for r in rows if r["answered_at"] is not None]
        answer = (
            "\n".join(
                f"- {r['topic']}: {r['correct']}/{len(r['questions'])} in practice [{r['evidence_id']}]"
                for r in completed[:8]
            )
            or "No completed practice attempts yet. Open Practice to begin."
        )
        answer += "\n\nPractice feedback is separate from formal marks."
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
    elif any(term in lower for term in ("coding", "solved", "github", "development", "dsa")):
        packet = await read("get_coding_snapshot", {})
        row = packet["latest"]["manual"]
        answer = (
            f"## Coding activity snapshot\n\n"
            f"Your latest saved snapshot reports **{row['normalized']['solved']} problems solved** and "
            f"**{row['normalized']['contributions']} GitHub contributions** [{row['evidence_id']}].\n\n"
            "### DSA / problem solving\n\n"
            f"- **Problems solved:** {row['normalized']['solved']}\n"
            f"- **Active days:** {row['normalized']['active_days']}\n\n"
            "### Development\n\n"
            f"- **Contributions:** {row['normalized']['contributions']}\n"
            f"- **Commits:** {row['normalized']['commits']}\n"
            f"- **Pull requests:** {row['normalized']['pull_requests']}\n"
            f"- **Stars:** {row['normalized']['stars']}\n\n"
            "### How to read this\n\n"
            "The two sections describe different kinds of effort. Problem-solving totals describe exercises completed, "
            "while development activity records actions around repositories. Read them side by side; adding the numbers "
            "would create a score with no useful meaning. The manual snapshot is self-reported and may cover a different "
            "period from your connected profile.\n\n"
            "- Use the contribution calendar to spot sustained periods and genuine breaks.\n"
            "- Pair totals with the projects you shipped; a count alone does not show code quality.\n"
            "- Review a recent repository and explain one architectural decision in your own words.\n\n"
            "```text\nA useful next session: choose one recent file, trace its inputs and outputs, then write three questions you would ask in a code review.\n```\n\n"
            "These are illustrative demo counts, not live imported statistics or proof of skill."
            "\n\n### Turn the summary into a balanced next session\n\n"
            "**DSA:** choose a problem from a topic you have already studied. Explain a simple solution first, "
            "then identify its time and space costs. After improving it, test an empty input, a smallest valid input, "
            "and an input that stresses your assumptions. Write down the pattern you would recognize next time.\n\n"
            "**Development:** pick one small change in a real repository. Trace the user action through the relevant "
            "function and storage layer, make the change, and add a focused check for the behavior. Review the diff "
            "and explain why the implementation fits the existing architecture before considering it finished.\n\n"
            "**Review together:** compare what you learned from the exercise with the decisions in the codebase. "
            "A useful outcome is one explained algorithm and one verified project improvement, not a target contribution count. "
            "Use the Coding statistics page to inspect each source and its saved date before comparing snapshots. "
            "A quiet period in the activity graph may reflect time away or missing data; it does not by itself establish lost progress."
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
        if "study room" in re.sub(r"[-–—]", " ", lower):
            project = next((r for r in rows if "study room" in re.sub(r"[-–—]", " ", r["project"].casefold())), None)
            if project:
                answer = (
                    "## Your Study room finder project\n\n"
                    f"**{project['project']}** is a campus booking prototype built during a team event. "
                    f"Your saved role was **{project['role']}** [{project['evidence_id']}].\n\n"
                    "### What you built\n\n"
                    f"{project['summary']} The core idea is to help students find a room and see availability before booking.\n\n"
                    "### Your contribution\n\n"
                    "The record describes backend work on a booking API, with an availability view as part of the prototype. "
                    "Your saved technology stack includes **Python, React, and PostgreSQL**. "
                    "The record does not include source code, so specific endpoints, schemas, and deployment details still need to be verified.\n\n"
                    "### Outcome and reflection\n\n"
                    f"**Outcome:** {project['result']}.\n\n"
                    f"**Your reflection:** {project['reflection']}\n\n"
                    "### A useful next iteration\n\n"
                    "1. **Validate bookings:** reject invalid time ranges and missing room details.\n"
                    "2. **Test overlapping requests:** send two requests for the same room and time, and check that only one succeeds.\n"
                    "3. **Make conflicts clear:** show a helpful message and refreshed availability when a slot is taken.\n"
                    "4. **Document the flow:** explain how the UI, booking API, and database coordinate a reservation.\n\n"
                    "These are suggested improvements, not claims about features already implemented.\n\n"
                    "### How to present it\n\n"
                    "Start with the user problem: students need to know whether a room is available before attempting a reservation. "
                    "Then explain your backend responsibility and the availability view described in the record. "
                    "Finish with the reliability challenge you identified, rather than listing tools alone.\n\n"
                    "### Technical discussion to prepare\n\n"
                    "Be ready to trace one booking from the interface to the database and back. Explain where you would "
                    "validate a time range, how you would detect an overlap, and what the user should see if another "
                    "booking takes the slot first. These are useful review questions; the saved record does not specify "
                    "which mechanisms your prototype currently uses.\n\n"
                    "A convincing demonstration would include a successful booking, an invalid request, and two "
                    "simultaneous requests for the same slot. Capture the expected outcome for each case before testing. "
                    "Attach the repository or reviewed files in Practice to discuss the actual implementation in more depth.\n\n"
                    "> I worked on the backend of a study-room booking prototype, connecting a booking API with an availability view. "
                    "My next focus is validation and reliable handling of simultaneous bookings.\n\n"
                    "This summary uses the illustrative project record in the demo workspace."
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
        answer = (
            "## I can help you turn your records into a next step\n\n"
            "This local demo uses a **rule-based assistant**, so it answers from the preloaded workspace rather than calling a live model. You can still explore the complete evidence-backed flow.\n\n"
            "### Try one of these\n\n"
            "- **Plan a session:** `SQL test Friday, two hours`\n"
            "- **Review performance:** `Compare my DBMS results`\n"
            "- **Inspect material:** `Show paper topics`\n"
            "- **Check momentum:** `Show coding activity`\n\n"
            "For each supported request, Orbit reads the relevant saved records, cites the evidence it used, and keeps suggestions separate from formal marks."
        )
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
