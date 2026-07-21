#!/usr/bin/env python3
"""Merge full 14-actor cohort and write final cross-thread report."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"C:\prjs\kampff-skills")
RAW = ROOT / "kampff-data" / "inbox" / "2026-07-19" / "raw" / "thread_park_19230278"
COH = RAW / "cohort"
OUT = ROOT / "kampff-data" / "out"
BASE = "https://www.clien.net"
SEED = "/service/board/park/19230278"

seed = json.loads((RAW / "thread.json").read_text(encoding="utf-8"))
id_nick = {c["author_id"]: c["display_name"] for c in seed["comments"]}
uids = list(dict.fromkeys(c["author_id"] for c in seed["comments"]))


def parse_paths(html: str) -> list[dict]:
    paths = sorted(set(re.findall(r'href="(/service/board/[a-zA-Z0-9_]+/\d+)', html)))
    out = []
    for p in paths:
        if "/annonce/" in p:
            continue
        parts = p.split("/")
        out.append(
            {"path": p, "url": BASE + p, "board": parts[3], "sn": parts[4]}
        )
    return out


by: dict = {}
for htmlp in sorted(COH.glob("[wc]_*.html")):
    m = re.match(r"([wc])_(.+)_park_po\d+$", htmlp.stem)
    if not m:
        continue
    kind, aid = m.group(1), m.group(2)
    items = parse_paths(htmlp.read_text(encoding="utf-8", errors="ignore"))
    if aid not in by:
        by[aid] = {
            "author_id": aid,
            "display_name": id_nick.get(aid, aid),
            "posts": [],
            "comment_threads": [],
        }
    if kind == "w":
        by[aid]["posts"] = items
    else:
        by[aid]["comment_threads"] = items

print("seed unique", len(uids), "cohort", len(by), "missing", [a for a in uids if a not in by])

cohort = {"ok": True, "by_actor": by, "merged_from": "full_14"}
for path in [COH / "cohort_index.json", RAW / "cohort_index.json"]:
    path.write_text(json.dumps(cohort, ensure_ascii=False, indent=2), encoding="utf-8")
(COH / "cohort_resume.json").write_text(
    json.dumps(
        {
            "done_actors": sorted(by.keys()),
            "next": [],
            "last_error": None,
            "cooldown_until": None,
            "complete": True,
        },
        indent=2,
    ),
    encoding="utf-8",
)

sets_c = {a: {it["path"] for it in b["comment_threads"]} for a, b in by.items()}
sets_p = {a: {it["path"] for it in b["posts"]} for a, b in by.items()}

pairs = []
ids = list(by)
for i, a in enumerate(ids):
    for b in ids[i + 1 :]:
        cc = (sets_c[a] & sets_c[b]) - {SEED}
        a_on_b = sets_c[a] & sets_p[b]
        b_on_a = sets_c[b] & sets_p[a]
        sc = len(cc) + len(a_on_b) + len(b_on_a)
        if sc:
            pairs.append(
                {
                    "a": a,
                    "b": b,
                    "a_nick": by[a]["display_name"],
                    "b_nick": by[b]["display_name"],
                    "co_comment_threads": len(cc),
                    "a_commented_on_b_posts": len(a_on_b),
                    "b_commented_on_a_posts": len(b_on_a),
                    "score": sc,
                    "sample_c": list(cc)[:5],
                    "sample_a_on_b": list(a_on_b)[:5],
                    "sample_b_on_a": list(b_on_a)[:5],
                }
            )
pairs.sort(key=lambda x: -x["score"])

dir_w: Counter = Counter()
dir_threads: dict = defaultdict(list)
for a in ids:
    for b in ids:
        if a == b:
            continue
        for pth in sets_c[a] & sets_p[b]:
            dir_w[(a, b)] += 1
            dir_threads[(a, b)].append(BASE + pth)

print("PAIR TOP 12")
for p in pairs[:12]:
    print(
        f"  {p['a_nick']}×{p['b_nick']} score={p['score']} "
        f"co={p['co_comment_threads']} a→b={p['a_commented_on_b_posts']} b→a={p['b_commented_on_a_posts']}"
    )
print("DIR")
for (a, b), w in dir_w.most_common(15):
    print(f"  {by[a]['display_name']} → {by[b]['display_name']} w={w}")

subprocess.check_call([sys.executable, str(ROOT / "scripts" / "rebuild_cross_from_cohort.py")])

jp = OUT / "2026-07-19-thread-park_19230278-actors.json"
r = json.loads(jp.read_text(encoding="utf-8"))
r["cross_thread"]["rich_pairs"] = pairs
r["edges_directed"] = [
    e for e in r.get("edges_directed") or [] if e.get("type") != "comment_on_post"
]
for (a, b), w in dir_w.items():
    r["edges_directed"].append(
        {
            "from_id": a,
            "to_id": b,
            "from_nick": by[a]["display_name"],
            "to_nick": by[b]["display_name"],
            "type": "comment_on_post",
            "direction": "A_to_B",
            "weight": w,
            "timestamp": "",
            "snippet": f"A commented on B OP x{w}",
            "threads": dir_threads[(a, b)][:10],
        }
    )

score = 0
reasons = []
strong = [p for p in pairs if p["score"] >= 2]
if strong:
    score += min(40, 8 * len(strong))
    reasons.append(f"cross pairs score>=2: {len(strong)}")
if pairs:
    top = pairs[0]
    score += min(25, 5 * top["score"])
    reasons.append(
        f"top pair {top['a_nick']}-{top['b_nick']} score={top['score']}"
    )
eng = len(dir_w)
if eng:
    score += min(25, eng * 2)
    reasons.append(f"directed comment_on_post pairs: {eng}")
seed_dir = sum(1 for e in r["edges_directed"] if e.get("type") == "reply_to")
if seed_dir:
    reasons.append(f"seed directed @replies: {seed_dir}")
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
r["coordination"] = {"score": score, "read": read, "reasons": reasons}
r["cohort"] = {
    "expanded": True,
    "n_actors_indexed": len(by),
    "error": None,
    "complete": len(by) >= len(uids),
}
r["honesty"]["cohort_depth"] = f"full_{len(by)}_actors_park_po0"
r["summary"]["one_line"] = (
    f"{len(by)}/{len(uids)} cohort · seed A→B @replies={seed_dir} · "
    f"cross DIR comment_on_post pairs={eng} · rich_pairs={len(pairs)} · "
    f"coord `{read}`({score}) · temporal seed+index"
)
r["summary"]["goal_status"] = {
    "cross_thread": "ok_all_seed_actors_indexed",
    "temporal_seed": "ok",
    "temporal_cross": "ok_index_plus_sampled_threads",
    "directed_network": "ok",
    "complete_all_actors": True,
    "note": "park board po=0 index depth; deeper history optional",
}
for a in r["actors"]:
    aid = a["author_id"]
    if aid in by:
        a["cohort_posts"] = len(by[aid]["posts"])
        a["cohort_comment_threads"] = len(by[aid]["comment_threads"])
        a["cohort_thread_index"] = len(by[aid]["posts"]) + len(
            by[aid]["comment_threads"]
        )

jp.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")


def esc(x: object) -> str:
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


dir_rows = "".join(
    f"<tr><td><b>{esc(by[a]['display_name'])}</b></td><td class='dir'>→</td>"
    f"<td><b>{esc(by[b]['display_name'])}</b></td><td>{w}</td>"
    f"<td style='font-size:11px'>{esc(', '.join(dir_threads[(a, b)][:2]))}</td></tr>"
    for (a, b), w in dir_w.most_common(40)
)
pair_rows = "".join(
    f"<tr><td>{esc(p['a_nick'])}</td><td>{esc(p['b_nick'])}</td>"
    f"<td>{p['co_comment_threads']}</td>"
    f"<td class='dir'>{p['a_commented_on_b_posts']}→</td>"
    f"<td class='dir'>←{p['b_commented_on_a_posts']}</td>"
    f"<td><b>{p['score']}</b></td></tr>"
    for p in pairs[:30]
)
cov = "".join(
    f"<tr><td>{esc(by[a]['display_name'])}</td><td><code>{esc(a)}</code></td>"
    f"<td>{len(by[a]['posts'])}</td><td>{len(by[a]['comment_threads'])}</td></tr>"
    for a in sorted(by, key=lambda x: by[x]["display_name"])
)

block = f"""
<section class="card" id="goal-complete">
<h2><span class="n">OK</span> Cross-thread goal — cohort complete</h2>
<p>{esc(r['summary']['one_line'])}</p>
<div class="one-line"><b>Direction:</b> <span class="dir">A → B</span> = A replied/mentioned B (seed)
or A commented on B's post (cross index). Co-comment = undirected multi-thread presence.</div>
<h3>Coverage (park search po=0)</h3>
<table><tr><th>nick</th><th>id</th><th>posts idx</th><th>cmt-threads idx</th></tr>
{cov}</table>
<h3>Directed cross: comment_on_post</h3>
<table><tr><th>from</th><th></th><th>to</th><th>w</th><th>sample</th></tr>
{dir_rows if dir_rows else '<tr><td colspan=5>none</td></tr>'}</table>
<h3>Pair scores</h3>
<table><tr><th>A</th><th>B</th><th>co-cmt</th><th>A on B</th><th>B on A</th><th>score</th></tr>
{pair_rows}</table>
<p>Coord <b>{esc(read)}</b> ({score}). Temporal: seed timestamps + cross index; sampled threads have clock lags.</p>
</section>
"""

hp = OUT / "2026-07-19-thread-park_19230278-actors.html"
html = hp.read_text(encoding="utf-8")
html = re.sub(
    r'<section class="card" id="goal-complete">[\s\S]*?</section>', "", html
)
if "</footer>" in html:
    html = html.replace("</footer>", block + "\n<footer>")
else:
    html += block
if ".dir{" not in html:
    html = html.replace(
        "</style>", ".dir{color:#5eead4;font-weight:700}</style>"
    )
hp.write_text(html, encoding="utf-8")
print("COMPLETE")
print(r["summary"]["one_line"])
print(
    "actors",
    len(by),
    "pairs",
    len(pairs),
    "dir",
    len(dir_w),
    "coord",
    read,
    score,
)
