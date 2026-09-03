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


def _raw_usable(raw: Path) -> bool:
    posts = raw / "posts"
    return (
        (posts.is_dir() and any(posts.glob("*.html")))
        or (raw / "thread_actors.json").is_file()
        or (raw / "relation_bundle.json").is_file()
    )


def _state_ids(raw: Path) -> set[str]:
    out = {raw.name, raw.name.lower()}
    st = raw / "STATE.json"
    if not st.is_file():
        return out
    try:
        data = json.loads(st.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    for key in ("author_id", "nick", "nickname"):
        val = str(data.get(key) or "").strip()
        if val:
            out.add(val)
            out.add(val.lower())
    return out


def index_inbox_raw(root: Path | None = None) -> dict[str, Path]:
    """Newest usable raw dir per folder name / author_id / nick."""
    inbox = (root or data_root()) / "inbox"
    catalog: dict[str, tuple[float, Path]] = {}
    if not inbox.is_dir():
        return {}
    for day in inbox.iterdir():
        raw_root = day / "raw"
        if not raw_root.is_dir():
            continue
        for raw in raw_root.iterdir():
            if not raw.is_dir() or not _raw_usable(raw):
                continue
            try:
                mt = raw.stat().st_mtime
            except OSError:
                continue
            for key in _state_ids(raw):
                prev = catalog.get(key)
                if not prev or mt > prev[0]:
                    catalog[key] = (mt, raw)
    return {k: p for k, (_mt, p) in catalog.items()}


def find_seed_raw(seed: str, root: Path | None = None) -> Path | None:
    seed = (seed or "").strip()
    if not seed:
        return None
    catalog = index_inbox_raw(root)
    return catalog.get(seed) or catalog.get(seed.lower())


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


def _thread_ids_touching(threads: list[dict], ids: set[str]) -> set[str]:
    out: set[str] = set()
    for t in threads:
        tid = str(t.get("thread_id") or "")
        if not tid:
            continue
        if t.get("op_id") in ids:
            out.add(tid)
            continue
        if any(c.get("author_id") in ids for c in t.get("comments") or []):
            out.add(tid)
            continue
        if any(
            lk.get("author_id") in ids or lk.get("target_id") in ids
            for lk in t.get("likes") or []
        ):
            out.add(tid)
    return out


def bundle_from_threads(
    seed: str,
    threads: list[dict[str, Any]],
    *,
    date: str = "",
    max_alters: int = 80,
    platform: str = "community",
    extra_threads: list[dict[str, Any]] | None = None,
    attached_ids: list[str] | None = None,
    max_hop2: int = 24,
) -> dict[str, Any]:
    seed = (seed or "").strip()
    day = date or date_cls.today().isoformat()
    attached_ids = [a for a in (attached_ids or []) if a and a != seed]
    extra_threads = list(extra_threads or [])
    seed_pool = list(threads)
    seed_threads = _thread_ids_for_seed(seed_pool, seed)
    scores = _score_alters(seed_pool, seed, seed_threads)
    ranked = sorted(scores, key=lambda i: (-scores[i], i))
    hop1 = set(ranked[: max(0, max_alters)])
    keep = {seed} | hop1
    hop_of: dict[str, int] = {seed: 0}
    for aid in hop1:
        hop_of[aid] = 1
    hop2: list[str] = []
    if extra_threads and attached_ids:
        all_for_hop2 = seed_pool + extra_threads
        for alter in attached_ids:
            a_threads = _thread_ids_for_seed(all_for_hop2, alter)
            a_scores = _score_alters(all_for_hop2, alter, a_threads)
            for pid in sorted(a_scores, key=lambda i: (-a_scores[i], i)):
                if pid in keep:
                    continue
                keep.add(pid)
                hop_of[pid] = 2
                hop2.append(pid)
                if len(hop2) >= max_hop2:
                    break
            if len(hop2) >= max_hop2:
                break
    threads = seed_pool + extra_threads
    active_threads = _thread_ids_touching(threads, keep)
    people: dict[str, dict] = {}
    _ensure_person(people, seed, seed)
    likes_n = 0
    likes_status = "not_collected"

    for t in threads:
        tid = str(t.get("thread_id") or "")
        if tid not in active_threads:
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
    for pid, row in people.items():
        row["hop"] = hop_of.get(pid, 1 if pid != seed else 0)
    rest = [people[i] for i in ranked if i in people and i != seed]
    rest += [people[i] for i in hop2 if i in people and i not in hop1 and i != seed]
    seen_ids = {seed}
    people_list = [people[seed]]
    for row in rest:
        if row["id"] in seen_ids:
            continue
        seen_ids.add(row["id"])
        people_list.append(row)
    return {
        "context": "community",
        "viewer_id": seed,
        "protocol": "relation-v1",
        "batch_date": day,
        "meta": {
            "platform": platform,
            "seed": seed,
            "ego": True,
            "ego_hops": 2 if attached_ids else 1,
            "n_threads": len(active_threads),
            "n_html_threads": len(threads),
            "max_alters": max_alters,
            "attached_ids": attached_ids,
            "n_hop1": len(hop1),
            "n_hop2": len(hop2),
            "likes": {"status": likes_status, "n": likes_n},
        },
        "people": people_list,
    }


def attach_existing_alters(
    seed: str,
    hop1_ids: list[str],
    raw_dir: Path,
    *,
    root: Path | None = None,
    max_attach: int = 6,
) -> tuple[list[dict[str, Any]], list[str]]:
    extra: list[dict[str, Any]] = []
    attached: list[str] = []
    catalog = index_inbox_raw(root)
    seed_raw = raw_dir.resolve()
    for aid in hop1_ids:
        if len(attached) >= max_attach:
            break
        other = catalog.get(aid) or catalog.get(aid.lower())
        if not other or other.resolve() == seed_raw:
            continue
        rows = load_threads(other)
        if not rows:
            continue
        extra.extend(rows)
        attached.append(aid)
    return extra, attached


def write_relation_artifacts(
    raw_dir: Path,
    seed: str,
    *,
    date: str = "",
    output: Path | None = None,
    max_alters: int = 80,
    platform: str = "community",
    attach_existing: bool = True,
    max_attach: int = 6,
    max_hop2: int = 24,
    data_root_override: Path | None = None,
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
    extra: list[dict[str, Any]] = []
    attached: list[str] = []
    if attach_existing:
        seed_threads = _thread_ids_for_seed(threads, seed)
        hop1 = [
            i
            for i, _s in sorted(
                _score_alters(threads, seed, seed_threads).items(),
                key=lambda kv: (-kv[1], kv[0]),
            )
        ]
        extra, attached = attach_existing_alters(
            seed,
            hop1,
            raw_dir,
            root=data_root_override,
            max_attach=max_attach,
        )
    bundle = bundle_from_threads(
        seed,
        threads,
        date=date,
        max_alters=max_alters,
        platform=platform,
        extra_threads=extra,
        attached_ids=attached,
        max_hop2=max_hop2,
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
    ap.add_argument(
        "--attach-existing",
        action="store_true",
        default=True,
        help="also read inbox raw for 1-hop ids that were already harvested",
    )
    ap.add_argument("--no-attach", dest="attach_existing", action="store_false")
    ap.add_argument("--max-attach", type=int, default=6)
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
        attach_existing=args.attach_existing,
        max_attach=args.max_attach,
    )
    print(path)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main()
