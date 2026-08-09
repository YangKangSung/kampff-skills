#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plain-language (easy) track for Kampff reports + dual HTML merger.

Used by render_kampff_report.py (--track easy|both) or standalone:

  python scripts/kampff_report_easy.py -a analysis.json -o out/easy.html
  python scripts/kampff_report_easy.py -a a.json --wrap-pro out/report.html
    # rewrites report.html into dual-track (pro body kept, easy added)
"""
from __future__ import annotations

import argparse
import html as htmlmod
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def esc(s: Any) -> str:
    return htmlmod.escape("" if s is None else str(s))


DISTANCE_PLAIN = {
    "engage": (
        "편하게 맞춰도 됨",
        "같이 이야기하거나 협업해도 부담이 비교적 적은 편입니다.",
    ),
    "neutral": (
        "평소 거리",
        "특별히 다가가거나 피할 필요는 없습니다. 상황 보고 두면 됩니다.",
    ),
    "caution": (
        "조심해서 거리 두기",
        "일부 주제·상황에서 마찰이 나기 쉽습니다. 한 발 물러서는 편이 낫습니다.",
    ),
    "avoid": (
        "가급적 피하기",
        "지금 기준으로는 접촉·같은 자리 비용을 크게 잡는 편이 안전합니다.",
    ),
}


def _clean_jargon(s: str) -> str:
    t = str(s or "")
    # drop dense English ops tokens; keep Korean prose
    t = re.sub(
        r"\b(L1|L2|L3|L4|L5|MBTI|ACH|CIA|SAT|ROI|DSM|ICD|Big\s*Five|"
        r"CONFIRMED|PROBABLE|SPECULATIVE|harvest|bundle|dossier)\b",
        "",
        t,
        flags=re.I,
    )
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\s*·\s*·\s*", " · ", t)
    return t.strip(" ·,;/")


def _first_sentences(text: str, n: int = 2, max_len: int = 280) -> str:
    t = _clean_jargon(text)
    if not t:
        return ""
    parts = re.split(r"(?<=[.。?!])\s+|(?<=다\.)\s+|(?<=요\.)\s+|(?<=습니다\.)\s+|(?<=거든요\.)\s+", t)
    out = []
    for p in parts:
        p = p.strip()
        if len(p) < 8:
            continue
        out.append(p)
        if len(out) >= n:
            break
    s = " ".join(out) if out else t
    if len(s) > max_len:
        s = s[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return s


def _bullets_from_identity(identity: dict, limit: int = 5) -> list[str]:
    raw = identity.get("bullets") or identity.get("points") or []
    if isinstance(raw, str):
        raw = [raw]
    out = []
    for b in raw:
        t = _clean_jargon(str(b))
        if len(t) >= 10:
            out.append(t)
        if len(out) >= limit:
            break
    return out


def _ops_plain(ops: list, distance: str) -> list[tuple[str, str]]:
    rows = []
    for o in ops or []:
        if isinstance(o, dict):
            tag = str(o.get("tag") or distance).lower()
            when = str(o.get("when") or "기본").strip()
        else:
            tag, when = distance, str(o)
        label, _ = DISTANCE_PLAIN.get(tag, DISTANCE_PLAIN["neutral"])
        rows.append((when or "기본", label))
    if not rows:
        label, _ = DISTANCE_PLAIN.get(distance, DISTANCE_PLAIN["neutral"])
        rows.append(("기본", label))
    return rows[:8]


def _honesty_plain(honesty: dict, corpus: dict) -> list[str]:
    lines = []
    posts = corpus.get("posts")
    cmts = corpus.get("comments")
    if posts is not None or cmts is not None:
        lines.append(
            f"모아 본 공개 글: 게시 {posts if posts is not None else '?'}건 · "
            f"댓글 {cmts if cmts is not None else '?'}건"
        )
    for key, label in (
        ("posts_note", "게시글 수집"),
        ("comments_note", "댓글 수집"),
        ("likes_note", "공감/좋아요"),
        ("note", "메모"),
    ):
        v = honesty.get(key)
        if v:
            lines.append(f"{label}: {_clean_jargon(str(v))}")
    if not lines:
        lines.append("수집 범위 메모가 비어 있습니다. 전문 트랙의 Collect 표를 보세요.")
    return lines[:6]


def _quotes_plain(quotes: list, limit: int = 3) -> list[str]:
    out = []
    for q in quotes or []:
        if isinstance(q, dict):
            text = q.get("text") or q.get("body") or q.get("quote") or ""
            src = q.get("src") or q.get("url") or q.get("when") or ""
        else:
            text, src = str(q), ""
        text = str(text).strip()
        if len(text) < 12:
            continue
        if len(text) > 220:
            text = text[:217] + "…"
        bit = f"「{text}」"
        if src:
            bit += f" — {src}"
        out.append(bit)
        if len(out) >= limit:
            break
    return out


def build_easy_inner(analysis: dict) -> str:
    """Return inner HTML for easy track (sections only, no full document)."""
    meta = analysis.get("meta") or {}
    target = analysis.get("target") or {}
    distance = str(analysis.get("distance") or "neutral").lower()
    conf_label = analysis.get("confidence") or "medium"
    conf_score = analysis.get("confidence_score")
    tldr = analysis.get("tldr") or analysis.get("one_line") or ""
    reco = analysis.get("recommendation") or ""
    tid = target.get("id") or "target"
    nick = target.get("nick") or tid
    date = meta.get("date") or datetime.now().strftime("%Y-%m-%d")
    platform = meta.get("platform") or "community"
    corpus = analysis.get("corpus") or {}
    honesty = analysis.get("honesty") or {}
    identity = analysis.get("identity") or {}
    ops = analysis.get("distance_ops") or []
    quotes = analysis.get("quotes") or []
    ach = (analysis.get("cia") or {}).get("ach") or analysis.get("ach") or []

    d_title, d_expl = DISTANCE_PLAIN.get(distance, DISTANCE_PLAIN["neutral"])
    conf_s = f"{conf_label}"
    if conf_score is not None:
        conf_s += f" ({conf_score})"

    plain_tldr = _first_sentences(tldr, 2, 320)
    plain_reco = _first_sentences(reco, 2, 260)
    who_bits = _bullets_from_identity(identity)
    if not who_bits and plain_tldr:
        who_bits = [plain_tldr]

    # ACH lead in plain words
    ach_lead = ""
    if isinstance(ach, list) and ach:
        h0 = ach[0] if isinstance(ach[0], dict) else {"title": str(ach[0])}
        ach_lead = _clean_jargon(str(h0.get("title") or h0.get("name") or ""))

    # do / don't from reco + distance
    if distance == "avoid":
        dos = ["공개 정보만 보고, 필요하면 제3 경로로 확인", "접촉이 필요하면 짧고 업무만"]
        donts = ["설득·논쟁으로 바꾸려 하기", "같은 민감 스레드에 오래 머물기"]
    elif distance == "caution":
        dos = [
            "비정치·생활 주제면 짧은 한두 줄만",
            "의견이 갈리는 글에서는 읽기만 하거나 자리 피하기",
        ]
        donts = [
            "진영·가치 논쟁으로 깊게 들어가기",
            "한 번의 댓글로 설득된다고 가정하기",
        ]
    elif distance == "engage":
        dos = ["공통 관심사에서 짧게 맞춰 보기", "공개 글 톤을 존중하며 질문하기"]
        donts = ["과한 사적 추정", "근거 없는 단정"]
    else:
        dos = ["필요할 때만 짧게", "공개 글·날짜를 기준으로 판단"]
        donts = ["성급히 가깝다고 가정하기", "수집이 얇은 축을 확신으로 쓰기"]

    # refine from reco fragments
    if plain_reco:
        if "스킵" in plain_reco or "피" in plain_reco:
            donts.insert(0, plain_reco if len(plain_reco) < 120 else plain_reco[:117] + "…")
            donts = donts[:4]

    ops_rows = _ops_plain(ops, distance)
    ops_html = "".join(
        f"<tr><td>{esc(w)}</td><td>{esc(lab)}</td></tr>" for w, lab in ops_rows
    )
    who_ul = "".join(f"<li>{esc(b)}</li>" for b in who_bits) or "<li class='muted'>(요약 없음)</li>"
    hon_ul = "".join(f"<li>{esc(x)}</li>" for x in _honesty_plain(honesty, corpus))
    q_html = "".join(f"<blockquote>{esc(q)}</blockquote>" for q in _quotes_plain(quotes))
    if not q_html:
        q_html = "<p class='muted'>붙인 인용 문장이 없습니다. 전문 트랙 Evidence를 보세요.</p>"

    ach_line = (
        f"<p class='easy-plain'>겉으로 자주 보이는 역할 가설: <b>{esc(ach_lead)}</b> "
        f"<span class='muted'>(가설 · 단정 아님)</span></p>"
        if ach_lead
        else ""
    )

    return f"""
  <header class="hero">
    <p class="kicker">Kampff · 쉬운 말 트랙 · 공개 글만 · 진단 아님</p>
    <h1 class="easy-hero-title">{esc(nick)} — 한눈에 보기</h1>
    <p class="sub">{esc(date)} · {esc(platform)} · id <b>{esc(tid)}</b></p>
    <div class="meta">
      <div class="chip"><b>거리</b>{esc(d_title)}</div>
      <div class="chip"><b>확신</b>{esc(conf_s)}</div>
      <div class="chip"><b>글 수</b>게시 {esc(corpus.get("posts","?"))} · 댓글 {esc(corpus.get("comments","?"))}</div>
    </div>
    <div class="distance-banner {esc(distance if distance in DISTANCE_PLAIN else 'neutral')}">
      <span class="pill {esc(distance if distance in DISTANCE_PLAIN else 'neutral')}">{esc(distance)}</span>
      <span class="easy-plain"><b>{esc(d_title)}</b> — {esc(d_expl)}</span>
    </div>
    <div class="tldr easy-lead"><b>한 줄</b> — {esc(plain_tldr or d_expl)}</div>
  </header>

  <section class="card" id="easy-who">
    <h2><span class="n">1</span> 이 사람은 (공개 글 기준)</h2>
    <ul class="easy-plain">{who_ul}</ul>
    {ach_line}
  </section>

  <section class="card" id="easy-do">
    <h2><span class="n">2</span> 이렇게 / 이렇게는 말고</h2>
    <div class="grid2">
      <div class="easy-box easy-do">
        <h3>해도 되는 쪽</h3>
        <ul>{"".join(f"<li>{esc(x)}</li>" for x in dos)}</ul>
      </div>
      <div class="easy-box easy-dont">
        <h3>피하는 쪽</h3>
        <ul>{"".join(f"<li>{esc(x)}</li>" for x in donts)}</ul>
      </div>
    </div>
    {f'<p class="easy-plain" style="margin-top:12px"><b>운영 메모</b> — {esc(plain_reco)}</p>' if plain_reco else ''}
  </section>

  <section class="card" id="easy-when">
    <h2><span class="n">3</span> 상황별 거리</h2>
    <table>
      <tr><th>상황</th><th>쉬운 말</th></tr>
      {ops_html}
    </table>
  </section>

  <section class="card" id="easy-collect">
    <h2><span class="n">4</span> 자료는 얼마나 봤나</h2>
    <ul class="easy-plain">{hon_ul}</ul>
    <p class="muted">확신이 낮으면 위를 더 의심하세요. 좋아요/공감 축이 비어 있으면 그 부분은 모릅니다.</p>
  </section>

  <section class="card" id="easy-quotes">
    <h2><span class="n">5</span> 근거로 남긴 말 (일부)</h2>
    {q_html}
  </section>

  <section class="card" id="easy-limit">
    <h2><span class="n">6</span> 한계</h2>
    <ul class="easy-plain">
      <li>공개된 글·댓글만 봅니다. 사생활·진단·법률 조언이 아닙니다.</li>
      <li>MBTI·임상 표현은 재미/가설용이며, 거리 결정의 유일한 이유가 되면 안 됩니다.</li>
      <li>더 촘촘한 표·그래프·레이어는 위쪽 <b>전문 분석</b> 트랙에 있습니다.</li>
    </ul>
  </section>
"""


EASY_CSS = """
.track-switch{
  display:flex;flex-wrap:wrap;gap:8px;align-items:center;
  margin:0 0 14px;padding:8px;border-radius:14px;
  background:#0d131b;border:1px solid var(--line);
}
.track-switch .lbl{font-size:11px;color:var(--muted);margin:0 4px 0 6px;font-family:var(--mono)}
.track-switch button{
  font:inherit;cursor:pointer;border-radius:999px;padding:7px 14px;
  border:1px solid var(--line);background:#121821;color:var(--muted);font-size:13px;
}
.track-switch button.active{
  color:#042f2e;background:linear-gradient(90deg,#5eead4,#38bdf8);
  border-color:transparent;font-weight:600;
}
.track-panel[hidden]{display:none!important}
.easy-hero-title{font-size:22px;margin:0 0 8px}
.easy-lead{font-size:16px;line-height:1.6;margin:10px 0 0}
.easy-box{
  margin:10px 0;padding:14px 16px;border-radius:12px;
  background:#0d151f;border:1px solid var(--line);
}
.easy-box h3{margin:0 0 8px;font-size:14px;color:var(--accent)}
.easy-box ul{margin:6px 0;padding-left:1.15rem}
.easy-box li{margin:4px 0}
.easy-do{border-color:#1f5c4a;background:#0c1f1a}
.easy-dont{border-color:#7c4a0a;background:#1c1408}
.easy-plain{font-size:15px;line-height:1.65;color:#e2e8f0}
@media print{
  .track-switch{display:none}
  .track-panel{display:block!important}
}
"""

TRACK_JS = """
<script id="kampff-track-js">
(function(){
  function setTrack(name){
    var pro = document.getElementById('track-pro');
    var easy = document.getElementById('track-easy');
    var bPro = document.getElementById('btn-track-pro');
    var bEasy = document.getElementById('btn-track-easy');
    if(!pro || !easy) return;
    var isEasy = name === 'easy';
    pro.hidden = isEasy;
    easy.hidden = !isEasy;
    if(bPro) bPro.classList.toggle('active', !isEasy);
    if(bEasy) bEasy.classList.toggle('active', isEasy);
    try { localStorage.setItem('kampff-report-track', isEasy ? 'easy' : 'pro'); } catch(e){}
  }
  var bPro = document.getElementById('btn-track-pro');
  var bEasy = document.getElementById('btn-track-easy');
  if(bPro) bPro.addEventListener('click', function(){ setTrack('pro'); });
  if(bEasy) bEasy.addEventListener('click', function(){ setTrack('easy'); });
  var init = 'easy';
  try {
    if (location.hash === '#pro') init = 'pro';
    else if (location.hash === '#easy') init = 'easy';
    else {
      var s = localStorage.getItem('kampff-report-track');
      if (s === 'easy' || s === 'pro') init = s;
    }
  } catch(e){}
  setTrack(init);
})();
</script>
"""


def render_easy_document(analysis: dict) -> str:
    """Standalone easy-only HTML (shares dark theme minimal)."""
    inner = build_easy_inner(analysis)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Kampff · easy · {esc((analysis.get("target") or {}).get("nick") or "report")}</title>
<style>
:root {{
  --bg:#0b0f14; --panel:#121821; --panel2:#18202b; --line:#243041;
  --text:#e7eef8; --muted:#93a4bb; --accent:#5eead4; --accent2:#38bdf8;
  --mono:"JetBrains Mono","SF Mono",Consolas,monospace;
  --sans:"Segoe UI",system-ui,sans-serif;
}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:var(--sans);color:var(--text);line-height:1.55;
  background:radial-gradient(1200px 600px at 10% -10%,#12324a55,transparent),var(--bg)}}
.wrap{{max-width:820px;margin:0 auto;padding:28px 18px 80px}}
header.hero{{border:1px solid var(--line);background:linear-gradient(180deg,var(--panel2),var(--panel));
  border-radius:18px;padding:26px;margin-bottom:18px}}
.kicker{{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}}
.sub{{color:var(--muted);font-size:13px}}
.meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-top:10px}}
.meta .chip{{background:#0d131b;border:1px solid var(--line);border-radius:12px;padding:10px 12px;font-size:12.5px}}
.meta .chip b{{display:block;color:var(--muted);font-weight:500;font-size:10px;margin-bottom:3px}}
.distance-banner{{margin-top:14px;padding:12px 14px;border-radius:12px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;background:#0c1f1a;border:1px solid #1f5c4a}}
.distance-banner.caution{{background:#1c1408;border-color:#7c4a0a}}
.distance-banner.avoid{{background:#1c0a0a;border-color:#7f1d1d}}
.distance-banner.engage{{background:#052e16;border-color:#166534}}
.pill{{display:inline-flex;padding:3px 10px;border-radius:999px;font-family:var(--mono);font-size:11px;border:1px solid #475569}}
.pill.caution{{color:#fde68a;border-color:#b45309;background:#422006}}
.pill.avoid{{color:#fecaca;border-color:#b91c1c;background:#450a0a}}
.pill.engage{{color:#a7f3d0;border-color:#059669;background:#064e3b}}
.pill.neutral{{color:#cbd5e1;border-color:#475569;background:#1e293b}}
.tldr{{margin:12px 0 0;padding:14px 16px;border-radius:12px;background:#0c1c28;border:1px solid #1e4d45}}
section.card{{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px;margin-bottom:14px}}
section.card h2{{margin:0 0 12px;font-size:17px}}
section.card h2 .n{{font-family:var(--mono);font-size:11px;color:var(--accent2);border:1px solid #1e3a5f;background:#0b1726;padding:2px 7px;border-radius:999px;margin-right:6px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
@media(max-width:720px){{.grid2{{grid-template-columns:1fr}}}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{border:1px solid var(--line);padding:8px;text-align:left}}
th{{background:#0e1520;color:var(--muted)}}
blockquote{{margin:10px 0;padding:10px 12px;border-left:3px solid var(--accent);background:#0d151f;border-radius:0 10px 10px 0}}
.muted{{color:var(--muted);font-size:12.5px}}
footer{{margin-top:24px;color:var(--muted);font-size:11px;text-align:center}}
{EASY_CSS}
</style>
</head>
<body>
<div class="wrap">
{inner}
<footer>Kampff easy track · not medical/legal · public text only</footer>
</div>
</body>
</html>
"""


def wrap_pro_with_easy(pro_html: str, analysis: dict) -> str:
    """Inject dual-track switcher into an existing pro report HTML."""
    if 'id="track-pro"' in pro_html or "id='track-pro'" in pro_html:
        # already dual — replace easy panel only
        easy_inner = build_easy_inner(analysis)
        pro_html = re.sub(
            r'<div class="track-panel" id="track-easy"[\s\S]*?</div>\s*<!-- /track-easy -->',
            f'<div class="track-panel" id="track-easy" hidden>\n{easy_inner}\n</div><!-- /track-easy -->',
            pro_html,
            count=1,
        )
        return pro_html

    easy_inner = build_easy_inner(analysis)

    # inject CSS before </style>
    if "</style>" in pro_html:
        pro_html = pro_html.replace("</style>", EASY_CSS + "\n</style>", 1)

    switcher = """
  <div class="track-switch" role="tablist" aria-label="리포트 트랙">
    <span class="lbl">TRACK</span>
    <button type="button" id="btn-track-easy" class="active">쉬운 말</button>
    <button type="button" id="btn-track-pro">전문 분석</button>
  </div>
"""

    # After <div class="wrap"> open dual structure
    m = re.search(r'(<div class="wrap">\s*)', pro_html)
    if not m:
        raise ValueError("pro HTML missing div.wrap")
    insert_at = m.end()
    # Find last footer + close wrap — wrap existing content as track-pro
    # Simpler: after wrap open, insert switcher + track-pro open; before final footer close track-pro and add easy

    pro_html = pro_html[:insert_at] + switcher + '\n  <div class="track-panel" id="track-pro" hidden>\n' + pro_html[insert_at:]

    # Before last </div>\n</body> that closes wrap — find footer
    foot = re.search(r'(<footer>[\s\S]*?</footer>\s*)(</div>\s*</body>)', pro_html)
    if foot:
        pro_html = (
            pro_html[: foot.start()]
            + "  </div><!-- /track-pro -->\n"
            + f'  <div class="track-panel" id="track-easy">\n{easy_inner}\n  </div><!-- /track-easy -->\n'
            + foot.group(1)
            + foot.group(2)
            + pro_html[foot.end() :]
        )
    else:
        pro_html = pro_html.replace(
            "</body>",
            "  </div><!-- /track-pro -->\n"
            f'  <div class="track-panel" id="track-easy">\n{easy_inner}\n  </div><!-- /track-easy -->\n'
            + TRACK_JS
            + "</body>",
            1,
        )
        return pro_html

    if "kampff-track-js" not in pro_html:
        pro_html = pro_html.replace("</body>", TRACK_JS + "\n</body>", 1)
    return pro_html


def main() -> None:
    ap = argparse.ArgumentParser(description="Kampff easy track / dual wrap")
    ap.add_argument("--analysis", "-a", required=True)
    ap.add_argument("--output", "-o", default="", help="easy-only HTML path")
    ap.add_argument(
        "--wrap-pro",
        default="",
        help="existing pro report.html to rewrite as dual-track",
    )
    args = ap.parse_args()
    analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))

    if args.wrap_pro:
        pro_path = Path(args.wrap_pro)
        dual = wrap_pro_with_easy(pro_path.read_text(encoding="utf-8"), analysis)
        out = Path(args.output) if args.output else pro_path
        out.write_text(dual, encoding="utf-8")
        print(out)
        return

    html = render_easy_document(analysis)
    out = Path(args.output or "report-easy.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
