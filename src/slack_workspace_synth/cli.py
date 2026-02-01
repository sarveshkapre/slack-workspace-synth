from __future__ import annotations

from pathlib import Path

import typer
from faker import Faker

from .generator import (
    GenerationConfig,
    generate_channels,
    generate_files,
    generate_messages,
    generate_users,
    generate_workspace,
)
from .plugins import PluginRegistry, load_plugins
from .storage import SQLiteStore, dump_json, dump_jsonl

app = typer.Typer(add_completion=False)


def _resolve_plugins(modules: list[str] | None) -> PluginRegistry:
    if not modules:
        return PluginRegistry()
    return load_plugins(modules)


@app.command()
def generate(
    workspace: str = typer.Option("Synth Workspace", help="Workspace name"),
    users: int = typer.Option(2000, help="Number of users"),
    channels: int = typer.Option(80, help="Number of channels"),
    messages: int = typer.Option(120000, help="Number of messages"),
    files: int = typer.Option(5000, help="Number of files"),
    seed: int = typer.Option(42, help="Random seed"),
    db: str = typer.Option("./data/workspace.db", help="SQLite DB path"),
    batch_size: int = typer.Option(500, help="Insert batch size"),
    plugin: list[str] | None = typer.Option(None, help="Plugin module path"),
    export_summary: str | None = typer.Option(None, help="Write summary JSON path"),
) -> None:
    """Generate a synthetic workspace into SQLite."""
    config = GenerationConfig(
        workspace_name=workspace,
        users=users,
        channels=channels,
        messages=messages,
        files=files,
        seed=seed,
        batch_size=batch_size,
    )
    rng = __import__("random").Random(seed)
    faker = Faker()
    faker.seed_instance(seed)
    plugins = _resolve_plugins(plugin)

    store = SQLiteStore(db)
    try:
        workspace_obj = generate_workspace(config, plugins)
        store.insert_workspace(workspace_obj)

        user_list = generate_users(config, workspace_obj.id, rng, faker, plugins)
        store.insert_users(user_list)

        channel_list = generate_channels(config, workspace_obj.id, rng, faker, plugins)
        store.insert_channels(channel_list)

        user_ids = [u.id for u in user_list]
        channel_ids = [c.id for c in channel_list]

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
