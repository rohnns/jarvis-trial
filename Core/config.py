from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class ConfigService:
    """JSON-backed configuration service."""
    config_path: Path

    def load(self) -> dict[str, Any]:
        with self.config_path.open('r', encoding='utf-8') as f:
            return json.load(f)

    def get(self, dotted_key: str, default: Any = None) -> Any:
        current: Any = self.load()
        for part in dotted_key.split('.'):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    def save(self, data: dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
