import json
from pathlib import Path

from typer.testing import CliRunner

from slack_workspace_synth.cli import app

runner = CliRunner()


def test_seed_import_bundle(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    out_dir = tmp_path / "import_bundle"

    result = runner.invoke(
        app,
        [
            "generate",
            "--workspace",
            "ImportBundleTest",
            "--users",
            "3",
            "--channels",
            "2",
            "--dm-channels",
            "1",
            "--mpdm-channels",
            "1",
            "--messages",
            "6",
            "--files",
            "0",
            "--seed",
            "12",
            "--db",
            str(source_db),
        ],
    )
    assert result.exit_code == 0, result.stdout

    pack = runner.invoke(
        app,
        [
            "seed-import",
            "--db",
            str(source_db),
            "--out",
            str(out_dir),
            "--limit-messages",
            "3",
        ],
    )
    assert pack.exit_code == 0, pack.stdout

    assert (out_dir / "users.json").exists()
    assert (out_dir / "channels.json").exists()
    assert (out_dir / "groups.json").exists()
    assert (out_dir / "dms.json").exists()
    assert (out_dir / "mpims.json").exists()
    assert (out_dir / "import_id_map.json").exists()

    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["messages"] == 3

    conversation_files = [p for p in out_dir.rglob("*.json") if p.parent != out_dir]
    assert conversation_files
