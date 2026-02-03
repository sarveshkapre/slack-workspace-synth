import json
from pathlib import Path

from typer.testing import CliRunner

from slack_workspace_synth.cli import app
from slack_workspace_synth.storage import SQLiteStore

runner = CliRunner()


def test_provision_slack_dry_run(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    channel_map_path = tmp_path / "channel_map.json"
    tokens_path = tmp_path / "tokens.json"
    slack_channels_path = tmp_path / "slack_channels.json"

    result = runner.invoke(
        app,
        [
            "generate",
            "--workspace",
            "ProvisionTest",
            "--users",
            "3",
            "--channels",
            "2",
            "--messages",
            "1",
            "--files",
            "0",
            "--seed",
            "31",
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

    slack_channels_payload = {
        "channels": [
            {"id": f"C{idx:08d}", "name": str(channel["name"])}
            for idx, channel in enumerate(channels, start=1)
        ]
    }
    slack_channels_path.write_text(json.dumps(slack_channels_payload), encoding="utf-8")

    provision = runner.invoke(
        app,
        [
            "provision-slack",
            "--db",
            str(source_db),
            "--slack-token",
            "xoxp-admin",
            "--slack-channels",
            str(slack_channels_path),
            "--tokens",
            str(tokens_path),
            "--out",
            str(channel_map_path),
            "--dry-run",
            "--allow-missing",
        ],
    )
    assert provision.exit_code == 0, provision.stdout
    assert channel_map_path.exists()
