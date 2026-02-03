from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from faker import Faker

from .generator import (
    GenerationConfig,
    generate_channel_members,
    generate_channels,
    generate_files,
    generate_messages,
    generate_users,
    generate_workspace,
)
from .models import Channel, ChannelMember, File, Message, User, Workspace
from .plugins import PluginRegistry, load_plugins
from .storage import SQLiteStore, dump_json, dump_jsonl, load_jsonl

app = typer.Typer(add_completion=False)

_PKG_VERSION = __import__("slack_workspace_synth").__version__


def _resolve_plugins(modules: list[str] | None) -> PluginRegistry:
    if not modules:
        return PluginRegistry()
    return load_plugins(modules)


@app.command()
def generate(
    workspace: str = typer.Option("Synth Workspace", help="Workspace name"),
    users: int | None = typer.Option(None, help="Number of users"),
    channels: int | None = typer.Option(None, help="Number of channels"),
    dm_channels: int | None = typer.Option(None, help="Number of direct-message channels"),
    mpdm_channels: int | None = typer.Option(None, help="Number of multi-party DMs"),
    messages: int | None = typer.Option(None, help="Number of messages"),
    files: int | None = typer.Option(None, help="Number of files"),
    seed: int = typer.Option(42, help="Random seed"),
    db: str = typer.Option("./data/workspace.db", help="SQLite DB path"),
    batch_size: int = typer.Option(500, help="Insert batch size"),
    channel_members_min: int | None = typer.Option(None, help="Minimum members per channel"),
    channel_members_max: int | None = typer.Option(None, help="Maximum members per channel"),
    mpdm_members_min: int | None = typer.Option(None, help="Minimum members per MPDM"),
    mpdm_members_max: int | None = typer.Option(None, help="Maximum members per MPDM"),
    plugin: list[str] | None = typer.Option(None, help="Plugin module path"),
    export_summary: str | None = typer.Option(None, help="Write summary JSON path"),
    profile: str = typer.Option("default", help="Generation profile: default or enterprise"),
) -> None:
    """Generate a synthetic workspace into SQLite."""
    profiles = {
        "default": {
            "users": 2000,
            "channels": 80,
            "dm_channels": 0,
            "mpdm_channels": 0,
            "messages": 120000,
            "files": 5000,
            "channel_members_min": 8,
            "channel_members_max": 120,
            "mpdm_members_min": 3,
            "mpdm_members_max": 7,
        },
        "enterprise": {
            "users": 2500,
            "channels": 120,
            "dm_channels": 1800,
            "mpdm_channels": 320,
            "messages": 180000,
            "files": 9000,
            "channel_members_min": 25,
            "channel_members_max": 350,
            "mpdm_members_min": 3,
            "mpdm_members_max": 9,
        },
    }
    if profile not in profiles:
        raise typer.BadParameter(f"Unknown profile: {profile}")
    defaults = profiles[profile]
    resolved_users = users if users is not None else defaults["users"]
    resolved_channels = channels if channels is not None else defaults["channels"]
    resolved_dm_channels = dm_channels if dm_channels is not None else defaults["dm_channels"]
    resolved_mpdm_channels = (
        mpdm_channels if mpdm_channels is not None else defaults["mpdm_channels"]
    )
    resolved_messages = messages if messages is not None else defaults["messages"]
    resolved_files = files if files is not None else defaults["files"]
    resolved_channel_members_min = (
        channel_members_min if channel_members_min is not None else defaults["channel_members_min"]
    )
    resolved_channel_members_max = (
        channel_members_max if channel_members_max is not None else defaults["channel_members_max"]
    )
    resolved_mpdm_members_min = (
        mpdm_members_min if mpdm_members_min is not None else defaults["mpdm_members_min"]
    )
    resolved_mpdm_members_max = (
        mpdm_members_max if mpdm_members_max is not None else defaults["mpdm_members_max"]
    )
    config = GenerationConfig(
        workspace_name=workspace,
        users=resolved_users,
        channels=resolved_channels,
        dm_channels=resolved_dm_channels,
        mpdm_channels=resolved_mpdm_channels,
        messages=resolved_messages,
        files=resolved_files,
        seed=seed,
        batch_size=batch_size,
        channel_members_min=resolved_channel_members_min,
        channel_members_max=resolved_channel_members_max,
        mpdm_members_min=resolved_mpdm_members_min,
        mpdm_members_max=resolved_mpdm_members_max,
    )
    rng = __import__("random").Random(seed)
    faker = Faker()
    faker.seed_instance(seed)
    plugins = _resolve_plugins(plugin)

    store = SQLiteStore(db)
    try:
        workspace_obj = generate_workspace(config, plugins)
        store.insert_workspace(workspace_obj)
        store.set_workspace_meta(
            workspace_obj.id,
            {
                "generator": "slack-workspace-synth",
                "generator_version": _PKG_VERSION,
                "seed": seed,
                "requested": {
                    "users": resolved_users,
                    "channels": resolved_channels,
                    "dm_channels": resolved_dm_channels,
                    "mpdm_channels": resolved_mpdm_channels,
                    "messages": resolved_messages,
                    "files": resolved_files,
                    "batch_size": batch_size,
                    "workspace_name": workspace,
                    "profile": profile,
                    "channel_members_min": resolved_channel_members_min,
                    "channel_members_max": resolved_channel_members_max,
                    "mpdm_members_min": resolved_mpdm_members_min,
                    "mpdm_members_max": resolved_mpdm_members_max,
                    "plugins": plugin or [],
                },
            },
        )

        user_list = generate_users(config, workspace_obj.id, rng, faker, plugins)
        store.insert_users(user_list)

        channel_list = generate_channels(config, workspace_obj.id, rng, faker, plugins)
        store.insert_channels(channel_list)

        user_ids = [u.id for u in user_list]
        channel_ids = [c.id for c in channel_list]

        channel_members = generate_channel_members(
            config, workspace_obj.id, user_list, channel_list, rng
        )
        store.insert_channel_members(channel_members)

        message_buffer = []
        for message in generate_messages(
            config, workspace_obj.id, user_ids, channel_ids, rng, faker, plugins
        ):
            message_buffer.append(message)
            if len(message_buffer) >= config.batch_size:
                store.insert_messages(message_buffer)
                message_buffer = []
        if message_buffer:
            store.insert_messages(message_buffer)

        file_buffer = []
        for file_item in generate_files(
            config, workspace_obj.id, user_ids, channel_ids, rng, faker, plugins
        ):
            file_buffer.append(file_item)
            if len(file_buffer) >= config.batch_size:
                store.insert_files(file_buffer)
                file_buffer = []
        if file_buffer:
            store.insert_files(file_buffer)

        if export_summary:
            summary = store.export_summary(workspace_obj.id)
            dump_json(export_summary, summary)
    finally:
        store.close()


@app.command("import-jsonl")
def import_jsonl(
    source: str = typer.Option("./export", help="Export directory (workspace id subdir)"),
    db: str = typer.Option("./data/workspace.db", help="SQLite DB path"),
    workspace_id: str | None = typer.Option(
        None, help="Workspace id (defaults to first subdir in export)"
    ),
    force: bool = typer.Option(False, help="Overwrite existing DB"),
    batch_size: int = typer.Option(1000, help="Insert batch size"),
) -> None:
    """Import JSONL export directory into SQLite."""
    source_path = Path(source)
    if not source_path.exists():
        raise typer.BadParameter(f"Export directory not found: {source}")

    if force and Path(db).exists():
        Path(db).unlink()

    resolved_workspace_id = workspace_id
    if not resolved_workspace_id:
        candidates = sorted([p.name for p in source_path.iterdir() if p.is_dir()])
        if not candidates:
            raise typer.BadParameter("No workspace export directories found.")
        resolved_workspace_id = candidates[0]

    export_dir = source_path / resolved_workspace_id
    if not export_dir.exists():
        raise typer.BadParameter(f"Workspace export not found: {export_dir}")

    workspace_path = export_dir / "workspace.json"
    if not workspace_path.exists():
        raise typer.BadParameter("workspace.json missing in export directory")

    with open(workspace_path, encoding="utf-8") as f:
        workspace_payload = json.load(f)

    workspace_data = workspace_payload.get("workspace")
    if not isinstance(workspace_data, dict):
        raise typer.BadParameter("workspace.json missing workspace object")

    workspace_obj = Workspace(
        id=str(workspace_data["id"]),
        name=str(workspace_data["name"]),
        created_at=int(workspace_data["created_at"]),
    )

    summary_path = export_dir / "summary.json"
    meta: dict[str, object] = {}
    if summary_path.exists():
        with open(summary_path, encoding="utf-8") as f:
            summary_payload = json.load(f)
            meta = summary_payload.get("meta", {}) if isinstance(summary_payload, dict) else {}

    store = SQLiteStore(db)
    try:
        store.insert_workspace(workspace_obj)
        if meta:
            store.set_workspace_meta(workspace_obj.id, meta)

        def _get_str(row: dict[str, Any], key: str, default: str | None = None) -> str:
            value = row.get(key, default)
            if value is None:
                raise typer.BadParameter(f"Missing required field: {key}")
            return str(value)

        def _get_int(row: dict[str, Any], key: str, default: int | None = None) -> int:
            value = row.get(key, default)
            if value is None:
                raise typer.BadParameter(f"Missing required field: {key}")
            return int(value)

        def _get_optional_int(row: dict[str, Any], key: str) -> int | None:
            value = row.get(key)
            return int(value) if value is not None else None

        def _import_users(path: Path) -> None:
            buffer: list[User] = []
            for row in load_jsonl(str(path)):
                data = row if isinstance(row, dict) else {}
                buffer.append(
                    User(
                        id=_get_str(data, "id"),
                        workspace_id=_get_str(data, "workspace_id", workspace_obj.id),
                        name=_get_str(data, "name"),
                        email=_get_str(data, "email"),
                        title=_get_str(data, "title"),
                        is_bot=_get_int(data, "is_bot"),
                    )
                )
                if len(buffer) >= batch_size:
                    store.insert_users(buffer)
                    buffer = []
            if buffer:
                store.insert_users(buffer)

        def _import_channels(path: Path) -> None:
            buffer: list[Channel] = []
            for row in load_jsonl(str(path)):
                data = row if isinstance(row, dict) else {}
                buffer.append(
                    Channel(
                        id=_get_str(data, "id"),
                        workspace_id=_get_str(data, "workspace_id", workspace_obj.id),
                        name=_get_str(data, "name"),
                        is_private=_get_int(data, "is_private"),
                        channel_type=_get_str(data, "channel_type", "public"),
                        topic=_get_str(data, "topic"),
                    )
                )
                if len(buffer) >= batch_size:
                    store.insert_channels(buffer)
                    buffer = []
            if buffer:
                store.insert_channels(buffer)

        def _import_channel_members(path: Path) -> None:
            if not path.exists():
                return
            buffer: list[ChannelMember] = []
            for row in load_jsonl(str(path)):
                data = row if isinstance(row, dict) else {}
                buffer.append(
                    ChannelMember(
                        channel_id=_get_str(data, "channel_id"),
                        workspace_id=_get_str(data, "workspace_id", workspace_obj.id),
                        user_id=_get_str(data, "user_id"),
                    )
                )
                if len(buffer) >= batch_size:
                    store.insert_channel_members(buffer)
                    buffer = []
            if buffer:
                store.insert_channel_members(buffer)

        def _import_messages(path: Path) -> None:
            buffer: list[Message] = []
            for row in load_jsonl(str(path)):
                data = row if isinstance(row, dict) else {}
                buffer.append(
                    Message(
                        id=_get_str(data, "id"),
                        workspace_id=_get_str(data, "workspace_id", workspace_obj.id),
                        channel_id=_get_str(data, "channel_id"),
                        user_id=_get_str(data, "user_id"),
                        ts=_get_int(data, "ts"),
                        text=_get_str(data, "text"),
                        thread_ts=_get_optional_int(data, "thread_ts"),
                        reply_count=_get_int(data, "reply_count"),
                        reactions_json=_get_str(data, "reactions_json"),
                    )
                )
                if len(buffer) >= batch_size:
                    store.insert_messages(buffer)
                    buffer = []
            if buffer:
                store.insert_messages(buffer)

        def _import_files(path: Path) -> None:
            buffer: list[File] = []
            for row in load_jsonl(str(path)):
                data = row if isinstance(row, dict) else {}
                buffer.append(
                    File(
                        id=_get_str(data, "id"),
                        workspace_id=_get_str(data, "workspace_id", workspace_obj.id),
                        user_id=_get_str(data, "user_id"),
                        name=_get_str(data, "name"),
                        size=_get_int(data, "size"),
                        mimetype=_get_str(data, "mimetype"),
                        created_ts=_get_int(data, "created_ts"),
                        channel_id=_get_str(data, "channel_id"),
                        message_id=_get_str(data, "message_id") if data.get("message_id") else None,
                        url=_get_str(data, "url"),
                    )
                )
                if len(buffer) >= batch_size:
                    store.insert_files(buffer)
                    buffer = []
            if buffer:
                store.insert_files(buffer)

        def _pick(path: Path, stem: str) -> Path:
            gz = path / f"{stem}.jsonl.gz"
            if gz.exists():
                return gz
            return path / f"{stem}.jsonl"

        _import_users(_pick(export_dir, "users"))
        _import_channels(_pick(export_dir, "channels"))
        _import_channel_members(_pick(export_dir, "channel_members"))
        _import_messages(_pick(export_dir, "messages"))
        _import_files(_pick(export_dir, "files"))

        typer.echo(f"Imported workspace {workspace_obj.id} into {db}")
    finally:
        store.close()


@app.command()
def serve(
    db: str = typer.Option("./data/workspace.db", help="SQLite DB path"),
    host: str = typer.Option("127.0.0.1", help="Host"),
    port: int = typer.Option(8080, help="Port"),
) -> None:
    """Run the FastAPI server."""
    import os

    import uvicorn

    os.environ["SWSYNTH_DB"] = db
    uvicorn.run(
        "slack_workspace_synth.api:app",
        host=host,
        port=port,
        reload=False,
        factory=False,
    )


@app.command("export-jsonl")
def export_jsonl(
    db: str = typer.Option("./data/workspace.db", help="SQLite DB path"),
    out: str = typer.Option("./export", help="Output directory"),
    workspace_id: str | None = typer.Option(
        None, help="Workspace id (defaults to most recently created workspace)"
    ),
    compress: bool = typer.Option(False, help="Gzip JSONL outputs"),
    chunk_size: int = typer.Option(2000, help="SQLite fetch chunk size"),
) -> None:
    """Export a workspace to JSON + JSONL files (streaming)."""
    store = SQLiteStore(db)
    try:
        resolved_workspace_id = workspace_id or store.latest_workspace_id()
        if not resolved_workspace_id:
            raise typer.BadParameter("No workspaces found in DB; generate one first.")

        workspace = store.get_workspace(resolved_workspace_id)
        if not workspace:
            raise typer.BadParameter(f"Workspace not found: {resolved_workspace_id}")

        out_dir = Path(out) / resolved_workspace_id
        out_dir.mkdir(parents=True, exist_ok=True)

        dump_json(str(out_dir / "workspace.json"), {"workspace": workspace})
        dump_json(str(out_dir / "summary.json"), store.export_summary(resolved_workspace_id))

        suffix = ".jsonl.gz" if compress else ".jsonl"
        dump_jsonl(
            str(out_dir / f"users{suffix}"),
            store.iter_users(resolved_workspace_id, chunk_size=chunk_size),
            compress=compress,
        )
        dump_jsonl(
            str(out_dir / f"channels{suffix}"),
            store.iter_channels(resolved_workspace_id, chunk_size=chunk_size),
            compress=compress,
        )
        dump_jsonl(
            str(out_dir / f"channel_members{suffix}"),
            store.iter_channel_members(resolved_workspace_id, chunk_size=chunk_size),
            compress=compress,
        )
        dump_jsonl(
            str(out_dir / f"messages{suffix}"),
            store.iter_messages(resolved_workspace_id, chunk_size=chunk_size),
            compress=compress,
        )
        dump_jsonl(
            str(out_dir / f"files{suffix}"),
            store.iter_files(resolved_workspace_id, chunk_size=chunk_size),
            compress=compress,
        )

        typer.echo(f"Wrote export to: {out_dir}")
    finally:
        store.close()


@app.command()
def stats(
    db: str = typer.Option("./data/workspace.db", help="SQLite DB path"),
    workspace_id: str | None = typer.Option(
        None, help="Workspace id (defaults to most recently created workspace)"
    ),
    json_out: str | None = typer.Option(None, help="Write summary JSON path"),
) -> None:
    """Print workspace counts (and optionally write summary JSON)."""
    store = SQLiteStore(db)
    try:
        resolved_workspace_id = workspace_id or store.latest_workspace_id()
        if not resolved_workspace_id:
            raise typer.BadParameter("No workspaces found in DB; generate one first.")

        summary = store.export_summary(resolved_workspace_id)
        if json_out:
            dump_json(json_out, summary)

        workspace = summary["workspace"]
        counts = summary["counts"]
        if not isinstance(workspace, dict) or not isinstance(counts, dict):
            raise RuntimeError("unexpected summary shape")

        created_at = workspace.get("created_at")
        created_at_iso = None
        if isinstance(created_at, int):
            created_at_iso = datetime.fromtimestamp(created_at, tz=UTC).isoformat()

        typer.echo(f"Workspace: {workspace.get('name')} ({workspace.get('id')})")
        if created_at_iso:
            typer.echo(f"Created:  {created_at_iso}")
        typer.echo("Counts:")
        for key in ("users", "channels", "channel_members", "messages", "files"):
            typer.echo(f"- {key}: {counts.get(key)}")
        channel_types = summary.get("channel_types")
        if isinstance(channel_types, dict) and channel_types:
            typer.echo("Channel types:")
            for key, value in channel_types.items():
                typer.echo(f"- {key}: {value}")
        if json_out:
            typer.echo(f"Wrote summary JSON to: {json_out}")
    finally:
        store.close()
