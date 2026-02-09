from __future__ import annotations

import csv
import hashlib
import json
import random
import time
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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
from .storage import SCHEMA_VERSION, SQLiteStore, dump_json, dump_jsonl, load_jsonl, validate_db

app = typer.Typer(add_completion=False)

_PKG_VERSION = __import__("slack_workspace_synth").__version__


def _resolve_plugins(modules: list[str] | None) -> PluginRegistry:
    if not modules:
        return PluginRegistry()
    return load_plugins(modules)


def _normalize_scopes(scope: str) -> str:
    return ",".join(part.strip() for part in scope.split(",") if part.strip())


def _make_import_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:9].upper()
    return f"{prefix}{digest}"


def _sanitize_folder_name(name: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in name.strip())
    return clean.strip("-") or "conversation"


def _load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise typer.BadParameter(f"Expected object JSON: {path}")
    return payload


def _load_json_any(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _validate_seed_import_bundle(
    out_dir: Path,
    *,
    zip_path: Path | None,
    messages_written: int,
) -> None:
    required_json = [
        "users.json",
        "channels.json",
        "groups.json",
        "dms.json",
        "mpims.json",
        "import_id_map.json",
        "summary.json",
    ]

    missing = [name for name in required_json if not (out_dir / name).exists()]
    if missing:
        raise ValueError(f"seed-import validation failed: missing {', '.join(missing)}")

    for name in required_json:
        path = out_dir / name
        try:
            _load_json_any(str(path))
        except Exception as exc:
            raise ValueError(f"seed-import validation failed: invalid JSON {path}: {exc}") from exc

    if messages_written > 0:
        conversation_files = [p for p in out_dir.rglob("*.json") if p.parent != out_dir]
        if not conversation_files:
            raise ValueError(
                "seed-import validation failed: expected at least one conversation/day json file"
            )

    if not zip_path:
        return

    if not zip_path.exists():
        raise ValueError(f"seed-import validation failed: zip not found: {zip_path}")

    with zipfile.ZipFile(zip_path) as handle:
        names = set(handle.namelist())

    missing_in_zip = [name for name in required_json if name not in names]
    if missing_in_zip:
        raise ValueError(f"seed-import validation failed: zip missing {', '.join(missing_in_zip)}")

    if messages_written > 0 and not any(name.endswith(".json") and "/" in name for name in names):
        raise ValueError(
            "seed-import validation failed: zip missing conversation/day json under subfolders"
        )


_SLACK_TRANSIENT_ERRORS = {"ratelimited", "timeout", "internal_error", "service_unavailable"}


def _slack_sleep_with_backoff(attempt: int, *, max_backoff_seconds: int) -> None:
    if max_backoff_seconds <= 0:
        return
    base = 0.5 * (2**attempt)
    # Jitter in [0.5, 1.0] keeps concurrent seeders from syncing retries.
    delay = min(float(max_backoff_seconds), base) * (0.5 + 0.5 * random.random())
    time.sleep(delay)


def _slack_request_json(
    token: str,
    request: Request,
    *,
    max_retries: int,
    timeout_seconds: int,
    max_backoff_seconds: int,
) -> dict[str, Any]:
    attempts = max(0, max_retries) + 1
    last_exc: Exception | None = None

    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                data = response.read().decode("utf-8")
        except HTTPError as exc:
            last_exc = exc
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""

            if exc.code == 429 and attempt < attempts - 1:
                retry_after_raw = exc.headers.get("Retry-After", "1")
                try:
                    retry_after = max(0, int(retry_after_raw))
                except ValueError:
                    retry_after = 1
                time.sleep(retry_after)
                continue

            if exc.code in {408} or 500 <= exc.code <= 599:
                if attempt < attempts - 1:
                    _slack_sleep_with_backoff(attempt, max_backoff_seconds=max_backoff_seconds)
                    continue

            snippet = body[:200] if body else str(exc)[:200]
            raise RuntimeError(f"Slack HTTP {exc.code} for {request.full_url}: {snippet}") from exc
        except URLError as exc:
            last_exc = exc
            if attempt < attempts - 1:
                _slack_sleep_with_backoff(attempt, max_backoff_seconds=max_backoff_seconds)
                continue
            raise RuntimeError(f"Slack request failed for {request.full_url}: {exc}") from exc

        parsed = json.loads(data)
        if not isinstance(parsed, dict):
            raise RuntimeError(f"Unexpected Slack response: {data[:200]}")

        if (
            parsed.get("ok") is False
            and str(parsed.get("error") or "") in _SLACK_TRANSIENT_ERRORS
            and attempt < attempts - 1
        ):
            _slack_sleep_with_backoff(attempt, max_backoff_seconds=max_backoff_seconds)
            continue

        return parsed

    raise RuntimeError(f"Slack request failed after {attempts} attempts: {last_exc}")


def _slack_post_json(
    token: str,
    url: str,
    payload: dict[str, Any],
    *,
    max_retries: int = 6,
    timeout_seconds: int = 30,
    max_backoff_seconds: int = 30,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method="POST")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json; charset=utf-8")
    return _slack_request_json(
        token,
        request,
        max_retries=max_retries,
        timeout_seconds=timeout_seconds,
        max_backoff_seconds=max_backoff_seconds,
    )


def _slack_get_json(
    token: str,
    url: str,
    params: dict[str, str],
    *,
    max_retries: int = 6,
    timeout_seconds: int = 30,
    max_backoff_seconds: int = 30,
) -> dict[str, Any]:
    query = urlencode(params)
    request = Request(f"{url}?{query}", method="GET")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    return _slack_request_json(
        token,
        request,
        max_retries=max_retries,
        timeout_seconds=timeout_seconds,
        max_backoff_seconds=max_backoff_seconds,
    )


def _load_slack_channels_payload(path: str) -> list[dict[str, Any]]:
    payload = _load_json_any(path)
    if isinstance(payload, dict) and isinstance(payload.get("channels"), list):
        return [item for item in payload["channels"] if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [item for item in payload["data"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    raise typer.BadParameter("Unrecognized slack-channels payload.")


def _collect_slack_channels(
    *,
    slack_token: str | None,
    slack_channels: str | None,
    include_private: bool,
    base_url: str,
    team_id: str | None,
    limit: int | None,
    slack_max_retries: int,
    slack_timeout_seconds: int,
    slack_max_backoff_seconds: int,
) -> list[dict[str, Any]]:
    if slack_channels:
        return _load_slack_channels_payload(slack_channels)
    if not slack_token:
        raise typer.BadParameter("Provide --slack-token or --slack-channels.")
    types = ["public_channel"]
    if include_private:
        types.append("private_channel")
    cursor: str | None = None
    fetched = 0
    entries: list[dict[str, Any]] = []
    while True:
        params = {"limit": "200", "types": ",".join(types)}
        if cursor:
            params["cursor"] = cursor
        if team_id:
            params["team_id"] = team_id
        response = _slack_get_json(
            slack_token,
            f"{base_url}/conversations.list",
            params,
            max_retries=slack_max_retries,
            timeout_seconds=slack_timeout_seconds,
            max_backoff_seconds=slack_max_backoff_seconds,
        )
        if not response.get("ok"):
            raise RuntimeError(f"conversations.list failed: {response}")
        batch = response.get("channels")
        if isinstance(batch, list):
            entries.extend([item for item in batch if isinstance(item, dict)])
            fetched += len(batch)
        cursor = None
        metadata = response.get("response_metadata")
        if isinstance(metadata, dict):
            cursor = str(metadata.get("next_cursor") or "") or None
        if not cursor:
            break
        if limit is not None and fetched >= limit:
            break
    return entries


def _generate_channel_map(
    *,
    channels: list[dict[str, object]],
    include_private: bool,
    slack_token: str | None,
    slack_channels: str | None,
    create_missing: bool,
    base_url: str,
    team_id: str | None,
    limit: int | None,
    slack_max_retries: int,
    slack_timeout_seconds: int,
    slack_max_backoff_seconds: int,
) -> tuple[dict[str, str], list[dict[str, object]]]:
    slack_entries = _collect_slack_channels(
        slack_token=slack_token,
        slack_channels=slack_channels,
        include_private=include_private,
        base_url=base_url,
        team_id=team_id,
        limit=limit,
        slack_max_retries=slack_max_retries,
        slack_timeout_seconds=slack_timeout_seconds,
        slack_max_backoff_seconds=slack_max_backoff_seconds,
    )
    slack_by_name = {
        str(entry.get("name")): entry
        for entry in slack_entries
        if entry.get("id") and entry.get("name")
    }

    mapping: dict[str, str] = {}
    missing: list[dict[str, object]] = []
    for channel in channels:
        name = str(channel["name"])
        synthetic_id = str(channel["id"])
        existing = slack_by_name.get(name)
        if existing:
            mapping[synthetic_id] = str(existing["id"])
        else:
            missing.append(channel)

    if missing and create_missing:
        if not slack_token:
            raise typer.BadParameter("create-missing requires --slack-token.")
        for channel in missing:
            name = str(channel["name"])
            payload = {"name": name, "is_private": bool(channel["is_private"])}
            response = _slack_post_json(
                slack_token,
                f"{base_url}/conversations.create",
                payload,
                max_retries=slack_max_retries,
                timeout_seconds=slack_timeout_seconds,
                max_backoff_seconds=slack_max_backoff_seconds,
            )
            if not response.get("ok"):
                raise RuntimeError(f"conversations.create failed: {response}")
            channel_id = str(response["channel"]["id"])
            mapping[str(channel["id"])] = channel_id

    return mapping, missing


def _load_token_map(path: str) -> dict[str, dict[str, str]]:
    payload = _load_json(path)
    entries: dict[str, dict[str, str]] = {}

    if "users" in payload and isinstance(payload["users"], list):
        for item in payload["users"]:
            if not isinstance(item, dict):
                continue
            synthetic_id = str(
                item.get("synthetic_user_id") or item.get("user_id") or item.get("id") or ""
            )
            slack_user_id = str(item.get("slack_user_id") or item.get("slack_id") or "")
            token = str(item.get("access_token") or item.get("token") or "")
            if synthetic_id and slack_user_id and token:
                entries[synthetic_id] = {
                    "slack_user_id": slack_user_id,
                    "access_token": token,
                }
        return entries

    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        slack_user_id = str(value.get("slack_user_id") or value.get("slack_id") or "")
        token = str(value.get("access_token") or value.get("token") or "")
        if key and slack_user_id and token:
            entries[str(key)] = {
                "slack_user_id": slack_user_id,
                "access_token": token,
            }
    return entries


def _load_user_id_map(tokens_path: str | None, user_map_path: str | None) -> dict[str, str]:
    if user_map_path:
        payload = _load_json(user_map_path)
        if isinstance(payload.get("users"), list):
            result: dict[str, str] = {}
            for item in payload["users"]:
                if not isinstance(item, dict):
                    continue
                synthetic_id = str(
                    item.get("synthetic_user_id") or item.get("user_id") or item.get("id") or ""
                )
                slack_user_id = str(item.get("slack_user_id") or item.get("slack_id") or "")
                if synthetic_id and slack_user_id:
                    result[synthetic_id] = slack_user_id
            return result
        if isinstance(payload, dict):
            result = {}
            for key, value in payload.items():
                if not isinstance(value, str):
                    continue
                result[str(key)] = value
            if result:
                return result
        raise typer.BadParameter("Unrecognized user-map payload.")
    if tokens_path:
        token_map = _load_token_map(tokens_path)
        return {key: entry["slack_user_id"] for key, entry in token_map.items()}
    return {}


def _load_existing_tokens(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = _load_json(str(path))
    entries: dict[str, dict[str, Any]] = {}

    if isinstance(payload.get("users"), list):
        for item in payload["users"]:
            if not isinstance(item, dict):
                continue
            synthetic_id = str(
                item.get("synthetic_user_id") or item.get("user_id") or item.get("id") or ""
            )
            if not synthetic_id:
                continue
            entries[synthetic_id] = dict(item)
        return entries

    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        if "access_token" not in value and "token" not in value:
            continue
        entries[str(key)] = dict(value)
        entries[str(key)].setdefault("synthetic_user_id", str(key))

    return entries


def _write_tokens_file(path: Path, tokens: dict[str, dict[str, Any]], meta: dict[str, Any]) -> None:
    users_list = [dict(entry) for entry in tokens.values()]
    users_list.sort(key=lambda item: str(item.get("synthetic_user_id", "")))
    payload = {"meta": meta, "users": users_list}
    dump_json(str(path), payload)


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

    for label, value in (
        ("users", resolved_users),
        ("channels", resolved_channels),
        ("dm-channels", resolved_dm_channels),
        ("mpdm-channels", resolved_mpdm_channels),
        ("messages", resolved_messages),
        ("files", resolved_files),
    ):
        if value < 0:
            raise typer.BadParameter(f"{label} must be >= 0")
    if batch_size <= 0:
        raise typer.BadParameter("batch-size must be >= 1")
    if resolved_channel_members_min <= 0 or resolved_channel_members_max <= 0:
        raise typer.BadParameter("channel member bounds must be >= 1")
    if resolved_channel_members_min > resolved_channel_members_max:
        raise typer.BadParameter("channel-members-min must be <= channel-members-max")
    if resolved_mpdm_members_min <= 0 or resolved_mpdm_members_max <= 0:
        raise typer.BadParameter("mpdm member bounds must be >= 1")
    if resolved_mpdm_members_min > resolved_mpdm_members_max:
        raise typer.BadParameter("mpdm-members-min must be <= mpdm-members-max")
    if resolved_users == 0 and (
        resolved_dm_channels > 0
        or resolved_mpdm_channels > 0
        or resolved_messages > 0
        or resolved_files > 0
    ):
        raise typer.BadParameter("users must be > 0 when generating DMs/MPDMs, messages, or files.")
    total_channels = resolved_channels + resolved_dm_channels + resolved_mpdm_channels
    if total_channels == 0 and (resolved_messages > 0 or resolved_files > 0):
        raise typer.BadParameter(
            "At least one channel (public/private/im/mpim) is required for messages/files."
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
                "schema_version": SCHEMA_VERSION,
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
    mode: str = typer.Option(
        "fresh",
        help=(
            "Import mode: fresh (new DB/workspace) or append "
            "(dedupe into existing DB by primary key)"
        ),
    ),
) -> None:
    """Import JSONL export directory into SQLite."""
    mode = mode.strip().lower()
    if mode not in {"fresh", "append"}:
        raise typer.BadParameter("mode must be one of: fresh, append")
    if mode == "append" and force:
        raise typer.BadParameter("Cannot use --force with --mode append.")

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
        ignore = mode == "append"
        existing_workspace = store.get_workspace(workspace_obj.id)
        if existing_workspace:
            # In append mode, refuse to merge different workspaces into the same id.
            existing_name = str(existing_workspace.get("name") or "")
            if existing_name and existing_name != workspace_obj.name:
                raise typer.BadParameter(
                    "Workspace id already exists with a different name; "
                    "use a fresh DB or choose a different export/workspace-id."
                )
        store.insert_workspace(workspace_obj, ignore=ignore)
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
                    store.insert_users(buffer, ignore=ignore)
                    buffer = []
            if buffer:
                store.insert_users(buffer, ignore=ignore)

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
                    store.insert_channels(buffer, ignore=ignore)
                    buffer = []
            if buffer:
                store.insert_channels(buffer, ignore=ignore)

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
                    store.insert_messages(buffer, ignore=ignore)
                    buffer = []
            if buffer:
                store.insert_messages(buffer, ignore=ignore)

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
                    store.insert_files(buffer, ignore=ignore)
                    buffer = []
            if buffer:
                store.insert_files(buffer, ignore=ignore)

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
    validate_db_before_start: bool = typer.Option(
        False, "--validate-db", help="Validate DB compatibility before starting server"
    ),
    require_workspace: bool = typer.Option(
        False, help="Fail validation when DB contains no workspaces"
    ),
) -> None:
    """Run the FastAPI server."""
    import os

    import uvicorn

    if validate_db_before_start:
        report = validate_db(
            db, workspace_id=None, require_workspace=require_workspace, tool_version=_PKG_VERSION
        )
        if not report.get("ok"):
            typer.echo(json.dumps(report, indent=2, ensure_ascii=False))
            raise typer.Exit(code=1)

    os.environ["SWSYNTH_DB"] = db
    uvicorn.run(
        "slack_workspace_synth.api:app",
        host=host,
        port=port,
        reload=False,
        factory=False,
    )


@app.command("validate-db")
def validate_db_cmd(
    db: str = typer.Option("./data/workspace.db", help="SQLite DB path"),
    workspace_id: str | None = typer.Option(
        None, help="Workspace id (defaults to most recently created workspace)"
    ),
    require_workspace: bool = typer.Option(
        False, help="Fail validation when DB contains no workspaces"
    ),
    out: str | None = typer.Option(None, help="Write validation report JSON path"),
    quiet: bool = typer.Option(False, help="Do not print report JSON to stdout"),
) -> None:
    """Validate that a SQLite DB appears compatible with slack-workspace-synth."""
    report = validate_db(
        db,
        workspace_id=workspace_id,
        require_workspace=require_workspace,
        tool_version=_PKG_VERSION,
    )
    if out:
        dump_json(out, report)
    if not quiet:
        typer.echo(json.dumps(report, indent=2, ensure_ascii=False))
    if not report.get("ok"):
        raise typer.Exit(code=1)


@app.command("export-jsonl")
def export_jsonl(
    db: str = typer.Option("./data/workspace.db", help="SQLite DB path"),
    out: str = typer.Option("./export", help="Output directory"),
    workspace_id: str | None = typer.Option(
        None, help="Workspace id (defaults to most recently created workspace)"
    ),
    compress: bool = typer.Option(False, help="Gzip JSONL outputs"),
    chunk_size: int = typer.Option(2000, help="SQLite fetch chunk size"),
    messages_after_ts: int | None = typer.Option(
        None,
        "--messages-after-ts",
        help="Only export messages with ts > this UNIX timestamp (seconds).",
    ),
    files_after_ts: int | None = typer.Option(
        None,
        "--files-after-ts",
        help="Only export files with created_ts > this UNIX timestamp (seconds).",
    ),
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
            store.iter_messages(
                resolved_workspace_id,
                chunk_size=chunk_size,
                after_ts=messages_after_ts,
            ),
            compress=compress,
        )
        dump_jsonl(
            str(out_dir / f"files{suffix}"),
            store.iter_files(
                resolved_workspace_id,
                chunk_size=chunk_size,
                after_ts=files_after_ts,
            ),
            compress=compress,
        )

        typer.echo(f"Wrote export to: {out_dir}")
    finally:
        store.close()


@app.command("seed-import")
def seed_import(
    db: str = typer.Option("./data/workspace.db", help="SQLite DB path"),
    out: str = typer.Option("./import_bundle", help="Output directory"),
    workspace_id: str | None = typer.Option(
        None, help="Workspace id (defaults to most recently created workspace)"
    ),
    include_private: bool = typer.Option(True, help="Include private channels"),
    include_dms: bool = typer.Option(True, help="Include 1:1 DMs"),
    include_mpims: bool = typer.Option(True, help="Include multi-party DMs"),
    include_bots: bool = typer.Option(False, help="Include bot users"),
    limit_messages: int | None = typer.Option(None, help="Limit number of messages"),
    zip_out: str | None = typer.Option(None, "--zip-out", help="Write a .zip bundle to this path"),
    zip_bundle: bool = typer.Option(
        False, "--zip", help="Also write a .zip bundle next to the output directory"
    ),
    validate: bool = typer.Option(
        False,
        "--validate",
        help="Validate required export artifacts exist (and validate zip when used).",
    ),
) -> None:
    """Generate a Slack export-style import bundle from the SQLite DB."""
    store = SQLiteStore(db)
    try:
        resolved_workspace_id = workspace_id or store.latest_workspace_id()
        if not resolved_workspace_id:
            raise typer.BadParameter("No workspaces found in DB; generate one first.")

        workspace = store.get_workspace(resolved_workspace_id)
        if not workspace:
            raise typer.BadParameter(f"Workspace not found: {resolved_workspace_id}")

        out_dir = Path(out)
        out_dir.mkdir(parents=True, exist_ok=True)

        users = []
        user_id_map: dict[str, str] = {}
        for row in store.iter_users(resolved_workspace_id, chunk_size=1000):
            if not include_bots and row["is_bot"]:
                continue
            synthetic_id = str(row["id"])
            import_id = _make_import_id("U", synthetic_id)
            user_id_map[synthetic_id] = import_id
            users.append(
                {
                    "id": import_id,
                    "name": str(row["name"]).lower().replace(" ", "."),
                    "real_name": str(row["name"]),
                    "profile": {
                        "real_name": str(row["name"]),
                        "display_name": str(row["name"]),
                        "email": str(row["email"]),
                        "title": str(row["title"]),
                    },
                    "is_bot": bool(row["is_bot"]),
                    "deleted": False,
                }
            )

        if not users:
            raise typer.BadParameter("No users available for import bundle.")

        channel_rows = list(store.iter_channels(resolved_workspace_id, chunk_size=1000))
        channel_members: dict[str, list[str]] = {}
        for member in store.iter_channel_members(resolved_workspace_id, chunk_size=2000):
            channel_members.setdefault(str(member["channel_id"]), []).append(
                user_id_map.get(str(member["user_id"]), str(member["user_id"]))
            )

        channel_id_map: dict[str, str] = {}
        channel_folder_map: dict[str, str] = {}
        channels_payload: list[dict[str, Any]] = []
        groups_payload: list[dict[str, Any]] = []
        dms_payload: list[dict[str, Any]] = []
        mpims_payload: list[dict[str, Any]] = []

        for channel in channel_rows:
            channel_type = str(channel["channel_type"])
            if channel_type == "private" and not include_private:
                continue
            if channel_type == "im" and not include_dms:
                continue
            if channel_type == "mpim" and not include_mpims:
                continue

            synthetic_id = str(channel["id"])
            if channel_type == "public":
                import_id = _make_import_id("C", synthetic_id)
            elif channel_type == "private":
                import_id = _make_import_id("G", synthetic_id)
            elif channel_type == "im":
                import_id = _make_import_id("D", synthetic_id)
            else:
                import_id = _make_import_id("G", synthetic_id)

            channel_id_map[synthetic_id] = import_id
            name = str(channel["name"])
            folder_name = _sanitize_folder_name(
                name if channel_type in ("public", "private") else import_id
            )
            channel_folder_map[synthetic_id] = folder_name

            members = channel_members.get(synthetic_id, [])
            creator = members[0] if members else next(iter(user_id_map.values()))
            created_at = int(cast(int, workspace["created_at"]))
            topic_value = str(channel["topic"])
            payload = {
                "id": import_id,
                "name": name,
                "created": created_at,
                "creator": creator,
                "members": members,
                "topic": {"value": topic_value, "creator": creator, "last_set": created_at},
                "purpose": {"value": topic_value, "creator": creator, "last_set": created_at},
                "is_private": bool(channel["is_private"]),
            }

            if channel_type == "public":
                channels_payload.append(payload)
            elif channel_type == "private":
                groups_payload.append(payload)
            elif channel_type == "im":
                dms_payload.append(
                    {
                        "id": import_id,
                        "created": created_at,
                        "members": members,
                    }
                )
            else:
                mpims_payload.append(
                    {
                        "id": import_id,
                        "created": created_at,
                        "members": members,
                    }
                )

        dump_json(str(out_dir / "users.json"), users)
        dump_json(str(out_dir / "channels.json"), channels_payload)
        dump_json(str(out_dir / "groups.json"), groups_payload)
        dump_json(str(out_dir / "dms.json"), dms_payload)
        dump_json(str(out_dir / "mpims.json"), mpims_payload)
        dump_json(
            str(out_dir / "import_id_map.json"),
            {"users": user_id_map, "channels": channel_id_map},
        )

        messages_written = 0
        current_channel: str | None = None
        current_date: str | None = None
        buffer: list[dict[str, Any]] = []

        def _flush_buffer() -> None:
            nonlocal buffer
            if not buffer or current_channel is None or current_date is None:
                buffer = []
                return
            folder = out_dir / channel_folder_map[current_channel]
            folder.mkdir(parents=True, exist_ok=True)
            file_path = folder / f"{current_date}.json"
            dump_json(str(file_path), buffer)
            buffer = []

        for message in store.iter_messages_for_import(resolved_workspace_id, chunk_size=2000):
            if limit_messages is not None and messages_written >= limit_messages:
                break
            synthetic_channel_id = str(message["channel_id"])
            if synthetic_channel_id not in channel_id_map:
                continue
            synthetic_user_id = str(message["user_id"])
            user_import_id = user_id_map.get(synthetic_user_id)
            if not user_import_id:
                continue

            ts_value = int(cast(int, message["ts"]))
            msg_date = datetime.fromtimestamp(ts_value, tz=UTC).strftime("%Y-%m-%d")
            if current_channel != synthetic_channel_id or current_date != msg_date:
                _flush_buffer()
                current_channel = synthetic_channel_id
                current_date = msg_date

            msg_payload: dict[str, Any] = {
                "type": "message",
                "user": user_import_id,
                "text": str(message["text"]),
                "ts": f"{ts_value}.000000",
            }
            if message.get("thread_ts") is not None:
                thread_ts_value = int(cast(int, message["thread_ts"]))
                msg_payload["thread_ts"] = f"{thread_ts_value}.000000"
            reactions_raw = message.get("reactions_json")
            if isinstance(reactions_raw, str):
                try:
                    reactions_payload = json.loads(reactions_raw)
                    if isinstance(reactions_payload, dict):
                        msg_payload["reactions"] = [
                            {"name": name, "count": int(count), "users": []}
                            for name, count in reactions_payload.items()
                        ]
                except json.JSONDecodeError:
                    pass
            buffer.append(msg_payload)
            messages_written += 1

        _flush_buffer()

        dump_json(
            str(out_dir / "summary.json"),
            {
                "workspace_id": resolved_workspace_id,
                "workspace_name": str(workspace["name"]),
                "users": len(users),
                "channels": len(channels_payload),
                "groups": len(groups_payload),
                "dms": len(dms_payload),
                "mpims": len(mpims_payload),
                "messages": messages_written,
            },
        )

        resolved_zip_path: Path | None = None
        if zip_out:
            resolved_zip_path = Path(zip_out)
        elif zip_bundle:
            resolved_zip_path = Path(f"{out_dir}.zip")

        if resolved_zip_path:
            if resolved_zip_path.exists():
                raise typer.BadParameter(f"Zip already exists: {resolved_zip_path}")
            resolved_zip_path.parent.mkdir(parents=True, exist_ok=True)

            files = [
                p
                for p in out_dir.rglob("*")
                if p.is_file() and p.resolve() != resolved_zip_path.resolve()
            ]
            files.sort(key=lambda item: item.relative_to(out_dir).as_posix())

            with zipfile.ZipFile(
                resolved_zip_path, mode="w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                for path in files:
                    archive.write(path, arcname=path.relative_to(out_dir).as_posix())

            typer.echo(f"Wrote import bundle zip to: {resolved_zip_path}")

        if validate:
            try:
                _validate_seed_import_bundle(
                    out_dir,
                    zip_path=resolved_zip_path,
                    messages_written=messages_written,
                )
            except ValueError as exc:
                typer.echo(str(exc), err=True)
                raise typer.Exit(code=1) from exc

        typer.echo(f"Wrote import bundle to: {out_dir}")
    finally:
        store.close()


@app.command("oauth-pack")
def oauth_pack(
    db: str = typer.Option("./data/workspace.db", help="SQLite DB path"),
    out: str = typer.Option("./oauth", help="Output directory"),
    workspace_id: str | None = typer.Option(
        None, help="Workspace id (defaults to most recently created workspace)"
    ),
    client_id: str = typer.Option(..., help="Slack app client ID"),
    redirect_uri: str = typer.Option("http://localhost:8080/callback", help="OAuth redirect URI"),
    scope: str = typer.Option("chat:write", help="Bot scopes (comma-separated)"),
    user_scope: str = typer.Option(
        "chat:write,channels:read,groups:read,im:read,mpim:read",
        help="User scopes (comma-separated)",
    ),
    limit: int | None = typer.Option(None, help="Limit number of users"),
    include_bots: bool = typer.Option(False, help="Include bot users from the DB"),
    state_seed: str | None = typer.Option(
        None, help="Optional seed to make OAuth state values deterministic"
    ),
) -> None:
    """Generate per-user OAuth URLs for clickops token collection."""
    store = SQLiteStore(db)
    try:
        resolved_workspace_id = workspace_id or store.latest_workspace_id()
        if not resolved_workspace_id:
            raise typer.BadParameter("No workspaces found in DB; generate one first.")

        workspace = store.get_workspace(resolved_workspace_id)
        if not workspace:
            raise typer.BadParameter(f"Workspace not found: {resolved_workspace_id}")

        out_dir = Path(out)
        out_dir.mkdir(parents=True, exist_ok=True)

        normalized_scope = _normalize_scopes(scope)
        normalized_user_scope = _normalize_scopes(user_scope)
        if not normalized_scope and not normalized_user_scope:
            raise typer.BadParameter("At least one of --scope or --user-scope must be set.")

        def _state_for(user_id: str, email: str) -> str:
            if state_seed is None:
                return uuid.uuid4().hex
            return uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{state_seed}:{resolved_workspace_id}:{user_id}:{email}",
            ).hex

        def _oauth_url(state: str) -> str:
            params: dict[str, str] = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "state": state,
            }
            if normalized_scope:
                params["scope"] = normalized_scope
            if normalized_user_scope:
                params["user_scope"] = normalized_user_scope
            return f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"

        rows: list[dict[str, str]] = []
        state_map: dict[str, object] = {}
        for row in store.iter_users(resolved_workspace_id, chunk_size=1000):
            if not include_bots and row["is_bot"]:
                continue
            state = _state_for(str(row["id"]), str(row["email"]))
            oauth_url = _oauth_url(state)
            rows.append(
                {
                    "user_id": str(row["id"]),
                    "email": str(row["email"]),
                    "name": str(row["name"]),
                    "state": state,
                    "oauth_url": oauth_url,
                }
            )
            state_map[state] = {
                "user_id": str(row["id"]),
                "email": str(row["email"]),
                "name": str(row["name"]),
            }
            if limit is not None and len(rows) >= limit:
                break

        if not rows:
            raise typer.BadParameter("No users available to build OAuth pack.")

        csv_path = out_dir / "oauth_urls.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["user_id", "email", "name", "state", "oauth_url"],
            )
            writer.writeheader()
            writer.writerows(rows)

        dump_json(str(out_dir / "state_map.json"), state_map)
        dump_json(
            str(out_dir / "summary.json"),
            {
                "workspace_id": resolved_workspace_id,
                "workspace_name": str(workspace["name"]),
                "user_count": len(rows),
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": normalized_scope,
                "user_scope": normalized_user_scope,
                "include_bots": include_bots,
                "limit": limit,
            },
        )

        typer.echo(f"Wrote OAuth pack to: {out_dir}")
    finally:
        store.close()


@app.command("seed-live")
def seed_live(
    db: str = typer.Option("./data/workspace.db", help="SQLite DB path"),
    workspace_id: str | None = typer.Option(
        None, help="Workspace id (defaults to most recently created workspace)"
    ),
    tokens: str = typer.Option(..., help="JSON file with per-user tokens"),
    channel_map: str | None = typer.Option(
        None, help="JSON map of synthetic channel id -> Slack channel id"
    ),
    slack_token: str | None = typer.Option(
        None, help="Slack token (required if channel map not provided)"
    ),
    slack_channels: str | None = typer.Option(
        None, help="JSON file of Slack channels (offline mapping)"
    ),
    include_private: bool = typer.Option(True, help="Include private channels in mapping"),
    create_missing: bool = typer.Option(False, help="Create missing channels via Slack API"),
    team_id: str | None = typer.Option(None, help="Enterprise Grid team/workspace id"),
    limit_channels: int | None = typer.Option(None, help="Limit Slack channels to fetch"),
    report: str | None = typer.Option(None, help="Write summary report JSON path"),
    limit_messages: int | None = typer.Option(None, help="Limit number of messages to post"),
    dry_run: bool = typer.Option(True, help="Do not call Slack APIs"),
    base_url: str = typer.Option("https://slack.com/api", help="Slack Web API base"),
    slack_max_retries: int = typer.Option(6, help="Max retries for Slack API calls"),
    slack_timeout_seconds: int = typer.Option(30, help="Slack API request timeout (seconds)"),
    slack_max_backoff_seconds: int = typer.Option(30, help="Max retry backoff delay (seconds)"),
    min_delay_ms: int = typer.Option(200, help="Delay between posts in ms"),
    continue_on_error: bool = typer.Option(True, help="Continue on Slack errors"),
) -> None:
    """Post messages to Slack as users using collected user tokens."""
    store = SQLiteStore(db)
    try:
        resolved_workspace_id = workspace_id or store.latest_workspace_id()
        if not resolved_workspace_id:
            raise typer.BadParameter("No workspaces found in DB; generate one first.")

        token_map = _load_token_map(tokens)
        if not token_map:
            raise typer.BadParameter("No usable tokens found in tokens file.")

        # Public/private channel mapping. In dry-run we guarantee zero Slack API calls.
        channel_id_map: dict[str, str] = {}
        channel_map_coverage: dict[str, object] = {
            "source": None,
            "channels_total": 0,
            "channels_mapped": 0,
            "channels_missing": 0,
            "missing_examples": [],
        }

        channels_for_map = [
            row
            for row in store.iter_channels(resolved_workspace_id, chunk_size=1000)
            if str(row["channel_type"]) in ("public", "private")
        ]
        if not include_private:
            channels_for_map = [
                row for row in channels_for_map if str(row["channel_type"]) == "public"
            ]

        if channel_map:
            channel_map_payload = _load_json(channel_map)
            if not isinstance(channel_map_payload, dict):
                raise typer.BadParameter(
                    "channel-map must be a JSON object mapping synthetic channel id -> "
                    "Slack channel id."
                )
            channel_id_map = {
                str(key): str(value) for key, value in channel_map_payload.items() if value
            }
            channel_map_coverage["source"] = "channel_map"
        elif channels_for_map:
            if dry_run:
                if create_missing:
                    raise typer.BadParameter("--create-missing is not allowed with --dry-run.")
                if not slack_channels:
                    raise typer.BadParameter(
                        "In --dry-run, provide --channel-map or --slack-channels (offline) "
                        "to avoid Slack API calls."
                    )
                channel_id_map, _missing = _generate_channel_map(
                    channels=channels_for_map,
                    include_private=include_private,
                    slack_token=None,
                    slack_channels=slack_channels,
                    create_missing=False,
                    base_url=base_url,
                    team_id=team_id,
                    limit=limit_channels,
                    slack_max_retries=slack_max_retries,
                    slack_timeout_seconds=slack_timeout_seconds,
                    slack_max_backoff_seconds=slack_max_backoff_seconds,
                )
                channel_map_coverage["source"] = "slack_channels"
            else:
                channel_id_map, _missing = _generate_channel_map(
                    channels=channels_for_map,
                    include_private=include_private,
                    slack_token=slack_token,
                    slack_channels=slack_channels,
                    create_missing=create_missing,
                    base_url=base_url,
                    team_id=team_id,
                    limit=limit_channels,
                    slack_max_retries=slack_max_retries,
                    slack_timeout_seconds=slack_timeout_seconds,
                    slack_max_backoff_seconds=slack_max_backoff_seconds,
                )
                channel_map_coverage["source"] = (
                    "slack_api" if slack_token and not slack_channels else "slack_channels"
                )
                if _missing and not create_missing:
                    missing_names = ", ".join(str(ch["name"]) for ch in _missing[:10])
                    raise typer.BadParameter(
                        f"Missing {len(_missing)} channels in Slack (e.g. {missing_names}). "
                        "Create them or pass --create-missing."
                    )

        if channels_for_map:
            missing_channels = [
                ch for ch in channels_for_map if str(ch["id"]) not in channel_id_map
            ]
            channel_map_coverage["channels_total"] = len(channels_for_map)
            channel_map_coverage["channels_mapped"] = len(channel_id_map)
            channel_map_coverage["channels_missing"] = len(missing_channels)
            channel_map_coverage["missing_examples"] = [
                str(ch["name"]) for ch in missing_channels[:10]
            ]

        channels = {
            str(row["id"]): {
                "channel_type": str(row["channel_type"]),
                "name": str(row["name"]),
            }
            for row in store.iter_channels(resolved_workspace_id, chunk_size=1000)
        }

        channel_members: dict[str, list[str]] = {}
        for member in store.iter_channel_members(resolved_workspace_id, chunk_size=2000):
            channel_members.setdefault(str(member["channel_id"]), []).append(str(member["user_id"]))

        dm_cache: dict[str, str] = {}
        skip_reasons: dict[str, int] = {}
        planned = 0
        posted = 0
        skipped_missing_user = 0
        skipped_missing_channel = 0
        skipped_missing_members = 0
        skipped_requires_slack = 0
        errors = 0
        channel_type_counts = store.channel_type_counts(resolved_workspace_id)

        def _resolve_dm_channel_id(synthetic_channel_id: str, author_token: str) -> str | None:
            if synthetic_channel_id in dm_cache:
                return dm_cache[synthetic_channel_id]
            members = channel_members.get(synthetic_channel_id, [])
            slack_users = [
                token_map[user_id]["slack_user_id"] for user_id in members if user_id in token_map
            ]
            if len(slack_users) < 2:
                return None
            payload = {"users": ",".join(sorted(set(slack_users)))}
            response = _slack_post_json(
                author_token,
                f"{base_url}/conversations.open",
                payload,
                max_retries=slack_max_retries,
                timeout_seconds=slack_timeout_seconds,
                max_backoff_seconds=slack_max_backoff_seconds,
            )
            if not response.get("ok"):
                raise RuntimeError(f"conversations.open failed: {response}")
            channel_id = str(response["channel"]["id"])
            dm_cache[synthetic_channel_id] = channel_id
            return channel_id

        delay = max(0, min_delay_ms) / 1000.0
        for message in store.iter_messages_chronological(resolved_workspace_id, chunk_size=2000):
            if limit_messages is not None and planned >= limit_messages:
                break
            synthetic_user_id = str(message["user_id"])
            token_entry = token_map.get(synthetic_user_id)
            if not token_entry:
                skipped_missing_user += 1
                continue

            synthetic_channel_id = str(message["channel_id"])
            channel_info = channels.get(synthetic_channel_id)
            if not channel_info:
                skipped_missing_channel += 1
                continue

            channel_type = channel_info["channel_type"]
            slack_channel_id: str | None = None
            if channel_type in ("public", "private"):
                slack_channel_id = channel_id_map.get(synthetic_channel_id)
            else:
                if dry_run:
                    skipped_requires_slack += 1
                    skip_reasons["dm_requires_conversations_open"] = (
                        skip_reasons.get("dm_requires_conversations_open", 0) + 1
                    )
                    continue
                slack_channel_id = _resolve_dm_channel_id(
                    synthetic_channel_id, token_entry["access_token"]
                )

            if not slack_channel_id:
                skipped_missing_members += 1
                if channel_type in ("public", "private"):
                    skip_reasons["missing_channel_map"] = (
                        skip_reasons.get("missing_channel_map", 0) + 1
                    )
                else:
                    skip_reasons["dm_open_failed_or_missing_members"] = (
                        skip_reasons.get("dm_open_failed_or_missing_members", 0) + 1
                    )
                continue

            planned += 1
            if dry_run:
                continue

            payload: dict[str, Any] = {
                "channel": slack_channel_id,
                "text": str(message["text"]),
            }
            if message.get("thread_ts") is not None:
                payload["thread_ts"] = str(message["thread_ts"])

            try:
                response = _slack_post_json(
                    token_entry["access_token"],
                    f"{base_url}/chat.postMessage",
                    payload,
                    max_retries=slack_max_retries,
                    timeout_seconds=slack_timeout_seconds,
                    max_backoff_seconds=slack_max_backoff_seconds,
                )
            except RuntimeError:
                errors += 1
                if not continue_on_error:
                    raise
                continue

            if not response.get("ok"):
                errors += 1
                if not continue_on_error:
                    raise RuntimeError(f"chat.postMessage failed: {response}")
                continue

            posted += 1
            if delay:
                time.sleep(delay)

        stats = {
            "workspace_id": resolved_workspace_id,
            "dry_run": dry_run,
            "planned": planned,
            "posted": posted,
            "skipped_missing_user": skipped_missing_user,
            "skipped_missing_channel": skipped_missing_channel,
            "skipped_missing_members": skipped_missing_members,
            "skipped_requires_slack": skipped_requires_slack,
            "errors": errors,
            "channel_map": channel_map_coverage,
            "channel_type_counts": channel_type_counts,
            "skip_reasons": skip_reasons,
        }
        if report:
            dump_json(report, stats)

        typer.echo(f"Seed live complete (planned={planned} posted={posted} dry_run={dry_run}).")
    finally:
        store.close()


@app.command("channel-map")
def channel_map(
    db: str = typer.Option("./data/workspace.db", help="SQLite DB path"),
    out: str = typer.Option("./channel_map.json", help="Output JSON path"),
    workspace_id: str | None = typer.Option(
        None, help="Workspace id (defaults to most recently created workspace)"
    ),
    slack_token: str | None = typer.Option(
        None, help="Slack token (required unless --slack-channels is provided)"
    ),
    slack_channels: str | None = typer.Option(
        None, help="JSON file of Slack channels (offline mapping)"
    ),
    include_private: bool = typer.Option(True, help="Include private channels"),
    create_missing: bool = typer.Option(False, help="Create missing channels via Slack API"),
    base_url: str = typer.Option("https://slack.com/api", help="Slack Web API base"),
    slack_max_retries: int = typer.Option(6, help="Max retries for Slack API calls"),
    slack_timeout_seconds: int = typer.Option(30, help="Slack API request timeout (seconds)"),
    slack_max_backoff_seconds: int = typer.Option(30, help="Max retry backoff delay (seconds)"),
    team_id: str | None = typer.Option(None, help="Enterprise Grid team/workspace id"),
    limit: int | None = typer.Option(None, help="Limit number of Slack channels to fetch"),
) -> None:
    """Generate synthetic channel id -> Slack channel id mapping."""
    store = SQLiteStore(db)
    try:
        resolved_workspace_id = workspace_id or store.latest_workspace_id()
        if not resolved_workspace_id:
            raise typer.BadParameter("No workspaces found in DB; generate one first.")

        channels = [
            row
            for row in store.iter_channels(resolved_workspace_id, chunk_size=1000)
            if str(row["channel_type"]) in ("public", "private")
        ]
        if not include_private:
            channels = [row for row in channels if str(row["channel_type"]) == "public"]

        if not channels:
            raise typer.BadParameter("No public/private channels found to map.")

        mapping, missing = _generate_channel_map(
            channels=channels,
            include_private=include_private,
            slack_token=slack_token,
            slack_channels=slack_channels,
            create_missing=create_missing,
            base_url=base_url,
            team_id=team_id,
            limit=limit,
            slack_max_retries=slack_max_retries,
            slack_timeout_seconds=slack_timeout_seconds,
            slack_max_backoff_seconds=slack_max_backoff_seconds,
        )
        if missing and not create_missing:
            missing_names = ", ".join(str(ch["name"]) for ch in missing[:10])
            raise typer.BadParameter(
                f"Missing {len(missing)} channels in Slack (e.g. {missing_names}). "
                "Create them or pass --create-missing."
            )

        dump_json(out, mapping)
        typer.echo(f"Wrote channel map to: {out}")
    finally:
        store.close()


@app.command("provision-slack")
def provision_slack(
    db: str = typer.Option("./data/workspace.db", help="SQLite DB path"),
    workspace_id: str | None = typer.Option(
        None, help="Workspace id (defaults to most recently created workspace)"
    ),
    slack_token: str | None = typer.Option(None, help="Slack token with channel/admin scopes"),
    out: str = typer.Option("./channel_map.json", help="Output channel map JSON path"),
    slack_channels: str | None = typer.Option(
        None, help="JSON file of Slack channels (offline mapping)"
    ),
    include_private: bool = typer.Option(True, help="Include private channels"),
    create_missing: bool = typer.Option(True, help="Create missing channels via Slack API"),
    allow_missing: bool = typer.Option(False, help="Allow missing channels without failing"),
    invite_members: bool = typer.Option(True, help="Invite members to channels"),
    tokens: str | None = typer.Option(None, help="Tokens JSON for user mapping"),
    user_map: str | None = typer.Option(None, help="User map JSON (synthetic -> Slack id)"),
    invite_batch: int = typer.Option(30, help="Invite batch size"),
    dry_run: bool = typer.Option(False, help="Do not call Slack APIs"),
    report: str | None = typer.Option(None, help="Write provisioning report JSON path"),
    base_url: str = typer.Option("https://slack.com/api", help="Slack Web API base"),
    slack_max_retries: int = typer.Option(6, help="Max retries for Slack API calls"),
    slack_timeout_seconds: int = typer.Option(30, help="Slack API request timeout (seconds)"),
    slack_max_backoff_seconds: int = typer.Option(30, help="Max retry backoff delay (seconds)"),
    team_id: str | None = typer.Option(None, help="Enterprise Grid team/workspace id"),
    limit_channels: int | None = typer.Option(None, help="Limit Slack channels to fetch"),
) -> None:
    """Create missing channels and optionally invite members."""
    store = SQLiteStore(db)
    try:
        resolved_workspace_id = workspace_id or store.latest_workspace_id()
        if not resolved_workspace_id:
            raise typer.BadParameter("No workspaces found in DB; generate one first.")

        channels = [
            row
            for row in store.iter_channels(resolved_workspace_id, chunk_size=1000)
            if str(row["channel_type"]) in ("public", "private")
        ]
        if not include_private:
            channels = [row for row in channels if str(row["channel_type"]) == "public"]

        if not channels:
            raise typer.BadParameter("No public/private channels found to provision.")

        create_effective = create_missing and not dry_run
        if create_effective and not slack_token:
            raise typer.BadParameter("create-missing requires --slack-token.")
        if invite_members and not dry_run and not slack_token:
            raise typer.BadParameter("Inviting members requires --slack-token.")

        mapping, missing = _generate_channel_map(
            channels=channels,
            include_private=include_private,
            slack_token=slack_token,
            slack_channels=slack_channels,
            create_missing=create_effective,
            base_url=base_url,
            team_id=team_id,
            limit=limit_channels,
            slack_max_retries=slack_max_retries,
            slack_timeout_seconds=slack_timeout_seconds,
            slack_max_backoff_seconds=slack_max_backoff_seconds,
        )

        if missing and not create_effective and not allow_missing:
            missing_names = ", ".join(str(ch["name"]) for ch in missing[:10])
            raise typer.BadParameter(
                f"Missing {len(missing)} channels in Slack (e.g. {missing_names}). "
                "Create them or pass --allow-missing/--dry-run."
            )

        dump_json(out, mapping)

        stats = {
            "channels_total": len(channels),
            "channels_mapped": len(mapping),
            "channels_missing": len(missing),
            "invites_planned": 0,
            "invites_sent": 0,
            "invite_errors": 0,
        }

        if invite_members:
            user_id_map = _load_user_id_map(tokens, user_map)
            if not user_id_map:
                raise typer.BadParameter("Provide --tokens or --user-map to invite members.")

            channel_members: dict[str, list[str]] = {}
            for member in store.iter_channel_members(resolved_workspace_id, chunk_size=2000):
                channel_members.setdefault(str(member["channel_id"]), []).append(
                    str(member["user_id"])
                )

            for channel in channels:
                synthetic_channel_id = str(channel["id"])
                slack_channel_id = mapping.get(synthetic_channel_id)
                if not slack_channel_id:
                    continue
                members = [
                    user_id_map[user_id]
                    for user_id in channel_members.get(synthetic_channel_id, [])
                    if user_id in user_id_map
                ]
                if not members:
                    continue
                stats["invites_planned"] += len(members)
                if dry_run:
                    continue
                for idx in range(0, len(members), max(1, invite_batch)):
                    batch = members[idx : idx + max(1, invite_batch)]
                    payload = {"channel": slack_channel_id, "users": ",".join(batch)}
                    try:
                        response = _slack_post_json(
                            str(slack_token),
                            f"{base_url}/conversations.invite",
                            payload,
                            max_retries=slack_max_retries,
                            timeout_seconds=slack_timeout_seconds,
                            max_backoff_seconds=slack_max_backoff_seconds,
                        )
                    except RuntimeError:
                        stats["invite_errors"] += 1
                        continue

                    if not response.get("ok"):
                        error = response.get("error")
                        if error in {"already_in_channel", "cant_invite_self"}:
                            stats["invites_sent"] += len(batch)
                            continue
                        stats["invite_errors"] += 1
                        continue
                    stats["invites_sent"] += len(batch)

        if report:
            dump_json(
                report,
                {
                    "workspace_id": resolved_workspace_id,
                    "dry_run": dry_run,
                    "channel_map_path": out,
                    "stats": stats,
                },
            )

        typer.echo(
            "Provisioned channels "
            "(mapped={mapped} missing={missing}) "
            "invites_sent={invites}".format(
                mapped=stats["channels_mapped"],
                missing=stats["channels_missing"],
                invites=stats["invites_sent"],
            )
        )
    finally:
        store.close()


@app.command("oauth-callback")
def oauth_callback(
    state_map: str = typer.Option(..., help="State map JSON from oauth-pack"),
    out: str = typer.Option("./tokens.json", help="Output tokens JSON"),
    client_id: str = typer.Option(..., help="Slack app client ID"),
    client_secret: str = typer.Option(..., help="Slack app client secret"),
    redirect_uri: str = typer.Option("http://localhost:8080/callback", help="OAuth redirect URI"),
    host: str = typer.Option("127.0.0.1", help="Callback server host"),
    port: int = typer.Option(8080, help="Callback server port"),
    timeout: int | None = typer.Option(
        None, help="Stop server after N seconds (None waits indefinitely)"
    ),
    max_users: int | None = typer.Option(
        None, help="Stop after capturing N users (default: all in state map)"
    ),
    append: bool = typer.Option(True, help="Append to existing tokens file"),
    base_url: str = typer.Option("https://slack.com/api", help="Slack API base URL"),
) -> None:
    """Run a local OAuth callback server and exchange codes for user tokens."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse

    state_map_payload = _load_json(state_map)
    if not state_map_payload:
        raise typer.BadParameter("State map is empty.")

    expected = (
        max_users
        if max_users is not None
        else len(state_map_payload)
        if isinstance(state_map_payload, dict)
        else 0
    )
    if expected <= 0:
        raise typer.BadParameter("No users in state map.")

    tokens_path = Path(out)
    tokens = _load_existing_tokens(tokens_path) if append else {}

    lock = threading.Lock()
    stop_event = threading.Event()
    stats = {"captured": 0, "errors": 0}

    def _write_snapshot() -> None:
        meta = {
            "captured": len(tokens),
            "updated_at": datetime.now(tz=UTC).isoformat(),
            "client_id": client_id,
            "redirect_uri": redirect_uri,
        }
        _write_tokens_file(tokens_path, tokens, meta)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, status: int, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path not in ("/", "/callback"):
                self._send(404, "<h3>Not Found</h3>")
                return
            if parsed.path == "/" and not parsed.query:
                self._send(200, "<h3>OAuth callback server running.</h3>")
                return

            params = parse_qs(parsed.query)
            if "error" in params:
                self._send(400, f"<h3>OAuth error: {params['error'][0]}</h3>")
                return

            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            if not code or not state:
                self._send(400, "<h3>Missing code or state</h3>")
                return

            state_entry = state_map_payload.get(state)
            if not isinstance(state_entry, dict):
                self._send(400, "<h3>Unknown state</h3>")
                return

            synthetic_user_id = str(
                state_entry.get("user_id")
                or state_entry.get("synthetic_user_id")
                or state_entry.get("id")
                or ""
            )
            if not synthetic_user_id:
                self._send(400, "<h3>State missing user_id</h3>")
                return

            with lock:
                if synthetic_user_id in tokens:
                    self._send(200, "<h3>Token already captured.</h3>")
                    return

            payload = {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            }
            response = _slack_post_json(
                token="", url=f"{base_url}/oauth.v2.access", payload=payload
            )
            if not response.get("ok"):
                self._send(400, f"<h3>Slack error: {response.get('error')}</h3>")
                with lock:
                    stats["errors"] += 1
                return

            authed_raw = response.get("authed_user")
            authed_user: dict[str, Any] = authed_raw if isinstance(authed_raw, dict) else {}
            access_token = str(
                authed_user.get("access_token") or response.get("access_token") or ""
            )
            if not access_token:
                self._send(400, "<h3>No user access token returned.</h3>")
                with lock:
                    stats["errors"] += 1
                return

            slack_user_id = str(authed_user.get("id") or response.get("user_id") or "")
            entry = {
                "synthetic_user_id": synthetic_user_id,
                "slack_user_id": slack_user_id,
                "access_token": access_token,
                "refresh_token": authed_user.get("refresh_token"),
                "expires_in": authed_user.get("expires_in"),
                "scope": authed_user.get("scope") or response.get("scope"),
                "token_type": "user",
                "captured_at": datetime.now(tz=UTC).isoformat(),
            }

            with lock:
                tokens[synthetic_user_id] = entry
                stats["captured"] = len(tokens)
                _write_snapshot()

                if stats["captured"] >= expected:
                    stop_event.set()

            self._send(200, "<h3>Token captured. You can close this tab.</h3>")

    server = ThreadingHTTPServer((host, port), Handler)
    server.timeout = 1.0

    typer.echo(
        f"OAuth callback server listening on http://{host}:{port}/callback (expected={expected})"
    )

    start = time.time()
    try:
        while not stop_event.is_set():
            server.handle_request()
            if timeout is not None and (time.time() - start) >= timeout:
                break
    finally:
        server.server_close()

    if tokens:
        _write_snapshot()

    typer.echo(f"Captured {len(tokens)} user tokens. Output: {tokens_path}")


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
