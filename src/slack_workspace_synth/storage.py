from __future__ import annotations

import base64
import json
import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import cast

from .models import Channel, ChannelMember, File, Message, User, Workspace


class SQLiteStore:
    def __init__(self, path: str, *, read_only: bool = False) -> None:
        self.path = path
        self.read_only = read_only
        if read_only:
            # API/server opens DB read-only to avoid mutating unknown/production DBs.
            self.conn = _sqlite_connect_readonly(path)
            self.conn.row_factory = sqlite3.Row
            return

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

            CREATE TABLE IF NOT EXISTS workspace_meta (
                workspace_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (workspace_id, key),
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
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
                channel_type TEXT NOT NULL,
                topic TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
            );

            CREATE TABLE IF NOT EXISTS channel_members (
                channel_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                PRIMARY KEY (channel_id, user_id),
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
            CREATE INDEX IF NOT EXISTS idx_users_workspace_id ON users(workspace_id, id);
            CREATE INDEX IF NOT EXISTS idx_channels_workspace ON channels(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_channels_workspace_id ON channels(workspace_id, id);
            CREATE INDEX IF NOT EXISTS idx_channel_members_workspace ON channel_members(
                workspace_id
            );
            CREATE INDEX IF NOT EXISTS idx_channel_members_channel ON channel_members(
                channel_id
            );
            CREATE INDEX IF NOT EXISTS idx_messages_workspace ON messages(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id);
            CREATE INDEX IF NOT EXISTS idx_messages_workspace_ts_id ON messages(
                workspace_id, ts DESC, id DESC
            );
            CREATE INDEX IF NOT EXISTS idx_files_workspace ON files(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_files_workspace_ts_id ON files(
                workspace_id, created_ts DESC, id DESC
            );
            CREATE INDEX IF NOT EXISTS idx_workspace_meta_workspace ON workspace_meta(workspace_id);
            """
        )
        self._ensure_column("channels", "channel_type", "TEXT", "public")
        self.conn.commit()

    def _ensure_column(self, table: str, column: str, column_type: str, default: str) -> None:
        cursor = self.conn.execute(f"PRAGMA table_info({table})")
        existing = {row["name"] for row in cursor.fetchall()}
        if column in existing:
            return
        escaped = default.replace("'", "''")
        self.conn.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {column_type} NOT NULL DEFAULT '{escaped}'"
        )

    def close(self) -> None:
        self.conn.close()

    def insert_workspace(self, workspace: Workspace, *, ignore: bool = False) -> None:
        verb = "INSERT OR IGNORE" if ignore else "INSERT"
        self.conn.execute(
            f"{verb} INTO workspaces (id, name, created_at) VALUES (?, ?, ?)",
            (workspace.id, workspace.name, workspace.created_at),
        )
        self.conn.commit()

    def insert_users(self, users: Iterable[User], *, ignore: bool = False) -> None:
        rows = [(u.id, u.workspace_id, u.name, u.email, u.title, u.is_bot) for u in users]
        verb = "INSERT OR IGNORE" if ignore else "INSERT"
        self.conn.executemany(
            (
                f"{verb} INTO users (id, workspace_id, name, email, title, is_bot) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            ),
            rows,
        )
        self.conn.commit()

    def insert_channels(self, channels: Iterable[Channel], *, ignore: bool = False) -> None:
        rows = [
            (c.id, c.workspace_id, c.name, c.is_private, c.channel_type, c.topic) for c in channels
        ]
        verb = "INSERT OR IGNORE" if ignore else "INSERT"
        self.conn.executemany(
            (
                f"{verb} INTO channels (id, workspace_id, name, is_private, channel_type, topic) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            ),
            rows,
        )
        self.conn.commit()

    def insert_channel_members(self, members: Iterable[ChannelMember]) -> None:
        rows = [(m.channel_id, m.workspace_id, m.user_id) for m in members]
        self.conn.executemany(
            (
                "INSERT OR IGNORE INTO channel_members (channel_id, workspace_id, user_id) "
                "VALUES (?, ?, ?)"
            ),
            rows,
        )
        self.conn.commit()

    def insert_messages(self, messages: Iterable[Message], *, ignore: bool = False) -> None:
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
        verb = "INSERT OR IGNORE" if ignore else "INSERT"
        self.conn.executemany(
            (
                f"{verb} INTO messages "
                "(id, workspace_id, channel_id, user_id, ts, text, thread_ts, reply_count, "
                "reactions_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            rows,
        )
        self.conn.commit()

    def insert_files(self, files: Iterable[File], *, ignore: bool = False) -> None:
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
        verb = "INSERT OR IGNORE" if ignore else "INSERT"
        self.conn.executemany(
            (
                f"{verb} INTO files "
                "(id, workspace_id, user_id, name, size, mimetype, created_ts, channel_id, "
                "message_id, url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            rows,
        )
        self.conn.commit()

    def list_workspaces(self) -> list[dict[str, object]]:
        cursor = self.conn.execute("SELECT * FROM workspaces ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def latest_workspace_id(self) -> str | None:
        row = self.conn.execute(
            "SELECT id FROM workspaces ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return str(row["id"])

    def get_workspace(self, workspace_id: str) -> dict[str, object] | None:
        cursor = self.conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def set_workspace_meta(self, workspace_id: str, meta: dict[str, object]) -> None:
        rows: list[tuple[str, str, str]] = []
        for key, value in meta.items():
            try:
                encoded = json.dumps(value, ensure_ascii=False)
            except TypeError:
                encoded = json.dumps(str(value), ensure_ascii=False)
            rows.append((workspace_id, key, encoded))
        self.conn.executemany(
            "INSERT OR REPLACE INTO workspace_meta (workspace_id, key, value) VALUES (?, ?, ?)",
            rows,
        )
        self.conn.commit()

    def get_workspace_meta(self, workspace_id: str) -> dict[str, object]:
        cursor = self.conn.execute(
            "SELECT key, value FROM workspace_meta WHERE workspace_id = ? ORDER BY key ASC",
            (workspace_id,),
        )
        meta: dict[str, object] = {}
        for row in cursor.fetchall():
            key = str(row["key"])
            raw = str(row["value"])
            try:
                meta[key] = json.loads(raw)
            except Exception:
                meta[key] = raw
        return meta

    def list_users(self, workspace_id: str, limit: int, offset: int) -> list[dict[str, object]]:
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE workspace_id = ? LIMIT ? OFFSET ?",
            (workspace_id, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_users_page(
        self, workspace_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[dict[str, object]], str | None]:
        where = ["workspace_id = ?"]
        params: list[object] = [workspace_id]

        decoded = decode_id_cursor(cursor) if cursor else None
        if decoded:
            where.append("id > ?")
            params.append(decoded["id"])

        sql = f"SELECT * FROM users WHERE {' AND '.join(where)} ORDER BY id ASC LIMIT ?"
        params.append(limit + 1)
        rows = [dict(r) for r in self.conn.execute(sql, params).fetchall()]

        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            next_cursor = encode_id_cursor(str(last["id"]))
            rows = rows[:limit]
        return rows, next_cursor

    def list_channels(
        self,
        workspace_id: str,
        limit: int,
        offset: int,
        *,
        channel_type: str | None = None,
    ) -> list[dict[str, object]]:
        if channel_type:
            cursor = self.conn.execute(
                (
                    "SELECT * FROM channels"
                    " WHERE workspace_id = ? AND channel_type = ?"
                    " LIMIT ? OFFSET ?"
                ),
                (workspace_id, channel_type, limit, offset),
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM channels WHERE workspace_id = ? LIMIT ? OFFSET ?",
                (workspace_id, limit, offset),
            )
        return [dict(row) for row in cursor.fetchall()]

    def list_channels_page(
        self,
        workspace_id: str,
        *,
        limit: int,
        cursor: str | None,
        channel_type: str | None = None,
    ) -> tuple[list[dict[str, object]], str | None]:
        where = ["workspace_id = ?"]
        params: list[object] = [workspace_id]

        if channel_type:
            where.append("channel_type = ?")
            params.append(channel_type)

        decoded = decode_id_cursor(cursor) if cursor else None
        if decoded:
            where.append("id > ?")
            params.append(decoded["id"])

        sql = f"SELECT * FROM channels WHERE {' AND '.join(where)} ORDER BY id ASC LIMIT ?"
        params.append(limit + 1)
        rows = [dict(r) for r in self.conn.execute(sql, params).fetchall()]

        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            next_cursor = encode_id_cursor(str(last["id"]))
            rows = rows[:limit]
        return rows, next_cursor

    def list_channel_members(
        self, workspace_id: str, limit: int, offset: int, *, channel_id: str | None = None
    ) -> list[dict[str, object]]:
        if channel_id:
            cursor = self.conn.execute(
                (
                    "SELECT * FROM channel_members"
                    " WHERE workspace_id = ? AND channel_id = ?"
                    " LIMIT ? OFFSET ?"
                ),
                (workspace_id, channel_id, limit, offset),
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM channel_members WHERE workspace_id = ? LIMIT ? OFFSET ?",
                (workspace_id, limit, offset),
            )
        return [dict(row) for row in cursor.fetchall()]

    def list_channel_members_page(
        self,
        workspace_id: str,
        *,
        limit: int,
        cursor: str | None,
        channel_id: str | None = None,
    ) -> tuple[list[dict[str, object]], str | None]:
        where = ["workspace_id = ?"]
        params: list[object] = [workspace_id]

        if channel_id:
            where.append("channel_id = ?")
            params.append(channel_id)

        decoded = decode_channel_member_cursor(cursor) if cursor else None
        if decoded:
            where.append("(channel_id > ? OR (channel_id = ? AND user_id > ?))")
            params.extend([decoded["channel_id"], decoded["channel_id"], decoded["user_id"]])

        sql = (
            "SELECT * FROM channel_members"
            f" WHERE {' AND '.join(where)}"
            " ORDER BY channel_id ASC, user_id ASC"
            " LIMIT ?"
        )
        params.append(limit + 1)
        rows = [dict(r) for r in self.conn.execute(sql, params).fetchall()]

        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            next_cursor = encode_channel_member_cursor(
                str(last["channel_id"]), str(last["user_id"])
            )
            rows = rows[:limit]
        return rows, next_cursor

    def _iter_query(
        self, sql: str, params: tuple[object, ...], *, chunk_size: int = 1000
    ) -> Iterable[dict[str, object]]:
        cursor = self.conn.execute(sql, params)
        while True:
            rows = cursor.fetchmany(chunk_size)
            if not rows:
                return
            for row in rows:
                yield dict(row)

    def iter_users(
        self, workspace_id: str, *, chunk_size: int = 1000
    ) -> Iterable[dict[str, object]]:
        yield from self._iter_query(
            "SELECT * FROM users WHERE workspace_id = ? ORDER BY id ASC",
            (workspace_id,),
            chunk_size=chunk_size,
        )

    def iter_channels(
        self, workspace_id: str, *, chunk_size: int = 1000
    ) -> Iterable[dict[str, object]]:
        yield from self._iter_query(
            "SELECT * FROM channels WHERE workspace_id = ? ORDER BY id ASC",
            (workspace_id,),
            chunk_size=chunk_size,
        )

    def iter_channel_members(
        self, workspace_id: str, *, chunk_size: int = 2000
    ) -> Iterable[dict[str, object]]:
        yield from self._iter_query(
            (
                "SELECT * FROM channel_members"
                " WHERE workspace_id = ?"
                " ORDER BY channel_id ASC, user_id ASC"
            ),
            (workspace_id,),
            chunk_size=chunk_size,
        )

    def iter_messages(
        self,
        workspace_id: str,
        *,
        chunk_size: int = 1000,
        after_ts: int | None = None,
    ) -> Iterable[dict[str, object]]:
        where = ["workspace_id = ?"]
        params: list[object] = [workspace_id]
        if after_ts is not None:
            where.append("ts > ?")
            params.append(after_ts)
        yield from self._iter_query(
            f"SELECT * FROM messages WHERE {' AND '.join(where)} ORDER BY ts DESC, id DESC",
            tuple(params),
            chunk_size=chunk_size,
        )

    def iter_messages_chronological(
        self, workspace_id: str, *, chunk_size: int = 1000
    ) -> Iterable[dict[str, object]]:
        yield from self._iter_query(
            "SELECT * FROM messages WHERE workspace_id = ? ORDER BY ts ASC, id ASC",
            (workspace_id,),
            chunk_size=chunk_size,
        )

    def iter_messages_for_import(
        self, workspace_id: str, *, chunk_size: int = 2000
    ) -> Iterable[dict[str, object]]:
        yield from self._iter_query(
            "SELECT * FROM messages WHERE workspace_id = ? ORDER BY channel_id ASC, ts ASC, id ASC",
            (workspace_id,),
            chunk_size=chunk_size,
        )

    def iter_files(
        self,
        workspace_id: str,
        *,
        chunk_size: int = 1000,
        after_ts: int | None = None,
    ) -> Iterable[dict[str, object]]:
        where = ["workspace_id = ?"]
        params: list[object] = [workspace_id]
        if after_ts is not None:
            where.append("created_ts > ?")
            params.append(after_ts)
        yield from self._iter_query(
            f"SELECT * FROM files WHERE {' AND '.join(where)} ORDER BY created_ts DESC, id DESC",
            tuple(params),
            chunk_size=chunk_size,
        )

    def list_messages(self, workspace_id: str, limit: int, offset: int) -> list[dict[str, object]]:
        cursor = self.conn.execute(
            "SELECT * FROM messages WHERE workspace_id = ? ORDER BY ts DESC LIMIT ? OFFSET ?",
            (workspace_id, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_messages_page(
        self,
        workspace_id: str,
        *,
        limit: int,
        cursor: str | None,
        channel_id: str | None = None,
        user_id: str | None = None,
        before_ts: int | None = None,
        after_ts: int | None = None,
    ) -> tuple[list[dict[str, object]], str | None]:
        where = ["workspace_id = ?"]
        params: list[object] = [workspace_id]

        if channel_id:
            where.append("channel_id = ?")
            params.append(channel_id)
        if user_id:
            where.append("user_id = ?")
            params.append(user_id)
        if before_ts is not None:
            where.append("ts < ?")
            params.append(before_ts)
        if after_ts is not None:
            where.append("ts > ?")
            params.append(after_ts)

        decoded = decode_cursor(cursor) if cursor else None
        if decoded:
            where.append("(ts < ? OR (ts = ? AND id < ?))")
            params.extend([decoded["ts"], decoded["ts"], decoded["id"]])

        sql = (
            f"SELECT * FROM messages WHERE {' AND '.join(where)} ORDER BY ts DESC, id DESC LIMIT ?"
        )
        params.append(limit + 1)
        rows = [dict(r) for r in self.conn.execute(sql, params).fetchall()]

        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            next_cursor = encode_cursor(int(last["ts"]), str(last["id"]))
            rows = rows[:limit]
        return rows, next_cursor

    def list_files(self, workspace_id: str, limit: int, offset: int) -> list[dict[str, object]]:
        cursor = self.conn.execute(
            "SELECT * FROM files WHERE workspace_id = ? ORDER BY created_ts DESC LIMIT ? OFFSET ?",
            (workspace_id, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_files_page(
        self,
        workspace_id: str,
        *,
        limit: int,
        cursor: str | None,
        channel_id: str | None = None,
        user_id: str | None = None,
        before_ts: int | None = None,
        after_ts: int | None = None,
    ) -> tuple[list[dict[str, object]], str | None]:
        where = ["workspace_id = ?"]
        params: list[object] = [workspace_id]

        if channel_id:
            where.append("channel_id = ?")
            params.append(channel_id)
        if user_id:
            where.append("user_id = ?")
            params.append(user_id)
        if before_ts is not None:
            where.append("created_ts < ?")
            params.append(before_ts)
        if after_ts is not None:
            where.append("created_ts > ?")
            params.append(after_ts)

        decoded = decode_cursor(cursor) if cursor else None
        if decoded:
            where.append("(created_ts < ? OR (created_ts = ? AND id < ?))")
            params.extend([decoded["ts"], decoded["ts"], decoded["id"]])

        sql = (
            "SELECT * FROM files"
            f" WHERE {' AND '.join(where)}"
            " ORDER BY created_ts DESC, id DESC"
            " LIMIT ?"
        )
        params.append(limit + 1)
        rows = [dict(r) for r in self.conn.execute(sql, params).fetchall()]

        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            next_cursor = encode_cursor(int(last["created_ts"]), str(last["id"]))
            rows = rows[:limit]
        return rows, next_cursor

    def stats(self, workspace_id: str) -> dict[str, int]:
        cursor = self.conn.cursor()
        counts = {}
        for table in ("users", "channels", "channel_members", "messages", "files"):
            res = cursor.execute(
                f"SELECT COUNT(*) as count FROM {table} WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()
            counts[table] = res["count"] if res else 0
        return counts

    def max_message_ts(self, workspace_id: str) -> int | None:
        row = self.conn.execute(
            "SELECT MAX(ts) AS max_ts FROM messages WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        if not row or row["max_ts"] is None:
            return None
        return int(row["max_ts"])

    def max_file_ts(self, workspace_id: str) -> int | None:
        row = self.conn.execute(
            "SELECT MAX(created_ts) AS max_ts FROM files WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        if not row or row["max_ts"] is None:
            return None
        return int(row["max_ts"])

    def channel_type_counts(self, workspace_id: str) -> dict[str, int]:
        cursor = self.conn.execute(
            (
                "SELECT channel_type, COUNT(*) as count FROM channels "
                "WHERE workspace_id = ? GROUP BY channel_type"
            ),
            (workspace_id,),
        )
        return {str(row["channel_type"]): int(row["count"]) for row in cursor.fetchall()}

    def export_summary(self, workspace_id: str) -> dict[str, object]:
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError("workspace not found")
        summary = {
            "workspace": workspace,
            "meta": self.get_workspace_meta(workspace_id),
            "counts": self.stats(workspace_id),
            "channel_types": self.channel_type_counts(workspace_id),
            "max": {
                "messages_max_ts": self.max_message_ts(workspace_id),
                "files_max_ts": self.max_file_ts(workspace_id),
            },
        }
        return summary


_REQUIRED_TABLES: dict[str, set[str]] = {
    "workspaces": {"id", "name", "created_at"},
    "workspace_meta": {"workspace_id", "key", "value"},
    "users": {"id", "workspace_id", "name", "email", "title", "is_bot"},
    "channels": {"id", "workspace_id", "name", "is_private", "channel_type", "topic"},
    "channel_members": {"channel_id", "workspace_id", "user_id"},
    "messages": {
        "id",
        "workspace_id",
        "channel_id",
        "user_id",
        "ts",
        "text",
        "thread_ts",
        "reply_count",
        "reactions_json",
    },
    "files": {
        "id",
        "workspace_id",
        "user_id",
        "name",
        "size",
        "mimetype",
        "created_ts",
        "channel_id",
        "message_id",
        "url",
    },
}

SCHEMA_VERSION = 1


def _sqlite_connect_readonly(path: str) -> sqlite3.Connection:
    # Use read-only mode so validation doesn't mutate unknown DBs.
    uri = f"file:{path}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _parse_semver(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", value.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def validate_db(
    path: str,
    *,
    workspace_id: str | None = None,
    require_workspace: bool = False,
    tool_version: str | None = None,
) -> dict[str, object]:
    """Validate that a SQLite DB appears compatible with slack-workspace-synth.

    This is a read-only check meant for fail-fast CLI diagnostics.
    """
    db_path = Path(path)
    report: dict[str, object] = {
        "db": str(db_path),
        "ok": False,
        "workspace_id": workspace_id,
        "errors": [],
        "warnings": [],
        "meta": {},
        "tool_version": tool_version,
        "required_schema_version": SCHEMA_VERSION,
    }
    errors: list[str] = cast(list[str], report["errors"])
    warnings: list[str] = cast(list[str], report["warnings"])

    if not db_path.exists():
        errors.append(f"DB file not found: {db_path}")
        return report

    try:
        conn = _sqlite_connect_readonly(str(db_path))
    except sqlite3.OperationalError as exc:
        errors.append(f"Unable to open DB read-only: {exc}")
        return report

    try:
        conn.row_factory = sqlite3.Row
        try:
            table_rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            errors.append(f"Not a usable SQLite database: {exc}")
            return report
        tables = {str(r["name"]) for r in table_rows}
        if not tables:
            errors.append("DB has no tables (did you point at the right SQLite file?).")
            return report

        for table, required_cols in _REQUIRED_TABLES.items():
            if table not in tables:
                errors.append(f"Missing table: {table}")
                continue
            col_rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            cols = {str(r["name"]) for r in col_rows}
            missing = sorted(required_cols - cols)
            if missing:
                errors.append(f"Table {table} missing columns: {', '.join(missing)}")

        # Optional workspace/meta inspection for quick operator context.
        if "workspaces" in tables and "workspace_meta" in tables:
            resolved_workspace = workspace_id
            if not resolved_workspace:
                row = conn.execute(
                    "SELECT id FROM workspaces ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                resolved_workspace = str(row["id"]) if row else None
            report["workspace_id"] = resolved_workspace

            if workspace_id:
                exists = conn.execute(
                    "SELECT 1 FROM workspaces WHERE id = ? LIMIT 1", (workspace_id,)
                ).fetchone()
                if not exists:
                    errors.append(f"Workspace not found: {workspace_id}")

            if require_workspace and not resolved_workspace:
                errors.append("No workspaces found in DB.")

            if resolved_workspace:
                meta_rows = conn.execute(
                    "SELECT key, value FROM workspace_meta WHERE workspace_id = ? ORDER BY key ASC",
                    (resolved_workspace,),
                ).fetchall()
                meta: dict[str, object] = {}
                for r in meta_rows:
                    key = str(r["key"])
                    raw = str(r["value"])
                    try:
                        meta[key] = json.loads(raw)
                    except Exception:
                        meta[key] = raw
                report["meta"] = meta

                generator = meta.get("generator")
                if generator and generator != "slack-workspace-synth":
                    warnings.append(f"Unexpected generator meta: {generator!r}")

                generator_version = meta.get("generator_version")
                if not generator_version:
                    warnings.append("Missing workspace_meta generator_version.")
                else:
                    parsed_gen = _parse_semver(generator_version)
                    parsed_tool = _parse_semver(tool_version) if tool_version else None
                    if parsed_gen and parsed_tool and parsed_gen > parsed_tool:
                        warnings.append(
                            "DB generator_version appears newer than this tool; "
                            "consider upgrading slack-workspace-synth."
                        )

                schema_version = meta.get("schema_version")
                if schema_version is None:
                    warnings.append("Missing workspace_meta schema_version (older DB export?).")
                elif isinstance(schema_version, int):
                    if schema_version > SCHEMA_VERSION:
                        errors.append(
                            f"DB schema_version {schema_version} is newer than supported "
                            f"{SCHEMA_VERSION}."
                        )
                else:
                    warnings.append(
                        f"Unrecognized schema_version type: {type(schema_version).__name__}"
                    )
    finally:
        conn.close()

    report["ok"] = len(errors) == 0
    return report


def dump_json(path: str, payload: object) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def dump_jsonl(path: str, rows: Iterable[dict[str, object]], *, compress: bool = False) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if compress:
        import gzip

        with gzip.open(path, "wt", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False))
                f.write("\n")
        return
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def load_jsonl(path: str) -> Iterable[dict[str, object]]:
    def _iter_lines(handle: Iterable[str]) -> Iterable[str]:
        for line in handle:
            raw = line.strip()
            if raw:
                yield raw

    if path.endswith(".gz"):
        import gzip

        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in _iter_lines(f):
                yield json.loads(line)
        return

    with open(path, encoding="utf-8") as f:
        for line in _iter_lines(f):
            yield json.loads(line)


def encode_cursor(ts: int, row_id: str) -> str:
    payload = json.dumps(
        {"ts": ts, "id": row_id}, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> dict[str, object] | None:
    if not cursor:
        return None
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        decoded = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValueError("invalid cursor") from None
    if not isinstance(decoded, dict):
        raise ValueError("invalid cursor")
    if "ts" not in decoded or "id" not in decoded:
        raise ValueError("invalid cursor")
    ts = decoded["ts"]
    row_id = decoded["id"]
    if not isinstance(ts, int) or not isinstance(row_id, str):
        raise ValueError("invalid cursor")
    return {"ts": ts, "id": row_id}


def encode_id_cursor(row_id: str) -> str:
    payload = json.dumps({"id": row_id}, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_id_cursor(cursor: str) -> dict[str, object] | None:
    if not cursor:
        return None
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        decoded = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValueError("invalid cursor") from None
    if not isinstance(decoded, dict):
        raise ValueError("invalid cursor")
    if "id" not in decoded:
        raise ValueError("invalid cursor")
    row_id = decoded["id"]
    if not isinstance(row_id, str):
        raise ValueError("invalid cursor")
    return {"id": row_id}


def encode_channel_member_cursor(channel_id: str, user_id: str) -> str:
    payload = json.dumps(
        {"channel_id": channel_id, "user_id": user_id},
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_channel_member_cursor(cursor: str) -> dict[str, object] | None:
    if not cursor:
        return None
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        decoded = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValueError("invalid cursor") from None
    if not isinstance(decoded, dict):
        raise ValueError("invalid cursor")
    if "channel_id" not in decoded or "user_id" not in decoded:
        raise ValueError("invalid cursor")
    channel_id = decoded["channel_id"]
    user_id = decoded["user_id"]
    if not isinstance(channel_id, str) or not isinstance(user_id, str):
        raise ValueError("invalid cursor")
    return {"channel_id": channel_id, "user_id": user_id}
