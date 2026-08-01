from __future__ import annotations

import asyncio
from pathlib import Path

from Core.config import ConfigService
from Core.plugin import CommandResult, PluginManager
from Plugins.google_search import GoogleSearchPlugin
from UI.orb import FloatingOrb, OrbState


async def main() -> None:
    assert ConfigService(Path('Config/settings.json')).get('assistant_name') == 'Jarvis'
    google = GoogleSearchPlugin()
    assert await google.can_handle('google python')

    class Never:
        name = 'never'
        dangerous = False
        async def can_handle(self, utterance: str) -> bool:
            return False
        async def handle(self, utterance: str) -> CommandResult:
            return CommandResult(True)

    result = await PluginManager([Never()]).dispatch('nothing')
    assert result.handled is False
    orb = FloatingOrb()
    orb.set_state(OrbState.LISTENING)
    assert orb.state == OrbState.LISTENING
    print('VALIDATION_OK')


if __name__ == '__main__':
    asyncio.run(main())
