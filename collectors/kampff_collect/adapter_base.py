from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .models import Target, TextItem


class CollectorAdapter(ABC):
    """Generic adapter — one implementation per transport, not per vendor."""

    transport: str

    def __init__(self, platform_config: dict[str, Any]) -> None:
        self.config = platform_config

    @abstractmethod
    def collect(self, target: Target, auth: dict[str, Any] | None) -> list[TextItem]:
        ...


def get_adapter(platform_config: dict[str, Any]) -> CollectorAdapter:
    transport = platform_config.get("transport")
    if transport == "rest":
        from .adapters.rest import RestAdapter

        return RestAdapter(platform_config)
    if transport == "playwright":
        from .adapters.playwright import PlaywrightAdapter

        return PlaywrightAdapter(platform_config)
    if transport == "file":
        from .adapters.file_import import FileAdapter

        return FileAdapter(platform_config)
    raise ValueError(f"Unsupported transport: {transport}")