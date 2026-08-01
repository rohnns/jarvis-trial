from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from Core.config import ConfigService
from Core.events import EventBus
from Core.plugin import AssistantPlugin, CommandResult, PluginManager
from Plugins.google_search import GoogleSearchPlugin
from Plugins.open_website import OpenWebsitePlugin
from UI.orb import FloatingOrb, OrbState


class Phase1ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_config_service_load_get_save(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "Temp") as temp_dir:
            config_path = Path(temp_dir) / "settings.json"
            service = ConfigService(config_path)
            service.save({"assistant": {"name": "Jarvis"}})
            self.assertEqual(service.get("assistant.name"), "Jarvis")
            self.assertEqual(service.get("missing", "fallback"), "fallback")
            self.assertEqual(json.loads(config_path.read_text())["assistant"]["name"], "Jarvis")

    def test_event_bus_publish_subscribe(self) -> None:
        async def scenario() -> list[str]:
            bus = EventBus()
            seen: list[str] = []

            async def handler(event):
                seen.append(event.payload["value"])

            bus.subscribe("wake.detected", handler)
            await bus.publish("wake.detected", value="jarvis")
            return seen

        self.assertEqual(asyncio.run(scenario()), ["jarvis"])

    def test_google_search_plugin(self) -> None:
        async def scenario() -> CommandResult:
            plugin = GoogleSearchPlugin()
            self.assertTrue(await plugin.can_handle("google python asyncio"))
            with patch("webbrowser.open") as opened:
                result = await plugin.handle("google python asyncio")
                opened.assert_called_once()
                self.assertIn("python+asyncio", opened.call_args.args[0])
                return result

        result = asyncio.run(scenario())
        self.assertTrue(result.handled)

    def test_open_website_plugin(self) -> None:
        async def scenario() -> CommandResult:
            plugin = OpenWebsitePlugin()
            self.assertTrue(await plugin.can_handle("go to example.com"))
            with patch("webbrowser.open") as opened:
                result = await plugin.handle("go to example.com")
                opened.assert_called_once_with("https://example.com")
                return result

        result = asyncio.run(scenario())
        self.assertTrue(result.handled)

    def test_plugin_manager_requires_confirmation_for_dangerous_plugin(self) -> None:
        class DangerousPlugin(AssistantPlugin):
            name = "dangerous"
            dangerous = True

            async def can_handle(self, utterance: str) -> bool:
                return True

            async def handle(self, utterance: str) -> CommandResult:
                raise AssertionError("dangerous plugin should not execute before confirmation")

        result = asyncio.run(PluginManager([DangerousPlugin()]).dispatch("shutdown"))
        self.assertTrue(result.handled)
        self.assertTrue(result.requires_confirmation)

    def test_orb_states(self) -> None:
        orb = FloatingOrb()
        orb.set_state(OrbState.LISTENING)
        self.assertEqual(orb.state, OrbState.LISTENING)
        orb.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
