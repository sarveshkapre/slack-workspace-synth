from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Workspace:
    id: str
    name: str
    created_at: int

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "created_at": self.created_at}


@dataclass(frozen=True)
class User:
    id: str
    workspace_id: str
    name: str
    email: str
    title: str
    is_bot: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "email": self.email,
            "title": self.title,
            "is_bot": self.is_bot,
        }


@dataclass(frozen=True)
class Channel:
    id: str
    workspace_id: str
    name: str
    is_private: int
    topic: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "is_private": self.is_private,
            "topic": self.topic,
        }


@dataclass(frozen=True)
class Message:
    id: str
    workspace_id: str
    channel_id: str
    user_id: str
    ts: int
    text: str
    thread_ts: int | None
    reply_count: int
    reactions_json: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "channel_id": self.channel_id,
            "user_id": self.user_id,
            "ts": self.ts,
            "text": self.text,
            "thread_ts": self.thread_ts,
            "reply_count": self.reply_count,
            "reactions_json": self.reactions_json,
        }


@dataclass(frozen=True)
class File:
    id: str
    workspace_id: str
    user_id: str
    name: str
    size: int
    mimetype: str
    created_ts: int
    channel_id: str
    message_id: str | None
    url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "name": self.name,
            "size": self.size,
            "mimetype": self.mimetype,
            "created_ts": self.created_ts,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "url": self.url,
        }
