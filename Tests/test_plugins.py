import pytest
from Core.plugin import CommandResult, PluginManager
from Plugins.google_search import GoogleSearchPlugin
from Plugins.open_website import OpenWebsitePlugin

@pytest.mark.asyncio
async def test_google_plugin_matches():
    p = GoogleSearchPlugin()
    assert await p.can_handle('google python')

@pytest.mark.asyncio
async def test_plugin_manager_unhandled():
    class Never:
        name='never'; dangerous=False
        async def can_handle(self, utterance): return False
        async def handle(self, utterance): return CommandResult(True)
    r = await PluginManager([Never()]).dispatch('x')
    assert not r.handled
