from __future__ import annotations
import asyncio
from Core.plugin import AssistantPlugin, CommandResult

class OpenAppPlugin(AssistantPlugin):
    name = 'open_app'
    async def can_handle(self, utterance: str) -> bool:
        return utterance.lower().startswith('open app ') or utterance.lower().startswith('open ')
    async def handle(self, utterance: str) -> CommandResult:
        app = utterance.split(' ', 1)[1].replace('app ', '', 1).strip()
        await asyncio.create_subprocess_shell(f'start "" "{app}"')
        return CommandResult(True, f'Opening {app}')
