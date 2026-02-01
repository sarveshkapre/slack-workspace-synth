from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .models import Channel, File, Message, User, Workspace


class SQLiteStore:
    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._configure()
        self._init_schema()

    def _configure(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA cache_size=20000")
        self.conn.commit()

    def _init_schema(self) -> None:
        cursor = self.conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                title TEXT NOT NULL,
                is_bot INTEGER NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
            );

            CREATE TABLE IF NOT EXISTS channels (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                name TEXT NOT NULL,
                is_private INTEGER NOT NULL,
                topic TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                ts INTEGER NOT NULL,
                text TEXT NOT NULL,
                thread_ts INTEGER,
                reply_count INTEGER NOT NULL,
                reactions_json TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
            );

            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                size INTEGER NOT NULL,
                mimetype TEXT NOT NULL,
                created_ts INTEGER NOT NULL,
                channel_id TEXT NOT NULL,
                message_id TEXT,
                url TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
            );

            CREATE INDEX IF NOT EXISTS idx_users_workspace ON users(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_channels_workspace ON channels(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_messages_workspace ON messages(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id);
            CREATE INDEX IF NOT EXISTS idx_files_workspace ON files(workspace_id);
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def insert_workspace(self, workspace: Workspace) -> None:
        self.conn.execute(
            "INSERT INTO workspaces (id, name, created_at) VALUES (?, ?, ?)",
            (workspace.id, workspace.name, workspace.created_at),
        )
        self.conn.commit()

    def insert_users(self, users: Iterable[User]) -> None:
        rows = [(u.id, u.workspace_id, u.name, u.email, u.title, u.is_bot) for u in users]
        self.conn.executemany(
            (
                "INSERT INTO users (id, workspace_id, name, email, title, is_bot) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            ),
            rows,
        )
        self.conn.commit()

    def insert_channels(self, channels: Iterable[Channel]) -> None:
        rows = [(c.id, c.workspace_id, c.name, c.is_private, c.topic) for c in channels]
        self.conn.executemany(
            (
                "INSERT INTO channels (id, workspace_id, name, is_private, topic) "
                "VALUES (?, ?, ?, ?, ?)"
            ),
            rows,
        )
        self.conn.commit()

    def insert_messages(self, messages: Iterable[Message]) -> None:
        rows = [
            (
                m.id,
                m.workspace_id,
                m.channel_id,
                m.user_id,
                m.ts,
                m.text,
                m.thread_ts,
                m.reply_count,
                m.reactions_json,
            )
            for m in messages
        ]
        self.conn.executemany(
            (
                "INSERT INTO messages "
                "(id, workspace_id, channel_id, user_id, ts, text, thread_ts, reply_count, "
                "reactions_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            rows,
        )
        self.conn.commit()

    def insert_files(self, files: Iterable[File]) -> None:
        rows = [
            (
                f.id,
                f.workspace_id,
                f.user_id,
                f.name,
                f.size,
                f.mimetype,
                f.created_ts,
                f.channel_id,
                f.message_id,
                f.url,
            )
            for f in files
        ]
        self.conn.executemany(
            (
                "INSERT INTO files "
                "(id, workspace_id, user_id, name, size, mimetype, created_ts, channel_id, "
                "message_id, url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            rows,
        )
        self.conn.commit()

    def list_workspaces(self) -> list[dict[str, object]]:
        cursor = self.conn.execute("SELECT * FROM workspaces ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def get_workspace(self, workspace_id: str) -> dict[str, object] | None:
        cursor = self.conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_users(self, workspace_id: str, limit: int, offset: int) -> list[dict[str, object]]:
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE workspace_id = ? LIMIT ? OFFSET ?",
            (workspace_id, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_channels(self, workspace_id: str, limit: int, offset: int) -> list[dict[str, object]]:
        cursor = self.conn.execute(
            "SELECT * FROM channels WHERE workspace_id = ? LIMIT ? OFFSET ?",
            (workspace_id, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_messages(self, workspace_id: str, limit: int, offset: int) -> list[dict[str, object]]:
        cursor = self.conn.execute(
            "SELECT * FROM messages WHERE workspace_id = ? ORDER BY ts DESC LIMIT ? OFFSET ?",
            (workspace_id, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_files(self, workspace_id: str, limit: int, offset: int) -> list[dict[str, object]]:
        cursor = self.conn.execute(
            "SELECT * FROM files WHERE workspace_id = ? ORDER BY created_ts DESC LIMIT ? OFFSET ?",
            (workspace_id, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    def stats(self, workspace_id: str) -> dict[str, int]:
        cursor = self.conn.cursor()
        counts = {}
        for table in ("users", "channels", "messages", "files"):
            res = cursor.execute(
                f"SELECT COUNT(*) as count FROM {table} WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()
            counts[table] = res["count"] if res else 0
        return counts

    def export_summary(self, workspace_id: str) -> dict[str, object]:
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError("workspace not found")
        summary = {"workspace": workspace, "counts": self.stats(workspace_id)}
        return summary


def dump_json(path: str, payload: dict[str, object]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
