#!/usr/bin/env python3
"""Smoke tests for relation graph. python scripts/test_kampff_graph.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_relation_bundle import bundle_from_threads  # noqa: E402
from kampff_graph import build_graph, ego_graph  # noqa: E402
from render_kampff_graph import render_graph  # noqa: E402
from thread_actors import parse_thread_file, parse_thread_html  # noqa: E402


def test_sample_brigade() -> None:
    bundle = json.loads((ROOT / "docs" / "sample-relation-bundle.json").read_text(encoding="utf-8"))
    g = build_graph(bundle, distances={"relay_ops": "neutral"})
    ids = {n["id"] for n in g["nodes"]}
    assert {"relay_ops", "ci_gate", "brigade_w1", "brigade_w2", "brigade_w3", "flame_once"} <= ids
    assert any(n["id"] == "relay_ops" and n["distance"] == "neutral" for n in g["nodes"])
    edges = g["edges"]
    assert any(e["level"] == 5 for e in edges), [e["level"] for e in edges]
    pair = next(
        e
        for e in edges
        if set((e["source"], e["target"])) == {"brigade_w1", "brigade_w2"}
    )
    assert pair["level"] >= 4
    assert "near_dup" in pair["kinds"]
    clusters = g["coordination"]["clusters"]
    assert clusters, "expected coordination cluster"
    members = set(clusters[0]["member_ids"])
    assert members == {"brigade_w1", "brigade_w2", "brigade_w3"}, members
    flame = [e for e in edges if "flame_once" in (e["source"], e["target"])]
    assert flame
    assert max(e["level"] for e in flame) <= 3
    html = render_graph(g)
    assert "minLevel" in html
    assert 'data-below="hide"' in html
    assert 'data-below="dim"' in html
    assert "minWidth" in html
    assert "relation-v1" in html or "Board graph" in html
    assert "brigade_w1" in html
    assert "likes" in html


def test_ego_from_html() -> None:
    t1 = parse_thread_file(ROOT / "docs" / "sample-ego-thread-seed.html")
    t2 = parse_thread_file(ROOT / "docs" / "sample-ego-thread-alter.html")
    assert t1["op_id"] == "seed_user"
    assert t2["op_id"] == "alter_a"
    authors = {c["author_id"] for c in t1["comments"]}
    assert {"alter_a", "seed_user", "alter_b"} <= authors
    seed_reply = next(c for c in t1["comments"] if c["sn"] == "12")
    assert seed_reply["reply_to"] == "alter_a"
    assert any(lk["author_id"] == "liker_c" for lk in t1["likes"])
    seed_on_alter = next(c for c in t2["comments"] if c["author_id"] == "seed_user")
    assert seed_on_alter["reply_to"] == "alter_a"
    bundle = bundle_from_threads("seed_user", [t1, t2], date="2026-07-13")
    ids = {p["id"] for p in bundle["people"]}
    assert ids == {"seed_user", "alter_a", "alter_b", "liker_c"}, ids
    assert bundle["meta"]["likes"]["status"] == "collected"
    g = build_graph(bundle)
    assert any(n["id"] == "seed_user" and n["role"] == "seed" for n in g["nodes"])
    assert any("likes" in (e.get("kinds") or []) for e in g["edges"])
    pair = next(
        e
        for e in g["edges"]
        if set((e["source"], e["target"])) == {"seed_user", "alter_a"}
    )
    assert pair["level"] >= 3
    g2 = ego_graph(g, "seed_user", hops=1)
    assert {n["id"] for n in g2["nodes"]} == ids
    html = render_graph(g, lang="ko")
    assert "seed_user 중심" in html
    assert "likes" in html


def test_attach_existing_hop2() -> None:
    t1 = parse_thread_file(ROOT / "docs" / "sample-ego-thread-seed.html")
    t2 = parse_thread_file(ROOT / "docs" / "sample-ego-thread-alter.html")
    t3 = parse_thread_html(
        """
        <div class="post_contact"><span class="nickname" title="alter_a"></span>
        <button data-author-id="alter_a">info</button></div>
        <h3 class="post_subject"><span>Alter other thread</span></h3>
        <span class="view_count date"></span> 2026-07-14 11:00:00
        <div class="post_article">alter_a wrote a second post seed never saw.</div>
        <div class="comment_row" data-author-id="hop2_user" data-comment-sn="31">
          <span class="nickname" title="hop2_user"></span>
          <span class="timestamp">2026-07-14 11:05:00</span>
          <div class="comment_view">Only talks to alter_a on this other thread.</div>
        </div>
        <div id="comment-write"></div>
        """,
        url="https://forum.example/board/park/1003",
    )
    base = bundle_from_threads("seed_user", [t1, t2], date="2026-07-13")
    assert "hop2_user" not in {p["id"] for p in base["people"]}
    merged = bundle_from_threads(
        "seed_user",
        [t1, t2],
        date="2026-07-13",
        extra_threads=[t3],
        attached_ids=["alter_a"],
    )
    ids = {p["id"] for p in merged["people"]}
    assert "hop2_user" in ids
    hop2 = next(p for p in merged["people"] if p["id"] == "hop2_user")
    assert hop2["hop"] == 2
    assert merged["meta"]["attached_ids"] == ["alter_a"]
    g = build_graph(merged, seed="seed_user")
    assert any(n["id"] == "hop2_user" and n.get("hop") == 2 for n in g["nodes"])
    html = render_graph(g, lang="ko")
    assert "이미 수확한 상대" in html
    assert "hop2_user" in html


def main() -> None:
    test_sample_brigade()
    test_ego_from_html()
    test_attach_existing_hop2()
    print("ok")


if __name__ == "__main__":
    main()
