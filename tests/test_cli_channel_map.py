import json
from pathlib import Path

from typer.testing import CliRunner

from slack_workspace_synth.cli import app
from slack_workspace_synth.storage import SQLiteStore

runner = CliRunner()


def test_channel_map_offline(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    out_path = tmp_path / "channel_map.json"
    slack_channels_path = tmp_path / "slack_channels.json"

    result = runner.invoke(
        app,
        [
            "generate",
            "--workspace",
            "ChannelMapTest",
            "--users",
            "3",
            "--channels",
            "2",
            "--messages",
            "1",
            "--files",
            "0",
            "--seed",
            "21",
            "--db",
            str(source_db),
        ],
    )
    assert result.exit_code == 0, result.stdout

    store = SQLiteStore(str(source_db))
    try:
        workspace_id = store.latest_workspace_id()
        assert workspace_id
        channels = list(store.iter_channels(workspace_id, chunk_size=100))
    finally:
        store.close()

    slack_channels_payload = {
        "channels": [
            {"id": f"C{idx:03d}", "name": str(channel["name"])}
            for idx, channel in enumerate(channels, start=1)
        ]
    }
    slack_channels_path.write_text(json.dumps(slack_channels_payload), encoding="utf-8")

    mapping = runner.invoke(
        app,
        [
            "channel-map",
            "--db",
            str(source_db),
            "--slack-channels",
            str(slack_channels_path),
            "--out",
            str(out_path),
        ],
    )
    assert mapping.exit_code == 0, mapping.stdout

    channel_map = json.loads(out_path.read_text(encoding="utf-8"))
    assert channel_map


def test_channel_map_offline_top_level_list(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    out_path = tmp_path / "channel_map.json"
    slack_channels_path = tmp_path / "slack_channels_list.json"

    result = runner.invoke(
        app,
        [
            "generate",
            "--workspace",
            "ChannelMapListTest",
            "--users",
            "3",
            "--channels",
            "2",
            "--messages",
            "1",
            "--files",
            "0",
            "--seed",
            "22",
            "--db",
            str(source_db),
        ],
    )
    assert result.exit_code == 0, result.stdout

    store = SQLiteStore(str(source_db))
    try:
        workspace_id = store.latest_workspace_id()
        assert workspace_id
        channels = list(store.iter_channels(workspace_id, chunk_size=100))
    finally:
        store.close()

    slack_channels_payload = [
        {"id": f"C{idx:03d}", "name": str(channel["name"])}
        for idx, channel in enumerate(channels, start=1)
    ]
    slack_channels_path.write_text(json.dumps(slack_channels_payload), encoding="utf-8")

    mapping = runner.invoke(
        app,
        [
            "channel-map",
            "--db",
            str(source_db),
            "--slack-channels",
            str(slack_channels_path),
            "--out",
            str(out_path),
        ],
    )
    assert mapping.exit_code == 0, mapping.stdout

    channel_map = json.loads(out_path.read_text(encoding="utf-8"))
    assert channel_map
