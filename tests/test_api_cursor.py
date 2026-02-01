import random

from faker import Faker
from fastapi.testclient import TestClient

from slack_workspace_synth.api import app
from slack_workspace_synth.generator import (
    GenerationConfig,
    generate_channels,
    generate_files,
    generate_messages,
    generate_users,
    generate_workspace,
)
from slack_workspace_synth.plugins import PluginRegistry
from slack_workspace_synth.storage import SQLiteStore


def _seed_db(tmp_path) -> tuple[str, str]:
    db_path = tmp_path / "demo.db"
    config = GenerationConfig(
        workspace_name="Test",
        users=5,
        channels=3,
        messages=10,
        files=6,
        seed=123,
        batch_size=50,
    )
    plugins = PluginRegistry()

    store = SQLiteStore(str(db_path))
    try:
        workspace = generate_workspace(config, plugins)
        store.insert_workspace(workspace)

        rng = random.Random(123)
        faker = Faker()
        faker.seed_instance(123)

        users = generate_users(config, workspace.id, rng, faker, plugins)
        channels = generate_channels(config, workspace.id, rng, faker, plugins)
        store.insert_users(users)
        store.insert_channels(channels)

        user_ids = [u.id for u in users]
        channel_ids = [c.id for c in channels]

        store.insert_messages(
            list(
                generate_messages(config, workspace.id, user_ids, channel_ids, rng, faker, plugins)
            )
        )
        store.insert_files(
            list(generate_files(config, workspace.id, user_ids, channel_ids, rng, faker, plugins))
        )
    finally:
        store.close()

    return str(db_path), workspace.id


def test_messages_cursor_pagination(tmp_path, monkeypatch):
    db_path, workspace_id = _seed_db(tmp_path)
    monkeypatch.setenv("SWSYNTH_DB", db_path)
    client = TestClient(app)

    r1 = client.get(f"/workspaces/{workspace_id}/messages", params={"cursor": "", "limit": 3})
    assert r1.status_code == 200
    page1 = r1.json()
    assert len(page1) == 3
    cursor = r1.headers.get("x-next-cursor")
    assert cursor

    r2 = client.get(f"/workspaces/{workspace_id}/messages", params={"cursor": cursor, "limit": 3})
    assert r2.status_code == 200
    page2 = r2.json()
    assert len(page2) == 3
    assert {m["id"] for m in page1}.isdisjoint({m["id"] for m in page2})

    r_bad = client.get(f"/workspaces/{workspace_id}/messages", params={"cursor": "not-a-cursor"})
    assert r_bad.status_code == 400

    r_both = client.get(
        f"/workspaces/{workspace_id}/messages", params={"cursor": "", "offset": 10, "limit": 3}
    )
    assert r_both.status_code == 400


def test_files_cursor_pagination(tmp_path, monkeypatch):
    db_path, workspace_id = _seed_db(tmp_path)
    monkeypatch.setenv("SWSYNTH_DB", db_path)
    client = TestClient(app)

    r1 = client.get(f"/workspaces/{workspace_id}/files", params={"cursor": "", "limit": 2})
    assert r1.status_code == 200
    page1 = r1.json()
    assert len(page1) == 2
    cursor = r1.headers.get("x-next-cursor")
    assert cursor

    r2 = client.get(f"/workspaces/{workspace_id}/files", params={"cursor": cursor, "limit": 2})
    assert r2.status_code == 200
    page2 = r2.json()
    assert len(page2) == 2
    assert {f["id"] for f in page1}.isdisjoint({f["id"] for f in page2})

    r_both = client.get(
        f"/workspaces/{workspace_id}/files", params={"cursor": "", "offset": 10, "limit": 2}
    )
    assert r_both.status_code == 400


def test_users_cursor_pagination(tmp_path, monkeypatch):
    db_path, workspace_id = _seed_db(tmp_path)
    monkeypatch.setenv("SWSYNTH_DB", db_path)
    client = TestClient(app)

    r1 = client.get(f"/workspaces/{workspace_id}/users", params={"cursor": "", "limit": 2})
    assert r1.status_code == 200
    page1 = r1.json()
    assert len(page1) == 2
    cursor = r1.headers.get("x-next-cursor")
    assert cursor

    r2 = client.get(f"/workspaces/{workspace_id}/users", params={"cursor": cursor, "limit": 2})
    assert r2.status_code == 200
    page2 = r2.json()
    assert len(page2) == 2
    assert {u["id"] for u in page1}.isdisjoint({u["id"] for u in page2})

    r_bad = client.get(f"/workspaces/{workspace_id}/users", params={"cursor": "not-a-cursor"})
    assert r_bad.status_code == 400

    r_both = client.get(
        f"/workspaces/{workspace_id}/users", params={"cursor": "", "offset": 10, "limit": 2}
    )
    assert r_both.status_code == 400


def test_channels_cursor_pagination(tmp_path, monkeypatch):
    db_path, workspace_id = _seed_db(tmp_path)
    monkeypatch.setenv("SWSYNTH_DB", db_path)
    client = TestClient(app)

    r1 = client.get(f"/workspaces/{workspace_id}/channels", params={"cursor": "", "limit": 2})
    assert r1.status_code == 200
    page1 = r1.json()
    assert len(page1) == 2
    cursor = r1.headers.get("x-next-cursor")
    assert cursor

    r2 = client.get(f"/workspaces/{workspace_id}/channels", params={"cursor": cursor, "limit": 2})
    assert r2.status_code == 200
    page2 = r2.json()
    assert len(page2) == 1
    assert {c["id"] for c in page1}.isdisjoint({c["id"] for c in page2})

    r_both = client.get(
        f"/workspaces/{workspace_id}/channels", params={"cursor": "", "offset": 10, "limit": 2}
    )
    assert r_both.status_code == 400
