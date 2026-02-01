from __future__ import annotations

import json
import random
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from faker import Faker

from .models import Channel, File, Message, User, Workspace
from .plugins import PluginRegistry


@dataclass
class GenerationConfig:
    workspace_name: str
    users: int
    channels: int
    messages: int
    files: int
    seed: int
    batch_size: int = 500


def _uuid() -> str:
    return uuid.uuid4().hex


def _base_ts(seed: int) -> int:
    return 1_700_000_000 + (seed % 10_000) * 100


def _slug(text: str) -> str:
    return "".join(c for c in text.lower().replace(" ", "-") if c.isalnum() or c == "-")


def generate_workspace(config: GenerationConfig, plugins: PluginRegistry) -> Workspace:
    ts = _base_ts(config.seed)
    payload = {"id": _uuid(), "name": config.workspace_name, "created_at": ts}
    payload = plugins.on_workspace(payload)
    return Workspace(
        id=cast(str, payload["id"]),
        name=cast(str, payload["name"]),
        created_at=cast(int, payload["created_at"]),
    )


def generate_users(
    config: GenerationConfig,
    workspace_id: str,
    rng: random.Random,
    faker: Faker,
    plugins: PluginRegistry,
) -> list[User]:
    users: list[User] = []
    for idx in range(config.users):
        name = faker.name()
        email = f"{_slug(name)}.{idx}@example.com"
        payload = {
            "id": _uuid(),
            "workspace_id": workspace_id,
            "name": name,
            "email": email,
            "title": faker.job(),
            "is_bot": 1 if rng.random() < 0.02 else 0,
        }
        payload = plugins.on_user(payload)
        users.append(
            User(
                id=cast(str, payload["id"]),
                workspace_id=cast(str, payload["workspace_id"]),
                name=cast(str, payload["name"]),
                email=cast(str, payload["email"]),
                title=cast(str, payload["title"]),
                is_bot=cast(int, payload["is_bot"]),
            )
        )
    return users


def generate_channels(
    config: GenerationConfig,
    workspace_id: str,
    rng: random.Random,
    faker: Faker,
    plugins: PluginRegistry,
) -> list[Channel]:
    channels: list[Channel] = []
    for idx in range(config.channels):
        base = faker.word().replace("_", "-")
        name = f"{base}-{idx}" if idx > 0 else base
        payload = {
            "id": _uuid(),
            "workspace_id": workspace_id,
            "name": name,
            "is_private": 1 if rng.random() < 0.15 else 0,
            "topic": faker.sentence(nb_words=6),
        }
        payload = plugins.on_channel(payload)
        channels.append(
            Channel(
                id=cast(str, payload["id"]),
                workspace_id=cast(str, payload["workspace_id"]),
                name=cast(str, payload["name"]),
                is_private=cast(int, payload["is_private"]),
                topic=cast(str, payload["topic"]),
            )
        )
    return channels


def generate_messages(
    config: GenerationConfig,
    workspace_id: str,
    user_ids: list[str],
    channel_ids: list[str],
    rng: random.Random,
    faker: Faker,
    plugins: PluginRegistry,
) -> Iterable[Message]:
    base_ts = _base_ts(config.seed)
    for _ in range(config.messages):
        payload = {
            "id": _uuid(),
            "workspace_id": workspace_id,
            "channel_id": rng.choice(channel_ids),
            "user_id": rng.choice(user_ids),
            "ts": base_ts - rng.randint(0, 60 * 60 * 24 * 30),
            "text": faker.sentence(nb_words=rng.randint(4, 20)),
            "thread_ts": None,
            "reply_count": rng.randint(0, 6),
            "reactions_json": json.dumps({"thumbsup": rng.randint(0, 5)}),
        }
        payload = plugins.on_message(payload)
        thread_ts = cast(int | None, payload.get("thread_ts"))
        yield Message(
            id=cast(str, payload["id"]),
            workspace_id=cast(str, payload["workspace_id"]),
            channel_id=cast(str, payload["channel_id"]),
            user_id=cast(str, payload["user_id"]),
            ts=cast(int, payload["ts"]),
            text=cast(str, payload["text"]),
            thread_ts=thread_ts,
            reply_count=cast(int, payload["reply_count"]),
            reactions_json=cast(str, payload["reactions_json"]),
        )


def generate_files(
    config: GenerationConfig,
    workspace_id: str,
    user_ids: list[str],
    channel_ids: list[str],
    rng: random.Random,
    faker: Faker,
    plugins: PluginRegistry,
) -> Iterable[File]:
    mime_types = ["application/pdf", "image/png", "text/plain", "application/zip"]
    base_ts = _base_ts(config.seed)
    for _ in range(config.files):
        payload = {
            "id": _uuid(),
            "workspace_id": workspace_id,
            "user_id": rng.choice(user_ids),
            "name": f"{faker.word()}.{rng.choice(['pdf', 'png', 'txt', 'zip'])}",
            "size": rng.randint(5_000, 5_000_000),
            "mimetype": rng.choice(mime_types),
            "created_ts": base_ts - rng.randint(0, 60 * 60 * 24 * 30),
            "channel_id": rng.choice(channel_ids),
            "message_id": None,
            "url": f"https://files.example.com/{_uuid()}",
        }
        payload = plugins.on_file(payload)
        message_id = cast(str | None, payload.get("message_id"))
        yield File(
            id=cast(str, payload["id"]),
            workspace_id=cast(str, payload["workspace_id"]),
            user_id=cast(str, payload["user_id"]),
            name=cast(str, payload["name"]),
            size=cast(int, payload["size"]),
            mimetype=cast(str, payload["mimetype"]),
            created_ts=cast(int, payload["created_ts"]),
            channel_id=cast(str, payload["channel_id"]),
            message_id=message_id,
            url=cast(str, payload["url"]),
        )
