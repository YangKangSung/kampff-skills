#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime

OUT = Path(r"C:\prjs\kampff-skills\kampff-data\out")
RAW = Path(
    r"C:\prjs\kampff-skills\kampff-data\inbox\2026-07-19\raw\thread_park_19230278"
)
jp = OUT / "2026-07-19-thread-park_19230278-actors.json"
r = json.loads(jp.read_text(encoding="utf-8"))
batch = json.loads(
    (RAW / "cohort" / "overlap_batch_wave2.json").read_text(encoding="utf-8")
)
prev = r.get("cross_thread", {}).get("overlap_evidence") or []


def iso(ts: str) -> str:
    if not ts:
        return ""
    ts = ts.replace(" ", "T")
    if len(ts) == 16:
        ts += ":00"
    if "+" not in ts:
        ts += "+09:00"
    return ts


COHORT = {
    "gunugunu",
    "crowking",
    "cv_clien",
    "ddoari",
    "pareto2025",
    "ericartman",
}

evidence = []
for th in batch:
    cmts = th["comments"]
    for c in cmts:
        c["timestamp"] = iso(c["timestamp"])
    timed = sorted([c for c in cmts if c["timestamp"]], key=lambda x: x["timestamp"])
    lags = []
    for i in range(1, len(timed)):
        t0 = datetime.fromisoformat(timed[i - 1]["timestamp"])
        t1 = datetime.fromisoformat(timed[i]["timestamp"])
        lags.append(
            {
                "from": timed[i - 1]["display_name"],
                "to": timed[i]["display_name"],
                "lag_sec": (t1 - t0).total_seconds(),
                "direction_time": f"{timed[i-1]['display_name']} then {timed[i]['display_name']}",
            }
        )
    op_id = th.get("op_id")
    directed = []
    for c in cmts:
        if op_id and c["author_id"] != op_id and op_id in COHORT:
            directed.append(
                {
                    "from_id": c["author_id"],
                    "from_nick": c["display_name"],
                    "to_id": op_id,
                    "to_nick": th.get("op_nick"),
                    "type": "comment_on_post",
                    "timestamp": c["timestamp"],
                    "direction": f"{c['display_name']} → {th.get('op_nick')}",
                }
            )
    evidence.append(
        {
            "thread_url": th["url"],
            "thread_title": th["title"],
            "op_nick": th.get("op_nick"),
            "op_id": op_id,
            "cohort_comments": cmts,
            "temporal_lags": lags,
            "directed_on_thread": directed,
        }
    )

by_url = {e["thread_url"]: e for e in prev}
for e in evidence:
    by_url[e["thread_url"]] = e
r.setdefault("cross_thread", {})["overlap_evidence"] = list(by_url.values())

for e in by_url.values():
    for c in e.get("cohort_comments") or []:
        r.setdefault("events_temporal", []).append(
            {
                "timestamp": c.get("timestamp") or "",
                "actor_id": c.get("author_id"),
                "actor_nick": c.get("display_name"),
                "event": "comment",
                "thread_url": e["thread_url"],
                "target_id": e.get("op_id") if e.get("op_id") in COHORT else None,
                "label": f"[cross] {(c.get('content') or '')[:80]}",
            }
        )
r["events_temporal"] = sorted(
    r.get("events_temporal") or [], key=lambda x: x.get("timestamp") or "9999"
)

idx = json.loads((RAW / "cohort" / "cohort_index.json").read_text(encoding="utf-8"))
n_coh = len(idx.get("by_actor") or {})
rich = r.get("cross_thread", {}).get("rich_pairs") or []
engage = sum(
    1 for e in r.get("edges_directed") or [] if e.get("type") == "comment_on_post"
)

r["summary"]["one_line"] = (
    f"14 seed actors · cohort expanded {n_coh}/14 · "
    f"seed A→B replies=2 · cross comment_on_post edges={engage} · "
    f"rich_pairs={len(rich)} · coord `{r['coordination']['read']}` · temporal seed+cross"
)
r["summary"]["goal_status"] = {
    "cross_thread": f"partial_{n_coh}_of_14_actors",
    "temporal_seed": "ok",
    "temporal_cross": f"ok_{len(by_url)}_threads_sampled",
    "directed_network": "ok_seed_and_cross_comment_on_post",
    "complete_all_actors": n_coh >= 14,
    "next": "wave expand remaining actors human-paced"
    if n_coh < 14
    else "done",
}
r["cohort"] = {"expanded": True, "error": None, "n_actors_indexed": n_coh}
r["honesty"]["cohort_depth"] = f"partial_{n_coh}_actors_park_po0"

jp.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")


def esc(x):
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


rows = []
for e in by_url.values():
    rows.append(
        f"<tr><td colspan=3><b><a href='{esc(e['thread_url'])}'>"
        f"{esc((e.get('thread_title') or '')[:60])}</a></b> · OP {esc(e.get('op_nick'))}</td></tr>"
    )
    for c in e.get("cohort_comments") or []:
        rows.append(
            f"<tr><td><code>{esc(c.get('timestamp'))}</code></td>"
            f"<td><b>{esc(c.get('display_name'))}</b></td>"
            f"<td>{esc((c.get('content') or '')[:140])}</td></tr>"
        )
    for L in e.get("temporal_lags") or []:
        rows.append(
            f"<tr><td colspan=3 class='dir'>time-order: {esc(L['direction_time'])} · "
            f"lag {int(L['lag_sec'])}s</td></tr>"
        )
    for d in e.get("directed_on_thread") or []:
        rows.append(
            f"<tr><td colspan=3 class='dir'>DIR {esc(d['direction'])} @ "
            f"{esc(d.get('timestamp'))}</td></tr>"
        )

rich_rows = []
for p in rich:
    rich_rows.append(
        f"<tr><td>{esc(p.get('a_nick', p.get('a')))}</td>"
        f"<td>{esc(p.get('b_nick', p.get('b')))}</td>"
        f"<td>{p.get('co_comment_threads', 0)}</td>"
        f"<td class='dir'>{p.get('a_commented_on_b_posts', 0)} →</td>"
        f"<td class='dir'>← {p.get('b_commented_on_a_posts', 0)}</td>"
        f"<td>{p.get('score')}</td></tr>"
    )

block = f"""
<section class="card" id="goal-progress">
<h2><span class="n">G</span> Cross-thread + temporal progress</h2>
<p>{esc(r['summary']['one_line'])}</p>
<table>
<tr><th>metric</th><th>value</th></tr>
<tr><td>cohort actors expanded</td><td><b>{n_coh}/14</b></td></tr>
<tr><td>rich pairs</td><td>{len(rich)}</td></tr>
<tr><td>directed comment_on_post</td><td>{engage}</td></tr>
<tr><td>coord</td><td>{esc(r['coordination']['read'])} ({r['coordination']['score']})</td></tr>
<tr><td>overlap threads sampled</td><td>{len(by_url)}</td></tr>
</table>
<h3>Pair scores (index)</h3>
<table><tr><th>A</th><th>B</th><th>co-cmt</th><th>A on B</th><th>B on A</th><th>score</th></tr>
{''.join(rich_rows)}
</table>
<h3>Sampled cross threads (with time)</h3>
<table><tr><th>time</th><th>actor</th><th>content / note</th></tr>
{''.join(rows)}
</table>
<div class="one-line"><b>Key directed cross:</b> 산좋아함 → MO42 · MO42 → 올데포.
<strong>또아리×올데포</strong> strongest co-comment (3). Temporal on seed + sampled cross threads.</div>
</section>
"""

hp = OUT / "2026-07-19-thread-park_19230278-actors.html"
html = hp.read_text(encoding="utf-8")
html = re.sub(
    r'<section class="card" id="goal-progress">[\s\S]*?</section>', "", html
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
print("DONE")
print(r["summary"]["one_line"])
print("goal", r["summary"]["goal_status"])
print("threads", list(by_url.keys()))
