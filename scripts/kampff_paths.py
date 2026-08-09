"""Shared Kampff path resolution — env first, else repo-local kampff-data/."""
from __future__ import annotations

import os
from pathlib import Path


def data_root() -> Path:
    env = (os.environ.get("KAMPFF_DATA") or "").strip()
    if env:
        p = Path(env)
        p.mkdir(parents=True, exist_ok=True)
        return p
    here = Path(__file__).resolve().parent.parent / "kampff-data"
    here.mkdir(parents=True, exist_ok=True)
    return here
