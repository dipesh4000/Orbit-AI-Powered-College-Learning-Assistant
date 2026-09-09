"""Regressions for the renamed entry point and working-directory-independent launch."""

import shutil
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from orbit.config import ROOT, Settings


def test_legacy_entrypoint_uses_same_application():
    from orbit import main
    from orbit.app import app, services, sessions

    assert app is main.app
    assert services is main.services
    assert sessions is main.sessions


def test_dataset_path_is_relative_to_backend(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None, dataset_dir="../..")
    assert settings.dataset_dir == ROOT.parent.parent


def test_launcher_uses_virtualenv_outside_backend(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "run.py"), "--version"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "uvicorn" in result.stdout.lower()


def test_launcher_propagates_failure(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "run.py"), "--not-a-real-option"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0


def test_direct_main_launch(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "orbit/main.py"), "--version"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "uvicorn" in result.stdout.lower()


def test_missing_virtualenv_has_actionable_error(tmp_path):
    launcher = tmp_path / "run.py"
    shutil.copyfile(ROOT / "run.py", launcher)
    result = subprocess.run(
        [sys.executable, str(launcher)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 1
    assert "virtual environment is missing" in result.stderr
    assert "uv venv .venv" in result.stderr


@pytest.mark.parametrize("hostname", ["localhost", "127.0.0.1"])
def test_loopback_origin_alias_can_modify_session(hostname):
    from orbit.config import settings
    from orbit.main import app

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(settings, "allowed_origin", "http://127.0.0.1:5173")
        with TestClient(app) as client:
            response = client.delete(
                "/api/session", headers={"Origin": f"http://{hostname}:5173"}
            )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "origin",
    ["http://localhost:9999", "http://localhost.evil:5173", "https://evil.example"],
)
def test_untrusted_origins_remain_rejected(origin):
    from orbit.main import app

    with TestClient(app) as client:
        response = client.delete("/api/session", headers={"Origin": origin})
    assert response.status_code == 403


def test_remote_origin_does_not_enable_loopback():
    settings = Settings(_env_file=None, allowed_origin="https://orbit.example")
    assert settings.allowed_origins == ["https://orbit.example"]
