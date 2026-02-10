import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from slack_workspace_synth.cli import app

runner = CliRunner()


def _count_lines(path: Path) -> int:
    data = path.read_text(encoding="utf-8")
    if not data:
        return 0
    return len([line for line in data.splitlines() if line.strip()])


def test_export_jsonl_after_ts_filters_messages_and_files(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    export_dir = tmp_path / "export"

    result = runner.invoke(
        app,
        [
            "generate",
            "--workspace",
            "ExportFiltersTest",
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

    with sqlite3.connect(str(source_db)) as conn:
        row = conn.execute("SELECT id FROM workspaces ORDER BY created_at DESC LIMIT 1").fetchone()
        assert row
        workspace_id = str(row[0])

        max_message_ts_row = conn.execute(
            "SELECT MAX(ts) FROM messages WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()
        max_file_ts_row = conn.execute(
            "SELECT MAX(created_ts) FROM files WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()
        assert max_message_ts_row and max_message_ts_row[0] is not None
        assert max_file_ts_row and max_file_ts_row[0] is not None

        max_message_ts = int(max_message_ts_row[0])
        max_file_ts = int(max_file_ts_row[0])

    export = runner.invoke(
        app,
        [
            "export-jsonl",
            "--db",
            str(source_db),
            "--out",
            str(export_dir),
            "--messages-after-ts",
            str(max_message_ts),
            "--files-after-ts",
            str(max_file_ts),
        ],
    )
    assert export.exit_code == 0, export.stdout

    out_dir = export_dir / workspace_id
    assert out_dir.exists()
    assert (out_dir / "workspace.json").exists()
    assert (out_dir / "summary.json").exists()

    assert _count_lines(out_dir / "messages.jsonl") == 0
    assert _count_lines(out_dir / "files.jsonl") == 0


def test_export_jsonl_incremental_state_defaults_to_previous_max_ts(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    export_dir = tmp_path / "export"
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        app,
        [
            "generate",
            "--workspace",
            "ExportIncrementalStateTest",
            "--users",
            "3",
            "--channels",
            "2",
            "--messages",
            "5",
            "--files",
            "4",
            "--seed",
            "21",
            "--db",
            str(source_db),
        ],
    )
    assert result.exit_code == 0, result.stdout

    with sqlite3.connect(str(source_db)) as conn:
        row = conn.execute("SELECT id FROM workspaces ORDER BY created_at DESC LIMIT 1").fetchone()
        assert row
        workspace_id = str(row[0])

    first = runner.invoke(
        app,
        [
            "export-jsonl",
            "--db",
            str(source_db),
            "--out",
            str(export_dir),
            "--incremental-state",
            str(state_path),
        ],
    )
    assert first.exit_code == 0, first.stdout
    assert state_path.exists()

    out_dir = export_dir / workspace_id
    assert _count_lines(out_dir / "messages.jsonl") > 0
    assert _count_lines(out_dir / "files.jsonl") > 0

    second = runner.invoke(
        app,
        [
            "export-jsonl",
            "--db",
            str(source_db),
            "--out",
            str(export_dir),
            "--incremental-state",
            str(state_path),
        ],
    )
    assert second.exit_code == 0, second.stdout

    # Second run should default to the state file's max timestamps,
    # producing empty incremental slices.
    assert _count_lines(out_dir / "messages.jsonl") == 0
    assert _count_lines(out_dir / "files.jsonl") == 0
