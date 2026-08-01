from __future__ import annotations

import asyncio
import logging

from Core.app_registry import AppResolutionError, resolve_app
from Core.plugin import AssistantPlugin, CommandResult

log = logging.getLogger(__name__)


class OpenAppPlugin(AssistantPlugin):
    """Opens known desktop applications by alias (e.g. 'chrome', 'calc', 'notepad')."""

    name = "open_app"

    async def can_handle(self, utterance: str) -> bool:
        u = utterance.lower()
        return u.startswith("open app ") or u.startswith("open ") or u.startswith("launch ") or u.startswith("start ")

    async def handle(self, utterance: str) -> CommandResult:
        app_name = self._extract_app_name(utterance)
        log.info("Plugin selected: open_app", extra={"utterance": utterance, "app_name": app_name})

        try:
            display_name, launch_target = resolve_app(app_name)
        except AppResolutionError:
            log.warning("App resolution failed", extra={"app_name": app_name})
            return CommandResult(False, f"I don't know how to open '{app_name}'")

        log.info(
            "App resolved",
            extra={"app_name": app_name, "display_name": display_name, "launch_target": launch_target},
        )

        try:
            await self._launch(launch_target)
        except Exception:
            log.exception(
                "Failed to launch application",
                extra={"display_name": display_name, "launch_target": launch_target},
            )
            return CommandResult(False, f"I found {display_name} but couldn't launch it")

        log.info("App launched", extra={"display_name": display_name})
        return CommandResult(True, f"Opening {display_name}")

    def _extract_app_name(self, utterance: str) -> str:
        u = utterance.lower()
        for prefix in ("open app ", "open ", "launch ", "start "):
            if u.startswith(prefix):
                return utterance[len(prefix):].strip()
        return utterance.strip()

    async def _launch(self, launch_target: str) -> None:
        """Launch a resolved executable path or Windows shell verb via `start`."""
        # `start` requires an explicit empty title arg ("") before the target so that
        # quoted paths/verbs containing spaces are handled correctly on Windows.
        command = f'start "" "{launch_target}"'
        process = await asyncio.create_subprocess_shell(command)
        await process.wait()
        if process.returncode not in (0, None):
            raise RuntimeError(f"'start' exited with code {process.returncode} for target {launch_target!r}")
