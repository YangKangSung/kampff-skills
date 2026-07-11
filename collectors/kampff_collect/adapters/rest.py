from __future__ import annotations

from typing import Any

from ..adapter_base import CollectorAdapter
from ..models import Target, TextItem


class RestAdapter(CollectorAdapter):
    """Generic REST collector — behavior from platform YAML endpoints + mapping."""

    transport = "rest"

    def collect(self, target: Target, auth: dict[str, Any] | None) -> list[TextItem]:
        # TODO: Jinja render endpoints, HTTP client, mapping engine
        raise NotImplementedError(
            "RestAdapter.collect: wire HTTP + mapping from platform YAML. "
            f"platform={target.platform} url={target.url}"
        )