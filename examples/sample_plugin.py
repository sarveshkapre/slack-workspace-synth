from __future__ import annotations

from slack_workspace_synth.plugins import PluginRegistry


def register(registry: PluginRegistry) -> None:
    def mark_bots(user: dict) -> dict:
        if user.get("title") == "CEO":
            user["is_bot"] = 1
        return user

    registry.user_hooks.append(mark_bots)
