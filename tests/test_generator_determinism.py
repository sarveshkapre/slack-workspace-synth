import random

from faker import Faker

from slack_workspace_synth.generator import (
    GenerationConfig,
    generate_channel_members,
    generate_channels,
    generate_files,
    generate_messages,
    generate_users,
    generate_workspace,
)
from slack_workspace_synth.plugins import PluginRegistry


def _snapshot(seed: int) -> dict[str, object]:
    config = GenerationConfig(
        workspace_name="Determinism",
        users=8,
        channels=4,
        dm_channels=2,
        mpdm_channels=1,
        messages=30,
        files=10,
        seed=seed,
        batch_size=10,
    )
    plugins = PluginRegistry()
    rng = random.Random(seed)
    faker = Faker()
    faker.seed_instance(seed)

    workspace = generate_workspace(config, plugins)
    users = generate_users(config, workspace.id, rng, faker, plugins)
    channels = generate_channels(config, workspace.id, rng, faker, plugins)
    members = generate_channel_members(config, workspace.id, users, channels, rng)
    user_ids = [user.id for user in users]
    channel_ids = [channel.id for channel in channels]
    messages = list(
        generate_messages(
            config,
            workspace.id,
            user_ids,
            channel_ids,
            rng,
            faker,
            plugins,
        )
    )
    files = list(
        generate_files(
            config,
            workspace.id,
            user_ids,
            channel_ids,
            rng,
            faker,
            plugins,
        )
    )

    return {
        "workspace": workspace.to_dict(),
        "users": [row.to_dict() for row in users],
        "channels": [row.to_dict() for row in channels],
        "members": [row.to_dict() for row in members],
        "messages": [row.to_dict() for row in messages],
        "files": [row.to_dict() for row in files],
    }


def test_generation_is_stable_for_same_seed() -> None:
    left = _snapshot(42)
    right = _snapshot(42)
    assert left == right


def test_generation_changes_for_different_seed() -> None:
    left = _snapshot(42)
    right = _snapshot(43)
    assert left["workspace"] != right["workspace"]
    assert left["users"] != right["users"]


def test_workspace_and_user_ids_change_when_shape_changes() -> None:
    plugins = PluginRegistry()
    base = GenerationConfig(
        workspace_name="Determinism",
        users=4,
        channels=2,
        dm_channels=0,
        mpdm_channels=0,
        messages=0,
        files=0,
        seed=99,
        batch_size=10,
    )
    variant = GenerationConfig(
        workspace_name="Determinism",
        users=6,
        channels=3,
        dm_channels=0,
        mpdm_channels=0,
        messages=0,
        files=0,
        seed=99,
        batch_size=10,
    )

    rng_a = random.Random(99)
    rng_b = random.Random(99)
    faker_a = Faker()
    faker_b = Faker()
    faker_a.seed_instance(99)
    faker_b.seed_instance(99)

    workspace_a = generate_workspace(base, plugins)
    workspace_b = generate_workspace(variant, plugins)
    users_a = generate_users(base, workspace_a.id, rng_a, faker_a, plugins)
    users_b = generate_users(variant, workspace_b.id, rng_b, faker_b, plugins)

    assert workspace_a.id != workspace_b.id
    assert {user.id for user in users_a}.isdisjoint({user.id for user in users_b})
