from __future__ import annotations

import importlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

Hook = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class PluginRegistry:
    workspace_hooks: list[Hook] = field(default_factory=list)
    user_hooks: list[Hook] = field(default_factory=list)
    channel_hooks: list[Hook] = field(default_factory=list)
    message_hooks: list[Hook] = field(default_factory=list)
    file_hooks: list[Hook] = field(default_factory=list)

    def apply(self, hooks: Iterable[Hook], payload: dict[str, Any]) -> dict[str, Any]:
        result = payload
        for hook in hooks:
            result = hook(result)
        return result

    def on_workspace(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.apply(self.workspace_hooks, payload)

    def on_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.apply(self.user_hooks, payload)

    def on_channel(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.apply(self.channel_hooks, payload)

    def on_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.apply(self.message_hooks, payload)

    def on_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.apply(self.file_hooks, payload)


def load_plugins(module_paths: Iterable[str]) -> PluginRegistry:
    registry = PluginRegistry()
    for path in module_paths:
        module = importlib.import_module(path)
        if not hasattr(module, "register"):
            raise ValueError(f"Plugin {path} missing register(registry) function")
        module.register(registry)
    return registry
