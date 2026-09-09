"""Pure rules. Unknown evidence is distinct from a failed condition."""


def course_metrics(row, full_marks=2):
    attempted, score = row["mcq_attempted"], row["mcq_score"]
    maximum = attempted * full_marks
    valid_score = attempted > 0 and 0 <= score <= maximum
    performance = round(score / maximum * 100, 2) if valid_score else None
    total, observed = row["total_activities"], row["observed_activities"]
    engagement = round(min(observed / total, 1) * 100, 2) if total > 0 else None
    # Certificate/legacy flags are supplied evidence; resource clicks are only a demo proxy.
    completion = 100.0 if row["certificate"] or row["legacy_completion"] else engagement
    return {
        **row,
        "performance_percent": performance,
        "full_marks_per_mcq": full_marks,
        "score_basis": "Demo assumption: 2 marks per recorded course MCQ attempt",
        "performance_note": None
        if valid_score
        else "No scored attempts or score outside the demo scale",
        "progress_percent": completion,
        "progress_basis": "Supplied completion flag"
        if row["certificate"] or row["legacy_completion"]
        else "Demo engagement proxy: distinct observed activity IDs / total activities; not verified completion",
    }


def eligibility(assessment, course, prerequisite, attempts):
    if assessment is None:
        return {
            "eligible": None,
            "status": "unknown",
            "reason": "Assessment not found.",
            "unmet_conditions": [],
            "missing_information": ["assessment"],
        }
    failed, missing = [], []
    if not assessment["active"]:
        failed.append("Assessment is inactive.")
    if course is None:
        failed.append("You are not enrolled in the target course in the supplied data.")
    elif assessment["completion_threshold"] > 0:
        if course["progress_percent"] is None:
            missing.append("Course engagement evidence")
        elif course["progress_percent"] < assessment["completion_threshold"]:
            failed.append(
                f"Requires {assessment['completion_threshold']:g}% demo engagement progress."
            )
    if assessment["prerequisite_course_id"]:
        if prerequisite is None or prerequisite["performance_percent"] is None:
            missing.append("Scored prerequisite course MCQs")
        elif prerequisite["performance_percent"] < assessment["pass_percent"]:
            failed.append(
                f"Prerequisite requires {assessment['pass_percent']:g}% on the demo score scale."
            )
    if attempts is None:
        missing.append("Assessment attempt count")
    elif attempts >= assessment["max_attempts"]:
        failed.append(f"Maximum of {assessment['max_attempts']} attempts reached.")
    status = "ineligible" if failed else "unknown" if missing else "eligible"
    return {
        "eligible": False if failed else None if missing else True,
        "status": status,
        "reason": " ".join(
            failed + (["Cannot verify: " + ", ".join(missing) + "."] if missing else [])
        )
        or "All configured demo assessment conditions are met.",
        "unmet_conditions": failed,
        "missing_information": missing,
        "assessment_id": assessment["assessment_id"],
        "demo_rules": True,
        "attempt_count": attempts,
        "max_attempts": assessment["max_attempts"],
    }
