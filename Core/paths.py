from __future__ import annotations
from pathlib import Path

class JarvisPaths:
    """Centralized path registry. Nothing app-owned is stored outside root."""
    def __init__(self, root: Path = Path("D:/Jarvis")) -> None:
        self.root = root
        self.app = root / "App"; self.assets = root / "Assets"; self.cache = root / "Cache"
        self.config = root / "Config"; self.core = root / "Core"; self.docs = root / "Docs"
        self.downloads = root / "Downloads"; self.installer = root / "Installer"; self.logs = root / "Logs"
        self.memory = root / "Memory"; self.models = root / "Models"; self.plugins = root / "Plugins"
        self.scripts = root / "Scripts"; self.temp = root / "Temp"; self.tests = root / "Tests"
        self.ui = root / "UI"; self.voices = root / "Voices"

    def ensure(self) -> None:
        for value in self.__dict__.values():
            if isinstance(value, Path):
                value.mkdir(parents=True, exist_ok=True)
