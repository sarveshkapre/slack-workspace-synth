from __future__ import annotations

import hashlib
import json
import random
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from faker import Faker

from .models import Channel, ChannelMember, File, Message, User, Workspace
from .plugins import PluginRegistry


@dataclass
class GenerationConfig:
    workspace_name: str
    users: int
    channels: int
    dm_channels: int
    mpdm_channels: int
    messages: int
    files: int
    seed: int
    batch_size: int = 500
    channel_members_min: int = 8
    channel_members_max: int = 120
    mpdm_members_min: int = 3
    mpdm_members_max: int = 7


_ID_STREAM_SEED_OFFSETS = {
    "workspace": 1_001,
    "users": 1_003,
    "channels": 1_009,
    "messages": 1_021,
    "files": 1_031,
}


def _id_rng(seed: int, stream: str, *, namespace: str = "") -> random.Random:
    offset = _ID_STREAM_SEED_OFFSETS[stream]
    payload = f"{seed}:{offset}:{namespace}".encode()
    digest = hashlib.sha256(payload).hexdigest()
    return random.Random(int(digest[:16], 16))


def _workspace_id_namespace(config: GenerationConfig) -> str:
    return "|".join(
        [
            config.workspace_name,
            str(config.users),
            str(config.channels),
            str(config.dm_channels),
            str(config.mpdm_channels),
            str(config.messages),
            str(config.files),
        ]
    )


def _seeded_uuid(rng: random.Random) -> str:
    # UUID v4 shape with deterministic bits from the seeded RNG.
    return uuid.UUID(int=rng.getrandbits(128), version=4).hex


def _base_ts(seed: int) -> int:
    return 1_700_000_000 + (seed % 10_000) * 100


def _slug(text: str) -> str:
    return "".join(c for c in text.lower().replace(" ", "-") if c.isalnum() or c == "-")


def generate_workspace(
    config: GenerationConfig,
    plugins: PluginRegistry,
    *,
    id_rng: random.Random | None = None,
) -> Workspace:
    ts = _base_ts(config.seed)
    ids = id_rng or _id_rng(
        config.seed,
        "workspace",
        namespace=_workspace_id_namespace(config),
    )
    payload = {"id": _seeded_uuid(ids), "name": config.workspace_name, "created_at": ts}
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
    *,
    id_rng: random.Random | None = None,
) -> list[User]:
    ids = id_rng or _id_rng(config.seed, "users", namespace=workspace_id)
    users: list[User] = []
    for idx in range(config.users):
        name = faker.name()
        email = f"{_slug(name)}.{idx}@example.com"
        payload = {
            "id": _seeded_uuid(ids),
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
    *,
    id_rng: random.Random | None = None,
) -> list[Channel]:
    ids = id_rng or _id_rng(config.seed, "channels", namespace=workspace_id)
    channels: list[Channel] = []
    for idx in range(config.channels):
        base = faker.word().replace("_", "-")
        name = f"{base}-{idx}" if idx > 0 else base
        is_private = 1 if rng.random() < 0.15 else 0
        payload = {
            "id": _seeded_uuid(ids),
            "workspace_id": workspace_id,
            "name": name,
            "is_private": is_private,
            "channel_type": "private" if is_private else "public",
            "topic": faker.sentence(nb_words=6),
        }
        payload = plugins.on_channel(payload)
        channels.append(
            Channel(
                id=cast(str, payload["id"]),
                workspace_id=cast(str, payload["workspace_id"]),
                name=cast(str, payload["name"]),
                is_private=cast(int, payload["is_private"]),
                channel_type=cast(str, payload["channel_type"]),
                topic=cast(str, payload["topic"]),
            )
        )
    for idx in range(config.dm_channels):
        payload = {
            "id": _seeded_uuid(ids),
            "workspace_id": workspace_id,
            "name": f"dm-{idx + 1:04d}",
            "is_private": 1,
            "channel_type": "im",
            "topic": "Direct message",
        }
        payload = plugins.on_channel(payload)
        channels.append(
            Channel(
                id=cast(str, payload["id"]),
                workspace_id=cast(str, payload["workspace_id"]),
                name=cast(str, payload["name"]),
                is_private=cast(int, payload["is_private"]),
                channel_type=cast(str, payload["channel_type"]),
                topic=cast(str, payload["topic"]),
            )
        )
    for idx in range(config.mpdm_channels):
        payload = {
            "id": _seeded_uuid(ids),
            "workspace_id": workspace_id,
            "name": f"mpdm-{idx + 1:04d}",
            "is_private": 1,
            "channel_type": "mpim",
            "topic": "Multi-party direct message",
        }
        payload = plugins.on_channel(payload)
        channels.append(
            Channel(
                id=cast(str, payload["id"]),
                workspace_id=cast(str, payload["workspace_id"]),
                name=cast(str, payload["name"]),
                is_private=cast(int, payload["is_private"]),
                channel_type=cast(str, payload["channel_type"]),
                topic=cast(str, payload["topic"]),
            )
        )
    return channels


def generate_channel_members(
    config: GenerationConfig,
    workspace_id: str,
    users: list[User],
    channels: list[Channel],
    rng: random.Random,
) -> list[ChannelMember]:
    user_ids = [user.id for user in users]
    members: list[ChannelMember] = []
    if not user_ids:
        return members

    def _add_members(channel_id: str, member_ids: list[str]) -> None:
        for user_id in member_ids:
            members.append(
                ChannelMember(
                    channel_id=channel_id,
                    workspace_id=workspace_id,
                    user_id=user_id,
                )
            )

    max_channel_members = max(1, min(config.channel_members_max, len(user_ids)))
    min_channel_members = max(1, min(config.channel_members_min, max_channel_members))
    for channel in channels:
        if channel.channel_type == "im":
            member_ids = rng.sample(user_ids, k=2) if len(user_ids) >= 2 else user_ids
            _add_members(channel.id, member_ids)
            continue
        if channel.channel_type == "mpim":
            max_mpdm = min(config.mpdm_members_max, len(user_ids))
            if max_mpdm < 3:
                _add_members(channel.id, user_ids)
                continue
            min_mpdm = max(3, min(config.mpdm_members_min, max_mpdm))
            member_count = rng.randint(min_mpdm, max_mpdm)
            _add_members(channel.id, rng.sample(user_ids, k=member_count))
            continue

        if max_channel_members == 0:
            continue
        member_count = rng.randint(min_channel_members, max_channel_members)
        _add_members(channel.id, rng.sample(user_ids, k=member_count))

    return members


def generate_messages(
    config: GenerationConfig,
    workspace_id: str,
    user_ids: list[str],
    channel_ids: list[str],
    rng: random.Random,
    faker: Faker,
    plugins: PluginRegistry,
    *,
    id_rng: random.Random | None = None,
) -> Iterable[Message]:
    ids = id_rng or _id_rng(config.seed, "messages", namespace=workspace_id)
    base_ts = _base_ts(config.seed)
    for _ in range(config.messages):
        payload = {
            "id": _seeded_uuid(ids),
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
    *,
    id_rng: random.Random | None = None,
) -> Iterable[File]:
    ids = id_rng or _id_rng(config.seed, "files", namespace=workspace_id)
    mime_types = ["application/pdf", "image/png", "text/plain", "application/zip"]
    base_ts = _base_ts(config.seed)
    for _ in range(config.files):
        payload = {
            "id": _seeded_uuid(ids),
            "workspace_id": workspace_id,
            "user_id": rng.choice(user_ids),
            "name": f"{faker.word()}.{rng.choice(['pdf', 'png', 'txt', 'zip'])}",
            "size": rng.randint(5_000, 5_000_000),
            "mimetype": rng.choice(mime_types),
            "created_ts": base_ts - rng.randint(0, 60 * 60 * 24 * 30),
            "channel_id": rng.choice(channel_ids),
            "message_id": None,
            "url": f"https://files.example.com/{_seeded_uuid(ids)}",
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
