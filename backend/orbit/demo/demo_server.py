"""Local-only, disposable populated demo. No external credentials or database."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from sqlalchemy import create_engine

from ..core import accounts
from ..core import database as db
from ..core.config import settings
from ..main import app
from . import demo


def main():
    settings.demo_enabled = False
    settings.llm_api_key = settings.nvidia_api_key = settings.hf_token = (
        settings.gemini_api_key
    ) = ""
    settings.cookie_secure = False
    settings.cookie_samesite = "lax"
    settings.allowed_origin = "http://localhost:4176"
    root = Path(__file__).resolve().parents[2] / "data"
    root.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=os.environ.get("ORBIT_SANDBOX_DIR", root)) as folder:
        engine = create_engine("sqlite:///" + (Path(folder) / "demo.db").as_posix())
        accounts.prepare(engine)
        owner = demo.seed(engine)
        db.get_engine = lambda: engine
        app.state.demo_owner_id = owner["id"]
        try:
            uvicorn.run(app, host="127.0.0.1", port=8011)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
