from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    handled: bool
    message: str = ""
    requires_confirmation: bool = False


class AssistantPlugin(ABC):
    """Base class for assistant command plugins."""

    name: str
    dangerous: bool = False

    @abstractmethod
    async def can_handle(self, utterance: str) -> bool:
        """Return True when this plugin can process the utterance."""
        raise RuntimeError("AssistantPlugin.can_handle must be implemented by subclasses")

    @abstractmethod
    async def handle(self, utterance: str) -> CommandResult:
        """Execute the command and return a result."""
        raise RuntimeError("AssistantPlugin.handle must be implemented by subclasses")


class PluginManager:
    """Loads and dispatches commands to plugins."""

    def __init__(self, plugins: list[AssistantPlugin]) -> None:
        self.plugins = plugins

    async def dispatch(self, utterance: str) -> CommandResult:
        for plugin in self.plugins:
            if await plugin.can_handle(utterance):
                if plugin.dangerous:
                    return CommandResult(True, f"Confirmation required for {plugin.name}", True)
                return await plugin.handle(utterance)
        return CommandResult(False, "No plugin handled the command")
