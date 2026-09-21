"""Disposable browser-test server; never connects to the configured database."""

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
    settings.cookie_secure = False
    settings.cookie_samesite = "lax"
    settings.allowed_origin = "http://127.0.0.1:4176"
    with TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "data") as folder:
        engine = create_engine("sqlite:///" + (Path(folder) / "browser.db").as_posix())
        accounts.prepare(engine)
        db.get_engine = lambda: engine
        try:
            uvicorn.run(app, host="127.0.0.1", port=8011)
        finally:
            engine.dispose()
