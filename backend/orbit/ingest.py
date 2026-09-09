"""Lossless, transactional import. Run: python -m orbit.ingest --verify-only."""

import argparse
import csv
import hashlib
import gzip
import json
import math
import uuid
from collections import Counter
from pathlib import Path
from itertools import islice
from sqlalchemy import select, func
from . import database as db
from .config import settings, ROOT

csv.field_size_limit(2**30)
FILES = {
    "valid_uuid_engagement.csv": (db.raw_engagement, True, True),
    "invalid_uuid_enagagement.csv": (db.invalid_engagement, True, False),
    "valid_uuid_submissions.csv": (db.raw_submissions, False, True),
    "invalid_uuid_submissions.csv": (db.invalid_submissions, False, False),
}
ORIGINALS = {
    "student_course_engagement - Course Engagement.csv": [
        "valid_uuid_engagement.csv",
        "invalid_uuid_enagagement.csv",
    ],
    "Hackathon Submissions.csv": [
        "valid_uuid_submissions.csv",
        "invalid_uuid_submissions.csv",
    ],
}
MCQ_FULL_MARKS = 2.0  # User-authorized demo assumption; never replaces supplied marks.


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def file_hash(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def valid_uuid(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        return None


def number(value, default=0):
    try:
        n = float(value)
        return n if math.isfinite(n) else default
    except (TypeError, ValueError):
        return default


def payload(row, engagement):
    text = row.get("engagement_json" if engagement else "submission_json", "")
    if not text.strip():
        return None, "missing_payload"
    try:
        result = json.loads(text)
        if not isinstance(result, dict if engagement else list):
            return None, "unexpected_payload_type"
        return result, None
    except (ValueError, TypeError):
        return None, "invalid_json"


def fingerprint(row):
    canonical = dict(row)
    for key in ["certificate_issued", "is_legacy_completion"]:
        if key in canonical:
            canonical[key] = canonical[key].lower()
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()
    ).digest()


def verify(directory):
    report = {
        "files": {},
        "reconciliation": {},
        "assumptions": {"course_mcq_full_marks": MCQ_FULL_MARKS},
    }
    fingerprints = {}
    for name, (_, engagement, expected_valid) in FILES.items():
        counts, signatures = Counter(), Counter()
        for row in rows(directory / name):
            counts["rows"] += 1
            signatures[fingerprint(row)] += 1
            if bool(valid_uuid(row.get("user_id"))) != expected_valid:
                raise ValueError(
                    f"Unexpected user_id classification in {name}, row {counts['rows']}"
                )
            data, issue = payload(row, engagement)
            if issue:
                counts[issue] += 1
            if isinstance(data, list):
                counts["question_objects"] += len(data)
        fingerprints[name] = signatures
        report["files"][name] = {**counts, "sha256": file_hash(directory / name)}
    for original, parts in ORIGINALS.items():
        if not (directory / original).exists():
            raise ValueError(f"Original required for no-loss verification: {original}")
        signatures = Counter(fingerprint(row) for row in rows(directory / original))
        combined = fingerprints[parts[0]] + fingerprints[parts[1]]
        match = signatures == combined
        report["reconciliation"][original] = {
            "rows": sum(signatures.values()),
            "all_fields_match_after_boolean_case_normalization": match,
            "sha256": file_hash(directory / original),
        }
        if not match:
            raise ValueError(
                f"Split files differ from original {original}; import stopped without dropping data."
            )
    return report


def normalize_progress(row, raw_id, data):
    data = data or {}
    observed = set()
    for event in data.get("resource_clicks_downloads", []) + data.get(
        "mcq_submissions", []
    ):
        if isinstance(event, dict) and event.get("chapter_activity_id") is not None:
            observed.add(str(event["chapter_activity_id"]))
    return dict(
        raw_id=raw_id,
        user_id=valid_uuid(row["user_id"]),
        course_id=row["course_id"],
        mcq_attempted=int(number(row["mcq_attempted_count"])),
        mcq_score=number(row["mcq_total_score_obtained"]),
        total_activities=int(number(row["total_activities_in_course"])),
        observed_activities=len(observed),
        certificate=row["certificate_issued"].lower() == "true",
        legacy_completion=row["is_legacy_completion"].lower() == "true",
        total_views=int(number(row["total_views"])),
    )


def normalize_questions(row, raw_id, data):
    for index, q in enumerate(data or []):
        if not isinstance(q, dict):
            continue  # Original object remains in raw_record.
        topics = q.get("question_sub_domain") or [q.get("skill") or "Unspecified"]
        if not isinstance(topics, list):
            topics = [str(topics)]
        maximum = number(q.get("question_score"), None)
        assumed = maximum is None
        for topic in dict.fromkeys(str(t) for t in topics):
            yield dict(
                raw_id=raw_id,
                question_index=index,
                user_id=valid_uuid(row["user_id"]),
                hackathon_id=row["hackathon_id"],
                round_id=str(q.get("round_id", "")),
                attempt_id=str(q["attempt_id"])
                if q.get("attempt_id") is not None
                else None,
                question_id=str(q.get("question_id", "")),
                skill=str(q.get("skill") or "Unspecified"),
                topic=topic,
                status=str(q.get("status", "unknown")),
                obtained=number(q.get("obtained_score"), None),
                maximum=MCQ_FULL_MARKS if assumed else maximum,
                assumed_maximum=assumed,
                submitted_at=str(q.get("submission_time") or ""),
            )


def import_all(directory, engine, report):
    db.metadata.create_all(engine)
    with engine.begin() as conn:
        for name in ORIGINALS:
            digest = report["reconciliation"][name]["sha256"]
            prior = (
                conn.execute(
                    select(db.source_archives).where(
                        db.source_archives.c.filename == name
                    )
                )
                .mappings()
                .first()
            )
            if prior and prior["sha256"] != digest:
                raise ValueError(f"Original {name} changed; use an explicit migration.")
            if not prior:
                conn.execute(
                    db.source_archives.insert().values(
                        filename=name,
                        sha256=digest,
                        gzip_bytes=gzip.compress(
                            (directory / name).read_bytes(), compresslevel=3
                        ),
                    )
                )
        for name, (table, engagement, is_valid) in FILES.items():
            digest = report["files"][name]["sha256"]
            prior = (
                conn.execute(select(db.imports).where(db.imports.c.filename == name))
                .mappings()
                .first()
            )
            if prior:
                if prior["sha256"] != digest or not prior["completed"]:
                    raise ValueError(
                        f"{name} changed after import. Use a new database or an explicit migration; no data overwritten."
                    )
                actual = conn.scalar(
                    select(func.count())
                    .select_from(table)
                    .where(table.c.source_file == name)
                )
                if actual != prior["row_count"]:
                    raise ValueError(f"Row-count mismatch for already imported {name}")
                continue
            course_ids = set(conn.execute(select(db.courses.c.course_id)).scalars())
            iterator = enumerate(rows(directory / name), 2)
            while batch := list(islice(iterator, 200)):
                raw_values, parsed = [], []
                for line, row in batch:
                    data, issue = payload(row, engagement)
                    parsed.append(data)
                    raw_values.append(
                        dict(
                            source_file=name,
                            source_row=line,
                            source_sha256=digest,
                            user_id=row.get("user_id"),
                            raw_record=row,
                            issue=";".join(
                                filter(
                                    None,
                                    [
                                        "invalid_user_id" if not is_valid else None,
                                        issue,
                                    ],
                                )
                            )
                            or None,
                        )
                    )
                inserted = conn.execute(
                    table.insert().returning(table.c.id, table.c.source_row), raw_values
                ).all()
                ids_by_line = {line: raw_id for raw_id, line in inserted}
                if not is_valid:
                    continue
                new_courses, normalized = [], []
                for (line, row), data in zip(batch, parsed):
                    raw_id = ids_by_line[line]
                    if engagement:
                        if row["course_id"] not in course_ids:
                            new_courses.append(
                                dict(
                                    course_id=row["course_id"],
                                    title=row["course_title"],
                                    subject=row["course_sub_domain"],
                                )
                            )
                            course_ids.add(row["course_id"])
                        normalized.append(normalize_progress(row, raw_id, data))
                    elif data:
                        normalized.extend(normalize_questions(row, raw_id, data))
                if new_courses:
                    conn.execute(db.courses.insert(), new_courses)
                target = db.progress if engagement else db.questions
                for start in range(0, len(normalized), 500):
                    conn.execute(target.insert(), normalized[start : start + 500])
            conn.execute(
                db.imports.insert().values(
                    filename=name,
                    sha256=digest,
                    row_count=report["files"][name]["rows"],
                    completed=True,
                )
            )
        seed(conn)


def seed(conn):
    if conn.scalar(select(func.count()).select_from(db.students)):
        return
    p, q = db.progress, db.questions
    scored = list(
        conn.execute(
            select(p.c.user_id)
            .where(p.c.mcq_attempted > 0)
            .order_by((p.c.mcq_score / p.c.mcq_attempted).desc(), p.c.user_id)
        ).scalars()
    )
    engaged = list(
        conn.execute(
            select(p.c.user_id)
            .group_by(p.c.user_id)
            .order_by(func.count().desc(), p.c.user_id)
        ).scalars()
    )
    shared = list(
        conn.execute(
            select(q.c.user_id)
            .where(q.c.user_id.in_(select(p.c.user_id)))
            .group_by(q.c.user_id)
            .order_by(func.count().desc(), q.c.user_id)
            .limit(2)
        ).scalars()
    )
    history = list(
        conn.execute(
            select(q.c.user_id)
            .group_by(q.c.user_id)
            .order_by(func.count().desc(), q.c.user_id)
            .limit(20)
        ).scalars()
    )
    chosen = list(dict.fromkeys(scored + shared + history + engaged))[:5]
    for i, user_id in enumerate(chosen, 1):
        has_mcq = conn.scalar(
            select(func.count())
            .select_from(p)
            .where(p.c.user_id == user_id, p.c.mcq_attempted > 0)
        )
        rationale = (
            "Has recorded course MCQ scores on the demo 2-point scale."
            if has_mcq
            else "Appears in both datasets: course progress plus hackathon topics and history."
            if user_id in shared
            else "Hackathon history with missing course enrollment: exercises honest missing-data responses."
        )
        conn.execute(
            db.students.insert().values(
                user_id=user_id, label=f"Student {i}", rationale=rationale
            )
        )
    for course in conn.execute(select(db.courses)).mappings():
        for level in ["foundation", "advanced", "closed"]:
            conn.execute(
                db.assessments.insert().values(
                    assessment_id=f"demo-{course['course_id']}-{level}",
                    course_id=course["course_id"],
                    title=f"{course['title']} — {level} demo assessment",
                    active=level != "closed",
                    max_attempts=3,
                    completion_threshold=60 if level == "advanced" else 0,
                    prerequisite_course_id=course["course_id"]
                    if level == "advanced"
                    else None,
                    pass_percent=60,
                    demo_rule=True,
                )
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=settings.dataset_dir)
    args = parser.parse_args()
    report = verify(args.data_dir.resolve())
    if not args.verify_only:
        import_all(args.data_dir.resolve(), db.get_engine(), report)
    output = ROOT / "data" / "import_report.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
