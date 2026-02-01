import json
from pathlib import Path

from typer.testing import CliRunner

from slack_workspace_synth.cli import app
from slack_workspace_synth.storage import SQLiteStore

runner = CliRunner()


def test_generate_writes_workspace_meta(tmp_path):
    db_path = tmp_path / "demo.db"
    result = runner.invoke(
        app,
        [
            "generate",
            "--workspace",
            "MetaTest",
            "--users",
            "1",
            "--channels",
            "1",
            "--messages",
            "0",
            "--files",
            "0",
            "--seed",
            "7",
            "--db",
            str(db_path),
        ],
    )
    assert result.exit_code == 0, result.stdout

    store = SQLiteStore(str(db_path))
    try:
        workspace_id = store.latest_workspace_id()
        assert workspace_id
    finally:
        store.close()

    out = tmp_path / "summary.json"
    stats = runner.invoke(
        app,
        [
            "stats",
            "--db",
            str(db_path),
            "--workspace-id",
            workspace_id,
            "--json-out",
            str(out),
        ],
    )
    assert stats.exit_code == 0, stats.stdout

    payload = json.loads(Path(out).read_text(encoding="utf-8"))
    meta = payload["meta"]
    assert meta["generator"] == "slack-workspace-synth"
    assert meta["seed"] == 7
    assert meta["requested"]["users"] == 1
    assert meta["requested"]["channels"] == 1
    assert meta["requested"]["messages"] == 0
    assert meta["requested"]["files"] == 0
