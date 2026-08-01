from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path

from Core.runtime_env import configure_runtime_environment

configure_runtime_environment(Path("D:/Jarvis"))

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from Core.ai import OllamaProvider
from Core.config import ConfigService
from Core.events import EventBus
from Core.logging_setup import configure_logging
from Core.normalize import normalize_transcript
from Core.paths import JarvisPaths
from Core.plugin import PluginManager
from Core.speech import PiperVoiceService, WakeWordService, WhisperSpeechRecognizer
from Plugins.ai_plugin import AIPlugin
from Plugins.google_search import GoogleSearchPlugin
from Plugins.open_app import OpenAppPlugin
from Plugins.open_website import OpenWebsitePlugin
from UI.orb import FloatingOrb, OrbState
from UI.tray import TrayController

log = logging.getLogger(__name__)


class JarvisApplication:
    """Composition root for the resident desktop assistant."""

    def __init__(self, qt_app: QApplication, root: Path = Path("D:/Jarvis")) -> None:
        self.qt_app = qt_app
        self.paths = JarvisPaths(root)
        self.paths.ensure()
        self.config = ConfigService(self.paths.config / "settings.json")
        self.settings = self.config.load()
        configure_logging(Path(self.settings["logging"]["file"]), self.settings["logging"]["level"])
        self.events = EventBus()
        self.shutdown_event = asyncio.Event()
        speech = self.settings["speech"]
        voice = self.settings["voice"]
        self.wake = WakeWordService(
            wake_words=self.settings["wake_words"],
            models_dir=self.paths.models / "openwakeword",
            threshold=float(self.settings.get("wake_word", {}).get("threshold", 0.55)),
        )
        self.recognizer = WhisperSpeechRecognizer(
            model_name=speech["whisper_model"],
            models_dir=self.paths.models / "whisper",
            device=speech.get("device", "auto"),
            compute_type=speech.get("compute_type", "auto"),
            command_seconds=float(speech.get("command_seconds", 5.0)),
        )
        self.voice = PiperVoiceService(
            executable=Path(voice["piper_executable"]),
            voice=Path(voice["default_voice"]),
            temp_dir=self.paths.temp,
        )
        provider = OllamaProvider(self.settings["ai"]["default_model"])
        self.plugins = PluginManager([OpenWebsitePlugin(), GoogleSearchPlugin(), OpenAppPlugin(), AIPlugin(provider)])
        self.orb = FloatingOrb(fade_ms=int(self.settings["ui"].get("orb_fade_ms", 2500)))
        self.tray = TrayController(
            self.settings["assistant_name"],
            on_show=self.show_orb,
            on_quit=self.request_shutdown,
            on_pause_toggle=self.set_manual_pause,
            on_restart=self.request_restart,
            on_settings=self.open_settings,
        )
        self._command_lock = asyncio.Lock()
        self._manually_paused = False

    async def start(self) -> None:
        """Start UI and background services without blocking the Qt loop."""
        self.tray.start()
        self.orb.set_state(OrbState.SLEEPING)
        await self.wake.start(self._on_wake_word)
        log.info("Jarvis started")

    async def stop(self) -> None:
        """Stop services and hide UI."""
        await self.wake.stop()
        self.tray.stop()
        self.shutdown_event.set()
        log.info("Jarvis stopped")

    def show_orb(self) -> None:
        """Show the orb when the tray icon is clicked."""
        self.orb.set_state(OrbState.LISTENING)

    def request_shutdown(self) -> None:
        """Schedule clean shutdown from the tray menu."""
        asyncio.create_task(self.stop())

    def request_restart(self) -> None:
        """Relaunch the assistant process and quit the current one."""
        log.info("Restart requested from tray")
        try:
            subprocess.Popen([sys.executable, *sys.argv], cwd=os.getcwd())
        except Exception:
            log.exception("Failed to spawn restarted process")
            return
        self.request_shutdown()

    def open_settings(self) -> None:
        """Open the settings file with the OS default handler."""
        settings_path = self.paths.config / "settings.json"
        log.info("Opening settings", extra={"settings_path": str(settings_path)})
        try:
            os.startfile(settings_path)  # type: ignore[attr-defined]
        except AttributeError:
            subprocess.Popen(["notepad.exe", str(settings_path)])
        except Exception:
            log.exception("Failed to open settings file")

    def set_manual_pause(self, paused: bool) -> None:
        """Pause/resume wake-word listening from the tray 'Pause Listening' toggle."""
        self._manually_paused = paused
        if paused:
            self.wake.suspend()
            self.orb.set_state(OrbState.SLEEPING)
            log.info("Listening manually paused from tray")
        else:
            asyncio.create_task(self.wake.resume_after_cooldown(cooldown_seconds=0.0))
            log.info("Listening manually resumed from tray")

    async def wait_until_shutdown(self) -> None:
        await self.shutdown_event.wait()

    async def _on_wake_word(self, wake_name: str, score: float) -> None:
        if self._command_lock.locked():
            log.info("Wake ignored because a command is already active")
            return
        async with self._command_lock:
            # The wake-word listener has already suspended itself (see
            # WakeWordService._listen_session), so the mic is free for the
            # entire STT -> parsing -> execution -> TTS cycle below. Resume
            # (with cooldown) happens in the finally block regardless of
            # outcome, unless the user manually paused listening from the tray.
            try:
                self.orb.set_state(OrbState.LISTENING)
                raw_utterance = await self.recognizer.transcribe_once()
                if not raw_utterance:
                    log.warning("Empty transcript received; nothing to dispatch")
                    self.orb.set_state(OrbState.ERROR)
                    await asyncio.sleep(1.0)
                    self.orb.set_state(OrbState.SLEEPING)
                    return
                utterance = normalize_transcript(raw_utterance)
                log.info("Transcript normalized", extra={"raw": raw_utterance, "normalized": utterance})
                if not utterance:
                    log.warning("Transcript normalized to empty string; nothing to dispatch")
                    self.orb.set_state(OrbState.ERROR)
                    await asyncio.sleep(1.0)
                    self.orb.set_state(OrbState.SLEEPING)
                    return
                result = await self.handle_utterance(utterance)
                if result.message:
                    await self.voice.speak(result.message)
                self.orb.set_state(OrbState.SLEEPING)
                log.info(
                    "Wake cycle completed",
                    extra={"wake_word": wake_name, "utterance": utterance, "handled": result.handled},
                )
            except Exception:
                log.exception("Command handling failed")
                self.orb.set_state(OrbState.ERROR)
                await asyncio.sleep(2.0)
                self.orb.set_state(OrbState.SLEEPING)
            finally:
                if self._manually_paused:
                    log.info("Skipping wake-word resume because listening is manually paused")
                else:
                    asyncio.create_task(self.wake.resume_after_cooldown())

    async def handle_utterance(self, utterance: str):
        self.orb.set_state(OrbState.EXECUTING)
        log.info("Executing command", extra={"utterance": utterance})
        result = await self.plugins.dispatch(utterance)
        self.orb.set_state(OrbState.SPEAKING if result.handled else OrbState.ERROR)
        log.info("Command handled", extra={"utterance": utterance, "handled": result.handled, "result_message": result.message})
        return result


async def _run(qt_app: QApplication) -> None:
    jarvis = JarvisApplication(qt_app)
    qt_app.aboutToQuit.connect(jarvis.request_shutdown)
    await jarvis.start()
    await jarvis.wait_until_shutdown()


def main() -> None:
    QApplication.setQuitOnLastWindowClosed(False)
    qt_app = QApplication.instance() or QApplication(sys.argv)
    loop = QEventLoop(qt_app)
    asyncio.set_event_loop(loop)
    for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
        if sig is not None:
            try:
                signal.signal(sig, lambda *_args: qt_app.quit())
            except ValueError:
                log.debug("Signal registration skipped")
    with loop:
        loop.run_until_complete(_run(qt_app))


if __name__ == "__main__":
    main()
