from __future__ import annotations
from Core.ai import AIProvider
from Core.plugin import AssistantPlugin, CommandResult

class AIPlugin(AssistantPlugin):
    name = 'ai'
    def __init__(self, provider: AIProvider) -> None: self.provider = provider
    async def can_handle(self, utterance: str) -> bool: return True
    async def handle(self, utterance: str) -> CommandResult:
        return CommandResult(True, await self.provider.ask(utterance))
