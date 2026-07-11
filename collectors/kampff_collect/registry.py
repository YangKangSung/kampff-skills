from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PLATFORMS_DIR = Path(__file__).resolve().parent.parent / "platforms"


def load_platform(platform_id: str) -> dict[str, Any]:
    path = PLATFORMS_DIR / f"{platform_id}.yaml"
    if not path.exists():
        raise KeyError(f"Unknown platform '{platform_id}'. Add collectors/platforms/{platform_id}.yaml")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data.get("id") != platform_id:
        raise ValueError(f"Platform id mismatch in {path}")
    return data


def list_platforms() -> list[str]:
    return sorted(p.stem for p in PLATFORMS_DIR.glob("*.yaml") if not p.stem.startswith("_"))