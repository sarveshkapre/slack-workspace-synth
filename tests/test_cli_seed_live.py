import json
from pathlib import Path

from typer.testing import CliRunner

from slack_workspace_synth.cli import app
from slack_workspace_synth.storage import SQLiteStore

runner = CliRunner()


def test_seed_live_dry_run(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    report_path = tmp_path / "report.json"
    tokens_path = tmp_path / "tokens.json"
    channel_map_path = tmp_path / "channel_map.json"

    result = runner.invoke(
        app,
        [
            "generate",
            "--workspace",
            "SeedLiveTest",
            "--users",
            "3",
            "--channels",
            "2",
            "--dm-channels",
            "0",
            "--mpdm-channels",
            "0",
            "--messages",
            "5",
            "--files",
            "0",
            "--seed",
            "13",
            "--db",
            str(source_db),
        ],
    )
    assert result.exit_code == 0, result.stdout

    store = SQLiteStore(str(source_db))
    try:
        workspace_id = store.latest_workspace_id()
        assert workspace_id
        users = list(store.iter_users(workspace_id, chunk_size=100))
        channels = list(store.iter_channels(workspace_id, chunk_size=100))
    finally:
        store.close()

    tokens_payload = {
        str(user["id"]): {
            "slack_user_id": f"U{idx:08d}",
            "access_token": f"xoxp-test-{idx}",
        }
        for idx, user in enumerate(users, start=1)
    }
    tokens_path.write_text(json.dumps(tokens_payload), encoding="utf-8")

    channel_map_payload = {
        str(channel["id"]): f"C{idx:08d}" for idx, channel in enumerate(channels, start=1)
    }
    channel_map_path.write_text(json.dumps(channel_map_payload), encoding="utf-8")

    seed = runner.invoke(
        app,
        [
            "seed-live",
            "--db",
            str(source_db),
            "--tokens",
            str(tokens_path),
            "--channel-map",
            str(channel_map_path),
            "--report",
            str(report_path),
            "--limit-messages",
            "3",
            "--dry-run",
        ],
    )
    assert seed.exit_code == 0, seed.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["planned"] == 3
    assert report["posted"] == 0
