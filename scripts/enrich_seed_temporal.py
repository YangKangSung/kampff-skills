#!/usr/bin/env python3
"""Seed temporal enrichment + bot-wall cooldown; no further crawl."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(r"C:\prjs\kampff-skills")
OUT = ROOT / "kampff-data" / "out"
RAW = ROOT / "kampff-data" / "inbox" / "2026-07-19" / "raw" / "thread_park_19230278"
RAW.mkdir(parents=True, exist_ok=True)
(RAW / "cohort").mkdir(exist_ok=True)

cd_until = (datetime.now() + timedelta(minutes=45)).isoformat(timespec="seconds")
resume = {
    "done_actors": [],
    "next": [],
    "last_error": "bot_wall_home",
    "cooldown_until": cd_until,
    "note": "clien bot wall on /service/ — no cohort expand until clear",
}
(RAW / "cohort" / "cohort_resume.json").write_text(
    json.dumps(resume, ensure_ascii=False, indent=2), encoding="utf-8"
)

jp = OUT / "2026-07-19-thread-park_19230278-actors.json"
result = json.loads(jp.read_text(encoding="utf-8"))
seed = result["seed"]
thread = json.loads((RAW / "thread.json").read_text(encoding="utf-8"))
comments = sorted(thread["comments"], key=lambda c: c.get("timestamp") or "")


def parse_ts(s: str):
    if not s:
        return None
    s = s.replace("+09:00", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            pass
    return None


times = [(c, parse_ts(c.get("timestamp"))) for c in comments]
times = [(c, t) for c, t in times if t]

lags = []
for i in range(1, len(times)):
    dt = (times[i][1] - times[i - 1][1]).total_seconds()
    lags.append(
        {
            "from": times[i - 1][0]["display_name"],
            "to": times[i][0]["display_name"],
            "lag_sec": dt,
            "ts": times[i][0]["timestamp"],
        }
    )

bursts = []
i = 0
while i < len(times):
    j = i
    while j + 1 < len(times) and (times[j + 1][1] - times[i][1]).total_seconds() <= 180:
        j += 1
    if j > i:
        bursts.append(
            {
                "start": times[i][0]["timestamp"],
                "end": times[j][0]["timestamp"],
                "n": j - i + 1,
                "actors": list(
                    dict.fromkeys(times[k][0]["display_name"] for k in range(i, j + 1))
                ),
            }
        )
    i = j + 1

by_actor_ts = defaultdict(list)
for c, t in times:
    by_actor_ts[c["author_id"]].append((t, c))

nick_to_id = {}
for c in comments:
    nick_to_id[c["display_name"]] = c["author_id"]
    nick_to_id[c["author_id"]] = c["author_id"]

edge_lags = []
for c, t in times:
    for m in c.get("mentions") or []:
        dst = nick_to_id.get(m)
        if not dst or dst == c["author_id"]:
            continue
        prev = [tt for tt, _cc in by_actor_ts.get(dst, []) if tt < t]
        lag = (t - max(prev)).total_seconds() if prev else None
        to_nick = next(
            (x["display_name"] for x in comments if x["author_id"] == dst), dst
        )
        edge_lags.append(
            {
                "from": c["display_name"],
                "to": to_nick,
                "from_id": c["author_id"],
                "to_id": dst,
                "timestamp": c["timestamp"],
                "lag_sec_after_target": lag,
                "direction": f"{c['display_name']} → {to_nick}",
            }
        )

result["temporal_seed"] = {
    "n_timestamped": len(times),
    "span_sec": (times[-1][1] - times[0][1]).total_seconds() if len(times) > 1 else 0,
    "first": times[0][0]["timestamp"] if times else None,
    "last": times[-1][0]["timestamp"] if times else None,
    "inter_arrival": lags,
    "bursts_3min": bursts,
    "directed_reply_lags": edge_lags,
}
result["honesty"]["cohort_depth"] = "seed_only_bot_wall"
result["honesty"]["bot_wall"] = True
result["honesty"]["cooldown_until"] = cd_until
result["cohort"] = {
    "expanded": False,
    "error": "bot_wall_home",
    "n_actors_indexed": 0,
}
reasons = list(result.get("coordination", {}).get("reasons") or [])
msg = "bot wall active — cross-thread expand deferred"
if msg not in reasons:
    reasons.append(msg)
result.setdefault("coordination", {})["reasons"] = reasons
result["summary"]["one_line"] = (
    f"{result['summary']['n_actors']} actors · "
    f"directed events={result['summary']['n_directed_events']} · "
    f"seed temporal {result['temporal_seed']['first']}→{result['temporal_seed']['last']} · "
    f"cohort=blocked(bot_wall)"
)
result["summary"]["goal_status"] = {
    "cross_thread": "blocked_bot_wall",
    "temporal_seed": "ok",
    "directed_network": "ok",
    "next": "wait cooldown; human login; expand max 3 actors park-only human-paced",
}
jp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

sample = (ROOT / "docs" / "sample-community-report.html").read_text(encoding="utf-8")
css = re.search(r"<style>([\s\S]*?)</style>", sample).group(1)


def esc(x):
    return (
        str(x)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


t0, t1 = times[0][1], times[-1][1]
span = max((t1 - t0).total_seconds(), 1)
acts = list(dict.fromkeys(c["display_name"] for c, _ in times))
act_y = {a: 40 + i * 28 for i, a in enumerate(acts)}
H = 40 + len(acts) * 28 + 40
dots = []
for c, t in times:
    x = 40 + 320 * ((t - t0).total_seconds() / span)
    y = act_y[c["display_name"]]
    dots.append(
        f'<circle cx="{x:.1f}" cy="{y}" r="5" fill="#2dd4bf">'
        f'<title>{esc(c["timestamp"])} {esc(c["display_name"])}</title></circle>'
    )
arrows = []
for el in edge_lags:
    src = [
        (c, t)
        for c, t in times
        if c["display_name"] == el["from"] and c["timestamp"] == el["timestamp"]
    ]
    if not src:
        continue
    c, t = src[0]
    x2 = 40 + 320 * ((t - t0).total_seconds() / span)
    y2 = act_y[el["from"]]
    prev = [(c2, t2) for c2, t2 in times if c2["author_id"] == el["to_id"] and t2 < t]
    if not prev:
        continue
    c1, t1p = max(prev, key=lambda x: x[1])
    x1 = 40 + 320 * ((t1p - t0).total_seconds() / span)
    y1 = act_y[c1["display_name"]]
    arrows.append(
        f'<line x1="{x1:.1f}" y1="{y1}" x2="{x2:.1f}" y2="{y2}" '
        f'stroke="#38bdf8" stroke-width="1.5" marker-end="url(#arr)"/>'
    )
labels = "".join(
    f'<text x="8" y="{y + 4}" fill="#93a4bb" font-size="10">{esc(a[:10])}</text>'
    for a, y in act_y.items()
)

erows = ""
for e in result.get("edges_directed") or []:
    erows += (
        f"<tr><td><b>{esc(e['from_nick'])}</b></td><td class='dir'>→</td>"
        f"<td><b>{esc(e['to_nick'])}</b></td><td>{esc(e['type'])}</td>"
        f"<td>{e['weight']}</td></tr>"
    )
tlags = "".join(
    f"<tr><td>{esc(x['direction'])}</td>"
    f"<td>{x['lag_sec_after_target'] if x['lag_sec_after_target'] is not None else '—'}</td>"
    f"<td>{esc(x['timestamp'])}</td></tr>"
    for x in edge_lags
)
blist = (
    "".join(
        f"<li>{esc(b['start'])}–{esc(b['end'])} · n={b['n']} · "
        f"{esc(', '.join(b['actors']))}</li>"
        for b in bursts
    )
    or "<li>no multi-comment 3min bursts</li>"
)

html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Kampff directed+temporal · park/19230278</title>
<style>{css}
.dir{{color:#5eead4;font-weight:700;font-family:var(--mono)}}
.pill.ok{{color:#bbf7d0;border-color:#16a34a;background:#052e16}}
.warnbox{{background:#2a1510;border:1px solid #7c2d12;border-radius:12px;padding:12px;margin:10px 0;color:#fed7aa;font-size:13px}}
</style></head><body><div class="wrap">
<header class="hero">
<p class="kicker">DIRECTED NETWORK · SEED TEMPORAL · CROSS-THREAD BLOCKED</p>
<h1>{esc(seed['title'][:100])}</h1>
<p class="sub"><a href="{esc(seed['url'])}">{esc(seed['url'])}</a></p>
<div class="meta">
<div class="chip"><b>OP</b>{esc(seed['op']['display_name'])}</div>
<div class="chip"><b>Comments</b>{seed['parsed_comments']}</div>
<div class="chip"><b>Directed</b>{result['summary']['n_directed_events']} events</div>
<div class="chip"><b>Span</b>{int(result['temporal_seed']['span_sec']//60)} min</div>
</div>
<div class="distance-banner" style="background:#0c1a24;border-color:#1e4d6b">
<span class="pill engage">A → B = A replies to B</span>
<span class="pill caution">cohort blocked</span>
<span style="font-size:12px;color:var(--muted)">{esc(result['summary']['one_line'])}</span>
</div>
</header>

<div class="warnbox"><b>Cross-thread expand paused.</b> Clien bot-wall on home.
Cooldown until <code>{esc(cd_until)}</code>. No crawl. Seed directed+temporal only.</div>

<nav class="toc">
<a href="#net">Directed</a><a href="#time">Temporal</a><a href="#goal">Goal</a>
</nav>

<section class="card" id="net">
<h2><span class="n">1</span> Directed reply (seed)</h2>
<p><span class="dir">A → B</span> = A mentions/replies to B.</p>
<table><tr><th>from</th><th></th><th>to</th><th>type</th><th>w</th></tr>
{erows or '<tr><td colspan=5>—</td></tr>'}
</table>
</section>

<section class="card" id="time">
<h2><span class="n">2</span> Temporal (seed)</h2>
<p>{esc(result['temporal_seed']['first'])} → {esc(result['temporal_seed']['last'])}
· {result['temporal_seed']['n_timestamped']} timestamped</p>
<div class="chart-box">
<h3>Actor × time</h3>
<svg viewBox="0 0 400 {H}" role="img">
<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5"
 markerWidth="6" markerHeight="6" orient="auto-start-reverse">
<path d="M0 0 L10 5 L0 10 z" fill="#7dd3fc"/></marker></defs>
{labels}
{''.join(arrows)}
{''.join(dots)}
</svg>
</div>
<h3>3-min bursts</h3>
<ul>{blist}</ul>
<h3>Directed reply lag (sec after target last spoke)</h3>
<table><tr><th>edge</th><th>lag_sec</th><th>when</th></tr>
{tlags or '<tr><td colspan=3>none</td></tr>'}
</table>
</section>

<section class="card" id="goal">
<h2><span class="n">3</span> Goal checklist</h2>
<table>
<tr><th>Requirement</th><th>Status</th></tr>
<tr><td>Relations beyond single post</td><td><b>blocked</b> (bot wall)</td></tr>
<tr><td>Temporal tracking</td><td><b>OK on seed</b></td></tr>
<tr><td>Directed reply network</td><td><b>OK</b> A→B</td></tr>
</table>
<p>After cooldown + login:
<code>python scripts/thread_actor_cohort.py --expand --max-actors 3 --max-pages 1</code>
(human-paced)</p>
</section>
<footer>No crawl while bot wall up.</footer>
</div></body></html>
"""
hp = OUT / "2026-07-19-thread-park_19230278-actors.html"
hp.write_text(html, encoding="utf-8")
print("HTML", hp)
print("cooldown_until", cd_until)
print("bursts", len(bursts), bursts[:3])
print("edge_lags", edge_lags)
print("one_line", result["summary"]["one_line"])
