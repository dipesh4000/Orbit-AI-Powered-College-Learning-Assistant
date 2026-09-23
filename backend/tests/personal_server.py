"""Disposable browser-test server; never connects to the configured database."""

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    import uvicorn
    from orbit import accounts
    from orbit import database as db
    from orbit.config import settings
    from orbit.main import app
    from sqlalchemy import create_engine

    settings.demo_enabled = False
    settings.llm_api_key = ""
    settings.nvidia_api_key = ""
    settings.hf_token = ""
    settings.gemini_api_key = ""
    settings.cookie_secure = False
    settings.cookie_samesite = "lax"
    settings.allowed_origin = "http://127.0.0.1:4176"
    if os.environ.get("ORBIT_TEST_CODOLIO") == "1":
        from codolio_fixture import fetch
        from orbit import coding

        coding.fetch_profile = fetch
    if os.environ.get("ORBIT_TEST_PRACTICE") == "1":
        import json

        from orbit import auth
        from orbit.llm import ModelUnavailable

        class PracticeFixture:
            async def complete(self, messages, tools=None):
                if tools is not None:
                    raise ModelUnavailable(
                        "No model provider configured. Configure a provider to enable AI responses."
                    )
                payload = json.loads(messages[1]["content"])
                return {
                    "content": json.dumps(
                        {
                            "questions": [
                                {
                                    "question": "Which keyword does the source use to read rows?",
                                    "options": ["SELECT", "DROP", "DELETE", "UPDATE"],
                                    "correct_answer": "SELECT",
                                    "explanation": "The supplied text explicitly says SELECT reads rows.",
                                    "source_reference": payload["passages"][0]["id"],
                                }
                            ]
                        }
                    )
                }

        auth.personal_model = PracticeFixture()
    if os.environ.get("ORBIT_TEST_WORKSPACE") == "1":
        from workspace_fixture import install

        install()
    (Path(__file__).resolve().parents[1] / "data").mkdir(exist_ok=True)
    with TemporaryDirectory(
        dir=os.environ.get(
            "ORBIT_SANDBOX_DIR", Path(__file__).resolve().parents[1] / "data"
        )
    ) as folder:
        engine = create_engine("sqlite:///" + (Path(folder) / "browser.db").as_posix())
        accounts.prepare(engine)
        db.get_engine = lambda: engine
        try:
            uvicorn.run(app, host="127.0.0.1", port=8011)
        finally:
            engine.dispose()
