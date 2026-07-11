from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapter_base import get_adapter
from .models import Person, Target, TargetsFile, TextItem
from .normalize import assign_items, to_bundle
from .registry import load_platform


def load_targets(path: Path) -> TargetsFile:
    data = json.loads(path.read_text(encoding="utf-8"))
    people = [
        Person(
            id=p["id"],
            aliases=p.get("aliases", []),
            display_name=p.get("display_name"),
        )
        for p in data["people"]
    ]
    targets = [
        Target(
            platform=t["platform"],
            url=t["url"],
            scope=t["scope"],
            collect=t["collect"],
            match_people=t["match_people"],
            auth_ref=t.get("auth_ref"),
            query=t.get("search", t.get("query", {})),
            playwright=t.get("playwright", {}),
        )
        for t in data["targets"]
    ]
    return TargetsFile(
        batch_date=data.get("batch_date"),
        viewer_id=data["viewer_id"],
        people=people,
        targets=targets,
        meta=data.get("meta", {}),
    )


def run_collect(targets_path: Path, out_path: Path, auth_dir: Path | None = None) -> dict[str, Any]:
    targets_file = load_targets(targets_path)
    all_items: list[TextItem] = []

    for target in targets_file.targets:
        platform = load_platform(target.platform)
        adapter = get_adapter(platform)
        auth = _resolve_auth(target.auth_ref, auth_dir)
        items = adapter.collect(target, auth)
        for item in items:
            item.platform = target.platform
            item.collected_from = item.collected_from or target.url
        all_items.extend(items)

    assigned = assign_items(targets_file, all_items)
    bundle = to_bundle(targets_file, assigned)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"items": len(all_items), "out": str(out_path)}


def _resolve_auth(auth_ref: str | None, auth_dir: Path | None) -> dict[str, Any] | None:
    if not auth_ref or not auth_dir:
        return None
    # TODO: load auth/{ref}.yaml + merge env
    return {"ref": auth_ref}