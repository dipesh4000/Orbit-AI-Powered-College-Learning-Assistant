"""Exercise the production importer against every provided row in a temporary test DB.

SQLite is used ONLY for this isolated verification; the application requires PostgreSQL.
Run from backend: python scripts/verify_dataset.py
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, select, func
from orbit import database as db
from orbit.ingest import verify, import_all, FILES
from orbit.config import ROOT, settings
from orbit.services import Services


def main():
    output = ROOT / "data"
    output.mkdir(exist_ok=True)
    report = verify(settings.dataset_dir.resolve())
    with tempfile.TemporaryDirectory(prefix="rehearsal-", dir=output) as folder:
        engine = create_engine("sqlite:///" + str(Path(folder) / "verification.db"))
        try:
            import_all(settings.dataset_dir.resolve(), engine, report)
            with engine.connect() as conn:
                counts = {
                    table.name: conn.scalar(select(func.count()).select_from(table))
                    for table, _, _ in FILES.values()
                }
                for filename, (table, _, _) in FILES.items():
                    assert counts[table.name] == report["files"][filename]["rows"]
                selected = [
                    dict(r) for r in conn.execute(select(db.students)).mappings()
                ]
                counts["normalized_question_topic_rows"] = conn.scalar(
                    select(func.count()).select_from(db.questions)
                )
            service = Services(engine)
            dashboards = {
                s["label"]: {
                    "course_rows": len(service.get_course_progress(s["user_id"])),
                    "weak_topics": len(service.get_weak_topics(s["user_id"])),
                    "recent_attempts": len(service.get_hackathon_history(s["user_id"])),
                }
                for s in selected
            }
            result = {
                "verification_backend": "Temporary SQLite test DB; Neon connection not tested",
                "counts": counts,
                "seeded_students": selected,
                "dashboard_coverage": dashboards,
                "original_files_reconciled": report["reconciliation"],
            }
            (output / "dataset_verification.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            print(json.dumps(result, indent=2))
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
