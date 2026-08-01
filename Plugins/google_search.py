from __future__ import annotations
import urllib.parse, webbrowser
from Core.plugin import AssistantPlugin, CommandResult

class GoogleSearchPlugin(AssistantPlugin):
    name = 'google_search'
    async def can_handle(self, utterance: str) -> bool:
        return utterance.lower().startswith(('google ', 'search google for ', 'search for '))
    async def handle(self, utterance: str) -> CommandResult:
        query = utterance.replace('search google for ', '').replace('search for ', '').replace('google ', '').strip()
        url = 'https://www.google.com/search?q=' + urllib.parse.quote_plus(query)
        webbrowser.open(url)
        return CommandResult(True, f'Searching Google for {query}')
