from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

try:  # pragma: no cover - winreg only exists on Windows, which is this app's target OS.
    import winreg
except ImportError:  # pragma: no cover - allows import/tests on non-Windows dev machines.
    winreg = None  # type: ignore[assignment]

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppEntry:
    """A resolvable application target."""

    display_name: str
    # Candidate executable names to look for via PATH / App Paths registry.
    executable_candidates: tuple[str, ...] = ()
    # Known absolute install locations to probe (with %ENV% placeholders).
    known_paths: tuple[str, ...] = ()
    # Shell verb fallback, e.g. "calc" or "notepad" understood natively by Windows.
    shell_verb: str | None = None


# Alias -> canonical registry key. Multiple aliases can point at the same app.
_ALIASES: dict[str, str] = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "calculator": "calculator",
    "calc": "calculator",
    "notepad": "notepad",
    "paint": "paint",
    "ms paint": "paint",
    "spotify": "spotify",
    "steam": "steam",
    "vscode": "vscode",
    "vs code": "vscode",
    "code": "vscode",
    "visual studio code": "vscode",
    "discord": "discord",
    "file explorer": "file_explorer",
    "explorer": "file_explorer",
    "files": "file_explorer",
    "task manager": "task_manager",
    "taskmanager": "task_manager",
}

_APPS: dict[str, AppEntry] = {
    "chrome": AppEntry(
        display_name="Google Chrome",
        executable_candidates=("chrome.exe",),
        known_paths=(
            "%PROGRAMFILES%/Google/Chrome/Application/chrome.exe",
            "%PROGRAMFILES(X86)%/Google/Chrome/Application/chrome.exe",
            "%LOCALAPPDATA%/Google/Chrome/Application/chrome.exe",
        ),
    ),
    "calculator": AppEntry(
        display_name="Calculator",
        executable_candidates=("CalculatorApp.exe",),
        shell_verb="calc",
    ),
    "notepad": AppEntry(
        display_name="Notepad",
        executable_candidates=("notepad.exe",),
        known_paths=("%WINDIR%/System32/notepad.exe",),
        shell_verb="notepad",
    ),
    "paint": AppEntry(
        display_name="Paint",
        executable_candidates=("mspaint.exe",),
        known_paths=("%WINDIR%/System32/mspaint.exe",),
        shell_verb="mspaint",
    ),
    "spotify": AppEntry(
        display_name="Spotify",
        executable_candidates=("Spotify.exe",),
        known_paths=("%APPDATA%/Spotify/Spotify.exe",),
    ),
    "steam": AppEntry(
        display_name="Steam",
        executable_candidates=("steam.exe",),
        known_paths=(
            "%PROGRAMFILES(X86)%/Steam/steam.exe",
            "%PROGRAMFILES%/Steam/steam.exe",
        ),
    ),
    "vscode": AppEntry(
        display_name="Visual Studio Code",
        executable_candidates=("Code.exe",),
        known_paths=(
            "%LOCALAPPDATA%/Programs/Microsoft VS Code/Code.exe",
            "%PROGRAMFILES%/Microsoft VS Code/Code.exe",
        ),
    ),
    "discord": AppEntry(
        display_name="Discord",
        executable_candidates=("Discord.exe",),
        known_paths=("%LOCALAPPDATA%/Discord/Update.exe",),
    ),
    "file_explorer": AppEntry(
        display_name="File Explorer",
        executable_candidates=("explorer.exe",),
        known_paths=("%WINDIR%/explorer.exe",),
        shell_verb="explorer",
    ),
    "task_manager": AppEntry(
        display_name="Task Manager",
        executable_candidates=("Taskmgr.exe",),
        known_paths=("%WINDIR%/System32/Taskmgr.exe",),
        shell_verb="taskmgr",
    ),
}


class AppResolutionError(RuntimeError):
    """Raised when an application name/alias cannot be resolved to a launch target."""


def normalize_app_key(name: str) -> str:
    """Normalize a raw app name/alias for lookup (lowercase, trimmed, no trailing punctuation)."""
    cleaned = name.strip().lower().strip(".,!?:;\"'")
    return " ".join(cleaned.split())


def resolve_app(name: str) -> tuple[str, str]:
    """Resolve an alias/app name to a (display_name, launch_target) pair.

    launch_target is either an absolute path to an executable or a Windows shell
    verb (e.g. "calc") that can be passed to `start`.

    Raises AppResolutionError if the app cannot be found on this system.
    """
    key = normalize_app_key(name)
    canonical = _ALIASES.get(key)
    if canonical is None:
        # Fall back to fuzzy contains-matching against known aliases so that
        # phrases like "open up google chrome browser" still resolve.
        for alias, target in _ALIASES.items():
            if alias in key or key in alias:
                canonical = target
                break
    if canonical is None:
        raise AppResolutionError(f"'{name}' is not a recognized application")

    entry = _APPS[canonical]

    # 1. Try the App Paths registry (most robust: works even if not on PATH).
    for exe_name in entry.executable_candidates:
        resolved = _resolve_via_app_paths_registry(exe_name)
        if resolved:
            return entry.display_name, resolved

    # 2. Try known install locations with environment variables expanded.
    for template in entry.known_paths:
        candidate = Path(os.path.expandvars(template.replace("/", os.sep)))
        if candidate.exists():
            return entry.display_name, str(candidate)

    # 3. Try PATH resolution.
    for exe_name in entry.executable_candidates:
        found = shutil.which(exe_name)
        if found:
            return entry.display_name, found

    # 4. Fall back to a native Windows shell verb Explorer understands directly.
    if entry.shell_verb:
        return entry.display_name, entry.shell_verb

    raise AppResolutionError(f"Could not locate an installed executable for '{entry.display_name}'")


def _resolve_via_app_paths_registry(exe_name: str) -> str | None:
    """Look up an executable's real path in the Windows 'App Paths' registry key."""
    if winreg is None:
        return None
    key_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, key_path) as key:
                value, _ = winreg.QueryValueEx(key, None)
                if value and Path(value).exists():
                    return value
        except OSError:
            continue
        except Exception:
            log.debug("Unexpected error reading App Paths registry for %s", exe_name, exc_info=True)
    return None


def known_aliases() -> tuple[str, ...]:
    """Return all recognized aliases, for help text / diagnostics."""
    return tuple(sorted(_ALIASES))
