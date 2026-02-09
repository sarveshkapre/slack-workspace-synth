import json
from pathlib import Path

from typer.testing import CliRunner

from slack_workspace_synth.cli import app

runner = CliRunner()


def test_validate_db_ok(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"

    result = runner.invoke(
        app,
        [
            "generate",
            "--workspace",
            "ValidateDbTest",
            "--users",
            "3",
            "--channels",
            "2",
            "--messages",
            "1",
            "--files",
            "0",
            "--seed",
            "45",
            "--db",
            str(source_db),
        ],
    )
    assert result.exit_code == 0, result.stdout

    validate = runner.invoke(
        app,
        [
            "validate-db",
            "--db",
            str(source_db),
            "--require-workspace",
        ],
    )
    assert validate.exit_code == 0, validate.stdout
    report = json.loads(validate.stdout)
    assert report["ok"] is True
    assert report["workspace_id"]


def test_validate_db_missing_file_fails(tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"
    validate = runner.invoke(app, ["validate-db", "--db", str(missing)])
    assert validate.exit_code != 0
    report = json.loads(validate.stdout)
    assert report["ok"] is False
