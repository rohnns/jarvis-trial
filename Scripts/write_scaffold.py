from __future__ import annotations

from pathlib import Path

ROOT = Path("D:/Jarvis")
REQUIRED_DIRS = [
    "App", "Assets", "Cache", "Config", "Core", "Docs", "Downloads", "Installer", "Logs", "Memory",
    "Models", "Plugins", "Scripts", "Temp", "Tests", "UI", "Voices",
]


def main() -> None:
    missing = [directory for directory in REQUIRED_DIRS if not (ROOT / directory).is_dir()]
    if missing:
        raise SystemExit(f"Jarvis project is missing required directories: {', '.join(missing)}")
    print("Jarvis project structure verified")


if __name__ == "__main__":
    main()
