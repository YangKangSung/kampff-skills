#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a Kampff relation graph from a multi-person bundle.

Layer 2 only. Node distance is an optional L1 join — never inferred from centrality.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z]{3,}|[가-힣]{2,}")
MENTION_RE = re.compile(r"@([A-Za-z0-9_\.]{2,})")
NEAR_DUP = 0.45

LEVEL_NAME = {
    1: "observe",
    2: "repeat",
    3: "reciprocal",
    4: "sync",
    5: "brigade",
}


def tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall((text or "").lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _pid(p: dict) -> str:
    return str(p.get("id") or "").strip()


def _nick(p: dict) -> str:
    return str(p.get("display_name") or p.get("nick") or p.get("id") or "").strip()


def _day(ts: str) -> str:
    t = str(ts or "")
    return t[:10] if len(t) >= 10 else ""


def _reply_to(text: dict, id_set: set[str], nick_map: dict[str, str]) -> str:
    raw = text.get("reply_to") or text.get("reply_to_id") or text.get("parent_author_id") or ""
    rid = str(raw).strip().lstrip("@")
    if rid in id_set:
        return rid
    if rid:
        for pid, nick in nick_map.items():
            if nick.lower() == rid.lower():
                return pid
    return ""


def _mentions(text: dict, id_set: set[str], nick_map: dict[str, str]) -> list[str]:
    body = str(text.get("content") or "")
    hits = []
    for m in MENTION_RE.findall(body):
        if m in id_set:
            hits.append(m)
            continue
        for pid, nick in nick_map.items():
            if nick.lower() == m.lower():
                hits.append(pid)
    extra = text.get("mentions") or []
    if isinstance(extra, list):
        for x in extra:
            s = str(x).strip().lstrip("@")
            if s in id_set:
                hits.append(s)
    return list(dict.fromkeys(hits))


def load_distance_map(analysis_paths: list[Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in analysis_paths:
        try:
            data = json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        tid = str((data.get("target") or {}).get("id") or "")
        dist = str(data.get("distance") or "").lower()
        if tid and dist in ("engage", "neutral", "caution", "avoid"):
            out[tid] = dist
    return out


LIKE_TYPES = {"like", "liked", "sympathy", "recommend"}
LIKE_SOURCES = {"community_like", "sns_like"}


def _is_like(text: dict) -> bool:
    return str(text.get("type") or "").lower() in LIKE_TYPES or str(
        text.get("source") or ""
    ).lower() in LIKE_SOURCES


def ego_graph(graph: dict, seed: str, hops: int = 1) -> dict:
    """Keep seed + neighbors within hops. Seed role is never inferred from degree."""
    seed = (seed or "").strip()
    if not seed:
        return graph
    hops = max(1, int(hops or 1))
    keep = {seed}
    frontier = {seed}
    for _ in range(hops):
        nxt: set[str] = set()
        for e in graph.get("edges") or []:
            a, b = str(e.get("source") or ""), str(e.get("target") or "")
            if a in frontier and b:
                nxt.add(b)
            if b in frontier and a:
                nxt.add(a)
        keep |= nxt
        frontier = nxt
    nodes = []
    for n in graph.get("nodes") or []:
        if n.get("id") not in keep:
            continue
        row = dict(n)
        if row.get("id") == seed:
            row["role"] = "seed"
        nodes.append(row)
    if seed not in {n["id"] for n in nodes}:
        nodes.insert(
            0,
            {
                "id": seed,
                "nick": seed,
                "distance": None,
                "n_texts": 0,
                "degree": 0,
                "coord_score": 0,
                "role": "seed",
            },
        )
    keep_ids = {n["id"] for n in nodes}
    edges = [
        e
        for e in (graph.get("edges") or [])
        if e.get("source") in keep_ids and e.get("target") in keep_ids
    ]
    for n in nodes:
        n["degree"] = sum(1 for e in edges if n["id"] in (e.get("source"), e.get("target")))
    coord = dict(graph.get("coordination") or {})
    clusters = []
    for c in coord.get("clusters") or []:
        members = [m for m in (c.get("member_ids") or []) if m in keep_ids]
        if len(members) >= 2:
            row = dict(c)
            row["member_ids"] = members
            clusters.append(row)
    coord["clusters"] = clusters
    meta = dict(graph.get("meta") or {})
    meta["seed"] = seed
    meta["ego"] = True
    meta["ego_hops"] = hops
    meta["n_nodes"] = len(nodes)
    meta["n_edges"] = len(edges)
    out = dict(graph)
    out["meta"] = meta
    out["viewer"] = {"id": seed}
    out["nodes"] = nodes
    out["edges"] = edges
    out["coordination"] = coord
    return out


def build_graph(
    bundle: dict,
    *,
    distances: dict[str, str] | None = None,
    date: str = "",
    seed: str = "",
    hops: int = 1,
) -> dict:
    people = [p for p in (bundle.get("people") or []) if isinstance(p, dict) and _pid(p)]
    id_set = {_pid(p) for p in people}
    nick_map = {_pid(p): _nick(p) for p in people}
    viewer = str(bundle.get("viewer_id") or (bundle.get("viewer") or {}).get("id") or "")
    meta = bundle.get("meta") or {}
    explicit_seed = bool((seed or "").strip())
    seed = (seed or str(meta.get("seed") or "")).strip()
    distances = distances or {}

    texts_by: dict[str, list[dict]] = {}
    for p in people:
        pid = _pid(p)
        rows = []
        for t in p.get("texts") or []:
            if not isinstance(t, dict):
                continue
            row = dict(t)
            row["_pid"] = pid
            row["_tok"] = tokens(str(t.get("content") or ""))
            rows.append(row)
        texts_by[pid] = rows

    replies: dict[tuple[str, str], int] = defaultdict(int)
    reply_snips: dict[tuple[str, str], list[str]] = defaultdict(list)
    mentions: dict[tuple[str, str], int] = defaultdict(int)
    likes: dict[tuple[str, str], int] = defaultdict(int)
    thread_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    burst: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for pid, rows in texts_by.items():
        for t in rows:
            if _is_like(t):
                tgt = _reply_to(t, id_set, nick_map) or str(t.get("like_of") or "").strip()
                if tgt and tgt != pid:
                    likes[(pid, tgt)] += 1
                continue
            tid = str(t.get("thread_id") or "").strip()
            if tid:
                thread_counts[tid][pid] += 1
                d = _day(str(t.get("timestamp") or ""))
                if d:
                    burst[(tid, d)][pid] += 1
            tgt = _reply_to(t, id_set, nick_map)
            if tgt and tgt != pid:
                replies[(pid, tgt)] += 1
                snip = str(t.get("content") or "")[:160]
                if snip and len(reply_snips[(pid, tgt)]) < 3:
                    reply_snips[(pid, tgt)].append(snip)
            for m in _mentions(t, id_set, nick_map):
                if m != pid:
                    mentions[(pid, m)] += 1

    co_thread: dict[tuple[str, str], int] = defaultdict(int)
    for tid, counts in thread_counts.items():
        active = [a for a, n in counts.items() if n >= 2]
        for i, a in enumerate(sorted(active)):
            for b in sorted(active)[i + 1 :]:
                co_thread[tuple(sorted((a, b)))] += 1

    burst_pairs: dict[tuple[str, str], list[str]] = defaultdict(list)
    for (tid, day), counts in burst.items():
        hot = [a for a, n in counts.items() if n >= 2]
        for i, a in enumerate(sorted(hot)):
            for b in sorted(hot)[i + 1 :]:
                key = tuple(sorted((a, b)))
                label = f"{day}:{tid}"
                if label not in burst_pairs[key]:
                    burst_pairs[key].append(label)

    near: dict[tuple[str, str], dict[str, Any]] = {}
    pids = sorted(texts_by)
    for i, a in enumerate(pids):
        for b in pids[i + 1 :]:
            best = 0.0
            pair_snips: list[str] = []
            for ta in texts_by[a]:
                if _is_like(ta) or len(ta["_tok"]) < 4:
                    continue
                for tb in texts_by[b]:
                    if _is_like(tb) or len(tb["_tok"]) < 4:
                        continue
                    j = jaccard(ta["_tok"], tb["_tok"])
                    if j > best:
                        best = j
                        pair_snips = [
                            str(ta.get("content") or "")[:160],
                            str(tb.get("content") or "")[:160],
                        ]
            if best >= NEAR_DUP:
                near[tuple(sorted((a, b)))] = {"jaccard": round(best, 3), "quotes": pair_snips}

    pair_keys: set[tuple[str, str]] = set()
    pair_keys |= {tuple(sorted(k)) for k in replies}
    pair_keys |= {tuple(sorted(k)) for k in mentions}
    pair_keys |= {tuple(sorted(k)) for k in likes}
    pair_keys |= set(co_thread)
    pair_keys |= set(burst_pairs)
    pair_keys |= set(near)

    edges = []
    for a, b in sorted(pair_keys):
        ab = replies.get((a, b), 0)
        ba = replies.get((b, a), 0)
        m_ab = mentions.get((a, b), 0)
        m_ba = mentions.get((b, a), 0)
        co = co_thread.get((a, b), 0)
        bursts = burst_pairs.get((a, b), [])
        dup = near.get((a, b))
        parts = []
        if ab:
            parts.append(
                {
                    "kind": "replies_to",
                    "from": a,
                    "to": b,
                    "n": ab,
                    "level": 3 if ba else (2 if ab >= 3 else 1),
                    "quotes": reply_snips.get((a, b), []),
                }
            )
        if ba:
            parts.append(
                {
                    "kind": "replies_to",
                    "from": b,
                    "to": a,
                    "n": ba,
                    "level": 3 if ab else (2 if ba >= 3 else 1),
                    "quotes": reply_snips.get((b, a), []),
                }
            )
        lk_ab = likes.get((a, b), 0)
        lk_ba = likes.get((b, a), 0)
        if m_ab or m_ba:
            parts.append(
                {
                    "kind": "mention",
                    "n": m_ab + m_ba,
                    "level": 1,
                }
            )
        if lk_ab or lk_ba:
            parts.append(
                {
                    "kind": "likes",
                    "n": lk_ab + lk_ba,
                    "level": 2 if max(lk_ab, lk_ba) >= 3 else 1,
                    "from": a if lk_ab else b,
                    "to": b if lk_ab else a,
                }
            )
        if co:
            parts.append(
                {
                    "kind": "co_thread",
                    "n": co,
                    "level": 2 if co >= 3 else 1,
                }
            )
        if bursts:
            parts.append(
                {
                    "kind": "burst_sync",
                    "n": len(bursts),
                    "level": 4,
                    "windows": bursts[:8],
                }
            )
        if dup:
            parts.append(
                {
                    "kind": "near_dup",
                    "n": 1,
                    "level": 5 if bursts else 4,
                    "jaccard": dup["jaccard"],
                    "quotes": dup["quotes"],
                }
            )
        if not parts:
            continue
        level = max(int(p["level"]) for p in parts)
        if dup and bursts:
            level = 5
        elif ab and ba:
            level = max(level, 3)
        weight = ab + ba + co + 2 * len(bursts) + (3 if dup else 0) + m_ab + m_ba + lk_ab + lk_ba
        kinds = list(dict.fromkeys(p["kind"] for p in parts))
        edges.append(
            {
                "source": a,
                "target": b,
                "level": level,
                "level_name": LEVEL_NAME[level],
                "weight": weight,
                "kinds": kinds,
                "confidence": "hypothesis" if level >= 4 else "observed",
                "parts": parts,
            }
        )

    # clusters walk near-dup / brigade only — same-thread heat (L4 burst) is not membership
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        if e["level"] >= 5 or "near_dup" in (e.get("kinds") or []):
            adj[e["source"]].add(e["target"])
            adj[e["target"]].add(e["source"])
    seen: set[str] = set()
    clusters = []
    cid = 1
    for start in sorted(adj):
        if start in seen:
            continue
        stack = [start]
        comp: set[str] = set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            comp.add(n)
            stack.extend(adj[n] - seen)
        if len(comp) < 2:
            continue
        reasons = []
        sub = [e for e in edges if e["source"] in comp and e["target"] in comp and e["level"] >= 4]
        if any("near_dup" in e["kinds"] for e in sub):
            reasons.append("near-duplicate talking points")
        if any("burst_sync" in e["kinds"] for e in sub):
            reasons.append("same-thread same-day bursts")
        if any(e["level"] == 5 for e in sub):
            reasons.append("brigade stack (near-dup + burst)")
        score = min(100, 20 * len(comp) + 8 * sum(e["level"] for e in sub))
        read = (
            "none"
            if score < 20
            else "weak"
            if score < 40
            else "moderate"
            if score < 65
            else "strong_signals"
        )
        clusters.append(
            {
                "id": f"C{cid}",
                "member_ids": sorted(comp),
                "score": score,
                "read": read,
                "reasons": reasons or ["L4+ component"],
            }
        )
        cid += 1

    coord_of: dict[str, int] = defaultdict(int)
    for c in clusters:
        for mid in c["member_ids"]:
            coord_of[mid] = max(coord_of[mid], int(c["score"]))

    nodes = []
    for p in people:
        pid = _pid(p)
        n_texts = len(texts_by.get(pid) or [])
        if n_texts == 0 and pid not in {viewer, seed}:
            continue
        deg = sum(1 for e in edges if pid in (e["source"], e["target"]))
        role = "alter"
        if pid == seed:
            role = "seed"
        elif pid == viewer:
            role = "viewer"
        nodes.append(
            {
                "id": pid,
                "nick": _nick(p),
                "distance": distances.get(pid) or None,
                "n_texts": n_texts,
                "degree": deg,
                "coord_score": coord_of.get(pid, 0),
                "role": role,
            }
        )
    keep = {n["id"] for n in nodes}
    edges = [e for e in edges if e["source"] in keep and e["target"] in keep]
    likes_meta = meta.get("likes") if isinstance(meta.get("likes"), dict) else {}

    graph = {
        "meta": {
            "date": date or str(bundle.get("batch_date") or datetime.now().strftime("%Y-%m-%d")),
            "platform": str(meta.get("platform") or bundle.get("context") or "community"),
            "protocol": "relation-v1",
            "synthetic": bool(meta.get("synthetic") or bundle.get("synthetic")),
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "seed": seed or None,
            "likes": likes_meta
            or {
                "status": "collected" if likes else "not_collected",
                "n": int(sum(likes.values())),
            },
        },
        "viewer": {"id": seed or viewer or "me"},
        "nodes": nodes,
        "edges": edges,
        "coordination": {
            "clusters": clusters,
            "disclaimer": "Public-text hypothesis. Not legal proof of a coordinated campaign.",
        },
    }
    if seed:
        for n in graph["nodes"]:
            if n["id"] == seed:
                n["role"] = "seed"
        graph["meta"]["seed"] = seed
        graph["viewer"] = {"id": seed}
        if explicit_seed:
            graph = ego_graph(graph, seed, hops=hops)
    return graph


def write_graph(graph: dict, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def bundle_to_graph_path(bundle_path: str | Path) -> Path:
    p = Path(bundle_path)
    name = p.name
    if name.endswith("-bundle.json"):
        return p.with_name(name[: -len("-bundle.json")] + "-graph.json")
    if name == "bundle.json":
        return p.with_name("graph.json")
    if name.endswith(".json"):
        return p.with_name(name[: -len(".json")] + "-graph.json")
    return p.with_suffix(".graph.json")


def graph_to_html_path(graph_path: str | Path) -> Path:
    p = Path(graph_path)
    if p.name.endswith("-graph.json"):
        return p.with_name(p.name[: -len("-graph.json")] + "-graph.html")
    if p.name.endswith(".json"):
        return p.with_name(p.name[: -len(".json")] + ".html")
    return p.with_suffix(".html")
