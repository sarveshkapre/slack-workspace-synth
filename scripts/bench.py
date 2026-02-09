#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import random
import sys
import time
from pathlib import Path

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
from slack_workspace_synth.storage import SCHEMA_VERSION, SQLiteStore, dump_json, dump_jsonl


def _profiles() -> dict[str, dict[str, int]]:
    return {
        "quick": {
            "users": 200,
            "channels": 20,
            "dm_channels": 0,
            "mpdm_channels": 0,
            "messages": 5_000,
            "files": 500,
        },
        "default": {
            "users": 2_000,
            "channels": 80,
            "dm_channels": 0,
            "mpdm_channels": 0,
            "messages": 120_000,
            "files": 5_000,
        },
        "enterprise": {
            "users": 2_500,
            "channels": 120,
            "dm_channels": 1_800,
            "mpdm_channels": 320,
            "messages": 180_000,
            "files": 9_000,
        },
    }


def _dir_size_bytes(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark workspace generation and JSONL export.")
    parser.add_argument("--out", default="./bench_out", help="Output directory")
    parser.add_argument("--workspace", default="Bench Workspace", help="Workspace name")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--profile",
        choices=sorted(_profiles().keys()),
        default="quick",
        help="Benchmark profile preset",
    )
    parser.add_argument("--users", type=int, default=None)
    parser.add_argument("--channels", type=int, default=None)
    parser.add_argument("--dm-channels", type=int, default=None)
    parser.add_argument("--mpdm-channels", type=int, default=None)
    parser.add_argument("--messages", type=int, default=None)
    parser.add_argument("--files", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--compress", action="store_true", help="Gzip JSONL outputs")
    parser.add_argument("--report", default=None, help="Write report JSON to this path")
    args = parser.parse_args(argv)

    preset = _profiles()[args.profile]
    config = GenerationConfig(
        workspace_name=args.workspace,
        users=int(args.users if args.users is not None else preset["users"]),
        channels=int(args.channels if args.channels is not None else preset["channels"]),
        dm_channels=int(
            args.dm_channels if args.dm_channels is not None else preset["dm_channels"]
        ),
        mpdm_channels=int(
            args.mpdm_channels if args.mpdm_channels is not None else preset["mpdm_channels"]
        ),
        messages=int(args.messages if args.messages is not None else preset["messages"]),
        files=int(args.files if args.files is not None else preset["files"]),
        seed=int(args.seed),
        batch_size=int(args.batch_size),
    )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / "workspace.db"
    export_dir = out_dir / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.report) if args.report else (out_dir / "report.json")

    rng = random.Random(config.seed)
    faker = Faker()
    faker.seed_instance(config.seed)
    plugins = PluginRegistry()

    t0 = time.perf_counter()
    store = SQLiteStore(str(db_path))
    try:
        workspace_obj = generate_workspace(config, plugins)
        store.insert_workspace(workspace_obj)
        store.set_workspace_meta(
            workspace_obj.id,
            {
                "generator": "slack-workspace-synth",
                "generator_version": __import__("slack_workspace_synth").__version__,
                "schema_version": SCHEMA_VERSION,
                "seed": config.seed,
                "requested": {
                    "users": config.users,
                    "channels": config.channels,
                    "dm_channels": config.dm_channels,
                    "mpdm_channels": config.mpdm_channels,
                    "messages": config.messages,
                    "files": config.files,
                    "batch_size": config.batch_size,
                    "workspace_name": config.workspace_name,
                    "profile": args.profile,
                },
            },
        )

        users = generate_users(config, workspace_obj.id, rng, faker, plugins)
        store.insert_users(users)

        channels = generate_channels(config, workspace_obj.id, rng, faker, plugins)
        store.insert_channels(channels)

        channel_members = generate_channel_members(config, workspace_obj.id, users, channels, rng)
        store.insert_channel_members(channel_members)

        user_ids = [u.id for u in users]
        channel_ids = [c.id for c in channels]

        message_buffer = []
        for msg in generate_messages(
            config, workspace_obj.id, user_ids, channel_ids, rng, faker, plugins
        ):
            message_buffer.append(msg)
            if len(message_buffer) >= config.batch_size:
                store.insert_messages(message_buffer)
                message_buffer = []
        if message_buffer:
            store.insert_messages(message_buffer)

        file_buffer = []
        for f in generate_files(
            config, workspace_obj.id, user_ids, channel_ids, rng, faker, plugins
        ):
            file_buffer.append(f)
            if len(file_buffer) >= config.batch_size:
                store.insert_files(file_buffer)
                file_buffer = []
        if file_buffer:
            store.insert_files(file_buffer)
    finally:
        store.close()
    gen_seconds = time.perf_counter() - t0

    t1 = time.perf_counter()
    store = SQLiteStore(str(db_path))
    try:
        suffix = ".jsonl.gz" if args.compress else ".jsonl"
        workspace = store.get_workspace(workspace_obj.id)
        if not workspace:
            raise RuntimeError("workspace missing after generation")

        out_workspace_dir = export_dir / workspace_obj.id
        out_workspace_dir.mkdir(parents=True, exist_ok=True)
        dump_json(str(out_workspace_dir / "workspace.json"), {"workspace": workspace})
        dump_json(str(out_workspace_dir / "summary.json"), store.export_summary(workspace_obj.id))

        dump_jsonl(
            str(out_workspace_dir / f"users{suffix}"),
            store.iter_users(workspace_obj.id, chunk_size=2000),
            compress=args.compress,
        )
        dump_jsonl(
            str(out_workspace_dir / f"channels{suffix}"),
            store.iter_channels(workspace_obj.id, chunk_size=2000),
            compress=args.compress,
        )
        dump_jsonl(
            str(out_workspace_dir / f"channel_members{suffix}"),
            store.iter_channel_members(workspace_obj.id, chunk_size=4000),
            compress=args.compress,
        )
        dump_jsonl(
            str(out_workspace_dir / f"messages{suffix}"),
            store.iter_messages(workspace_obj.id, chunk_size=2000),
            compress=args.compress,
        )
        dump_jsonl(
            str(out_workspace_dir / f"files{suffix}"),
            store.iter_files(workspace_obj.id, chunk_size=2000),
            compress=args.compress,
        )
    finally:
        store.close()
    export_seconds = time.perf_counter() - t1

    report = {
        "ok": True,
        "profile": args.profile,
        "config": {
            "workspace": config.workspace_name,
            "seed": config.seed,
            "users": config.users,
            "channels": config.channels,
            "dm_channels": config.dm_channels,
            "mpdm_channels": config.mpdm_channels,
            "messages": config.messages,
            "files": config.files,
            "batch_size": config.batch_size,
            "compress": bool(args.compress),
        },
        "paths": {
            "out_dir": str(out_dir),
            "db": str(db_path),
            "export_dir": str(export_dir),
            "workspace_id": workspace_obj.id,
        },
        "timings_seconds": {"generate": gen_seconds, "export_jsonl": export_seconds},
        "sizes_bytes": {
            "db": db_path.stat().st_size if db_path.exists() else None,
            "export_dir_total": _dir_size_bytes(export_dir),
        },
        "env": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
