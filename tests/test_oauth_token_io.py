import json
from pathlib import Path

from slack_workspace_synth import cli


def test_token_io_roundtrip(tmp_path: Path) -> None:
    tokens_path = tmp_path / "tokens.json"
    tokens = {
        "u1": {
            "synthetic_user_id": "u1",
            "slack_user_id": "U111",
            "access_token": "xoxp-1",
        },
        "u2": {
            "synthetic_user_id": "u2",
            "slack_user_id": "U222",
            "access_token": "xoxp-2",
        },
    }
    cli._write_tokens_file(tokens_path, tokens, {"captured": 2})

    loaded = cli._load_existing_tokens(tokens_path)
    assert len(loaded) == 2
    assert loaded["u1"]["access_token"] == "xoxp-1"

    payload = json.loads(tokens_path.read_text(encoding="utf-8"))
    assert "users" in payload


def test_load_existing_tokens_mapping(tmp_path: Path) -> None:
    tokens_path = tmp_path / "tokens_map.json"
    payload = {
        "u1": {"slack_user_id": "U111", "access_token": "xoxp-1"},
        "meta": {"captured": 1},
    }
    tokens_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = cli._load_existing_tokens(tokens_path)
    assert "u1" in loaded
    assert loaded["u1"]["access_token"] == "xoxp-1"
