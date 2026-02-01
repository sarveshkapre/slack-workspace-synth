import random

from faker import Faker

from slack_workspace_synth.generator import (
    GenerationConfig,
    generate_channels,
    generate_users,
    generate_workspace,
)
from slack_workspace_synth.plugins import PluginRegistry
from slack_workspace_synth.storage import SQLiteStore


def test_workspace_generation(tmp_path):
    db_path = tmp_path / "demo.db"
    config = GenerationConfig(
        workspace_name="Test",
        users=5,
        channels=3,
        messages=0,
        files=0,
        seed=123,
        batch_size=2,
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

        summary = store.export_summary(workspace.id)
        assert summary["counts"]["users"] == 5
        assert summary["counts"]["channels"] == 3
    finally:
        store.close()
