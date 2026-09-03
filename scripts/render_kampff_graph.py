#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render an interactive Kampff relation graph (offline).

  python scripts/render_kampff_graph.py -g docs/sample-graph.json -o docs/sample-graph.html
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from kampff_graph import graph_to_html_path

CSS = r"""
:root {
  --bg:#0b0f14; --panel:#121821; --line:#243041; --text:#e7eef8; --muted:#93a4bb;
  --accent:#5eead4; --l1:#64748b; --l2:#38bdf8; --l3:#2dd4bf; --l4:#fbbf24; --l5:#f87171;
  --mono:"JetBrains Mono","SF Mono",Consolas,monospace; --sans:"Segoe UI",system-ui,sans-serif;
}
*{box-sizing:border-box}
body{margin:0;font-family:var(--sans);color:var(--text);background:
  radial-gradient(1000px 480px at 0% -10%,#12324a44,transparent),var(--bg)}
.wrap{display:grid;grid-template-columns:260px 1fr 300px;min-height:100vh}
@media(max-width:1100px){.wrap{grid-template-columns:1fr;}}
aside,section.card{padding:16px;border-right:1px solid var(--line)}
section.card{border-right:none;border-left:1px solid var(--line)}
h1{font-size:18px;margin:0 0 4px}
.kicker{font:11px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin:0 0 8px}
.muted{color:var(--muted);font-size:12.5px}
label{display:block;font-size:11px;color:var(--muted);margin:12px 0 4px}
input[type=range]{width:100%;accent-color:var(--accent)}
.lvl{font:22px/1 var(--mono);color:var(--accent);margin:0}
.chip{display:inline-flex;align-items:center;gap:6px;margin:4px 6px 0 0;font-size:12px}
.chip i{width:10px;height:10px;border-radius:99px;display:inline-block}
.kinds button{
  font:11px var(--mono);margin:3px 4px 0 0;padding:4px 8px;border-radius:999px;cursor:pointer;
  background:#0d131b;border:1px solid var(--line);color:var(--muted);
}
.kinds button.on{color:#042f2e;background:var(--accent);border-color:var(--accent)}
.seg{display:flex;gap:0;margin-top:4px}
.seg button{
  flex:1;font:11px var(--mono);padding:6px 8px;cursor:pointer;
  background:#0d131b;border:1px solid var(--line);color:var(--muted);
}
.seg button:first-child{border-radius:8px 0 0 8px}
.seg button:last-child{border-radius:0 8px 8px 0}
.seg button.on{color:#042f2e;background:var(--accent);border-color:var(--accent)}
.val{font:12px var(--mono);color:var(--accent);float:right}
#stage{position:relative;min-height:70vh;background:#0a1018}
canvas{display:block;width:100%;height:100%;min-height:70vh}
.warn{margin-top:10px;padding:8px 10px;border-radius:10px;background:#1c1408;border:1px solid #7c4a0a;color:#fde68a;font-size:12.5px}
.q{margin:8px 0;padding:8px 10px;background:#0d151f;border-left:3px solid var(--accent);font:12px/1.4 var(--mono);white-space:pre-wrap}
.pill{display:inline-block;font:11px var(--mono);padding:2px 8px;border-radius:999px;border:1px solid var(--line)}
a{color:#38bdf8}
"""

JS = r"""
(function(){
  var G = {};
  try { G = JSON.parse(document.getElementById("kampff-graph-seed").textContent || "{}"); } catch(e) { G = {}; }
  var nodes = (G.nodes || []).map(function(n,i){
    return {id:n.id, nick:n.nick||n.id, distance:n.distance, n_texts:n.n_texts||0, degree:n.degree||0, coord_score:n.coord_score||0, role:n.role, hop:n.hop||0, x: 400 + Math.cos(i)*80, y: 300 + Math.sin(i)*80, vx:0, vy:0};
  });
  var byId = {};
  nodes.forEach(function(n){ byId[n.id] = n; });
  var edges = (G.edges || []).map(function(e){
    return Object.assign({}, e, {a: byId[e.source], b: byId[e.target]});
  }).filter(function(e){ return e.a && e.b; });
  var minLevel = 1;
  var belowMode = "hide";
  var minWidth = 1.2;
  var kindsOn = {replies_to:true, co_thread:true, burst_sync:true, near_dup:true, mention:true, likes:true};
  var sel = null;
  var drag = null;
  var colors = {1:"#64748b",2:"#38bdf8",3:"#2dd4bf",4:"#fbbf24",5:"#f87171"};
  try {
    if (localStorage.getItem("kampff-graph-below") === "dim") belowMode = "dim";
    var w0 = Number(localStorage.getItem("kampff-graph-minw"));
    if (w0 >= 0.5 && w0 <= 8) minWidth = w0;
  } catch (e) {}

  function $(id){ return document.getElementById(id); }
  function kindOk(e){
    return (e.kinds||[]).some(function(k){ return kindsOn[k]; });
  }
  function drawnEdges(){
    return edges.filter(function(e){
      if (!kindOk(e)) return false;
      if (belowMode === "hide" && e.level < minLevel) return false;
      return true;
    });
  }
  function focusEdges(){
    return drawnEdges().filter(function(e){ return e.level >= minLevel; });
  }
  function visibleNodeIds(drawn){
    var s = {};
    drawn.forEach(function(e){ s[e.source]=1; s[e.target]=1; });
    if (minLevel <= 1 || belowMode === "dim") nodes.forEach(function(n){ s[n.id]=1; });
    nodes.forEach(function(n){ if (n.role === "seed") s[n.id]=1; });
    return s;
  }
  function widthOf(e){
    return minWidth + Math.log(1 + (e.weight||1)) * 2.4;
  }
  function paintInfo(item){
    var box = $("info");
    if (!box) return;
    if (!item) {
      box.innerHTML = '<p class="muted">Click a node or a line.</p>';
      return;
    }
    if (item.nick) {
      box.innerHTML = '<h2 style="margin:0 0 6px;font-size:16px">'+esc(item.nick)+'</h2>'+
        '<p class="muted">id '+esc(item.id)+' · texts '+item.n_texts+' · degree '+item.degree+'</p>'+
        (item.role === "seed" ? '<p><span class="pill">seed</span> posts / comments / likes around this id</p>' : '')+
        (item.hop ? '<p class="muted">hop '+item.hop+(item.hop>=2?' · via already-harvested alter':'')+'</p>' : '')+
        (item.distance ? '<p>L1 distance <span class="pill">'+esc(item.distance)+'</span></p>' : '<p class="muted">No L1 distance joined.</p>')+
        '<p>coord_score <b>'+item.coord_score+'</b></p>';
      return;
    }
    var parts = (item.parts||[]).map(function(p){
      var q = (p.quotes||[]).map(function(t){ return '<div class="q">'+esc(t)+'</div>'; }).join("");
      return '<p><span class="pill">'+esc(p.kind)+'</span> n='+p.n+' · L'+p.level+(p.jaccard!=null?' · J='+p.jaccard:'')+'</p>'+q;
    }).join("");
    box.innerHTML = '<h2 style="margin:0 0 6px;font-size:16px">'+esc(item.source)+' — '+esc(item.target)+'</h2>'+
      '<p>level <b>'+item.level+'</b> '+esc(item.level_name)+' · weight '+item.weight+' · '+esc(item.confidence)+'</p>'+
      '<p class="muted">'+esc((item.kinds||[]).join(" · "))+'</p>'+parts;
  }
  function esc(s){ return String(s||"").replace(/[&<>"]/g, function(ch){ return ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[ch]); }); }

  var canvas = $("graph");
  var ctx = canvas.getContext("2d");
  function resize(){
    var r = canvas.parentElement.getBoundingClientRect();
    canvas.width = Math.max(320, r.width);
    canvas.height = Math.max(420, r.height);
  }
  resize();
  window.addEventListener("resize", resize);

  function step(){
    var vis = drawnEdges();
    var keep = visibleNodeIds(vis);
    var live = nodes.filter(function(n){ return keep[n.id]; });
    var i,j,n,m,e,dx,dy,dist,f;
    for (i=0;i<live.length;i++){
      for (j=i+1;j<live.length;j++){
        n = live[i]; m = live[j];
        dx = n.x-m.x; dy = n.y-m.y;
        dist = Math.sqrt(dx*dx+dy*dy) || 0.01;
        f = 900 / (dist*dist);
        n.vx += dx/dist*f; n.vy += dy/dist*f;
        m.vx -= dx/dist*f; m.vy -= dy/dist*f;
      }
    }
    vis.forEach(function(e){
      dx = e.b.x-e.a.x; dy = e.b.y-e.a.y;
      dist = Math.sqrt(dx*dx+dy*dy) || 0.01;
      var rest = 150 - e.level*8;
      f = (dist-rest)*0.012;
      e.a.vx += dx/dist*f; e.a.vy += dy/dist*f;
      e.b.vx -= dx/dist*f; e.b.vy -= dy/dist*f;
    });
    var cx = canvas.width/2, cy = canvas.height/2;
    live.forEach(function(n){
      var pull = n.role === "seed" ? 0.018 : 0.002;
      n.vx += (cx-n.x)*pull;
      n.vy += (cy-n.y)*pull;
      if (n !== drag) {
        n.vx *= 0.86; n.vy *= 0.86;
        n.x += n.vx; n.y += n.vy;
      }
      n.x = Math.max(24, Math.min(canvas.width-24, n.x));
      n.y = Math.max(24, Math.min(canvas.height-24, n.y));
    });
  }
  function hit(x,y){
    var vis = drawnEdges();
    var keep = visibleNodeIds(vis);
    for (var i=nodes.length-1;i>=0;i--){
      var n = nodes[i];
      if (!keep[n.id]) continue;
      var dx=n.x-x, dy=n.y-y;
      if (dx*dx+dy*dy < 14*14) return n;
    }
    var ranked = vis.slice().sort(function(a,b){ return (b.level||0)-(a.level||0); });
    for (var j=0;j<ranked.length;j++){
      var e = ranked[j];
      if (distToSeg(x,y,e.a.x,e.a.y,e.b.x,e.b.y) < 7) return e;
    }
    return null;
  }
  function distToSeg(px,py,x1,y1,x2,y2){
    var dx=x2-x1, dy=y2-y1, l=dx*dx+dy*dy || 1;
    var t=Math.max(0,Math.min(1,((px-x1)*dx+(py-y1)*dy)/l));
    var x=x1+t*dx, y=y1+t*dy;
    return Math.sqrt((px-x)*(px-x)+(py-y)*(py-y));
  }
  function draw(){
    ctx.clearRect(0,0,canvas.width,canvas.height);
    var vis = drawnEdges();
    var keep = visibleNodeIds(vis);
    var focusIds = {};
    focusEdges().forEach(function(e){ focusIds[e.source]=1; focusIds[e.target]=1; });
    vis.forEach(function(e){
      var below = e.level < minLevel;
      ctx.beginPath();
      ctx.moveTo(e.a.x, e.a.y);
      ctx.lineTo(e.b.x, e.b.y);
      ctx.strokeStyle = colors[e.level] || colors[1];
      ctx.lineWidth = widthOf(e);
      var a = below ? 0.16 : 0.92;
      if (sel && sel !== e && sel.id !== e.source && sel.id !== e.target) a *= below ? 0.5 : 0.2;
      ctx.globalAlpha = a;
      ctx.stroke();
      ctx.globalAlpha = 1;
    });
    nodes.forEach(function(n){
      if (!keep[n.id]) return;
      var dimNode = belowMode === "dim" && minLevel > 1 && !focusIds[n.id];
      var r = 7 + Math.min(8, Math.sqrt(n.n_texts||1)*1.6);
      if (n.role === "seed") r += 4;
      if (n.hop >= 2) r = Math.max(5, r - 2);
      ctx.beginPath();
      ctx.arc(n.x,n.y,r,0,Math.PI*2);
      ctx.fillStyle = n.role==="seed" ? "#fbbf24" : (n.role==="viewer" ? "#5eead4" : (n.hop>=2 ? "#7dd3fc" : (n.coord_score>=40 ? "#f87171" : "#e7eef8")));
      var a = dimNode ? 0.22 : 1;
      if (sel && sel !== n && !(sel.source && (sel.source===n.id || sel.target===n.id))) a *= dimNode ? 0.7 : 0.25;
      ctx.globalAlpha = a;
      ctx.fill();
      if (n.role === "seed") {
        ctx.strokeStyle = "#fde68a";
        ctx.lineWidth = 2;
        ctx.stroke();
      }
      ctx.globalAlpha = dimNode ? 0.35 : 1;
      ctx.fillStyle = "#93a4bb";
      ctx.font = "11px Segoe UI,sans-serif";
      ctx.fillText(n.nick, n.x+r+4, n.y+4);
      ctx.globalAlpha = 1;
    });
    var count = $("edgeCount");
    if (count) {
      var nFocus = focusEdges().length;
      var nDrawn = vis.length;
      count.textContent = belowMode === "dim"
        ? nFocus + " focus · " + (nDrawn - nFocus) + " dimmed  < L" + minLevel
        : nFocus + " edges ≥ L" + minLevel;
    }
  }
  function tick(){
    for (var i=0;i<3;i++) step();
    draw();
    requestAnimationFrame(tick);
  }
  function localXY(ev){
    var r = canvas.getBoundingClientRect();
    return {x: (ev.clientX-r.left)*canvas.width/r.width, y:(ev.clientY-r.top)*canvas.height/r.height};
  }
  canvas.addEventListener("mousedown", function(ev){
    var p = localXY(ev);
    var h = hit(p.x,p.y);
    if (h && h.nick) { drag = h; sel = h; paintInfo(h); }
    else if (h) { sel = h; paintInfo(h); }
    else { sel = null; paintInfo(null); }
  });
  window.addEventListener("mousemove", function(ev){
    if (!drag) return;
    var p = localXY(ev);
    drag.x = p.x; drag.y = p.y; drag.vx = 0; drag.vy = 0;
  });
  window.addEventListener("mouseup", function(){ drag = null; });

  var rng = $("minLevel");
  var lvl = $("lvlNow");
  if (rng) rng.addEventListener("input", function(){
    minLevel = Number(rng.value||1);
    if (lvl) lvl.textContent = "L"+minLevel;
    paintInfo(sel);
  });
  function setBelow(mode){
    belowMode = mode === "dim" ? "dim" : "hide";
    document.querySelectorAll("[data-below]").forEach(function(b){
      b.classList.toggle("on", b.getAttribute("data-below") === belowMode);
    });
    try { localStorage.setItem("kampff-graph-below", belowMode); } catch (e) {}
  }
  document.querySelectorAll("[data-below]").forEach(function(b){
    b.addEventListener("click", function(){ setBelow(b.getAttribute("data-below")); });
  });
  setBelow(belowMode);
  var wRng = $("minWidth");
  var wLab = $("minWidthNow");
  function setMinWidth(v){
    minWidth = Math.max(0.5, Math.min(8, Number(v) || 1.2));
    if (wRng) wRng.value = String(minWidth);
    if (wLab) wLab.textContent = minWidth.toFixed(1) + " px";
    try { localStorage.setItem("kampff-graph-minw", String(minWidth)); } catch (e) {}
  }
  if (wRng) wRng.addEventListener("input", function(){ setMinWidth(wRng.value); });
  setMinWidth(minWidth);
  document.querySelectorAll("[data-kind]").forEach(function(b){
    b.addEventListener("click", function(){
      var k = b.getAttribute("data-kind");
      kindsOn[k] = !kindsOn[k];
      b.classList.toggle("on", kindsOn[k]);
    });
  });
  paintInfo(null);
  tick();
})();
"""


def render_graph(graph: dict, *, lang: str = "en") -> str:
    lang = "ko" if lang == "ko" else "en"
    meta = graph.get("meta") or {}
    coord = graph.get("coordination") or {}
    clusters = coord.get("clusters") or []
    seed = json.dumps(graph, ensure_ascii=False).replace("<", "\\u003c")
    cl_html = ""
    if clusters:
        rows = "".join(
            f"<li><b>{c.get('id')}</b> {', '.join(c.get('member_ids') or [])} "
            f"— {c.get('read')} ({c.get('score')}) · {'; '.join(c.get('reasons') or [])}</li>"
            for c in clusters
        )
        cl_html = f'<div class="warn"><b>Coordination (hypothesis)</b><ul>{rows}</ul><p class="muted">{coord.get("disclaimer") or ""}</p></div>'
    syn = "synthetic · " if meta.get("synthetic") else ""
    seed_id = str(meta.get("seed") or "")
    likes = meta.get("likes") if isinstance(meta.get("likes"), dict) else {}
    likes_st = str(likes.get("status") or "")
    likes_n = likes.get("n", 0)
    attached = [str(x) for x in (meta.get("attached_ids") or []) if x]
    n_hop2 = meta.get("n_hop2") or 0
    if lang == "ko":
        heading = f"{seed_id} 중심" if seed_id else "보드 그래프"
        kicker = "Kampff · 관계"
        sub = "이 ID의 글·댓글·공감에 걸린 사람들" if seed_id else "같은 스레드의 여러 사람"
        if attached:
            sub += f" · 이미 수확한 상대 {len(attached)}명 연결"
        likes_line = (
            f'<p class="muted">공감/좋아요: {likes_st or "not_collected"}'
            + (f" · {likes_n}" if likes_n else "")
            + (" — HTML에 공감 ID가 없으면 비움" if likes_st != "collected" else "")
            + "</p>"
        )
        if attached:
            likes_line += (
                f'<p class="muted">2홉: {", ".join(attached[:6])}'
                + (f" · +{n_hop2}명" if n_hop2 else "")
                + " (새 수집 없음)</p>"
            )
        footer = "한 사람 도сье(거리 책상)와 다른 페이지. L5는 법정 증거가 아닙니다."
    else:
        heading = f"Ego · {seed_id}" if seed_id else "Board graph"
        kicker = "Kampff · relation"
        sub = "IDs on this person's posts, comments, likes" if seed_id else "Many people, same threads"
        if attached:
            sub += f" · attached {len(attached)} already-harvested alter(s)"
        likes_line = (
            f'<p class="muted">likes: {likes_st or "not_collected"}'
            + (f" · {likes_n}" if likes_n else "")
            + (" — no liker ids in saved HTML" if likes_st != "collected" else "")
            + "</p>"
        )
        if attached:
            likes_line += (
                f'<p class="muted">hop 2: {", ".join(attached[:6])}'
                + (f" · +{n_hop2}" if n_hop2 else "")
                + " (no new harvest)</p>"
            )
        footer = "One person dossier is a different page. This is the board. L5 is not a court."
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Kampff · relation graph · {meta.get("date","")}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <aside>
    <p class="kicker">{kicker}</p>
    <h1>{heading}</h1>
    <p class="muted">{syn}{sub}</p>
    <p class="muted">{meta.get("platform","")} · {meta.get("date","")} · {meta.get("n_nodes",0)} nodes</p>
    {likes_line}
    <label for="minLevel">Min relation level</label>
    <p class="lvl" id="lvlNow">L1</p>
    <input id="minLevel" type="range" min="1" max="5" value="1"/>
    <label>Below min level</label>
    <div class="seg" role="group" aria-label="Below min level">
      <button type="button" class="on" data-below="hide">Hide</button>
      <button type="button" data-below="dim">Dim</button>
    </div>
    <p class="muted">Hide removes weaker ties. Dim keeps them faded.</p>
    <label for="minWidth">Min edge width <span class="val" id="minWidthNow">1.2 px</span></label>
    <input id="minWidth" type="range" min="0.5" max="8" step="0.1" value="1.2"/>
    <p class="muted" id="edgeCount"></p>
    <p class="muted">L1 observe · L2 repeat · L3 reciprocal · L4 sync · L5 brigade</p>
    <div class="chip"><i style="background:var(--l1)"></i>L1 slate</div>
    <div class="chip"><i style="background:var(--l2)"></i>L2 sky</div>
    <div class="chip"><i style="background:var(--l3)"></i>L3 teal</div>
    <div class="chip"><i style="background:var(--l4)"></i>L4 amber</div>
    <div class="chip"><i style="background:var(--l5)"></i>L5 rose</div>
    <p class="muted">Thicker line = more stacked observations.</p>
    <label>Kinds</label>
    <div class="kinds">
      <button type="button" class="on" data-kind="replies_to">replies_to</button>
      <button type="button" class="on" data-kind="co_thread">co_thread</button>
      <button type="button" class="on" data-kind="burst_sync">burst_sync</button>
      <button type="button" class="on" data-kind="near_dup">near_dup</button>
      <button type="button" class="on" data-kind="mention">mention</button>
      <button type="button" class="on" data-kind="likes">likes</button>
    </div>
    {cl_html}
    <p class="muted" style="margin-top:16px">{footer}</p>
  </aside>
  <div id="stage"><canvas id="graph"></canvas></div>
  <section class="card" id="info"></section>
</div>
<script type="application/json" id="kampff-graph-seed">{seed}</script>
<script>{JS}</script>
</body>
</html>
"""


def write_graph_html(graph: dict, out: Path, *, lang: str = "en") -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_graph(graph, lang=lang), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Render Kampff relation graph HTML")
    ap.add_argument("--graph", "-g", required=True, help="graph.json")
    ap.add_argument("--output", "-o", default="", help="output html")
    ap.add_argument("--lang", choices=("auto", "en", "ko"), default="")
    args = ap.parse_args()
    graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    out = Path(args.output) if args.output else graph_to_html_path(args.graph)
    raw = (args.lang or os.environ.get("KAMPFF_LANG") or "auto").strip().lower()
    if raw in ("en", "ko"):
        lang = raw
    else:
        loc = (os.environ.get("LANG") or os.environ.get("LC_ALL") or "").lower()
        lang = "ko" if loc.startswith("ko") else "en"
    path = write_graph_html(graph, out, lang=lang)
    print(path)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main()
