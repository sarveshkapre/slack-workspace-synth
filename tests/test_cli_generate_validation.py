from pathlib import Path

from typer.testing import CliRunner

from slack_workspace_synth.cli import app

runner = CliRunner()


def test_generate_rejects_messages_without_users(tmp_path: Path) -> None:
    db_path = tmp_path / "invalid.db"
    result = runner.invoke(
        app,
        [
            "generate",
            "--users",
            "0",
            "--channels",
            "1",
            "--messages",
            "1",
            "--files",
            "0",
            "--db",
            str(db_path),
        ],
    )
    assert result.exit_code != 0
    assert "users must be > 0" in result.output


def test_generate_rejects_invalid_member_bounds(tmp_path: Path) -> None:
    db_path = tmp_path / "invalid.db"
    result = runner.invoke(
        app,
        [
            "generate",
            "--users",
            "10",
            "--channels",
            "2",
            "--messages",
            "1",
            "--files",
            "0",
            "--channel-members-min",
            "20",
            "--channel-members-max",
            "10",
            "--db",
            str(db_path),
        ],
    )
    assert result.exit_code != 0
    assert "channel-members-min must be <=" in result.output


def test_generate_rejects_non_positive_batch_size(tmp_path: Path) -> None:
    db_path = tmp_path / "invalid.db"
    result = runner.invoke(
        app,
        [
            "generate",
            "--users",
            "10",
            "--channels",
            "2",
            "--messages",
            "1",
            "--files",
            "0",
            "--batch-size",
            "0",
            "--db",
            str(db_path),
        ],
    )
    assert result.exit_code != 0
    assert "batch-size must be >= 1" in result.output
