from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_collect
from .registry import list_platforms


def main() -> None:
    parser = argparse.ArgumentParser(description="Generic kampff collector")
    sub = parser.add_subparsers(dest="cmd")

    c = sub.add_parser("collect", help="targets.json → bundle.json")
    c.add_argument("--targets", required=True, type=Path)
    c.add_argument("--out", required=True, type=Path)
    c.add_argument("--auth-dir", type=Path, default=Path("kampff-data/auth"))

    sub.add_parser("platforms", help="List platform configs")

    args = parser.parse_args()
    if args.cmd == "platforms":
        for p in list_platforms():
            print(p)
        return
    if args.cmd == "collect":
        stats = run_collect(args.targets, args.out, args.auth_dir)
        print(stats)
        return
    parser.print_help()


if __name__ == "__main__":
    main()