from sqlalchemy import and_, case, func, select

from . import database as db
from .business_rules import course_metrics, eligibility
from .cache import cache


class Services:
    def __init__(self, engine):
        self.engine = engine

    def list_courses(self, user_id):
        with self.engine.connect() as conn:
            statement = (
                select(db.courses)
                .join(db.progress, db.courses.c.course_id == db.progress.c.course_id)
                .where(db.progress.c.user_id == user_id)
                .distinct()
            )
            return [dict(r) for r in conn.execute(statement).mappings()]

    def get_course_progress(self, user_id, course_id=None):
        p = db.progress
        statement = (
            select(p, db.courses.c.title, db.courses.c.subject)
            .join(db.courses, p.c.course_id == db.courses.c.course_id)
            .where(p.c.user_id == user_id)
        )
        if course_id is not None:
            statement = statement.where(p.c.course_id == course_id)
        with self.engine.connect() as conn:
            result = [
                course_metrics(dict(r)) for r in conn.execute(statement).mappings()
            ]
        # Duplicates stay in storage. Avoid silently adding duplicate snapshots together.
        counts = {}
        for row in result:
            counts[row["course_id"]] = counts.get(row["course_id"], 0) + 1
        for row in result:
            row["multiple_source_rows"] = counts[row["course_id"]] > 1
        return result

    def get_course_performance(self, user_id):
        return self.get_course_progress(user_id)

    def unique_questions(self, user_id):
        q = db.questions
        # One question can have several topic tags. History scores count it once.
        return (
            select(
                q.c.raw_id,
                q.c.question_index,
                q.c.hackathon_id,
                q.c.round_id,
                q.c.attempt_id,
                q.c.question_id,
                q.c.status,
                q.c.obtained,
                q.c.maximum,
                q.c.submitted_at,
            )
            .where(q.c.user_id == user_id)
            .distinct()
            .subquery()
        )

    def get_hackathon_history(self, user_id, limit=30):
        q = self.unique_questions(user_id)
        scored = and_(
            q.c.status.in_(["pass", "fail", "partiallyCorrect", "unAttempted"]),
            q.c.maximum > 0,
            q.c.obtained >= 0,
            q.c.obtained <= q.c.maximum,
        )
        statement = select(
            q.c.hackathon_id,
            q.c.round_id,
            q.c.attempt_id,
            func.count().label("question_count"),
            func.sum(case((scored, q.c.obtained), else_=0)).label("obtained"),
            func.sum(case((scored, q.c.maximum), else_=0)).label("maximum"),
            func.sum(case((q.c.status == "underReview", 1), else_=0)).label(
                "pending_questions"
            ),
            func.max(q.c.submitted_at).label("submitted_at"),
        )
        statement = (
            statement.group_by(q.c.hackathon_id, q.c.round_id, q.c.attempt_id)
            .order_by(func.max(q.c.submitted_at).desc())
            .limit(limit)
        )
        with self.engine.connect() as conn:
            result = [dict(r) for r in conn.execute(statement).mappings()]
        for row in result:
            row["score_percent"] = (
                round(100 * row["obtained"] / row["maximum"], 2)
                if row["maximum"]
                else None
            )
            row["score_basis"] = (
                "Supplied question marks; missing marks use demo 2-point scale. Pending review excluded."
            )
        return result

    def get_weak_topics(self, user_id, threshold=0.6, course_id=None):
        q = db.questions
        condition = and_(
            q.c.user_id == user_id,
            q.c.status.in_(["pass", "fail", "partiallyCorrect", "unAttempted"]),
            q.c.maximum > 0,
            q.c.obtained >= 0,
            q.c.obtained <= q.c.maximum,
        )
        if course_id:
            with self.engine.connect() as conn:
                subject = conn.scalar(
                    select(db.courses.c.subject).where(
                        db.courses.c.course_id == course_id
                    )
                )
            aliases = {"English Ability": "English", "Database Management": "SQL"}
            condition = and_(
                condition,
                func.lower(q.c.skill) == (aliases.get(subject, subject) or "").lower(),
            )
        statement = select(
            q.c.skill,
            q.c.topic,
            func.count().label("question_count"),
            func.sum(q.c.obtained).label("obtained"),
            func.sum(q.c.maximum).label("maximum"),
        ).where(condition)
        statement = statement.group_by(q.c.skill, q.c.topic).having(
            func.sum(q.c.obtained) < threshold * func.sum(q.c.maximum)
        )
        with self.engine.connect() as conn:
            result = [dict(r) for r in conn.execute(statement).mappings()]
        for row in result:
            row["score_percent"] = round(100 * row["obtained"] / row["maximum"], 2)
            row["evidence"] = (
                "Hackathon question topics; subject mapping is a documented demo assumption."
            )
        return sorted(result, key=lambda r: (r["score_percent"], -r["question_count"]))[
            :20
        ]

    def get_recommended_topics(self, user_id, course_id):
        return [
            row["topic"] for row in self.get_weak_topics(user_id, course_id=course_id)
        ]

    def list_assessments(self, user_id, course_id=None):
        enrolled = select(db.progress.c.course_id).where(
            db.progress.c.user_id == user_id
        )
        statement = select(db.assessments).where(
            db.assessments.c.course_id.in_(enrolled)
        )
        if course_id:
            statement = statement.where(db.assessments.c.course_id == course_id)
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(statement).mappings()]

    def check_assessment_eligibility(self, user_id, assessment_id):
        # Always fresh, including its inputs. Never use the tool cache here.
        with self.engine.connect() as conn:
            assessment = (
                conn.execute(
                    select(db.assessments).where(
                        db.assessments.c.assessment_id == assessment_id
                    )
                )
                .mappings()
                .first()
            )
            attempts = conn.scalar(
                select(func.count())
                .select_from(db.assessment_attempts)
                .where(
                    db.assessment_attempts.c.user_id == user_id,
                    db.assessment_attempts.c.assessment_id == assessment_id,
                )
            )
        if not assessment:
            return eligibility(None, None, None, None)
        rows = self.get_course_progress(user_id, assessment["course_id"])
        prerequisite = (
            self.get_course_progress(user_id, assessment["prerequisite_course_id"])
            if assessment["prerequisite_course_id"]
            else []
        )
        if len(rows) > 1 or len(prerequisite) > 1:
            return {
                "eligible": None,
                "status": "unknown",
                "reason": "Multiple source snapshots require reconciliation.",
                "unmet_conditions": [],
                "missing_information": ["Unambiguous course progress"],
            }
        return eligibility(
            dict(assessment),
            rows[0] if rows else None,
            prerequisite[0] if prerequisite else None,
            attempts,
        )

    def dashboard(self, user_id):
        result, hit = cache.get_or_load(
            (user_id, "dashboard"),
            lambda: {
                "courses": self.get_course_progress(user_id),
                "weak_topics": self.get_weak_topics(user_id),
                "history": self.get_hackathon_history(user_id),
                "assessments": self.list_assessments(user_id),
            },
        )
        return {
            **result,
            "cache_hit": hit,
            "demo_notice": "Course MCQs use assumed full marks. Progress is an engagement proxy. Assessment rules and study materials are demo-authored.",
        }
