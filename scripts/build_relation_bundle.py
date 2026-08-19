#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a seed-centered multi-person bundle from saved thread HTML.

  python scripts/build_relation_bundle.py --seed someid
  python scripts/build_relation_bundle.py --seed someid --raw inbox/DATE/raw/someid -o out.json

People = the seed plus IDs tied to that seed's posts, comments, and likes.
Does not scrape. Re-reads harvest HTML (or thread_actors.json).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date as date_cls
from pathlib import Path
from typing import Any

from kampff_paths import data_root
from thread_actors import parse_thread_file, to_iso


def find_seed_raw(seed: str, root: Path | None = None) -> Path | None:
    seed = (seed or "").strip()
    if not seed:
        return None
    inbox = (root or data_root()) / "inbox"
    if not inbox.is_dir():
        return None
    hits: list[Path] = []
    for day in inbox.iterdir():
        if not day.is_dir():
            continue
        raw = day / "raw" / seed
        if not raw.is_dir():
            continue
        posts = raw / "posts"
        has_html = posts.is_dir() and any(posts.glob("*.html"))
        has_actors = (raw / "thread_actors.json").is_file()
        has_rel = (raw / "relation_bundle.json").is_file()
        if has_html or has_actors or has_rel:
            hits.append(raw)
    if not hits:
        return None
    hits.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0]


def load_threads(raw_dir: Path) -> list[dict[str, Any]]:
    posts = raw_dir / "posts"
    if posts.is_dir():
        files = sorted(posts.glob("*.html"))
        if files:
            return [parse_thread_file(p) for p in files]
    actors = raw_dir / "thread_actors.json"
    if actors.is_file():
        data = json.loads(actors.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [t for t in data if isinstance(t, dict)]
        if isinstance(data, dict) and isinstance(data.get("threads"), list):
            return [t for t in data["threads"] if isinstance(t, dict)]
    return []


def _ensure_person(people: dict[str, dict], pid: str, nick: str = "") -> dict:
    pid = (pid or "").strip()
    if not pid:
        return {}
    row = people.setdefault(
        pid,
        {"id": pid, "display_name": nick or pid, "texts": []},
    )
    if nick and row.get("display_name") in ("", pid):
        row["display_name"] = nick
    return row


def _add_text(person: dict, **kw: Any) -> None:
    if not person:
        return
    content = str(kw.get("content") or "").strip()
    if not content:
        return
    person["texts"].append(
        {
            "content": content[:4000],
            "timestamp": kw.get("timestamp") or "",
            "source": kw.get("source") or "community_comment",
            "type": kw.get("type") or "comment",
            "url": kw.get("url") or "",
            "thread_id": kw.get("thread_id") or "",
            "reply_to": kw.get("reply_to") or "",
            "parent_url": kw.get("parent_url") or "",
        }
    )


def _thread_ids_for_seed(threads: list[dict], seed: str) -> set[str]:
    out: set[str] = set()
    for t in threads:
        tid = str(t.get("thread_id") or "")
        if not tid:
            continue
        if t.get("op_id") == seed:
            out.add(tid)
            continue
        if any(c.get("author_id") == seed for c in t.get("comments") or []):
            out.add(tid)
            continue
        if any(
            lk.get("author_id") == seed or lk.get("target_id") == seed
            for lk in t.get("likes") or []
        ):
            out.add(tid)
    return out


def _score_alters(threads: list[dict], seed: str, seed_threads: set[str]) -> dict[str, int]:
    score: dict[str, int] = defaultdict(int)
    for t in threads:
        tid = str(t.get("thread_id") or "")
        if tid not in seed_threads:
            continue
        op = str(t.get("op_id") or "")
        if op and op != seed:
            score[op] += 4 if t.get("op_id") != seed else 0
        if op == seed:
            for c in t.get("comments") or []:
                aid = str(c.get("author_id") or "")
                if aid and aid != seed:
                    score[aid] += 3
        for c in t.get("comments") or []:
            aid = str(c.get("author_id") or "")
            tgt = str(c.get("reply_to") or "")
            if aid == seed and tgt and tgt != seed:
                score[tgt] += 5
            if tgt == seed and aid and aid != seed:
                score[aid] += 5
        for lk in t.get("likes") or []:
            a = str(lk.get("author_id") or "")
            b = str(lk.get("target_id") or "")
            if a == seed and b and b != seed:
                score[b] += 4
            if b == seed and a and a != seed:
                score[a] += 4
    return dict(score)


def bundle_from_threads(
    seed: str,
    threads: list[dict[str, Any]],
    *,
    date: str = "",
    max_alters: int = 80,
    platform: str = "community",
) -> dict[str, Any]:
    seed = (seed or "").strip()
    day = date or date_cls.today().isoformat()
    seed_threads = _thread_ids_for_seed(threads, seed)
    scores = _score_alters(threads, seed, seed_threads)
    ranked = sorted(scores, key=lambda i: (-scores[i], i))
    keep = {seed} | set(ranked[: max(0, max_alters)])
    people: dict[str, dict] = {}
    _ensure_person(people, seed, seed)
    likes_n = 0
    likes_status = "not_collected"

    for t in threads:
        tid = str(t.get("thread_id") or "")
        if tid not in seed_threads:
            continue
        url = str(t.get("url") or "")
        ts = to_iso(str(t.get("timestamp") or ""), day)
        op = str(t.get("op_id") or "")
        op_nick = str(t.get("op_nick") or op)
        if op in keep:
            p = _ensure_person(people, op, op_nick)
            body = str(t.get("body") or "").strip()
            title = str(t.get("title") or "").strip()
            content = ((" [title] " + title + "\n") if title else "") + body
            if content.strip():
                _add_text(
                    p,
                    content=content.strip()[:8000],
                    timestamp=ts,
                    source="community_post",
                    type="post",
                    url=url,
                    thread_id=tid,
                )
        for c in t.get("comments") or []:
            aid = str(c.get("author_id") or "")
            if aid not in keep:
                continue
            p = _ensure_person(people, aid, str(c.get("nick") or aid))
            reply_to = str(c.get("reply_to") or "")
            if reply_to not in keep:
                reply_to = ""
            _add_text(
                p,
                content=str(c.get("text") or "").strip() or "[comment]",
                timestamp=to_iso(str(c.get("timestamp") or ""), day) or ts,
                source="community_comment",
                type="reply" if c.get("is_reply") else "comment",
                url=f"{url}#comment{c.get('sn') or ''}" if url else "",
                thread_id=tid,
                reply_to=reply_to,
                parent_url=url,
            )
        if t.get("likes_status") == "collected":
            likes_status = "collected"
        for lk in t.get("likes") or []:
            likes_n += 1
            a = str(lk.get("author_id") or "")
            b = str(lk.get("target_id") or "")
            if a not in keep:
                continue
            p = _ensure_person(people, a, a)
            _add_text(
                p,
                content="[like]",
                timestamp=ts,
                source="community_like",
                type="like",
                url=url,
                thread_id=tid,
                reply_to=b if b in keep else "",
            )

    if likes_n and likes_status != "collected":
        likes_status = "collected"
    people_list = [people[seed]] + [people[i] for i in ranked if i in people and i != seed]
    return {
        "context": "community",
        "viewer_id": seed,
        "protocol": "relation-v1",
        "batch_date": day,
        "meta": {
            "platform": platform,
            "seed": seed,
            "ego": True,
            "n_threads": len(seed_threads),
            "n_html_threads": len(threads),
            "max_alters": max_alters,
            "likes": {"status": likes_status, "n": likes_n},
        },
        "people": people_list,
    }


def write_relation_artifacts(
    raw_dir: Path,
    seed: str,
    *,
    date: str = "",
    output: Path | None = None,
    max_alters: int = 80,
    platform: str = "community",
) -> Path:
    raw_dir = Path(raw_dir)
    threads = load_threads(raw_dir)
    if not threads:
        rel = raw_dir / "relation_bundle.json"
        if rel.is_file():
            if output and Path(output).resolve() != rel.resolve():
                out = Path(output)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(rel.read_text(encoding="utf-8"), encoding="utf-8")
                return out
            return rel
        raise SystemExit(f"no thread HTML or thread_actors.json under {raw_dir}")
    (raw_dir / "thread_actors.json").write_text(
        json.dumps({"seed": seed, "threads": threads}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    bundle = bundle_from_threads(
        seed, threads, date=date, max_alters=max_alters, platform=platform
    )
    out = Path(output) if output else raw_dir / "relation_bundle.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if output and output.resolve() != (raw_dir / "relation_bundle.json").resolve():
        (raw_dir / "relation_bundle.json").write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed-centered relation bundle from harvest HTML")
    ap.add_argument("--seed", "-s", required=True, help="member / author id")
    ap.add_argument("--raw", "-r", default="", help="inbox/DATE/raw/{id} (auto-find if omitted)")
    ap.add_argument("--output", "-o", default="", help="relation bundle.json")
    ap.add_argument("--max-alters", type=int, default=80)
    ap.add_argument("--date", default="")
    ap.add_argument("--platform", default="community")
    args = ap.parse_args()
    raw = Path(args.raw) if args.raw else find_seed_raw(args.seed)
    if not raw:
        raise SystemExit(
            f"no harvest raw for {args.seed} — run Analyze/harvest first "
            f"(inbox/*/raw/{args.seed}/posts)"
        )
    day = args.date or raw.parent.parent.name
    out = Path(args.output) if args.output else raw / "relation_bundle.json"
    path = write_relation_artifacts(
        raw,
        args.seed,
        date=day,
        output=out,
        max_alters=args.max_alters,
        platform=args.platform,
    )
    print(path)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main()
