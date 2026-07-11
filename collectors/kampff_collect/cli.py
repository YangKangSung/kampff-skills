from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_collect
from .registry import list_platforms, list_prebuilt, load_platform


def main() -> None:
    parser = argparse.ArgumentParser(description="Generic kampff collector")
    sub = parser.add_subparsers(dest="cmd")

    c = sub.add_parser("collect", help="targets.json → bundle.json")
    c.add_argument("--targets", required=True, type=Path)
    c.add_argument("--out", required=True, type=Path)
    c.add_argument("--auth-dir", type=Path, default=Path("kampff-data/auth"))

    sub.add_parser("platforms", help="List all platform YAML ids")
    cat = sub.add_parser("catalog", help="List prebuilt platform packs")
    cat.add_argument("--tags", help="Filter by tag (workplace, sns, dev)")

    show = sub.add_parser("show", help="Show one platform YAML metadata")
    show.add_argument("platform")

    args = parser.parse_args()
    if args.cmd == "platforms":
        for p in list_platforms():
            print(p)
        return
    if args.cmd == "catalog":
        tag = getattr(args, "tags", None)
        for entry in list_prebuilt():
            if tag and tag not in entry.get("tags", []):
                continue
            note = entry.get("note", "")
            suffix = f"  # {note}" if note else ""
            print(f"{entry['id']:20} {entry['label']:28} [{entry['transport']}]{suffix}")
        return
    if args.cmd == "show":
        cfg = load_platform(args.platform)
        print(f"id: {cfg.get('id')}  prebuilt: {cfg.get('prebuilt', False)}")
        print(f"transport: {cfg.get('transport')}  auth: {cfg.get('auth')}")
        print(f"capabilities: {', '.join(cfg.get('capabilities', []))}")
        return
    if args.cmd == "collect":
        stats = run_collect(args.targets, args.out, args.auth_dir)
        print(stats)
        return
    parser.print_help()


if __name__ == "__main__":
    main()