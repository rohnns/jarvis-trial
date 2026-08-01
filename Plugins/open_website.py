from __future__ import annotations
import webbrowser
from Core.plugin import AssistantPlugin, CommandResult

class OpenWebsitePlugin(AssistantPlugin):
    name = 'open_website'
    async def can_handle(self, utterance: str) -> bool:
        u = utterance.lower(); return u.startswith('open website ') or u.startswith('go to ')
    async def handle(self, utterance: str) -> CommandResult:
        url = utterance.split(' ', 2)[-1].strip()
        if not url.startswith(('http://','https://')): url = 'https://' + url
        webbrowser.open(url)
        return CommandResult(True, f'Opening {url}')
