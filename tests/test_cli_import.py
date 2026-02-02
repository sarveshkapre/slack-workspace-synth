from pathlib import Path

from typer.testing import CliRunner

from slack_workspace_synth.cli import app
from slack_workspace_synth.storage import SQLiteStore

runner = CliRunner()


def test_import_jsonl_roundtrip(tmp_path):
    source_db = tmp_path / "source.db"
    export_dir = tmp_path / "export"
    target_db = tmp_path / "target.db"

    result = runner.invoke(
        app,
        [
            "generate",
            "--workspace",
            "ImportTest",
            "--users",
            "3",
            "--channels",
            "2",
            "--messages",
            "5",
            "--files",
            "4",
            "--seed",
            "11",
            "--db",
            str(source_db),
        ],
    )
    assert result.exit_code == 0, result.stdout

    export = runner.invoke(app, ["export-jsonl", "--db", str(source_db), "--out", str(export_dir)])
    assert export.exit_code == 0, export.stdout

    subdirs = [p for p in Path(export_dir).iterdir() if p.is_dir()]
    assert len(subdirs) == 1
    workspace_id = subdirs[0].name

    imported = runner.invoke(
        app,
        [
            "import-jsonl",
            "--source",
            str(export_dir),
            "--workspace-id",
            workspace_id,
            "--db",
            str(target_db),
        ],
    )
    assert imported.exit_code == 0, imported.stdout

    store = SQLiteStore(str(target_db))
    try:
        summary = store.export_summary(workspace_id)
    finally:
        store.close()

    assert summary["counts"]["users"] == 3
    assert summary["counts"]["channels"] == 2
    assert 4 <= summary["counts"]["channel_members"] <= 6
    assert summary["counts"]["messages"] == 5
    assert summary["counts"]["files"] == 4
