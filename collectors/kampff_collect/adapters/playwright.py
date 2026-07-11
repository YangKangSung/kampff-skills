from __future__ import annotations

from typing import Any

from ..adapter_base import CollectorAdapter
from ..models import Target, TextItem


class PlaywrightAdapter(CollectorAdapter):
    """Generic Playwright collector — selectors from platform YAML + target.query overrides."""

    transport = "playwright"

    def collect(self, target: Target, auth: dict[str, Any] | None) -> list[TextItem]:
        # TODO: launch browser, storage_state from auth, DOM extract per selectors
        raise NotImplementedError(
            "PlaywrightAdapter.collect: wire Playwright + selectors from YAML. "
            f"url={target.url}"
        )