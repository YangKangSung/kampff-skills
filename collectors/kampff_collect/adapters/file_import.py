from __future__ import annotations

from typing import Any

from ..adapter_base import CollectorAdapter
from ..models import Target, TextItem


class FileAdapter(CollectorAdapter):
    """Generic file/import transport — glob + parser id from YAML."""

    transport = "file"

    def collect(self, target: Target, auth: dict[str, Any] | None) -> list[TextItem]:
        raise NotImplementedError("FileAdapter.collect: wire glob parsers from YAML")