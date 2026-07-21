#!/usr/bin/env python3
"""
Kampff HTML report renderer — professional, graph-heavy, offline-first.

Usage:
  python scripts/render_kampff_report.py --analysis path/to/analysis.json -o out/report.html
  python scripts/render_kampff_report.py --analysis a.json --bundle b.json -o out/report.html

analysis.json schema: see docs/report-analysis.schema.md (inline below in MODULE DOC).

Design goals:
  - User-friendly: sticky TOC, hero distance, TL;DR, print CSS
  - Professional: CIA/MBTI/L1–L5 cards, honesty triad, dossier
  - Graphs: radar (drivers/MBTI/Big5), honesty bars, ACH, timeline,
            source donut, confidence gauge, alliance bars, distance map
  - Offline: pure SVG/CSS, no CDN
"""
from __future__ import annotations

import argparse
import html as htmlmod
import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def esc(s: Any) -> str:
    return htmlmod.escape("" if s is None else str(s))


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


# ── SVG helpers ──────────────────────────────────────────────────────────────

def _radar_points(values: list[float], cx: float, cy: float, r: float) -> str:
    """values 0–1, n axes, start top, clockwise."""
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        ang = -math.pi / 2 + (2 * math.pi * i / n)
        rr = r * clamp(v, 0, 1)
        pts.append(f"{cx + rr * math.cos(ang):.1f},{cy + rr * math.sin(ang):.1f}")
    return " ".join(pts)


def svg_radar(
    labels: list[str],
    values: list[float],
    *,
    max_v: float = 3.0,
    title: str = "",
    color: str = "#2dd4bf",
    size: int = 320,
) -> str:
    cx = cy = size / 2
    r = size * 0.32
    n = len(labels)
    norms = [clamp(v / max_v, 0, 1) for v in values]
    rings = []
    for k in (1.0, 0.66, 0.33):
        pts = _radar_points([k] * n, cx, cy, r)
        rings.append(f'<polygon points="{pts}" fill="none" stroke="#243041" stroke-width="1" opacity="{0.4 + k*0.4}"/>')
    axes = []
    labs = []
    for i, lab in enumerate(labels):
        ang = -math.pi / 2 + (2 * math.pi * i / n)
        x2 = cx + r * math.cos(ang)
        y2 = cy + r * math.sin(ang)
        axes.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155" stroke-width="1"/>')
        lx = cx + (r + 22) * math.cos(ang)
        ly = cy + (r + 22) * math.sin(ang)
        val = values[i]
        labs.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" '
            f'fill="#93a4bb" font-size="11" font-family="Segoe UI,sans-serif">{esc(lab)} {val:g}</text>'
        )
    poly = _radar_points(norms, cx, cy, r)
    dots = []
    for i, v in enumerate(norms):
        ang = -math.pi / 2 + (2 * math.pi * i / n)
        x = cx + r * v * math.cos(ang)
        y = cy + r * v * math.sin(ang)
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>')
    return f'''<svg viewBox="0 0 {size} {size}" role="img" aria-label="{esc(title or 'radar')}">
  {"".join(rings)}
  {"".join(axes)}
  <polygon points="{poly}" fill="{color}44" stroke="{color}" stroke-width="2"/>
  {"".join(dots)}
  {"".join(labs)}
</svg>'''


def svg_hbar_rows(rows: list[tuple[str, float, str]], *, unit: str = "%") -> str:
    """rows: (label, 0-100, color_class teal|amber|rose|violet|sky)"""
    out = ['<div class="hbar">']
    for lab, pct, cls in rows:
        pct = clamp(pct)
        out.append(
            f'<div class="hbar-row"><span title="{esc(lab)}">{esc(lab[:18])}</span>'
            f'<div class="track"><div class="fill {cls}" style="width:{pct:.0f}%"></div></div>'
            f'<span>{pct:.0f}{unit if unit=="%" else ""}</span></div>'
        )
    out.append("</div>")
    return "\n".join(out)


def svg_donut(parts: list[tuple[str, float, str]], *, size: int = 220) -> str:
    """parts: (label, value, color). SVG donut."""
    total = sum(v for _, v, _ in parts) or 1
    cx = cy = size / 2
    r = size * 0.32
    stroke = size * 0.12
    circ = 2 * math.pi * r
    acc = 0.0
    segs = []
    legend = []
    for lab, v, col in parts:
        frac = v / total
        dash = circ * frac
        gap = circ - dash
        offset = circ * 0.25 - acc  # start top
        segs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{col}" '
            f'stroke-width="{stroke}" stroke-dasharray="{dash:.2f} {gap:.2f}" '
            f'stroke-dashoffset="{offset:.2f}" transform="rotate(-90 {cx} {cy})"/>'
        )
        acc += dash
        legend.append(f'<span><i style="background:{col}"></i>{esc(lab)} ({v:g})</span>')
    return f'''<svg viewBox="0 0 {size} {size}" role="img" aria-label="source mix">
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#1a2330" stroke-width="{stroke}"/>
  {"".join(segs)}
  <text x="{cx}" y="{cy-4}" text-anchor="middle" fill="#e7eef8" font-size="18" font-weight="700" font-family="Segoe UI,sans-serif">{int(total)}</text>
  <text x="{cx}" y="{cy+14}" text-anchor="middle" fill="#93a4bb" font-size="10">texts</text>
</svg>
<div class="legend">{"".join(legend)}</div>'''


def svg_gauge(score: float, label: str = "confidence") -> str:
    """score 0–100 semicircle gauge."""
    score = clamp(score)
    # map to angle -180..0
    ang = math.radians(180 - 180 * score / 100)
    cx, cy, r = 120, 110, 80
    x = cx + r * math.cos(ang)
    y = cy - r * math.sin(ang)
    color = "#4ade80" if score >= 70 else "#fbbf24" if score >= 40 else "#f87171"
    return f'''<svg viewBox="0 0 240 140" role="img" aria-label="{esc(label)}">
  <path d="M40 110 A80 80 0 0 1 200 110" fill="none" stroke="#1a2330" stroke-width="16" stroke-linecap="round"/>
  <path d="M40 110 A80 80 0 0 1 200 110" fill="none" stroke="{color}" stroke-width="16" stroke-linecap="round"
    stroke-dasharray="{score/100*251:.1f} 251" />
  <line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#e7eef8" stroke-width="3" stroke-linecap="round"/>
  <circle cx="{cx}" cy="{cy}" r="5" fill="#e7eef8"/>
  <text x="{cx}" y="90" text-anchor="middle" fill="{color}" font-size="28" font-weight="700" font-family="Segoe UI,sans-serif">{score:.0f}</text>
  <text x="{cx}" y="130" text-anchor="middle" fill="#93a4bb" font-size="11">{esc(label)}</text>
</svg>'''


def timeline_activity(ev: dict) -> float:
    """Activity volume for a timeline node (texts / weight)."""
    for k in ("n", "count", "activity", "weight", "volume"):
        if ev.get(k) is None:
            continue
        try:
            v = float(ev[k])
            if v >= 0:
                return v
        except (TypeError, ValueError):
            continue
    return 0.0


def svg_timeline(events: list[dict]) -> str:
    """events: {t, label, color?, n|count|activity?} — node radius ∝ activity."""
    if not events:
        return '<p class="muted">No timeline events.</p>'
    w = 1040
    h = 168
    pad = 56
    n = len(events)
    xs = [pad + i * (w - 2 * pad) / max(n - 1, 1) for i in range(n)]
    acts = [timeline_activity(ev) for ev in events]
    # If no activity provided, fall back to equal mid size (not index-ramp).
    if max(acts) <= 0:
        acts = [1.0] * n
    # sqrt scale so large bursts don't swallow the axis
    sacts = [math.sqrt(a) for a in acts]
    lo, hi = min(sacts), max(sacts)
    r_min, r_max = 6.0, 22.0

    def radius(sa: float) -> float:
        if hi <= lo:
            return (r_min + r_max) / 2
        return r_min + (sa - lo) / (hi - lo) * (r_max - r_min)

    cy = 78
    line = f'<line x1="{pad}" y1="{cy}" x2="{w-pad}" y2="{cy}" stroke="#334155" stroke-width="2"/>'
    nodes = []
    for i, (ev, x, a, sa) in enumerate(zip(events, xs, acts, sacts)):
        col = ev.get("color") or ("#2dd4bf" if i == n - 1 else "#38bdf8")
        r = radius(sa)
        lab = esc(ev.get("label", ""))[:28]
        tlab = esc(ev.get("t", ""))
        # count badge: prefer integer activity
        a_int = int(round(a)) if a > 0 else 0
        title = esc(f'{ev.get("t","")} · {ev.get("label","")} · n={a_int}')
        # label y pushes down for fat nodes
        lab_y = cy + r + 16
        count_fill = "#0b0f14" if r >= 11 else col
        count_txt = f"{a_int}" if a_int > 0 else ""
        count_fs = 10 if r >= 12 else 9
        nodes.append(
            f'<g class="tl-node" data-n="{a_int}">'
            f'<title>{title}</title>'
            f'<circle cx="{x:.0f}" cy="{cy}" r="{r:.1f}" fill="{col}" fill-opacity="0.92" stroke="#0b0f14" stroke-width="1.2"/>'
            f'<text x="{x:.0f}" y="{cy + 4:.0f}" text-anchor="middle" fill="{count_fill if r >= 11 else "#e7eef8"}" '
            f'font-size="{count_fs}" font-family="ui-monospace,monospace" font-weight="700">{count_txt}</text>'
            f'<text x="{x:.0f}" y="{cy - r - 10:.0f}" text-anchor="middle" fill="#94a3b8" font-size="11">{tlab}</text>'
            f'<text x="{x:.0f}" y="{lab_y:.0f}" text-anchor="middle" fill="#64748b" font-size="10">{lab}</text>'
            f"</g>"
        )
    note = esc(events[-1].get("note", "")) if events else ""
    legend = "node size ∝ activity (n = texts in bucket)"
    return f'''<svg viewBox="0 0 {w} {h}" role="img" aria-label="ephemeris timeline (node size proportional to activity)">
  {line}
  {"".join(nodes)}
  <text x="{pad}" y="{h - 8}" fill="#64748b" font-size="11">{legend}{" · " + note if note else ""}</text>
</svg>'''


def svg_ach(hypotheses: list[dict]) -> str:
    """[{id, label, status: lead|weak|fail, score:0-100}]"""
    rows = []
    y = 20
    for h in hypotheses:
        st = h.get("status", "weak")
        col = {"lead": "#10b981", "weak": "#fbbf24", "fail": "#f87171"}.get(st, "#94a3b8")
        sc = clamp(float(h.get("score", 50 if st == "weak" else 90 if st == "lead" else 15)))
        w = 2.0 * sc
        rows.append(
            f'<text x="8" y="{y+12}" fill="#e7eef8" font-size="12">{esc(h.get("id","H"))} {esc(h.get("label",""))[:28]}</text>'
            f'<rect x="150" y="{y}" width="200" height="18" rx="5" fill="#1a2330"/>'
            f'<rect x="150" y="{y}" width="{w:.0f}" height="18" rx="5" fill="{col}" opacity=".9"/>'
            f'<text x="360" y="{y+12}" fill="{col}" font-size="11" font-family="monospace">{esc(st)}</text>'
        )
        y += 36
    return f'<svg viewBox="0 0 400 {max(y, 80)}" role="img" aria-label="ACH">{"".join(rows)}</svg>'


DISTANCE_COLORS = {
    "engage": ("#a7f3d0", "#059669", "#064e3b"),
    "neutral": ("#cbd5e1", "#475569", "#1e293b"),
    "caution": ("#fde68a", "#b45309", "#422006"),
    "avoid": ("#fecaca", "#b91c1c", "#450a0a"),
}


def pill(tag: str) -> str:
    t = (tag or "neutral").lower().split()[0]
    if t not in DISTANCE_COLORS:
        t = "neutral"
    return f'<span class="pill {t}">{esc(tag)}</span>'


# ── Bundle stats ─────────────────────────────────────────────────────────────

def bundle_source_counts(bundle: dict | None, person_id: str) -> list[tuple[str, float, str]]:
    if not bundle:
        return []
    colors = {
        "community_post": "#2dd4bf",
        "community_comment": "#38bdf8",
        "mail": "#a78bfa",
        "meeting": "#fbbf24",
        "chat": "#f472b6",
        "sns_post": "#fb7185",
        "sns_comment": "#94a3b8",
    }
    texts = []
    for p in bundle.get("people") or []:
        if p.get("id") == person_id:
            texts = p.get("texts") or []
            break
    c = Counter((t.get("source") or "other") for t in texts)
    return [(k, float(v), colors.get(k, "#64748b")) for k, v in c.most_common()]


def infer_timeline_from_bundle(bundle: dict | None, person_id: str, limit: int = 8) -> list[dict]:
    """Month-bucket activity timeline: node n = text count in YYYY-MM."""
    if not bundle:
        return []
    texts = []
    for p in bundle.get("people") or []:
        if p.get("id") == person_id:
            texts = p.get("texts") or []
            break
    by_month: dict[str, list[dict]] = {}
    for t in texts:
        ts = (t.get("timestamp") or "")[:7]  # YYYY-MM
        if len(ts) < 7:
            continue
        by_month.setdefault(ts, []).append(t)
    if not by_month:
        return []
    months = sorted(by_month.keys())
    # if too many months, pick densest + edges
    if len(months) > limit:
        ranked = sorted(months, key=lambda m: (-len(by_month[m]), m))
        keep = set(ranked[: max(limit - 2, 1)])
        keep.add(months[0])
        keep.add(months[-1])
        months = [m for m in months if m in keep][:limit]
        # ensure chronological
        months = sorted(months)

    events = []
    for m in months:
        bucket = by_month[m]
        # pick a representative label from longest content / first post title
        label = m
        best = ""
        for t in bucket:
            content = t.get("content") or ""
            mt = re.search(r"\[title\]\s*(.+)", content)
            cand = (mt.group(1).split("\n")[0] if mt else content.replace("\n", " "))[:28]
            if len(cand) > len(best):
                best = cand
        posts = sum(
            1
            for t in bucket
            if (t.get("type") == "post") or (t.get("source") == "community_post")
        )
        cmts = len(bucket) - posts
        if best:
            label = best
        elif posts and cmts:
            label = f"{posts}p/{cmts}c"
        elif posts:
            label = f"{posts} posts"
        else:
            label = f"{cmts} cmts"
        events.append(
            {
                "t": m,
                "label": label,
                "color": "#2dd4bf" if m == months[-1] else "#38bdf8",
                "n": len(bucket),
                "posts": posts,
                "comments": cmts,
            }
        )
    return events


def enrich_timeline_activity(
    timeline: list[dict], bundle: dict | None, person_id: str
) -> list[dict]:
    """Fill missing n/count from bundle month (or day) buckets. Keeps explicit n."""
    if not timeline:
        return timeline
    if all(timeline_activity(ev) > 0 for ev in timeline):
        return timeline
    if not bundle:
        return timeline
    texts = []
    for p in bundle.get("people") or []:
        if p.get("id") == person_id:
            texts = p.get("texts") or []
            break
    if not texts:
        return timeline
    by_month: Counter[str] = Counter()
    by_day: Counter[str] = Counter()
    for t in texts:
        ts = t.get("timestamp") or ""
        if len(ts) >= 7:
            by_month[ts[:7]] += 1
        if len(ts) >= 10:
            by_day[ts[:10]] += 1
    out = []
    for ev in timeline:
        e = dict(ev)
        if timeline_activity(e) > 0:
            out.append(e)
            continue
        key = str(e.get("t") or "")
        n = 0
        if len(key) >= 10 and key[:10] in by_day:
            n = by_day[key[:10]]
        elif len(key) >= 7 and key[:7] in by_month:
            n = by_month[key[:7]]
        else:
            # fuzzy: any month key that startswith or is contained
            for mk, mv in by_month.items():
                if key.startswith(mk) or mk.startswith(key[:7]):
                    n = mv
                    break
        if n > 0:
            e["n"] = n
        out.append(e)
    return out


# ── HTML assembly ────────────────────────────────────────────────────────────

CSS = r"""
:root {
  --bg:#0b0f14; --panel:#121821; --panel2:#18202b; --line:#243041;
  --text:#e7eef8; --muted:#93a4bb; --accent:#5eead4; --accent2:#38bdf8;
  --warn:#fbbf24; --ok:#4ade80; --bad:#f87171;
  --mono:"JetBrains Mono","SF Mono",Consolas,monospace;
  --sans:"Segoe UI",system-ui,sans-serif;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;font-family:var(--sans);color:var(--text);line-height:1.55;
  background:
    radial-gradient(1200px 600px at 10% -10%,#12324a55,transparent),
    radial-gradient(900px 500px at 100% 0%,#0f3d3555,transparent),
    var(--bg);
}
.wrap{max-width:1180px;margin:0 auto;padding:28px 18px 80px}
header.hero{
  border:1px solid var(--line);
  background:linear-gradient(180deg,var(--panel2),var(--panel));
  border-radius:18px;padding:26px;margin-bottom:18px;position:relative;overflow:hidden;
}
header.hero::before{content:"";position:absolute;inset:0 auto 0 0;width:5px;background:linear-gradient(180deg,var(--accent),var(--accent2))}
.kicker{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin:0 0 8px}
h1{margin:0 0 6px;font-size:26px;letter-spacing:-.02em}
.sub{color:var(--muted);font-size:13px;margin:0 0 14px}
.tldr{
  margin:12px 0 0;padding:14px 16px;border-radius:12px;
  background:linear-gradient(90deg,#0c1c28,#0d1a16);border:1px solid #1e4d45;font-size:14.5px;
}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px}
.meta .chip{background:#0d131b;border:1px solid var(--line);border-radius:12px;padding:10px 12px;font-size:12.5px}
.meta .chip b{display:block;color:var(--muted);font-weight:500;font-size:10px;margin-bottom:3px}
.distance-banner{
  margin-top:14px;padding:12px 14px;border-radius:12px;
  display:flex;flex-wrap:wrap;gap:8px;align-items:center;
  background:#0c1f1a;border:1px solid #1f5c4a;
}
.distance-banner.caution{background:#1c1408;border-color:#7c4a0a}
.distance-banner.avoid{background:#1c0a0a;border-color:#7f1d1d}
.distance-banner.engage{background:#052e16;border-color:#166534}
.pill{display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;font-family:var(--mono);font-size:11px;border:1px solid}
.pill.neutral{color:#cbd5e1;border-color:#475569;background:#1e293b}
.pill.engage{color:#a7f3d0;border-color:#059669;background:#064e3b}
.pill.caution{color:#fde68a;border-color:#b45309;background:#422006}
.pill.avoid{color:#fecaca;border-color:#b91c1c;background:#450a0a}
.pill.ok{color:#bbf7d0;border-color:#16a34a;background:#052e16}
nav.toc{
  position:sticky;top:0;z-index:5;backdrop-filter:blur(10px);
  background:#0b0f14cc;border-bottom:1px solid var(--line);
  margin:0 -18px 18px;padding:8px 18px;display:flex;gap:6px;flex-wrap:wrap;
}
nav.toc a{color:var(--muted);text-decoration:none;font-size:11.5px;padding:5px 9px;border-radius:999px;border:1px solid transparent}
nav.toc a:hover{color:var(--text);border-color:var(--line);background:var(--panel)}
section.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px;margin-bottom:14px}
section.card h2{margin:0 0 12px;font-size:17px;display:flex;align-items:center;gap:8px}
section.card h2 .n{font-family:var(--mono);font-size:11px;color:var(--accent2);border:1px solid #1e3a5f;background:#0b1726;padding:2px 7px;border-radius:999px}
h3{margin:16px 0 8px;font-size:14px;color:#dbeafe}
p,li{color:#d5e0ee;font-size:14px}
ul{padding-left:1.1rem;margin:6px 0}
blockquote{margin:10px 0;padding:10px 12px;border-left:3px solid var(--accent);background:#0d151f;border-radius:0 10px 10px 0;color:#cfe7ff;font-size:13px}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin:8px 0}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{background:#0e1520;color:var(--muted);font-weight:600}
tr:nth-child(even) td{background:#0f1620}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media(max-width:960px){.grid2,.grid3{grid-template-columns:1fr}}
.stat{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px}
.stat .v{font-size:20px;font-weight:700;color:var(--accent);font-family:var(--mono)}
.stat .l{font-size:11px;color:var(--muted)}
.chart-box{background:#0a1018;border:1px solid var(--line);border-radius:14px;padding:14px}
.chart-box h3{margin:0 0 10px;font-size:12px;color:var(--muted);font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.chart-box svg{display:block;width:100%;height:auto}
.legend{display:flex;flex-wrap:wrap;gap:10px;margin-top:8px;font-size:11px;color:var(--muted)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.hbar{display:grid;gap:9px}
.hbar-row{display:grid;grid-template-columns:110px 1fr 40px;gap:8px;align-items:center;font-size:12px}
.track{height:10px;background:#1a2330;border-radius:99px;overflow:hidden}
.fill{height:100%;border-radius:99px;transition:width .6s ease}
.fill.teal{background:linear-gradient(90deg,#0ea5e9,#2dd4bf)}
.fill.amber{background:linear-gradient(90deg,#f59e0b,#fbbf24)}
.fill.rose{background:linear-gradient(90deg,#e11d48,#fb7185)}
.fill.violet{background:linear-gradient(90deg,#7c3aed,#a78bfa)}
.fill.sky{background:linear-gradient(90deg,#0284c7,#38bdf8)}
pre.dossier{background:#070b10;border:1px solid var(--line);border-radius:12px;padding:12px 14px;overflow:auto;font-family:var(--mono);font-size:11.5px;line-height:1.45;color:#b8c7da;white-space:pre-wrap}
.dist-map{display:grid;gap:8px}
.dist-row{display:grid;grid-template-columns:1fr 120px;gap:10px;align-items:center;padding:10px 12px;border-radius:10px;background:#0d131b;border:1px solid var(--line);font-size:13px}
.q{margin:10px 0;padding:10px 12px;background:#121a24;border-left:3px solid var(--accent);border-radius:0 8px 8px 0}
.q figcaption{color:var(--muted);font-size:.78rem;margin-bottom:6px}
.q pre{white-space:pre-wrap;margin:0;font:13px/1.45 var(--mono);color:#d5deea}
.muted{color:var(--muted);font-size:12.5px}
.cp-actions{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.cp-actions button{
  font:inherit;cursor:pointer;border-radius:10px;padding:8px 14px;
  border:1px solid var(--line);background:#0d1520;color:var(--text);
}
.cp-actions button.primary{border-color:#1e4d45;background:#0c1c28;color:var(--accent)}
.cp-actions button:hover{filter:brightness(1.08)}
.cp-out{
  width:100%;min-height:140px;box-sizing:border-box;resize:vertical;
  font:14px/1.55 var(--sans);color:var(--text);
  background:#070b10;border:1px solid #1e4d45;border-radius:12px;padding:12px 14px;
}
.cp-status{font-size:12px;color:var(--muted);min-height:1.2em;margin-top:6px}

footer{margin-top:24px;color:var(--muted);font-size:11px;text-align:center}
a{color:var(--accent2)}
@media print{
  body{background:#fff;color:#111}
  nav.toc,.kicker{display:none}
  section.card,header.hero{break-inside:avoid;border-color:#ccc;background:#fff}
  .chart-box{background:#f8fafc;border-color:#ddd}
}
"""
KAMPFF_CP_JS = '\n<script id="kampff-cp-js">\n(function(){\n  function seed(){\n    var el = document.getElementById(\'kampff-cp-seed\');\n    if(!el) return {};\n    try { return JSON.parse(el.textContent || \'{}\'); } catch(e){ return {}; }\n  }\n  function cleanOps(s){\n    return String(s||\'\')\n      .replace(/\\b(caution|avoid|engage|ops|ROI|distance|worldview|alliance|stability|drift|risk|L[1-5]|MBTI|ACH|CIA|SAT|Big ?Five|clinical|diagnosis|doxx?|CONFIRMED|PROBABLE|SPECULATIVE)\\b/gi,\'\')\n      .replace(/(표본|수집분?|분석\\s*결과|리포트|독시어|권고\\s*태그|matrix|honesty|bundle|harvest)/gi,\'\')\n      .replace(/\\s{2,}/g,\' \').trim();\n  }\n  function tagSalad(t){\n    t = String(t||\'\').trim();\n    if (!t || t.length < 8) return true;\n    var hasStop = /[.。?!]|다\\.|요\\.|임\\.|습니다|거든요|봅니다/.test(t);\n    var parts = t.split(/[\\s·|/,:;]+/).filter(Boolean);\n    if (!hasStop && parts.length >= 3 && parts.every(function(p){ return p.length <= 12; })) return true;\n    if (/\\b(park|kin|use|cm_stock)\\b/i.test(t) && !hasStop) return true;\n    if (/(공유형|논객형|생활형|문제해결형)/.test(t) && !hasStop) return true;\n    return false;\n  }\n  function distill(d){\n    var cands = [d.point, d.mechanism, d.claim, d.one_line, d.tldr, d.trigger].map(cleanOps).filter(Boolean);\n    for (var i=0;i<cands.length;i++){\n      var raw = cands[i];\n      if (tagSalad(raw)) continue;\n      var t = (raw.split(/(?<=[.。?!]|다\\.|요\\.|습니다\\.|거든요\\.)\\s+/)[0] || raw).trim();\n      t = t.replace(/^[\\s,.:;·\\/-]+|[\\s,.:;·\\/-]+$/g,\'\');\n      if (tagSalad(t)) continue;\n      if (t.length > 110) t = t.slice(0,108).replace(/\\s+\\S*$/,\'\') + \'\\u2026\';\n      if (t.length >= 16) return t;\n    }\n    return \'\';\n  }\n  function endDot(s){\n    s = String(s||\'\').trim();\n    if (!s) return s;\n    if (/[다요임]$|[.。]$|습니다$|거든요$|봅니다$/.test(s)) return s;\n    return s + \'.\';\n  }\n  var REFUSE = \'[게시 초안 생성 불가]\\n이 칸은 회원 전반 분석(독시어)이 아닙니다.\\nanalysis seed 문장이 없어 일반 템플릿으로 채우지 않습니다.\\n→ 위 TL;DR · L1–L5 · Distance · Evidence 가 본 분석입니다.\';\n  function generate(){\n    var d = seed();\n    var preset = d.preset && String(d.preset).trim();\n    if (preset && preset.length <= 600 && preset.split(\'\\n\').length <= 10 && !tagSalad(preset)) return preset;\n    var mech = cleanOps(d.mechanism || \'\');\n    var claim = cleanOps(d.claim || \'\');\n    var anchor = cleanOps(d.anchor || \'\');\n    var point = distill(d);\n    if (mech && (claim || point)) {\n      var c = (claim || point).replace(/^["\']|["\']$/g,\'\');\n      var lines = [endDot(mech), \'\', \'그래서 \' + c + \'만 보고 단정까지는 잘 안 갑니다.\'];\n      lines.push(anchor ? (\'판단은 \' + anchor + \' 쪽에 두는 편이 낫다고 생각합니다.\') : \'판단은 확인 가능한 근거에 두는 편이 낫다고 생각합니다.\');\n      return lines.join(\'\\n\');\n    }\n    if (point && !tagSalad(point)) {\n      return [endDot(point), \'\', \'이 한 줄은 게시용 초안일 뿐, 전반 분석 전체가 아닙니다.\'].join(\'\\n\');\n    }\n    return REFUSE;\n  }\n  function $(id){ return document.getElementById(id); }\n  var out = $(\'cpOut\'), st = $(\'cpStatus\');\n  var gen = $(\'cpGen\'), copy = $(\'cpCopy\'), clr = $(\'cpClear\');\n  if (gen) gen.addEventListener(\'click\', function(){\n    out.value = generate();\n    st.textContent = out.value.indexOf(\'[게시 초안 생성 불가]\') === 0 ? \'거부 — 독시어가 분석\' : \'optional export\';\n  });\n  if (copy) copy.addEventListener(\'click\', async function(){\n    if (!out.value.trim()) out.value = generate();\n    if (out.value.indexOf(\'[게시 초안 생성 불가]\') === 0) { st.textContent = \'거부문 — copy 안 함\'; return; }\n    try { await navigator.clipboard.writeText(out.value); st.textContent = \'copied\'; }\n    catch (e) { out.focus(); out.select(); try { document.execCommand(\'copy\'); st.textContent = \'copied\'; } catch (e2) { st.textContent = \'fail\'; } }\n  });\n  if (clr) clr.addEventListener(\'click\', function(){ out.value=\'\'; st.textContent=\'cleared\'; });\n})();\n</script>\n'
def render(analysis: dict, bundle: dict | None = None) -> str:
    meta = analysis.get("meta") or {}
    target = analysis.get("target") or {}
    viewer = analysis.get("viewer") or {"id": "me"}
    distance = (analysis.get("distance") or "neutral").lower()
    confidence = float(analysis.get("confidence_score") or 55)
    conf_label = analysis.get("confidence") or "medium"
    tldr = analysis.get("tldr") or analysis.get("one_line") or ""
    tid = target.get("id") or "target"
    nick = target.get("nick") or tid
    date = meta.get("date") or datetime.now().strftime("%Y-%m-%d")
    platform = meta.get("platform") or "community"
    protocol = meta.get("protocol") or "L1–L5 · MBTI · clinical · CIA-SAT"

    honesty = analysis.get("honesty") or {}
    posts_pct = float(honesty.get("posts_pct", 50))
    cmts_pct = float(honesty.get("comments_pct", 40))
    likes_pct = honesty.get("likes_pct")
    likes_na = likes_pct is None or str(honesty.get("likes_status", "")).lower() in ("n/a", "na")

    matrix = analysis.get("matrix") or {}
    identity = analysis.get("identity") or {}
    spectro = analysis.get("spectrograph") or analysis.get("l1_l5") or {}
    mbti = analysis.get("mbti") or {}
    cia = analysis.get("cia") or {}
    clinical = analysis.get("clinical_psych") or analysis.get("psych") or {}
    ops = analysis.get("distance_ops") or []
    cross = analysis.get("cross_check") or []
    quotes = analysis.get("quotes") or []
    files = analysis.get("files") or {}
    trigger = analysis.get("trigger") or {}
    timeline = analysis.get("timeline") or infer_timeline_from_bundle(bundle, tid)
    timeline = enrich_timeline_activity(timeline or [], bundle, tid)
    sources = analysis.get("source_mix") or bundle_source_counts(bundle, tid)

    # Big Five
    big5 = analysis.get("big5") or spectro.get("big5") or {
        "O": 50, "C": 50, "E": 50, "A": 50, "N": 50
    }
    big5_rows = [
        ("Openness", float(big5.get("O", 50)), "violet"),
        ("Conscient.", float(big5.get("C", 50)), "teal"),
        ("Extraversion", float(big5.get("E", 50)), "sky"),
        ("Agreeable", float(big5.get("A", 50)), "amber"),
        ("Neuroticism", float(big5.get("N", 50)), "rose"),
    ]

    # Drivers
    drivers = cia.get("drivers") or analysis.get("drivers") or {
        "resource": 2, "control": 2, "status": 1, "belonging": 1, "autonomy": 2
    }
    d_labels = ["resource", "control", "status", "belong", "autonomy"]
    d_vals = [
        float(drivers.get("resource", drivers.get("resource/career", 2))),
        float(drivers.get("control", drivers.get("certainty/control", 2))),
        float(drivers.get("status", 1)),
        float(drivers.get("belonging", drivers.get("belong", 1))),
        float(drivers.get("autonomy", 2)),
    ]

    # MBTI leans 0-100 toward second letter of pair displayed
    leans = mbti.get("leans") or {"E": 50, "I": 50, "S": 50, "N": 50, "T": 50, "F": 50, "J": 50, "P": 50}
    mbti_type = mbti.get("type") or mbti.get("guess") or "xxxx"
    # radar axes I,S,T,J as strength of those poles
    m_labels = ["I", "S", "T", "J"]
    m_vals = [
        float(leans.get("I", 100 - float(leans.get("E", 50)))),
        float(leans.get("S", 50)),
        float(leans.get("T", 50)),
        float(leans.get("J", 50)),
    ]

    ach = cia.get("ach") or analysis.get("ach") or [
        {"id": "H1", "label": "primary", "status": "lead", "score": 85},
        {"id": "H2", "label": "alt", "status": "weak", "score": 35},
        {"id": "H3", "label": "noise", "status": "fail", "score": 15},
    ]

    # Clinical / psychologist formulation (non-diagnostic)
    clin_on = bool(clinical) and clinical.get("enabled", True) is not False
    clin_one = clinical.get("one_line") or ""
    clin_conf = clinical.get("confidence") or "low"
    clin_disc = clinical.get("disclaimer") or (
        "Public-text formulation only — not diagnosis, not treatment."
    )
    clin_affect = clinical.get("affect") or {}
    clin_attach = clinical.get("attachment") or {}
    clin_cog = clinical.get("cognition") or {}
    clin_self = clinical.get("self_other") or {}
    clin_ip = clinical.get("interpersonal") or {}
    clin_ego = clinical.get("ego_threat") or {}
    clin_bridge = clinical.get("distance_bridge") or ""
    clin_not = clinical.get("not_claimed") or ["No DSM/ICD diagnosis"]
    clin_defs = clinical.get("defenses") or []
    clin_hyps = clinical.get("hypotheses") or []
    # defense bars level 0-3 → 0-100
    def_rows = []
    for d in clin_defs[:8]:
        if isinstance(d, dict):
            lv = float(d.get("level", 0))
            def_rows.append((str(d.get("name", "?"))[:18], min(100.0, lv * 33.3), "rose"))
        elif isinstance(d, (list, tuple)) and len(d) >= 2:
            def_rows.append((str(d[0])[:18], min(100.0, float(d[1]) * 33.3), "rose"))
    clin_hyp_svg = svg_ach(clin_hyps) if clin_hyps else ""
    clin_def_svg = svg_hbar_rows(def_rows) if def_rows else '<p class="muted">No defense ratings</p>'
    clin_trig = clin_affect.get("triggers") or []
    if isinstance(clin_trig, str):
        clin_trig = [clin_trig]
    clin_trig_html = "".join(f"<li>{esc(t)}</li>" for t in clin_trig) or "<li class='muted'>—</li>"
    clin_not_html = "".join(f"<li>{esc(t)}</li>" for t in clin_not)
    clin_section = ""
    if clin_on and (clin_one or clin_defs or clin_hyps or clin_bridge):
        clin_section = f'''
  <section class="card" id="clinical">
    <h2><span class="n">6b</span> Clinical / psychologist <span class="muted">(비진단 · formulation)</span></h2>
    <div class="tldr" style="border-color:#f43f5e55"><b>Disclaimer</b> — {esc(clin_disc)}</div>
    <p><b>One-line formulation:</b> {esc(clin_one) or "—"}</p>
    <p class="muted">confidence: {esc(clin_conf)} · never sole distance reason · not DSM/ICD</p>
    <div class="grid2" style="margin-top:12px">
      <div class="chart-box">
        <h3>Defense style (0–3 → bar)</h3>
        {clin_def_svg}
      </div>
      <div class="chart-box">
        <h3>C-hypotheses (formulation ACH)</h3>
        {clin_hyp_svg or "<p class='muted'>No C-hypotheses</p>"}
      </div>
    </div>
    <div class="grid2" style="margin-top:12px">
      <div>
        <h3>Affect regulation</h3>
        <p>{esc(clin_affect.get("pattern", "—"))}</p>
        <p class="muted">volatility ~ {esc(str(clin_affect.get("score_volatility", "—")))}/100</p>
        <ul>{clin_trig_html}</ul>
      </div>
      <div>
        <h3>Attachment signals</h3>
        <p><b>{esc(clin_attach.get("signals", "—"))}</b></p>
        <p class="muted">{esc(clin_attach.get("note", ""))}</p>
        <h3 style="margin-top:10px">Cognition</h3>
        <p>{esc(clin_cog.get("style", "—"))}</p>
        <p class="muted">rigidity {esc(str(clin_cog.get("rigidity", "—")))} · mentalization {esc(str(clin_cog.get("mentalization", "—")))}</p>
      </div>
    </div>
    <div class="grid2" style="margin-top:12px">
      <div>
        <h3>Self / other</h3>
        <p>{esc(clin_self.get("pattern", "—"))}</p>
        <p class="muted">{esc(clin_self.get("note", ""))}</p>
      </div>
      <div>
        <h3>Interpersonal script</h3>
        <p>{esc(clin_ip.get("script", "—"))}</p>
        <p class="muted">repair: {esc(clin_ip.get("repair", "—"))}</p>
        <h3 style="margin-top:10px">Ego threat response</h3>
        <p>{esc(clin_ego.get("response", "—"))}</p>
        <p class="muted">{esc(clin_ego.get("note", ""))}</p>
      </div>
    </div>
    <p style="margin-top:12px"><b>Distance bridge:</b> {esc(clin_bridge) or "—"}</p>
    <h3>Not claimed</h3>
    <ul>{clin_not_html}</ul>
  </section>'''

    alliance = analysis.get("alliance_bars") or [
        ("domain trust", float(matrix.get("alliance_score", 40)), "teal"),
        ("craft peer", 45, "sky"),
        ("soft friendship", 20, "amber"),
        ("persuade ROI", 15, "rose"),
    ]
    if alliance and isinstance(alliance[0], dict):
        alliance = [(a.get("label", ""), float(a.get("pct", 0)), a.get("color", "teal")) for a in alliance]

    banner_cls = distance if distance in DISTANCE_COLORS else "neutral"

    # honesty svg bars
    likes_bar = (
        f'<text x="8" y="138" fill="#93a4bb" font-size="12">Likes</text>'
        f'<rect x="80" y="122" width="280" height="22" rx="6" fill="#1a2330"/>'
        f'<text x="200" y="138" fill="#64748b" font-size="12">n/a</text>'
        if likes_na
        else (
            f'<text x="8" y="138" fill="#93a4bb" font-size="12">Likes</text>'
            f'<rect x="80" y="122" width="280" height="22" rx="6" fill="#1a2330"/>'
            f'<rect x="80" y="122" width="{2.8 * float(likes_pct):.0f}" height="22" rx="6" fill="#f87171"/>'
            f'<text x="370" y="138" fill="#f87171" font-size="12" font-family="monospace">{float(likes_pct):.0f}%</text>'
        )
    )
    honesty_svg = f'''<svg viewBox="0 0 400 180" role="img" aria-label="collection completeness">
  <text x="8" y="38" fill="#93a4bb" font-size="12">Posts</text>
  <rect x="80" y="22" width="280" height="22" rx="6" fill="#1a2330"/>
  <rect x="80" y="22" width="{2.8*posts_pct:.0f}" height="22" rx="6" fill="url(#g1)"/>
  <text x="370" y="38" fill="#4ade80" font-size="12" font-family="monospace">{posts_pct:.0f}%</text>
  <text x="8" y="88" fill="#93a4bb" font-size="12">Comments</text>
  <rect x="80" y="72" width="280" height="22" rx="6" fill="#1a2330"/>
  <rect x="80" y="72" width="{2.8*cmts_pct:.0f}" height="22" rx="6" fill="#fbbf24"/>
  <text x="370" y="88" fill="#fbbf24" font-size="12" font-family="monospace">{cmts_pct:.0f}%</text>
  {likes_bar}
  <defs><linearGradient id="g1" x1="0" x2="1"><stop stop-color="#0ea5e9"/><stop offset="1" stop-color="#2dd4bf"/></linearGradient></defs>
  <text x="80" y="168" fill="#64748b" font-size="10">{esc(honesty.get("note",""))}</text>
</svg>'''

    # stats chips
    corpus = analysis.get("corpus") or {}
    n_posts = corpus.get("posts", honesty.get("posts_n", "?"))
    n_cmts = corpus.get("comments", honesty.get("comments_n", "?"))
    n_likes = corpus.get("likes", "n/a" if likes_na else honesty.get("likes_n", "?"))

    quote_html = []
    for q in quotes[:12]:
        label = q.get("label") or q.get("type") or "Q"
        ts = q.get("timestamp") or ""
        body = q.get("text") or q.get("content") or ""
        quote_html.append(
            f'<figure class="q"><figcaption>{esc(label)} · {esc(ts)}</figcaption>'
            f"<pre>{esc(body[:900])}</pre></figure>"
        )

    id_bullets = identity.get("bullets") or identity.get("points") or []
    if isinstance(id_bullets, str):
        id_bullets = [id_bullets]
    id_ul = "".join(f"<li>{esc(b)}</li>" for b in id_bullets)

    l_sections = []
    for key, title in [
        ("L1", "Psych"),
        ("L2", "Worldview"),
        ("L3", "Behavioral"),
        ("L4", "Alliance"),
        ("L5", "Ephemeris"),
    ]:
        body = spectro.get(key) or spectro.get(key.lower()) or ""
        if isinstance(body, list):
            body = "</p><p>".join(esc(x) for x in body)
            l_sections.append(f"<p><strong>{key} {title}</strong> — {body}</p>")
        else:
            l_sections.append(f"<p><strong>{key} {title}</strong> — {esc(body)}</p>")

    ops_rows = []
    for o in ops:
        if isinstance(o, dict):
            ops_rows.append(f"<tr><td>{pill(o.get('tag',''))}</td><td>{esc(o.get('when',''))}</td></tr>")
        else:
            ops_rows.append(f"<tr><td colspan='2'>{esc(o)}</td></tr>")

    cross_ol = "".join(f"<li>{esc(c)}</li>" for c in cross)

    dossier = cia.get("card") or cia.get("dossier") or analysis.get("dossier") or ""
    if isinstance(dossier, dict):
        dossier = "\n".join(f"{k.upper()}: {v}" for k, v in dossier.items())

    ach_lead = next((h for h in ach if h.get("status") == "lead"), ach[0] if ach else {})

    matrix_row = (
        f"<tr><td>{esc(tid)}</td>"
        f"<td>{esc(matrix.get('worldview_fit','—'))}</td>"
        f"<td>{esc(matrix.get('alliance_fit','—'))}</td>"
        f"<td>{esc(matrix.get('stability','—'))}</td>"
        f"<td>{esc(matrix.get('drift','—'))}</td>"
        f"<td>{esc(matrix.get('risk','—'))}</td>"
        f"<td>{esc(matrix.get('one_line', tldr))}</td></tr>"
    )

    files_html = "<br/>".join(f"{esc(k)}: {esc(v)}" for k, v in files.items()) if files else "—"

    trigger_html = ""
    if trigger:
        trigger_html = f'''
  <section class="card" id="trigger">
    <h2><span class="n">3</span> Trigger / Debate</h2>
    <p>{esc(trigger.get("summary",""))}</p>
    <p class="muted">{esc(trigger.get("url",""))}</p>
  </section>'''

    donut = svg_donut(sources) if sources else '<p class="muted">No source mix</p>'


    # community post Generate+Copy seed (section HTML; JS attached after f-string)
    _cp = analysis.get("community_post") or analysis.get("community_voice") or {}
    if isinstance(_cp, str):
        _cp = {"text_ko": _cp}
    if not isinstance(_cp, dict):
        _cp = {}
    cp_seed = {
        "nick": nick,
        "id": tid,
        "platform": platform,
        "board": (_cp.get("board") or _cp.get("board_hint") or platform or "park"),
        "tldr": tldr,
        "one_line": (matrix.get("one_line") if isinstance(matrix, dict) else "") or "",
        "preset": (_cp.get("text_ko") or _cp.get("text") or _cp.get("body") or "").strip(),
        "trigger": (trigger.get("summary") if isinstance(trigger, dict) else "") or "",
        "mechanism": (_cp.get("mechanism") or "").strip(),
        "claim": (_cp.get("claim") or "").strip(),
        "anchor": (_cp.get("anchor") or "").strip(),
        "point": (_cp.get("point") or "").strip(),
    }
    cp_seed_json = esc(json.dumps(cp_seed, ensure_ascii=False))
    community_section = (
        '<section class="card" id="optional-export" style="opacity:.92">'
        '<h2><span class="n">Z</span> 선택 · 게시 초안 export '
        '<span class="muted" style="font-weight:500;font-size:12px">분석 본체 아님</span></h2>'
        '<p class="muted"><b>회원 전반 독시어는 위 섹션(TL;DR · Distance · L1–L5 · Evidence)입니다.</b> '
        "이 칸은 커뮤니티 문장을 <i>선택적으로</i> 뽑을 때만 씁니다. "
        "seed 없으면 일반 템플릿으로 채우지 않고 거부합니다. "
        "신상·단정·진단·ops 태그 금지.</p>"
        '<div class="cp-actions">'
        '<button type="button" id="cpGen">초안 시도</button>'
        '<button type="button" id="cpCopy">Copy</button>'
        '<button type="button" id="cpClear">Clear</button>'
        "</div>"
        '<textarea class="cp-out" id="cpOut" placeholder="비어 있음=정상. seed 없으면 거부."></textarea>'
        '<div class="cp-status" id="cpStatus">optional export · not the dossier</div>'
        '<p class="muted" style="margin-top:10px"><b>Do not post:</b> 실명·연락처 · 단정 · 진단 · ops 태그</p>'
        f'<script type="application/json" id="kampff-cp-seed">{cp_seed_json}</script>'
        "</section>"
    )


    html = f'''<!DOCTYPE html>
<html lang="{esc(meta.get("language","ko"))}">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Kampff · {esc(platform)} / {esc(nick)} · {esc(date)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <p class="kicker">Kampff · 회원 전반 독시어 · 게시 초안≠분석</p>
    <h1>{esc(nick)} — 회원 전반 분석</h1>
    <p class="sub">{esc(date)} · {esc(platform)} · id <b>{esc(tid)}</b> · viewer {esc(viewer.get("id","me"))}</p>
    <div class="meta">
      <div class="chip"><b>Target</b>{esc(nick)} · {esc(tid)}</div>
      <div class="chip"><b>Corpus</b>posts {esc(n_posts)} · cmts {esc(n_cmts)} · likes {esc(n_likes)}</div>
      <div class="chip"><b>Confidence</b>{esc(conf_label)} ({confidence:.0f})</div>
      <div class="chip"><b>MBTI</b>{esc(mbti_type)} · ACH {esc(ach_lead.get("id","H1"))}</div>
      {f'<div class="chip"><b>Clinical</b>formulation · {esc(clin_conf)}</div>' if clin_on and clin_one else ''}
    </div>
    <div class="distance-banner {banner_cls}">
      <span style="font-size:12px;color:var(--muted)">Distance</span>
      {pill(distance)}
      <span style="font-size:12px;color:var(--muted)">ACH lead: <b style="color:#fff">{esc(ach_lead.get("label",""))}</b></span>
    </div>
    <div class="tldr"><b>TL;DR</b> — {esc(tldr)}</div>
  </header>

  <nav class="toc">
    <a href="#graphs">Graphs</a>
    <a href="#honesty">Collect</a>
    <a href="#distance">Distance</a>
    <a href="#identity">Identity</a>
    <a href="#spectro">L1–L5</a>
    <a href="#mbti">MBTI</a>
    {('<a href="#clinical">Clinical</a>' if clin_section else '')}
    <a href="#cia">CIA/KGB</a>
    <a href="#quotes">Evidence</a>
    <a href="#check">Cross-check</a>
    <a href="#optional-export" style="opacity:.7">선택 export</a>
  </nav>

  <section class="card" id="graphs">
    <h2><span class="n">G</span> Visual summary</h2>
    <div class="grid3" style="margin-bottom:12px">
      <div class="stat"><div class="v">{esc(distance.upper())}</div><div class="l">distance tag</div></div>
      <div class="stat"><div class="v">{esc(mbti_type)}</div><div class="l">MBTI lean (fun)</div></div>
      <div class="stat"><div class="v">{confidence:.0f}</div><div class="l">confidence score</div></div>
    </div>

    <div class="grid2">
      <div class="chart-box">
        <h3>Motivational drivers (0–3)</h3>
        {svg_radar(d_labels, d_vals, max_v=3, title="drivers", color="#2dd4bf")}
        <div class="legend"><span><i style="background:#2dd4bf"></i>CIA-SAT drivers</span></div>
      </div>
      <div class="chart-box">
        <h3>MBTI leans (fun · low validity)</h3>
        {svg_radar(m_labels, m_vals, max_v=100, title="mbti", color="#38bdf8")}
        <div class="legend"><span><i style="background:#38bdf8"></i>{esc(mbti_type)} · not diagnostic</span></div>
      </div>
    </div>

    <div class="grid2" style="margin-top:12px">
      <div class="chart-box">
        <h3>Big Five (L1)</h3>
        {svg_hbar_rows(big5_rows)}
      </div>
      <div class="chart-box">
        <h3>Confidence gauge</h3>
        {svg_gauge(confidence, conf_label)}
      </div>
    </div>

    <div class="grid2" style="margin-top:12px">
      <div class="chart-box">
        <h3>Collection completeness</h3>
        {honesty_svg}
      </div>
      <div class="chart-box">
        <h3>ACH — hypothesis survival</h3>
        {svg_ach(ach)}
      </div>
    </div>

    <div class="grid2" style="margin-top:12px">
      <div class="chart-box">
        <h3>Source mix</h3>
        {donut}
      </div>
      <div class="chart-box">
        <h3>Alliance vs viewer (L4)</h3>
        {svg_hbar_rows([(a[0], float(a[1]), a[2] if len(a)>2 else "teal") for a in alliance])}
      </div>
    </div>

    <div class="chart-box" style="margin-top:12px">
      <h3>Ephemeris timeline (L5)</h3>
      {svg_timeline(timeline)}
    </div>

    <div class="grid2" style="margin-top:12px">
      <div class="chart-box">
        <h3>Distance map by situation</h3>
        <div class="dist-map">
          {"".join(f'<div class="dist-row"><span>{esc(o.get("when") if isinstance(o,dict) else o)}</span>{pill(o.get("tag","neutral") if isinstance(o,dict) else "neutral")}</div>' for o in (ops or [{"tag":distance,"when":"default"}]))}
        </div>
      </div>
      <div class="chart-box">
        <h3>Fit snapshot</h3>
        {svg_hbar_rows([
          ("worldview", float(matrix.get("worldview_score", 35)), "violet"),
          ("alliance", float(matrix.get("alliance_score", 40)), "teal"),
          ("stability", float(matrix.get("stability_score", 40)), "sky"),
          ("risk (inv)", 100-float(matrix.get("risk_score", 40)), "amber"),
        ])}
        <p class="muted">Higher risk bar = safer. Scores are analyst estimates 0–100.</p>
      </div>
    </div>
  </section>

  <section class="card" id="honesty">
    <h2><span class="n">0</span> Collection honesty</h2>
    <table>
      <tr><th>Axis</th><th>Status</th><th>Notes</th></tr>
      <tr><td>posts</td><td>{esc(honesty.get("posts_status", f"{posts_pct:.0f}%"))}</td><td>{esc(honesty.get("posts_note",""))}</td></tr>
      <tr><td>comments</td><td>{esc(honesty.get("comments_status", f"{cmts_pct:.0f}%"))}</td><td>{esc(honesty.get("comments_note",""))}</td></tr>
      <tr><td>likes</td><td>{esc(honesty.get("likes_status", "n/a"))}</td><td>{esc(honesty.get("likes_note",""))}</td></tr>
    </table>
    <p class="muted">{esc(honesty.get("note",""))}</p>
  </section>

  <section class="card" id="distance">
    <h2><span class="n">1</span> Matrix + distance ops</h2>
    <table>
      <tr><th>id</th><th>worldview</th><th>alliance</th><th>stability</th><th>drift</th><th>risk</th><th>one_line</th></tr>
      {matrix_row}
    </table>
    <table>
      <tr><th>tag</th><th>when</th></tr>
      {"".join(ops_rows) or f"<tr><td>{pill(distance)}</td><td>default</td></tr>"}
    </table>
    <p><b>Recommendation:</b> {pill(distance)} — {esc(analysis.get("recommendation") or tldr)}</p>
  </section>

  <section class="card" id="identity">
    <h2><span class="n">2</span> Identity</h2>
    <ul>{id_ul or "<li class='muted'>No bullets</li>"}</ul>
    <p class="muted">{esc(identity.get("not_seen",""))}</p>
  </section>
  {trigger_html}

  <section class="card" id="spectro">
    <h2><span class="n">4</span> Spectrograph L1–L5</h2>
    {"".join(l_sections) or "<p class='muted'>No L1–L5 text</p>"}
  </section>

  <section class="card" id="mbti">
    <h2><span class="n">6</span> MBTI (fun · low validity)</h2>
    <div class="grid2">
      <div>
        <p><b>Type guess:</b> {esc(mbti_type)}</p>
        <p><b>Engage cost (soft):</b> {esc(mbti.get("engage_cost",""))}</p>
        <p class="muted">confidence: {esc(mbti.get("confidence","low"))} — never sole distance reason</p>
      </div>
      <div class="chart-box">{svg_radar(m_labels, m_vals, max_v=100, color="#38bdf8")}</div>
    </div>
  </section>

  {clin_section}

  <section class="card" id="cia">
    <h2><span class="n">7</span> CIA / KGB-style card</h2>
    <div class="grid2">
      <div class="chart-box">
        <h3>Drivers</h3>
        {svg_radar(d_labels, d_vals, max_v=3, color="#2dd4bf")}
      </div>
      <div class="chart-box">
        <h3>ACH</h3>
        {svg_ach(ach)}
      </div>
    </div>
    <h3>Dossier</h3>
    <pre class="dossier">{esc(dossier)}</pre>
    <p class="muted">Public analytic form only — not ops, not medical/legal.</p>
  </section>

  <section class="card" id="quotes">
    <h2><span class="n">E</span> Evidence quotes</h2>
    {"".join(quote_html) or "<p class='muted'>No quotes attached</p>"}
  </section>

  <section class="card" id="check">
    <h2><span class="n">8</span> Cross-check prompts</h2>
    <ol>{cross_ol or "<li>keep / revise / reverse distance?</li>"}</ol>
  </section>

  <section class="card" id="files">
    <h2><span class="n">9</span> Files</h2>
    <div class="muted">{files_html}</div>
  </section>

  {community_section}

  <footer>
    Kampff report · not medical/legal · MBTI entertainment · clinical_psych = formulation only · lawful sources only · {esc(date)}
  </footer>
</div>
</body>
</html>'''
    html = html.replace("</body>", KAMPFF_CP_JS + "</body>", 1)
    return html


def main() -> None:
    ap = argparse.ArgumentParser(description="Render Kampff HTML report")
    ap.add_argument("--analysis", "-a", required=True, help="analysis.json path")
    ap.add_argument("--bundle", "-b", default="", help="optional bundle.json")
    ap.add_argument("--output", "-o", required=True, help="output .html")
    args = ap.parse_args()
    analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))
    bundle = None
    if args.bundle:
        bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    html = render(analysis, bundle)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
