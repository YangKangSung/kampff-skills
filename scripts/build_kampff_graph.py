#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bundle.json → graph.json (Kampff relation layer)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kampff_graph import (
    build_graph,
    bundle_to_graph_path,
    load_distance_map,
    write_graph,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build Kampff relation graph.json")
    ap.add_argument("--bundle", "-b", required=True, help="multi-person bundle.json")
    ap.add_argument("--output", "-o", default="", help="graph.json (default: sibling)")
    ap.add_argument(
        "--analysis",
        "-a",
        action="append",
        default=[],
        help="optional analysis.json to join node.distance (repeatable)",
    )
    ap.add_argument("--seed", "-s", default="", help="ego filter: this id + neighbors")
    ap.add_argument("--hops", type=int, default=1, help="ego hops (with --seed)")
    args = ap.parse_args()
    bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    distances = load_distance_map([Path(p) for p in args.analysis])
    graph = build_graph(
        bundle,
        distances=distances,
        seed=args.seed,
        hops=args.hops,
    )
    out = Path(args.output) if args.output else bundle_to_graph_path(args.bundle)
    write_graph(graph, out)
    print(out)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main()
