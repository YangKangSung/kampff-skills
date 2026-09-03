#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kampff Distance Desk — paper-test one person's distance call.

Not a crowd graph. You + this person + quotes + time.
Mute evidence, pick a situation, scrub L5. See if the call still stands.

  python scripts/render_kampff_desk.py -a docs/sample-analysis.json -o docs/sample-desk.html
"""
from __future__ import annotations

import argparse
import html as htmlmod
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

RINGS = ("engage", "neutral", "caution", "avoid")
RING_R = {"engage": 56, "neutral": 96, "caution": 136, "avoid": 176}
RING_COLOR = {
    "engage": "#34d399",
    "neutral": "#94a3b8",
    "caution": "#fbbf24",
    "avoid": "#f87171",
}


def esc(s: Any) -> str:
    return htmlmod.escape("" if s is None else str(s))


def _dist(v: Any) -> str:
    t = str(v or "neutral").strip().lower()
    return t if t in RINGS else "neutral"


def analysis_to_desk_path(analysis_path: str | Path) -> Path:
    p = Path(analysis_path)
    name = p.name
    if name.endswith("-analysis.json"):
        return p.with_name(name[: -len("-analysis.json")] + "-desk.html")
    if name.endswith(".json"):
        return p.with_name(name[: -len(".json")] + "-desk.html")
    return p.with_suffix(".desk.html")


def _quote_id(i: int, q: dict) -> str:
    raw = q.get("id")
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    return f"q{i}"


def build_desk_model(analysis: dict) -> dict:
    """Normalize analysis.json into the desk payload (no new facts)."""
    meta = analysis.get("meta") or {}
    target = analysis.get("target") or {}
    viewer = analysis.get("viewer") or {}
    desk = analysis.get("desk") or {}
    tid = str(target.get("id") or "target")
    nick = str(target.get("nick") or tid)
    distance = _dist(analysis.get("distance"))
    raw_conf = analysis.get("confidence_score")
    conf = float(raw_conf) if raw_conf is not None and raw_conf != "" else 55.0
    quotes_in = list(analysis.get("quotes") or [])
    quotes = []
    for i, q in enumerate(quotes_in):
        if not isinstance(q, dict):
            continue
        supports = q.get("supports") or q.get("claim_ids") or []
        if isinstance(supports, str):
            supports = [supports]
        quotes.append(
            {
                "id": _quote_id(i, q),
                "label": str(q.get("label") or "Q"),
                "timestamp": str(q.get("timestamp") or q.get("t") or ""),
                "text": str(q.get("text") or q.get("quote") or ""),
                "supports": [str(x) for x in supports if str(x).strip()],
            }
        )

    ach_src = (analysis.get("cia") or {}).get("ach") or analysis.get("ach") or []
    claims_src = desk.get("claims") or ach_src
    claims = []
    for i, c in enumerate(claims_src):
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or f"H{i + 1}")
        qids = c.get("quote_ids") or c.get("quotes") or []
        if not qids:
            qids = [q["id"] for q in quotes if cid in (q.get("supports") or [])]
        if not qids and quotes and str(c.get("status") or "").lower() == "lead":
            qids = [q["id"] for q in quotes]
        claims.append(
            {
                "id": cid,
                "label": str(c.get("label") or c.get("text") or cid),
                "status": str(c.get("status") or "weak"),
                "score": float(c.get("score") or 0),
                "quote_ids": [str(x) for x in qids],
                "distance_pull": _dist(c.get("distance_pull") or c.get("supports_distance") or distance),
            }
        )
    if quotes:
        for q in quotes:
            if q["supports"]:
                continue
            lead = next((c for c in claims if c["status"] == "lead"), claims[0] if claims else None)
            if lead:
                q["supports"] = [lead["id"]]
                if q["id"] not in lead["quote_ids"]:
                    lead["quote_ids"].append(q["id"])

    ops = desk.get("situations") or analysis.get("distance_ops") or []
    situations = []
    for i, op in enumerate(ops):
        if isinstance(op, dict):
            tag = _dist(op.get("tag") or op.get("distance"))
            when = str(op.get("when") or op.get("label") or "")
            situations.append(
                {
                    "id": str(op.get("id") or f"s{i}"),
                    "tag": tag,
                    "when": when,
                    "en": str(op.get("en") or when),
                    "ko": str(op.get("ko") or when),
                }
            )
        elif isinstance(op, (list, tuple)) and len(op) >= 2:
            situations.append(
                {
                    "id": f"s{i}",
                    "tag": _dist(op[0]),
                    "when": str(op[1]),
                    "en": str(op[1]),
                    "ko": str(op[1]),
                }
            )

    history_src = desk.get("history") or analysis.get("timeline") or []
    history = []
    for ev in history_src:
        if not isinstance(ev, dict):
            continue
        history.append(
            {
                "t": str(ev.get("t") or ev.get("date") or ""),
                "label": str(ev.get("label") or ev.get("note") or ev.get("t") or ""),
                "distance": _dist(ev.get("distance") or distance),
                "note": str(ev.get("note") or ""),
            }
        )

    honesty = analysis.get("honesty") or {}
    matrix = analysis.get("matrix") or {}
    big5 = analysis.get("big5") or {}
    viewer_fit = desk.get("viewer_fit") or {}
    viewer_big5 = viewer_fit.get("big5") or viewer.get("big5") or {}

    return {
        "target": {"id": tid, "nick": nick},
        "viewer": {"id": str(viewer.get("id") or "me")},
        "distance": distance,
        "confidence": conf,
        "confidence_label": str(analysis.get("confidence") or "medium"),
        "tldr": str(analysis.get("tldr") or analysis.get("one_line") or ""),
        "recommendation": str(analysis.get("recommendation") or ""),
        "platform": str(meta.get("platform") or "community"),
        "date": str(meta.get("date") or datetime.now().strftime("%Y-%m-%d")),
        "synthetic": bool(
            desk.get("synthetic")
            if "synthetic" in desk
            else ("synthetic" in str(meta.get("protocol") or "").lower()
            or "synthetic" in str(honesty.get("note") or "").lower())
        ),
        "honesty": {
            "posts_pct": honesty.get("posts_pct"),
            "comments_pct": honesty.get("comments_pct"),
            "likes_pct": honesty.get("likes_pct"),
            "note": str(honesty.get("note") or ""),
        },
        "matrix": {
            "one_line": str(matrix.get("one_line") or ""),
            "worldview_score": float(matrix.get("worldview_score") or 0),
            "alliance_score": float(matrix.get("alliance_score") or 0),
            "stability_score": float(matrix.get("stability_score") or 0),
            "risk_score": float(matrix.get("risk_score") or 0),
        },
        "situations": situations,
        "history": history,
        "quotes": quotes,
        "claims": claims,
        "big5": {k: float(big5.get(k, 50)) for k in ("O", "C", "E", "A", "N")},
        "viewer_big5": {k: float(viewer_big5.get(k, 50)) for k in ("O", "C", "E", "A", "N")}
        if viewer_big5
        else {},
        "viewer_note": str(viewer_fit.get("note") or ""),
        "cross_check": [str(x) for x in (analysis.get("cross_check") or [])],
        "report_href": str((analysis.get("files") or {}).get("html") or ""),
    }


def desk_cta_html(href: str) -> str:
    if not href:
        return ""
    return (
        f'<p class="desk-cta">Paper-test this call → '
        f'<a href="{esc(href)}">Distance Desk</a>'
        f' <span class="muted">mute quotes · pick a situation · scrub time · one person</span></p>'
    )


CSS = r"""
:root {
  --bg:#0b0f14; --panel:#121821; --panel2:#18202b; --line:#243041;
  --text:#e7eef8; --muted:#93a4bb; --accent:#5eead4; --accent2:#38bdf8;
  --warn:#fbbf24; --ok:#4ade80; --bad:#f87171;
  --mono:"JetBrains Mono","SF Mono",Consolas,monospace;
  --sans:"Segoe UI",system-ui,sans-serif;
  --engage:#34d399; --neutral:#94a3b8; --caution:#fbbf24; --avoid:#f87171;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;font-family:var(--sans);color:var(--text);line-height:1.5;
  background:
    radial-gradient(1100px 520px at 8% -12%,#12324a55,transparent),
    radial-gradient(800px 420px at 100% 0%,#0f3d3555,transparent),
    var(--bg);
}
.wrap{max-width:1180px;margin:0 auto;padding:22px 16px 72px}
.top{
  display:flex;justify-content:space-between;align-items:flex-start;gap:12px;
  margin-bottom:14px;flex-wrap:wrap;
}
.kicker{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin:0 0 6px}
h1{margin:0;font-size:26px;letter-spacing:-.02em}
.sub{color:var(--muted);font-size:13px;margin:6px 0 0}
.lang{display:flex;gap:6px}
.lang button{
  font:11px var(--mono);color:var(--muted);background:#0d131b;
  border:1px solid var(--line);border-radius:999px;padding:5px 10px;cursor:pointer;
}
.lang button.on{color:#042f2e;background:var(--accent);border-color:var(--accent)}
.desk{display:grid;grid-template-columns:280px 1fr;gap:14px}
@media(max-width:900px){.desk{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:16px}
.call{font-size:34px;font-weight:700;letter-spacing:-.03em;margin:4px 0 2px;text-transform:uppercase;font-family:var(--mono)}
.call.engage{color:var(--engage)} .call.neutral{color:#cbd5e1}
.call.caution{color:var(--caution)} .call.avoid{color:var(--avoid)}
.pill{display:inline-flex;align-items:center;padding:2px 9px;border-radius:999px;font-family:var(--mono);font-size:11px;border:1px solid}
.pill.engage{color:#a7f3d0;border-color:#059669;background:#064e3b}
.pill.neutral{color:#cbd5e1;border-color:#475569;background:#1e293b}
.pill.caution{color:#fde68a;border-color:#b45309;background:#422006}
.pill.avoid{color:#fecaca;border-color:#b91c1c;background:#450a0a}
.muted{color:var(--muted);font-size:12.5px}
.tldr{margin:10px 0 0;padding:10px 12px;border-radius:10px;background:#0c1c28;border:1px solid #1e4d45;font-size:13.5px}
.warnbar{margin-top:10px;padding:9px 11px;border-radius:10px;background:#1c1408;border:1px solid #7c4a0a;color:#fde68a;font-size:12.5px;display:none}
.warnbar.on{display:block}
.stat{display:flex;justify-content:space-between;gap:8px;font-size:12.5px;margin:7px 0;padding-bottom:7px;border-bottom:1px solid #1b2533}
.stat b{font-family:var(--mono);color:var(--accent)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.sit{
  font:12px var(--sans);color:var(--text);background:#0d131b;border:1px solid var(--line);
  border-radius:999px;padding:5px 10px;cursor:pointer;text-align:left;
}
.sit.on{border-color:var(--accent);color:var(--accent);background:#0c1c1a}
.ring-box{background:#0a1018;border:1px solid var(--line);border-radius:16px;padding:10px}
svg.rings{display:block;width:100%;height:auto;max-height:460px}
.legend{display:flex;flex-wrap:wrap;gap:10px;margin-top:8px;font-size:11px;color:var(--muted)}
.legend i{display:inline-block;width:9px;height:9px;border-radius:99px;margin-right:4px}
input[type=range]{width:100%;accent-color:var(--accent)}
.q{
  margin:8px 0;padding:10px 12px;background:#0d151f;border:1px solid var(--line);
  border-radius:10px;display:grid;grid-template-columns:auto 1fr;gap:10px;align-items:start;
}
.q.muted-q{opacity:.42}
.q pre{white-space:pre-wrap;margin:4px 0 0;font:12.5px/1.45 var(--mono);color:#d5deea}
.q figcaption{color:var(--muted);font-size:11px}
.q button{
  font:11px var(--mono);cursor:pointer;border-radius:8px;padding:6px 8px;
  background:#0b1726;border:1px solid #1e3a5f;color:#dbeafe;
}
.q button.on{background:#422006;border-color:#b45309;color:#fde68a}
.hbar{display:grid;gap:8px}
.hbar-row{display:grid;grid-template-columns:140px 1fr 44px;gap:8px;align-items:center;font-size:12px}
.track{height:9px;background:#1a2330;border-radius:99px;overflow:hidden}
.fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#0ea5e9,#2dd4bf)}
.fill.lead{background:linear-gradient(90deg,#34d399,#5eead4)}
.fill.weak{background:linear-gradient(90deg,#f59e0b,#fbbf24)}
.fill.fail{background:linear-gradient(90deg,#e11d48,#fb7185)}
.radar{width:100%;height:auto}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
@media(max-width:900px){.row2{grid-template-columns:1fr}}
footer{margin-top:18px;color:var(--muted);font-size:12px}
a{color:var(--accent2)}
[data-i18n-ko]{display:none}
html[lang=ko] [data-i18n-en]{display:none}
html[lang=ko] [data-i18n-ko]{display:inline}
html[lang=ko] p[data-i18n-ko],html[lang=ko] li[data-i18n-ko]{display:block}
"""

JS = r"""
(function(){
  var seedEl = document.getElementById("kampff-desk-seed");
  var D = {};
  try { D = JSON.parse(seedEl.textContent || "{}"); } catch (e) { D = {}; }
  var muted = {};
  var sit = null;
    var histLast = (D.history && D.history.length) ? D.history.length - 1 : 0;
    var hist = histLast;
    var histTouched = false;
  var rings = {engage:56, neutral:96, caution:136, avoid:176};
  var colors = {engage:"#34d399", neutral:"#94a3b8", caution:"#fbbf24", avoid:"#f87171"};

  function $(id){ return document.getElementById(id); }
  function setLang(lang){
    document.documentElement.lang = lang === "ko" ? "ko" : "en";
    document.querySelectorAll(".lang button").forEach(function(b){
      b.classList.toggle("on", b.getAttribute("data-lang") === document.documentElement.lang);
    });
    try { localStorage.setItem("kampff-desk-lang", document.documentElement.lang); } catch (e) {}
  }
  function live(){
    var quotes = D.quotes || [];
    var n = quotes.length || 1;
    var muteN = 0;
    quotes.forEach(function(q){ if (muted[q.id]) muteN++; });
    var muteFrac = muteN / n;
    var claims = (D.claims || []).map(function(c){
      var ids = c.quote_ids || [];
      var m = 0;
      ids.forEach(function(id){ if (muted[id]) m++; });
      var frac = ids.length ? (m / ids.length) : muteFrac;
      var score = Number(c.score || 0) * (1 - 0.65 * frac);
      return {id:c.id, label:c.label, status:c.status, base:Number(c.score||0), score:score, quote_ids:ids, distance_pull:c.distance_pull};
    }).sort(function(a,b){ return b.score - a.score; });
    var origLead = (D.claims || []).find(function(c){ return c.status === "lead"; }) || (D.claims||[])[0];
    var lead = claims[0];
    var second = claims[1];
    var conf = Math.max(8, Math.round(Number(D.confidence||55) * (1 - 0.55 * muteFrac)));
    var unanchored = muteN === quotes.length && quotes.length > 0;
    var flipped = !!(origLead && lead && origLead.id !== lead.id);
    var close = !!(lead && second && second.score > lead.score * 0.92);
    var dist = D.distance;
    if (sit && sit.tag) dist = sit.tag;
    else if (histTouched && D.history && D.history[hist] && D.history[hist].distance) dist = D.history[hist].distance;
    return {claims:claims, conf:conf, muteN:muteN, muteFrac:muteFrac, unanchored:unanchored, flipped:flipped, close:close, dist:dist, lead:lead, origLead:origLead};
  }
  function place(dist){
    var r = rings[dist] || rings.neutral;
    var node = $("subj");
    if (!node) return;
    node.setAttribute("cx", String(200));
    node.setAttribute("cy", String(200 - r));
    node.setAttribute("fill", colors[dist] || colors.neutral);
    var glow = $("subjGlow");
    if (glow) {
      glow.setAttribute("cx", "200");
      glow.setAttribute("cy", String(200 - r));
      glow.setAttribute("stroke", colors[dist] || colors.neutral);
    }
    var lab = $("subjLab");
    if (lab) {
      lab.setAttribute("x", "200");
      lab.setAttribute("y", String(200 - r - 18));
    }
  }
  function paint(){
    var L = live();
    var call = $("callTag");
    if (call) {
      call.textContent = L.dist;
      call.className = "call " + L.dist;
    }
    var conf = $("confNow");
    if (conf) conf.textContent = String(L.conf);
    var rec = $("sitRec");
    if (rec) rec.textContent = L.dist;
    rec && (rec.className = "pill " + L.dist);
    place(L.dist);
    var warn = $("warn");
    var bits = [];
    if (L.unanchored) bits.push("No quotes left — this call is vibe, not evidence.");
    if (L.flipped) bits.push("Lead hypothesis flipped after mute. Do not keep the original call on autopilot.");
    if (L.close && !L.flipped) bits.push("Rival hypothesis is close. Call is soft.");
    if (L.muteN && !L.unanchored) bits.push("Muted " + L.muteN + " quote(s). Confidence is paper-discounted.");
    if (warn) {
      warn.textContent = bits.join(" ");
      warn.className = "warnbar" + (bits.length ? " on" : "");
    }
    var box = $("claims");
    if (box) {
      box.innerHTML = L.claims.map(function(c){
        var w = Math.max(2, Math.min(100, c.score));
        var cls = (c.id === (L.lead && L.lead.id) ? "lead" : (c.score < 30 ? "fail" : "weak"));
        return '<div class="hbar-row"><span>' + escapeHtml(c.id + " · " + c.label) +
          '</span><div class="track"><div class="fill ' + cls + '" style="width:' + w +
          '%"></div></div><span>' + Math.round(c.score) + '</span></div>';
      }).join("");
    }
    document.querySelectorAll(".q").forEach(function(el){
      var id = el.getAttribute("data-qid");
      el.classList.toggle("muted-q", !!muted[id]);
      var b = el.querySelector("button");
      if (b) {
        b.classList.toggle("on", !!muted[id]);
        b.textContent = muted[id] ? "muted" : "mute";
      }
    });
    var ev = (D.history || [])[hist];
    var ht = $("histLabel");
    if (ht) ht.textContent = ev ? (ev.t + " · " + ev.label) : "—";
  }
  function escapeHtml(s){
    return String(s||"").replace(/[&<>"]/g, function(ch){
      return ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[ch]);
    });
  }
  document.querySelectorAll(".lang button").forEach(function(b){
    b.addEventListener("click", function(){ setLang(b.getAttribute("data-lang")); });
  });
  document.querySelectorAll(".sit").forEach(function(b){
    b.addEventListener("click", function(){
      var id = b.getAttribute("data-sit");
      sit = (D.situations || []).find(function(s){ return s.id === id; }) || null;
      document.querySelectorAll(".sit").forEach(function(x){ x.classList.toggle("on", x === b); });
      paint();
    });
  });
  document.querySelectorAll(".q button").forEach(function(b){
    b.addEventListener("click", function(){
      var id = b.getAttribute("data-qid");
      muted[id] = !muted[id];
      paint();
    });
  });
  var rng = $("histRange");
  if (rng) {
    rng.addEventListener("input", function(){
      hist = Number(rng.value || 0);
      histTouched = true;
      sit = null;
      document.querySelectorAll(".sit").forEach(function(x){ x.classList.remove("on"); });
      paint();
    });
  }
  var reset = $("resetDesk");
  if (reset) reset.addEventListener("click", function(){
    muted = {};
    sit = null;
    histTouched = false;
    hist = histLast;
    if (rng) rng.value = String(hist);
    document.querySelectorAll(".sit").forEach(function(x){ x.classList.remove("on"); });
    paint();
  });
  var saved = "en";
  try { saved = localStorage.getItem("kampff-desk-lang") || document.documentElement.getAttribute("data-kampff-lang") || "en"; } catch (e) {}
  setLang(saved === "ko" ? "ko" : "en");
  paint();
})();
"""


def _radar_svg(subject: dict, viewer: dict) -> str:
    axes = [("O", "O"), ("C", "C"), ("E", "E"), ("A", "A"), ("N", "N")]
    n = len(axes)
    cx = cy = 90.0
    r = 68.0

    def pts2(src: dict) -> str:
        out = []
        for i, (k, _) in enumerate(axes):
            ang = -math.pi / 2 + i * 2 * math.pi / n
            v = max(0.0, min(100.0, float(src.get(k, 50)))) / 100.0
            out.append(f"{cx + r * v * math.cos(ang):.1f},{cy + r * v * math.sin(ang):.1f}")
        return " ".join(out)

    rings = []
    for frac in (0.25, 0.5, 0.75, 1.0):
        rings.append(
            f'<polygon points="{pts2({k: 100 * frac for k, _ in axes})}" fill="none" stroke="#243041" stroke-width="1"/>'
        )
    labels = []
    for i, (_, lab) in enumerate(axes):
        ang = -math.pi / 2 + i * 2 * math.pi / n
        labels.append(
            f'<text x="{cx + (r + 14) * math.cos(ang):.1f}" y="{cy + (r + 14) * math.sin(ang):.1f}" '
            f'text-anchor="middle" fill="#93a4bb" font-size="10">{lab}</text>'
        )
    viewer_poly = ""
    if viewer:
        viewer_poly = (
            f'<polygon points="{pts2(viewer)}" fill="#38bdf822" stroke="#38bdf8" stroke-width="1.4"/>'
        )
    return f'''<svg class="radar" viewBox="0 0 180 180" role="img" aria-label="you vs them Big Five">
  {"".join(rings)}
  {viewer_poly}
  <polygon points="{pts2(subject)}" fill="#5eead433" stroke="#5eead4" stroke-width="1.6"/>
  {"".join(labels)}
</svg>'''


def _rings_svg(model: dict) -> str:
    nick = esc(model["target"]["nick"])
    you = esc(model["viewer"]["id"])
    circles = []
    labels = []
    for name, rr in RING_R.items():
        col = RING_COLOR[name]
        circles.append(
            f'<circle cx="200" cy="200" r="{rr}" fill="none" stroke="{col}" stroke-opacity=".35" stroke-width="1.2"/>'
        )
        labels.append(
            f'<text x="{200 + rr + 8}" y="204" text-anchor="start" fill="{col}" font-size="10" font-family="ui-monospace,monospace">{name}</text>'
        )
    return f'''<svg class="rings" viewBox="0 0 400 400" role="img" aria-label="distance rings">
  {"".join(circles)}
  <circle cx="200" cy="200" r="18" fill="#0c1c28" stroke="#5eead4" stroke-width="2"/>
  <text x="200" y="204" text-anchor="middle" fill="#5eead4" font-size="9" font-family="ui-monospace,monospace">{you}</text>
  <circle id="subjGlow" cx="200" cy="104" r="16" fill="none" stroke="#94a3b8" stroke-width="6" opacity=".35"/>
  <circle id="subj" cx="200" cy="104" r="9" fill="#94a3b8"/>
  <text id="subjLab" x="200" y="86" text-anchor="middle" fill="#e7eef8" font-size="11">{nick}</text>
  {"".join(labels)}
</svg>'''


def render_desk(model: dict, *, lang: str = "en") -> str:
    lang = "ko" if lang == "ko" else "en"
    tid = esc(model["target"]["id"])
    nick = esc(model["target"]["nick"])
    you = esc(model["viewer"]["id"])
    date = esc(model["date"])
    platform = esc(model["platform"])
    tldr = esc(model["tldr"])
    rec = esc(model["recommendation"])
    syn = (
        '<span class="pill neutral">synthetic</span> '
        if model.get("synthetic")
        else ""
    )
    report = model.get("report_href") or ""
    report_link = (
        f'<a href="{esc(report)}"><span data-i18n-en>Full dossier</span><span data-i18n-ko>전체 도셔</span></a>'
        if report
        else ""
    )
    sits = []
    for s in model.get("situations") or []:
        sits.append(
            f'<button type="button" class="sit" data-sit="{esc(s["id"])}">'
            f'<span class="pill {esc(s["tag"])}">{esc(s["tag"])}</span> {esc(s["when"])}'
            f"</button>"
        )
    hist = model.get("history") or []
    hist_ctrl = ""
    if hist:
        last = len(hist) - 1
        hist_ctrl = (
            f'<label class="muted" for="histRange"><span data-i18n-en>Time (L5)</span>'
            f'<span data-i18n-ko>시간축 (L5)</span></label>'
            f'<input id="histRange" type="range" min="0" max="{last}" value="{last}" />'
            f'<p class="muted" id="histLabel">{esc(hist[last]["t"])} · {esc(hist[last]["label"])}</p>'
        )
    quotes_html = []
    for q in model.get("quotes") or []:
        quotes_html.append(
            f'<figure class="q" data-qid="{esc(q["id"])}">'
            f'<button type="button" data-qid="{esc(q["id"])}">mute</button>'
            f"<div><figcaption>{esc(q['label'])} · {esc(q['timestamp'])} · "
            f"supports {esc(', '.join(q.get('supports') or []) or '—')}</figcaption>"
            f"<pre>{esc(q['text'])}</pre></div></figure>"
        )
    if not quotes_html:
        quotes_html.append(
            '<p class="muted"><span data-i18n-en>No quotes in this analysis — desk cannot paper-test.</span>'
            '<span data-i18n-ko>인용이 없으면 책상에서 검증할 수 없습니다.</span></p>'
        )
    checks = "".join(f"<li>{esc(x)}</li>" for x in (model.get("cross_check") or []))
    def _pct(v: Any) -> str:
        if v is None or v == "":
            return "n/a"
        try:
            return f"{float(v):.0f}%"
        except (TypeError, ValueError):
            return "n/a"

    h = model.get("honesty") or {}
    honesty_line = (
        f"posts {_pct(h.get('posts_pct'))} · comments {_pct(h.get('comments_pct'))} · likes {_pct(h.get('likes_pct'))}"
    )
    payload = json.dumps(model, ensure_ascii=False).replace("<", "\\u003c")
    viewer_note = esc(model.get("viewer_note") or "")
    radar = _radar_svg(model.get("big5") or {}, model.get("viewer_big5") or {})
    return f'''<!DOCTYPE html>
<html lang="{lang}" data-kampff-lang="{lang}">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Kampff Desk · {platform} / {nick} · {date}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div>
      <p class="kicker">Kampff · Distance Desk</p>
      <h1>{nick} <span class="muted">/ {tid}</span></h1>
      <p class="sub">{date} · {platform} · viewer {you} · {syn}{report_link}</p>
    </div>
    <div class="lang" role="group" aria-label="Language">
      <button type="button" data-lang="en">English</button>
      <button type="button" data-lang="ko">한국어</button>
    </div>
  </div>

  <div class="desk">
    <aside class="card">
      <p class="muted" data-i18n-en>Distance call</p>
      <p class="muted" data-i18n-ko>거리 판정</p>
      <div id="callTag" class="call {esc(model['distance'])}">{esc(model['distance'])}</div>
      <div class="stat"><span data-i18n-en>Paper confidence</span><span data-i18n-ko>종이 신뢰도</span><b id="confNow">{int(model['confidence'])}</b></div>
      <div class="stat"><span data-i18n-en>Honesty</span><span data-i18n-ko>수집 정직</span><b>{esc(honesty_line)}</b></div>
      <p class="tldr">{tldr}</p>
      <p class="muted" style="margin-top:8px">{rec}</p>
      <div id="warn" class="warnbar"></div>
      <p class="muted" style="margin-top:12px" data-i18n-en>Situation — moves the node. Does not invent a new person.</p>
      <p class="muted" style="margin-top:12px" data-i18n-ko>상황 — 점만 옮깁니다. 사람을 새로 만들지 않습니다.</p>
      <div class="chips">{"".join(sits) or '<span class="muted">—</span>'}</div>
      <p style="margin:12px 0 4px" class="muted"><span data-i18n-en>This situation → stay</span><span data-i18n-ko>이 상황 → 거리</span>
        <span id="sitRec" class="pill {esc(model['distance'])}">{esc(model['distance'])}</span></p>
      {hist_ctrl}
      <p><button type="button" class="sit" id="resetDesk"><span data-i18n-en>Reset mutes + time</span><span data-i18n-ko>뮤트·시간 초기화</span></button></p>
    </aside>
    <section class="ring-box">
      {_rings_svg(model)}
      <div class="legend">
        <span><i style="background:var(--accent)"></i><span data-i18n-en>You (center)</span><span data-i18n-ko>나 (가운데)</span></span>
        <span><i style="background:var(--engage)"></i>engage</span>
        <span><i style="background:var(--neutral)"></i>neutral</span>
        <span><i style="background:var(--caution)"></i>caution</span>
        <span><i style="background:var(--avoid)"></i>avoid</span>
      </div>
      <p class="muted" style="margin:8px 12px 4px" data-i18n-en>One person on rings around you. Not a board map. Edges between third parties do not belong here.</p>
      <p class="muted" style="margin:8px 12px 4px" data-i18n-ko>당신 둘레의 고리에 한 사람만. 게시판 전체 지도가 아닙니다. 제3자끼리의 선은 여기 없습니다.</p>
    </section>
  </div>

  <div class="row2">
    <section class="card">
      <h2 style="margin:0 0 8px;font-size:16px"><span data-i18n-en>Evidence ledger</span><span data-i18n-ko>근거 원장</span></h2>
      <p class="muted" data-i18n-en>Mute a quote. Confidence drops. Lead H can flip. The distance tag does not auto-rewrite itself — you decide.</p>
      <p class="muted" data-i18n-ko>인용을 끄면 신뢰도가 내려갑니다. 선두 가설은 뒤집힐 수 있습니다. 거리 태그는 자동으로 바뀌지 않습니다 — 당신이 정합니다.</p>
      {"".join(quotes_html)}
    </section>
    <section class="card">
      <h2 style="margin:0 0 8px;font-size:16px"><span data-i18n-en>ACH after mute</span><span data-i18n-ko>뮤트 후 ACH</span></h2>
      <div class="hbar" id="claims"></div>
      <h3 style="margin:16px 0 6px;font-size:13px;color:#dbeafe"><span data-i18n-en>You vs them (Big Five lean)</span><span data-i18n-ko>나와 이 사람 (Big Five lean)</span></h3>
      {radar}
      <p class="muted">{viewer_note or "Teal = subject. Blue = viewer (only if present in analysis)."}</p>
      <h3 style="margin:16px 0 6px;font-size:13px;color:#dbeafe"><span data-i18n-en>Still ask</span><span data-i18n-ko>아직 물을 것</span></h3>
      <ul>{checks or "<li>—</li>"}</ul>
    </section>
  </div>

  <footer>
    Kampff Distance Desk · one person · not medical/legal · mute is a paper test, not a new crawl · {date}
  </footer>
</div>
<script type="application/json" id="kampff-desk-seed">{payload}</script>
<script>{JS}</script>
</body>
</html>
'''


def write_desk(analysis: dict, out: Path, *, lang: str = "en") -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_desk(build_desk_model(analysis), lang=lang), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Render Kampff Distance Desk HTML")
    ap.add_argument("--analysis", "-a", required=True, help="analysis.json path")
    ap.add_argument("--output", "-o", default="", help="output .html (default: sibling *-desk.html)")
    ap.add_argument(
        "--lang",
        choices=("auto", "en", "ko"),
        default="",
        help="Default language. Default: $KAMPFF_LANG or auto.",
    )
    args = ap.parse_args()
    analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))
    out = Path(args.output) if args.output else analysis_to_desk_path(args.analysis)
    raw = (args.lang or os.environ.get("KAMPFF_LANG") or "auto").strip().lower()
    if raw in ("en", "ko"):
        lang = raw
    else:
        loc = (os.environ.get("LANG") or os.environ.get("LC_ALL") or "").lower()
        lang = "ko" if loc.startswith("ko") else "en"
    path = write_desk(analysis, out, lang=lang)
    print(path)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main()
