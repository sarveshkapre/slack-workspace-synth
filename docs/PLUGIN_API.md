# PLUGIN API

## Overview
Plugins are Python modules that expose a `register(registry)` function. Hooks receive a dict payload and must return a dict payload.

## Available hooks
- `registry.workspace_hooks`
- `registry.user_hooks`
- `registry.channel_hooks`
- `registry.message_hooks`
- `registry.file_hooks`

## Example
```python
from slack_workspace_synth.plugins import PluginRegistry

def register(registry: PluginRegistry) -> None:
    def tweak_channel(channel: dict) -> dict:
        channel["topic"] = "demo: " + channel["topic"]
        return channel

    registry.channel_hooks.append(tweak_channel)
```
