"""Application entry-point, configuration, and development-origin regressions."""

import pytest
from fastapi.testclient import TestClient
from orbit.config import ROOT, Settings


def test_application_entrypoint_health():
    from orbit.main import app

    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dataset_path_is_relative_to_backend(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None, dataset_dir="../..")
    assert settings.dataset_dir == ROOT.parent.parent


def test_cors_preflight_rejects_untrusted_origin():
    from orbit.main import app

    with TestClient(app) as client:
        response = client.options(
            "/api/session",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


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
