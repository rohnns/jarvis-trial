from __future__ import annotations
from typing import Any, TypeVar
T = TypeVar('T')

class Container:
    """Minimal dependency injection container."""
    def __init__(self) -> None:
        self._services: dict[str, Any] = {}
    def register(self, key: str, service: Any) -> None:
        self._services[key] = service
    def resolve(self, key: str) -> Any:
        return self._services[key]
