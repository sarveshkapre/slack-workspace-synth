import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

import slack_workspace_synth.cli as cli_mod
from slack_workspace_synth.cli import app
from slack_workspace_synth.models import Message
from slack_workspace_synth.storage import SQLiteStore

runner = CliRunner()
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def test_seed_live_dry_run(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    report_path = tmp_path / "report.json"
    tokens_path = tmp_path / "tokens.json"
    slack_channels_path = tmp_path / "slack_channels.json"

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

    slack_channels_payload = {
        "channels": [
            {"id": f"C{idx:08d}", "name": str(channel["name"])}
            for idx, channel in enumerate(channels, start=1)
        ]
    }
    slack_channels_path.write_text(json.dumps(slack_channels_payload), encoding="utf-8")

    seed = runner.invoke(
        app,
        [
            "seed-live",
            "--db",
            str(source_db),
            "--tokens",
            str(tokens_path),
            "--slack-channels",
            str(slack_channels_path),
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


def test_seed_live_dry_run_requires_offline_mapping(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    tokens_path = tmp_path / "tokens.json"

    result = runner.invoke(
        app,
        [
            "generate",
            "--workspace",
            "SeedLiveNoMapTest",
            "--users",
            "2",
            "--channels",
            "1",
            "--dm-channels",
            "0",
            "--mpdm-channels",
            "0",
            "--messages",
            "2",
            "--files",
            "0",
            "--seed",
            "17",
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

    seed = runner.invoke(
        app,
        [
            "seed-live",
            "--db",
            str(source_db),
            "--tokens",
            str(tokens_path),
            "--dry-run",
        ],
    )
    assert seed.exit_code != 0
    clean = _strip_ansi(seed.output).lower()
    assert "provide --channel-map or --slack-channels" in clean


def test_seed_live_dry_run_skips_dms_without_slack_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_db = tmp_path / "source.db"
    report_path = tmp_path / "report.json"
    tokens_path = tmp_path / "tokens.json"
    slack_channels_path = tmp_path / "slack_channels.json"

    result = runner.invoke(
        app,
        [
            "generate",
            "--workspace",
            "SeedLiveDMTest",
            "--users",
            "3",
            "--channels",
            "1",
            "--dm-channels",
            "1",
            "--mpdm-channels",
            "0",
            "--messages",
            "0",
            "--files",
            "0",
            "--seed",
            "23",
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
        pub_channels = [c for c in channels if str(c.get("channel_type")) in {"public", "private"}]
        assert pub_channels, "expected at least one public/private channel"
        dm_channels = [c for c in channels if str(c.get("channel_type")) in {"im", "mpim"}]
        assert dm_channels, "expected at least one DM/MPDM channel"
        dm_channel_id = str(dm_channels[0]["id"])
        user_id = str(users[0]["id"])
        store.insert_messages(
            [
                Message(
                    id="dm-test-msg-1",
                    workspace_id=workspace_id,
                    channel_id=dm_channel_id,
                    user_id=user_id,
                    ts=1,
                    text="hello from dm",
                    thread_ts=None,
                    reply_count=0,
                    reactions_json="[]",
                )
            ]
        )
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
        "channels": [{"id": "C00000001", "name": str(pub_channels[0]["name"])}]
    }
    slack_channels_path.write_text(json.dumps(slack_channels_payload), encoding="utf-8")

    def _no_slack_calls(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("Slack API should not be called in --dry-run")

    monkeypatch.setattr(cli_mod, "_slack_post_json", _no_slack_calls)
    monkeypatch.setattr(cli_mod, "_slack_get_json", _no_slack_calls)

    seed = runner.invoke(
        app,
        [
            "seed-live",
            "--db",
            str(source_db),
            "--tokens",
            str(tokens_path),
            "--slack-channels",
            str(slack_channels_path),
            "--report",
            str(report_path),
            "--dry-run",
        ],
    )
    assert seed.exit_code == 0, seed.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["posted"] == 0
    assert report["skipped_requires_slack"] >= 1
    assert report["skip_reasons"]["dm_requires_conversations_open"] >= 1
