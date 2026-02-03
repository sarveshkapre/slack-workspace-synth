import csv
import json
from pathlib import Path

from typer.testing import CliRunner

from slack_workspace_synth.cli import app

runner = CliRunner()


def test_oauth_pack(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    out_dir = tmp_path / "oauth"

    result = runner.invoke(
        app,
        [
            "generate",
            "--workspace",
            "OAuthPackTest",
            "--users",
            "3",
            "--channels",
            "2",
            "--messages",
            "5",
            "--files",
            "1",
            "--seed",
            "11",
            "--db",
            str(source_db),
        ],
    )
    assert result.exit_code == 0, result.stdout

    pack = runner.invoke(
        app,
        [
            "oauth-pack",
            "--db",
            str(source_db),
            "--out",
            str(out_dir),
            "--client-id",
            "123.456",
            "--redirect-uri",
            "http://localhost/callback",
            "--scope",
            "chat:write",
            "--user-scope",
            "chat:write,channels:read",
            "--include-bots",
        ],
    )
    assert pack.exit_code == 0, pack.stdout

    csv_path = out_dir / "oauth_urls.csv"
    assert csv_path.exists()
    with open(csv_path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    for row in rows:
        assert row["oauth_url"].startswith("https://slack.com/oauth/v2/authorize?")

    state_map = json.loads((out_dir / "state_map.json").read_text(encoding="utf-8"))
    assert isinstance(state_map, dict)
    assert len(state_map) == 3

    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["user_count"] == 3
    assert summary["client_id"] == "123.456"
