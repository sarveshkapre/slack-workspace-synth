import io
import json
from email.message import Message

import pytest

import slack_workspace_synth.cli as cli


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:  # pragma: no cover
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover
        return None


def test_slack_retries_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    slept: list[float] = []

    def fake_sleep(value: float) -> None:
        slept.append(float(value))

    def fake_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        calls.append(request.full_url)
        if len(calls) == 1:
            hdrs = Message()
            hdrs["Retry-After"] = "0"
            raise cli.HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                hdrs,
                io.BytesIO(b'{"ok":false,"error":"ratelimited"}'),
            )
        return _FakeResponse({"ok": True})

    monkeypatch.setattr(cli.time, "sleep", fake_sleep)
    monkeypatch.setattr(cli, "urlopen", fake_urlopen)

    response = cli._slack_post_json(
        "xoxp-test",
        "https://slack.com/api/chat.postMessage",
        {"channel": "C123", "text": "hi"},
        max_retries=1,
        timeout_seconds=1,
        max_backoff_seconds=0,
    )
    assert response["ok"] is True
    assert len(calls) == 2
    assert slept == [0.0]


def test_slack_retries_on_ok_false_ratelimited(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    slept: list[float] = []

    def fake_sleep(value: float) -> None:
        slept.append(float(value))

    def fake_random() -> float:
        return 0.0

    def fake_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if calls == 1:
            return _FakeResponse({"ok": False, "error": "ratelimited"})
        return _FakeResponse({"ok": True})

    monkeypatch.setattr(cli.time, "sleep", fake_sleep)
    monkeypatch.setattr(cli.random, "random", fake_random)
    monkeypatch.setattr(cli, "urlopen", fake_urlopen)

    response = cli._slack_get_json(
        "xoxp-test",
        "https://slack.com/api/conversations.list",
        {"limit": "1", "types": "public_channel"},
        max_retries=1,
        timeout_seconds=1,
        max_backoff_seconds=1,
    )
    assert response["ok"] is True
    assert calls == 2
    assert slept == [0.25]


def test_slack_retries_on_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    slept: list[float] = []

    def fake_sleep(value: float) -> None:
        slept.append(float(value))

    def fake_random() -> float:
        return 0.0

    def fake_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if calls == 1:
            hdrs = Message()
            raise cli.HTTPError(
                request.full_url,
                500,
                "Internal Server Error",
                hdrs,
                io.BytesIO(b'{"ok":false,"error":"internal_error"}'),
            )
        return _FakeResponse({"ok": True})

    monkeypatch.setattr(cli.time, "sleep", fake_sleep)
    monkeypatch.setattr(cli.random, "random", fake_random)
    monkeypatch.setattr(cli, "urlopen", fake_urlopen)

    response = cli._slack_post_json(
        "xoxp-test",
        "https://slack.com/api/conversations.create",
        {"name": "demo"},
        max_retries=1,
        timeout_seconds=1,
        max_backoff_seconds=1,
    )
    assert response["ok"] is True
    assert calls == 2
    assert slept == [0.25]
