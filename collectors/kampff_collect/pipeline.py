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
    import os

    import yaml

    out: dict[str, Any] = {"ref": auth_ref}
    profile = auth_dir / auth_ref / "profile.yaml"
    legacy = auth_dir / f"{auth_ref}.yaml"
    index_path = auth_dir / "auth.json"
    data: dict[str, Any] = {}
    if profile.exists():
        data = yaml.safe_load(profile.read_text(encoding="utf-8")) or {}
    elif legacy.exists():
        data = yaml.safe_load(legacy.read_text(encoding="utf-8")) or {}
    elif index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            meta = index.get(auth_ref) or {}
            out.update({k: v for k, v in meta.items() if k != "profile"})
        except json.JSONDecodeError:
            pass
    if data:
        out.update({k: v for k, v in data.items() if k not in ("notes",)})
        env_map = data.get("env") or {}
        alt_env = data.get("alt_env") or {}
        resolved: dict[str, str] = {}
        for logical, primary in env_map.items():
            names = [primary] + list(alt_env.get(logical) or [])
            for name in names:
                val = os.environ.get(name)
                if val and str(val).strip():
                    resolved[logical] = val
                    if logical == "token":
                        out["token"] = val
                    break
        out["env_resolved"] = {k: bool(v) for k, v in resolved.items()}
        # expose non-secret path-like env values for file transports
        for logical in ("export_dir",):
            if logical in resolved:
                out[logical] = resolved[logical]
    return out