#!/usr/bin/env python3
"""Rebuild cross-thread + temporal report from seed + saved cohort_index (no crawl)."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\prjs\kampff-skills")
OUT = ROOT / "kampff-data" / "out"
RAW = ROOT / "kampff-data" / "inbox" / "2026-07-19" / "raw" / "thread_park_19230278"
BASE = "https://www.clien.net"
SEED_URL = f"{BASE}/service/board/park/19230278"

# import analyze helpers
import sys

sys.path.insert(0, str(ROOT / "scripts"))
from thread_actor_cohort import (  # noqa: E402
    analyze,
    parse_seed_thread,
    render_html,
)


def path_key(it: dict) -> str:
    p = it.get("path") or ""
    if not p and it.get("url"):
        m = re.search(r"/service/board/[a-zA-Z0-9_]+/\d+", it["url"])
        p = m.group(0) if m else it["url"]
    return p


def enrich_cross(cohort: dict, seed_url: str) -> dict:
    by = cohort.get("by_actor") or {}
    # participation: comment threads + posts (as OP of that thread)
    comment_threads: dict[str, set[str]] = defaultdict(set)
    posts: dict[str, set[str]] = defaultdict(set)
    all_part: dict[str, set[str]] = defaultdict(set)
    id_nick = {}
    for aid, blob in by.items():
        id_nick[aid] = blob.get("display_name") or aid
        for it in blob.get("comment_threads") or []:
            k = path_key(it)
            if not k:
                continue
            u = BASE + k if k.startswith("/") else k
            if u.rstrip("/") == seed_url.rstrip("/"):
                continue
            comment_threads[aid].add(k)
            all_part[aid].add("C:" + k)
        for it in blob.get("posts") or []:
            k = path_key(it)
            if not k:
                continue
            posts[aid].add(k)
            all_part[aid].add("P:" + k)

    # co-comment pairs
    thread_actors: dict[str, set[str]] = defaultdict(set)
    for aid, ths in comment_threads.items():
        for k in ths:
            thread_actors[k].add(aid)

    co_comment = Counter()
    co_comment_threads: dict[tuple, list] = defaultdict(list)
    for k, acts in thread_actors.items():
        acts = sorted(acts)
        for i in range(len(acts)):
            for j in range(i + 1, len(acts)):
                pair = (acts[i], acts[j])
                co_comment[pair] += 1
                co_comment_threads[pair].append(BASE + k)

    # A commented on B's post
    directed_engage = []
    for aid, ths in comment_threads.items():
        for k in ths:
            for bid, bposts in posts.items():
                if aid == bid:
                    continue
                if k in bposts:
                    directed_engage.append(
                        {
                            "from_id": aid,
                            "to_id": bid,
                            "from_nick": id_nick.get(aid, aid),
                            "to_nick": id_nick.get(bid, bid),
                            "type": "comment_on_post",
                            "direction": "A_to_B",
                            "thread_url": BASE + k,
                            "weight": 1,
                            "note": "A commented on thread where B is OP (index-level)",
                        }
                    )

    # co-presence any activity
    co_any = Counter()
    for i, a in enumerate(sorted(all_part.keys())):
        for b in sorted(all_part.keys())[i + 1 :]:
            inter = all_part[a] & all_part[b]
            # also comment-thread equal ignoring C:/P:
            ca = {x[2:] for x in all_part[a] if x.startswith("C:")}
            cb = {x[2:] for x in all_part[b] if x.startswith("C:")}
            pa = {x[2:] for x in all_part[a] if x.startswith("P:")}
            pb = {x[2:] for x in all_part[b] if x.startswith("P:")}
            c_inter = ca & cb
            # A comment on B post
            a_on_b = ca & pb
            b_on_a = cb & pa
            score = len(c_inter) + len(a_on_b) + len(b_on_a)
            if score:
                co_any[(a, b)] = {
                    "co_comment_threads": len(c_inter),
                    "a_commented_on_b_posts": len(a_on_b),
                    "b_commented_on_a_posts": len(b_on_a),
                    "score": score,
                    "sample_c": list(c_inter)[:5],
                    "sample_a_on_b": list(a_on_b)[:5],
                    "sample_b_on_a": list(b_on_a)[:5],
                }

    co_list = []
    for (a, b), n in co_comment.most_common(50):
        co_list.append(
            {
                "a": a,
                "b": b,
                "a_nick": id_nick.get(a, a),
                "b_nick": id_nick.get(b, b),
                "co_thread_count": n,
                "type": "co_presence",
                "undirected": True,
                "threads": co_comment_threads[(a, b)][:10],
            }
        )

    # richer pairs
    rich = []
    for (a, b), info in sorted(co_any.items(), key=lambda x: -x[1]["score"]):
        rich.append(
            {
                "a": a,
                "b": b,
                "a_nick": id_nick.get(a, a),
                "b_nick": id_nick.get(b, b),
                **info,
            }
        )

    return {
        "co_presence_pairs": co_list,
        "rich_pairs": rich,
        "directed_comment_on_post": directed_engage[:100],
        "actor_thread_counts": {k: len(v) for k, v in all_part.items()},
        "actor_comment_thread_counts": {k: len(v) for k, v in comment_threads.items()},
        "actor_post_counts": {k: len(v) for k, v in posts.items()},
        "n_cross_threads_indexed": len(thread_actors),
        "id_nick": id_nick,
    }


def main() -> None:
    seed_html = (
        ROOT
        / "kampff-data"
        / "inbox"
        / "2026-07-19"
        / "raw"
        / "thread_19230278"
        / "post.html"
    )
    seed = parse_seed_thread(seed_html.read_text(encoding="utf-8", errors="ignore"), SEED_URL)
    cohort = json.loads((RAW / "cohort" / "cohort_index.json").read_text(encoding="utf-8"))
    result = analyze(seed, cohort, focus_id="151990173")
    cross = enrich_cross(cohort, SEED_URL)
    result["cross_thread"] = cross

    # merge directed engage into edges list as separate type
    extra = []
    for e in cross.get("directed_comment_on_post") or []:
        extra.append(
            {
                **e,
                "timestamp": "",
                "snippet": e.get("note", ""),
            }
        )
    # aggregate extra
    from collections import defaultdict as dd

    bag = dd(lambda: {"weight": 0, "threads": []})
    for e in extra:
        k = (e["from_id"], e["to_id"], e["type"])
        bag[k]["weight"] += 1
        bag[k]["threads"].append(e["thread_url"])
        bag[k]["meta"] = e
    for k, v in bag.items():
        e = v["meta"]
        result["edges_directed"].append(
            {
                "from_id": e["from_id"],
                "to_id": e["to_id"],
                "from_nick": e["from_nick"],
                "to_nick": e["to_nick"],
                "type": "comment_on_post",
                "direction": "A_to_B",
                "weight": v["weight"],
                "timestamp": "",
                "snippet": f"index: A commented on B's posts ×{v['weight']}",
                "threads": v["threads"][:10],
            }
        )

    # update actor cohort fields from cross
    for a in result["actors"]:
        aid = a["author_id"]
        a["cohort_thread_index"] = cross["actor_thread_counts"].get(aid, 0)
        if aid in (cohort.get("by_actor") or {}):
            blob = cohort["by_actor"][aid]
            a["cohort_posts"] = len(blob.get("posts") or [])
            a["cohort_comment_threads"] = len(blob.get("comment_threads") or [])

    # coordination bump from rich pairs
    score = result["coordination"]["score"]
    reasons = list(result["coordination"]["reasons"])
    rich = cross.get("rich_pairs") or []
    if rich:
        top = rich[0]
        if top["score"] >= 1:
            score += min(30, 10 * top["score"])
            reasons.append(
                f"cross-thread link {top['a_nick']}–{top['b_nick']} score={top['score']} "
                f"(co_cmt={top['co_comment_threads']}, a_on_b={top['a_commented_on_b_posts']}, b_on_a={top['b_commented_on_a_posts']})"
            )
    engage_n = len(cross.get("directed_comment_on_post") or [])
    if engage_n:
        score += min(20, engage_n)
        reasons.append(f"directed comment_on_post events: {engage_n}")
    # anti already applied in analyze
    score = max(0, min(100, score))
    read = (
        "none"
        if score < 20
        else "weak"
        if score < 40
        else "moderate"
        if score < 65
        else "strong_signals"
    )
    result["coordination"] = {"score": score, "read": read, "reasons": reasons}
    result["summary"]["one_line"] = (
        f"{result['summary']['n_actors']} actors · directed seed replies="
        f"{result['summary']['n_directed_events']} · "
        f"cross comment_on_post={engage_n} · rich_pairs={len(rich)} · "
        f"coord `{read}` · cohort=3 actors park"
    )
    result["summary"]["goal_status"] = {
        "cross_thread": "partial_3_actors",
        "temporal_seed": "ok",
        "directed_network": "ok",
        "next": "expand more actors slowly; optional sample-fetch overlapping threads for timestamps",
    }
    result["edge_legend"]["comment_on_post"] = (
        "A → B : A appeared as commenter on a thread B authored (search index)"
    )

    # temporal seed already from analyze events
    base = OUT / "2026-07-19-thread-park_19230278-actors"
    (Path(str(base) + ".json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    render_html(result, Path(str(base) + ".html"))

    # append cross section patch into html (render_html may be thin on rich pairs)
    hp = Path(str(base) + ".html")
    html = hp.read_text(encoding="utf-8")
    rich_rows = []
    for p in rich[:20]:
        rich_rows.append(
            f"<tr><td>{p['a_nick']}</td><td>{p['b_nick']}</td>"
            f"<td>{p['co_comment_threads']}</td>"
            f"<td class='dir'>{p['a_commented_on_b_posts']} →</td>"
            f"<td class='dir'>← {p['b_commented_on_a_posts']}</td>"
            f"<td>{p['score']}</td></tr>"
        )
    eng_rows = []
    for e in result["edges_directed"]:
        if e.get("type") != "comment_on_post":
            continue
        eng_rows.append(
            f"<tr><td><b>{e['from_nick']}</b></td><td class='dir'>→</td>"
            f"<td><b>{e['to_nick']}</b></td><td>w={e['weight']}</td>"
            f"<td style='font-size:11px'>{', '.join((e.get('threads') or [])[:3])}</td></tr>"
        )
    block = f"""
<section class="card" id="cross-rich">
<h2><span class="n">X</span> Cross-thread (cohort park index)</h2>
<p>Expanded actors: 산좋아함, fiat, ISLAY · board=park · pages=1 · human-paced.</p>
<p><b>Directed</b> <span class="dir">A → B</span> = A commented on a post authored by B (index-level).</p>
<table><tr><th>from</th><th></th><th>to</th><th>w</th><th>sample threads</th></tr>
{''.join(eng_rows) or '<tr><td colspan=5>none</td></tr>'}
</table>
<h3>Pair scores</h3>
<table><tr><th>A</th><th>B</th><th>co-comment thr</th><th>A on B posts</th><th>B on A posts</th><th>score</th></tr>
{''.join(rich_rows) or '<tr><td colspan=6>none</td></tr>'}
</table>
</section>
"""
    if "</footer>" in html:
        html = html.replace("</footer>", block + "\n<footer>")
    else:
        html += block
    # ensure .dir style
    if ".dir{" not in html and ".dir {" not in html:
        html = html.replace(
            "</style>",
            ".dir{color:#5eead4;font-weight:700;font-family:var(--mono)}</style>",
        )
    hp.write_text(html, encoding="utf-8")

    print("one_line", result["summary"]["one_line"])
    print("coord", result["coordination"])
    print("rich", rich[:5])
    print("engage", engage_n)
    for e in result["edges_directed"]:
        if e.get("type") == "comment_on_post":
            print(" DIR", e["from_nick"], "→", e["to_nick"], "w", e["weight"])


if __name__ == "__main__":
    main()
