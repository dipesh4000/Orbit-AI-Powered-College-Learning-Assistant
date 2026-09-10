import json

from orbit import orchestrator, telemetry


def test_vercel_logs_metadata_without_writing_files_or_full_traces(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(orchestrator, "ROOT", tmp_path)
    monkeypatch.setattr(telemetry, "ROOT", tmp_path)
    monkeypatch.setattr(telemetry._logger, "handlers", [])
    telemetry.record("chat", "turn", 25, outcome="answered")
    orchestrator.write_trace({"question": "PRIVATE STUDENT QUESTION"})
    output = capsys.readouterr().err
    assert json.loads(output)["outcome"] == "answered"
    assert "PRIVATE STUDENT QUESTION" not in output
    assert not (tmp_path / "logs").exists()
