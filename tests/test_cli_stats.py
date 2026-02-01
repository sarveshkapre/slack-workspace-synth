import json
import random

from faker import Faker
from typer.testing import CliRunner

from slack_workspace_synth.cli import app
from slack_workspace_synth.generator import (
    GenerationConfig,
    generate_channels,
    generate_files,
    generate_messages,
    generate_users,
    generate_workspace,
)
from slack_workspace_synth.plugins import PluginRegistry
from slack_workspace_synth.storage import SQLiteStore

runner = CliRunner()


def _seed_db(tmp_path) -> tuple[str, str]:
    db_path = tmp_path / "demo.db"
    config = GenerationConfig(
        workspace_name="Test",
        users=5,
        channels=3,
        messages=10,
        files=6,
        seed=123,
        batch_size=50,
    )
    plugins = PluginRegistry()

    store = SQLiteStore(str(db_path))
    try:
        workspace = generate_workspace(config, plugins)
        store.insert_workspace(workspace)

        rng = random.Random(123)
        faker = Faker()
        faker.seed_instance(123)

        users = generate_users(config, workspace.id, rng, faker, plugins)
        channels = generate_channels(config, workspace.id, rng, faker, plugins)
        store.insert_users(users)
        store.insert_channels(channels)

        user_ids = [u.id for u in users]
        channel_ids = [c.id for c in channels]

        store.insert_messages(
            list(
                generate_messages(config, workspace.id, user_ids, channel_ids, rng, faker, plugins)
            )
        )
        store.insert_files(
            list(generate_files(config, workspace.id, user_ids, channel_ids, rng, faker, plugins))
        )
    finally:
        store.close()

    return str(db_path), workspace.id


def test_stats_writes_json(tmp_path):
    db_path, workspace_id = _seed_db(tmp_path)
    out = tmp_path / "summary.json"

    result = runner.invoke(
        app, ["stats", "--db", db_path, "--workspace-id", workspace_id, "--json-out", str(out)]
    )
    assert result.exit_code == 0, result.stdout

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["workspace"]["id"] == workspace_id
    assert payload["counts"]["users"] == 5
    assert payload["counts"]["channels"] == 3
    assert payload["counts"]["messages"] == 10
    assert payload["counts"]["files"] == 6
