#!/usr/bin/env python3
"""Thread actor analysis: parse one Clien (or generic) post HTML → actors/network/coordination → HTML+JSON."""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

# ---------- paths ----------
DATE = date.today().isoformat()
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "kampff-data"
INBOX = DATA / "inbox" / DATE
OUT = DATA / "out"
OUT.mkdir(parents=True, exist_ok=True)

DEFAULT_HTML = None
DEFAULT_URL = ""  # require --url


def strip_tags(h: str) -> str:
    h = re.sub(r"<script[\s\S]*?</script>", " ", h, flags=re.I)
    h = re.sub(r"<style[\s\S]*?</style>", " ", h, flags=re.I)
    h = re.sub(r"<br\s*/?>", "\n", h, flags=re.I)
    h = re.sub(r"</p>", "\n", h, flags=re.I)
    h = re.sub(r"<[^>]+>", " ", h)
    for a, b in [
        ("&nbsp;", " "),
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&#39;", "'"),
    ]:
        h = h.replace(a, b)
    return re.sub(r"[ \t]{2,}", " ", h).strip()


def parse_thread(html: str, url: str) -> dict:
    title_m = re.search(r"post_subject[^>]*>([\s\S]*?)</h3>", html, re.I)
    title = strip_tags(title_m.group(1) if title_m else "")
    title = re.sub(r"\s+\d+\s*$", "", title).strip()
    title = re.sub(r"\s+", " ", title)

    # OP author: first post_contact nickname before comments
    op_block = html.split("post_comment")[0] if "post_comment" in html else html[:80000]
    op_id = ""
    op_nick = ""
    id_m = re.search(r"popup\.userInfoPopup\('basic',\s*'([^']+)'\)", op_block)
    if id_m:
        op_id = id_m.group(1)
    nick_m = re.search(
        r'class="nickname"[^>]*>\s*<span title="([^"]+)"', op_block
    )
    if nick_m:
        op_nick = nick_m.group(1)
    if not op_nick:
        t = re.search(r'post_contact[\s\S]{0,600}?title="([^"]+)"', op_block)
        op_nick = t.group(1) if t else "OP"

    body_m = re.search(
        r'class="[^"]*post_article[^"]*"[^>]*>([\s\S]*?)(?:<div class="[^"]*post_writer|<div class="[^"]*post_button|<div class="[^"]*post_comment)',
        html,
        re.I,
    )
    op_body = strip_tags(body_m.group(1)) if body_m else ""

    ui_cmt = None
    cm = re.search(r"댓글\s*[•·]?\s*\[?\s*<strong>(\d+)</strong>", html)
    if not cm:
        cm = re.search(r"comment[^\d]{0,40}(\d+)\s*\]", html, re.I)
    if cm:
        ui_cmt = int(cm.group(1))

    comments = []
    rows = re.split(r'(?=<div class="comment_row)', html)
    for row in rows[1:]:
        cid_m = re.search(r'data-comment-sn="(\d+)"', row)
        if not cid_m:
            cid_m = re.search(r'id="(\d{6,})"', row)
        cid = cid_m.group(1) if cid_m else ""
        aid_m = re.search(r"popup\.userInfoPopup\('basic',\s*'([^']+)'\)", row)
        author_id = aid_m.group(1) if aid_m else ""
        nick_m = re.search(
            r'class="nickname"[^>]*>\s*<span title="([^"]+)"', row
        )
        nick = nick_m.group(1) if nick_m else ""
        if not nick:
            for t in re.findall(r'title="([^"]+)"', row[:1800]):
                if t.startswith("댓글") or "바로가기" in t:
                    continue
                if len(t) < 40:
                    nick = t
                    break
        if not author_id:
            am = re.search(r"data-author-id=([^\s>\"']+)", row)
            author_id = am.group(1) if am else nick or "unknown"
        if not nick:
            nick = author_id

        content_m = re.search(
            r'class="[^"]*comment_view[^"]*"[^>]*>([\s\S]*?)(?:<input|</div>\s*<div class="comment_)',
            row,
            re.I,
        )
        if not content_m:
            content_m = re.search(
                r'data-role="comment-content-\d+"[^>]*>\s*<div[^>]*>([\s\S]*?)</div>',
                row,
                re.I,
            )
        # clien often uses comment_content wrapping without comment_view class in some skins
        if not content_m:
            content_m = re.search(
                r'comment_content"[^>]*>\s*<div[^>]*class="[^"]*"[^>]*>([\s\S]*?)</div>',
                row,
                re.I,
            )
        # fallback: after nickname block take text-ish
        if not content_m:
            # try plain text between comment_content_symph end structures
            content_m = re.search(
                r'data-role="comment-content-\d+"[\s\S]*?<div[^>]*>([\s\S]*?)</div>',
                row,
                re.I,
            )
        body = strip_tags(content_m.group(1)) if content_m else ""
        if not body:
            # last resort: strip row noise
            tmp = re.sub(r"<script[\s\S]*?</script>", " ", row, flags=re.I)
            tmp = strip_tags(tmp)
            # drop UI chrome
            for noise in [
                "쪽지 보내기",
                "작성글 검색",
                "댓글 검색",
                "차단 / 메모",
                "이용제한요청",
                "ID:",
            ]:
                tmp = tmp.replace(noise, " ")
            body = re.sub(r"\s+", " ", tmp).strip()[:500]

        if len(body) < 2:
            continue

        ts_m = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", row)
        if not ts_m:
            ts_m = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", row)
        ts = ts_m.group(1) if ts_m else ""

        depth = 1 if re.search(r'comment_row\s+re', row[:80], re.I) else 0
        mentions = re.findall(r"@([^\s님]+)(?:\s*님)?", body)
        # also @nick 님 pattern already covered; clean
        mentions = [m.strip(".,!?") for m in mentions if m]

        likes = None
        lm = re.search(r'id="setLikeCount_\d+"[^>]*>\s*(\d+)\s*<', row)
        if lm:
            likes = int(lm.group(1))

        comments.append(
            {
                "id": cid,
                "author_id": author_id,
                "display_name": nick,
                "timestamp": ts,
                "content": body[:4000],
                "depth": depth,
                "mentions": mentions,
                "likes": likes,
                "url": f"{url.split('?')[0]}#{cid}" if cid else url,
            }
        )

    return {
        "url": url.split("?")[0],
        "title": title,
        "op": {
            "author_id": op_id or op_nick,
            "display_name": op_nick,
            "content": op_body[:12000],
        },
        "ui_comment_count": ui_cmt,
        "comments": comments,
    }


# ---------- intent / stance ----------
PRO_POLICY = ["상폐는 안", "상폐 불가", "당연히 안", "어려워", "충격"]
ANTI_POLICY = ["사퇴", "짤려", "경솔", "졸속", "책임", "사과", "느긋", "패착", "악재"]
CONSPIRACY = ["손잡고", "감옥", "짜고", "배후", "누군가랑"]
PILE = ["ㅋㅋ", "ㅎㅎ", "레전드", "답없다"]
INFO = ["자산운용사", "신청", "제도", "규제", "거래대금", "외국인", "기관"]


def classify_comment(text: str, op_text: str) -> dict:
    t = text
    flags = []
    stance = "unclear"
    intent = "unclear"
    malice = []

    anti = sum(1 for k in ANTI_POLICY if k in t)
    pro = sum(1 for k in PRO_POLICY if k in t)
    cons = sum(1 for k in CONSPIRACY if k in t)
    info = sum(1 for k in INFO if k in t)
    pile = sum(1 for k in PILE if k in t)

    if cons:
        flags.append("conspiracy_frame")
        malice.append("conspiracy_unsourced")
        intent = "conspiracy"
        stance = "attack_person"
    elif anti >= 2 or ("사퇴" in t or "짤려" in t):
        stance = "anti_policy"
        intent = "partisan" if "정치" in t or "짤려" in t else "policy_argument"
        if "사퇴" in t or "짤려" in t:
            malice.append("punitive_call")
    elif pro >= 1 and anti == 0:
        stance = "pro_policy_claim"
        intent = "policy_argument"
    elif info >= 1:
        stance = "meta"
        intent = "information"
        flags.append("adds_claim_or_detail")
    elif pile and len(t) < 40:
        intent = "pile_on"
        stance = "mixed"
        malice.append("pile_on")
    elif "?" in t and len(t) < 80:
        intent = "challenge_question"
        stance = "meta"
    else:
        if anti:
            stance = "anti_policy"
            intent = "policy_argument"
        elif len(t) > 80:
            intent = "policy_argument"
            stance = "mixed"

    # sincere counter-signal
    if intent in ("policy_argument", "information") and not malice:
        flags.append("sincere_policy_signal")

    if re.search(r"(바보|한심|쓰레기|꼴값)", t):
        malice.append("ad_hominem")
        intent = "troll" if intent == "unclear" else intent

    risk = "low"
    if "conspiracy_unsourced" in malice or "ad_hominem" in malice:
        risk = "elevated"
    if len(malice) >= 2 or ("conspiracy_unsourced" in malice and "punitive_call" in malice):
        risk = "high"
    if intent in ("policy_argument", "information") and not malice:
        risk = "low"

    return {
        "stance": stance,
        "intent": intent,
        "malice_signals": malice,
        "malice_risk": risk,
        "flags": flags,
    }


def tokenize(s: str) -> set[str]:
    s = re.sub(r"[^\w가-힣]+", " ", s.lower())
    return {w for w in s.split() if len(w) >= 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def analyze(thread: dict, focus_id: str | None = None) -> dict:
    comments = thread["comments"]
    op = thread["op"]

    # per comment classify
    enriched = []
    for c in comments:
        cl = classify_comment(c["content"], op.get("content") or "")
        e = {**c, **cl}
        enriched.append(e)

    # actors
    by_actor: dict[str, list] = defaultdict(list)
    for c in enriched:
        key = c["author_id"] or c["display_name"]
        by_actor[key].append(c)

    # nick map for mentions
    nick_to_id = {}
    for c in enriched:
        nick_to_id[c["display_name"]] = c["author_id"]
        nick_to_id[c["author_id"]] = c["author_id"]

    # edges A -> B
    edges = []
    for c in enriched:
        src = c["author_id"]
        for m in c["mentions"]:
            # strip
            m2 = m.lstrip("@")
            dst = nick_to_id.get(m2) or nick_to_id.get(m2.replace(" ", ""))
            if not dst:
                # fuzzy: display name startswith
                for nick, aid in nick_to_id.items():
                    if nick.startswith(m2) or m2.startswith(nick):
                        dst = aid
                        break
            if dst and dst != src:
                edges.append(
                    {
                        "from": src,
                        "to": dst,
                        "from_nick": c["display_name"],
                        "comment_id": c["id"],
                    }
                )

    out_deg = Counter(e["from"] for e in edges)
    in_deg = Counter(e["to"] for e in edges)

    actors = []
    for aid, clist in by_actor.items():
        stances = Counter(c["stance"] for c in clist)
        intents = Counter(c["intent"] for c in clist)
        malice = []
        for c in clist:
            malice.extend(c["malice_signals"])
        malice_c = Counter(malice)
        risks = [c["malice_risk"] for c in clist]
        risk = "high" if "high" in risks else ("elevated" if "elevated" in risks else "low")
        primary_intent = intents.most_common(1)[0][0]
        primary_stance = stances.most_common(1)[0][0]
        texts = " | ".join(c["content"][:120] for c in clist)
        actors.append(
            {
                "author_id": aid,
                "display_name": clist[0]["display_name"],
                "n_comments": len(clist),
                "stance": primary_stance,
                "intent_primary": primary_intent,
                "malice_risk": risk,
                "malice_signals": dict(malice_c),
                "out_degree": out_deg.get(aid, 0),
                "in_degree": in_deg.get(aid, 0),
                "reply_to": sorted({e["to"] for e in edges if e["from"] == aid}),
                "replied_by": sorted({e["from"] for e in edges if e["to"] == aid}),
                "sample": clist[0]["content"][:240],
                "comments": [
                    {
                        "id": c["id"],
                        "content": c["content"],
                        "stance": c["stance"],
                        "intent": c["intent"],
                        "malice_risk": c["malice_risk"],
                        "malice_signals": c["malice_signals"],
                        "mentions": c["mentions"],
                        "timestamp": c["timestamp"],
                        "url": c["url"],
                    }
                    for c in clist
                ],
            }
        )

    actors.sort(key=lambda a: (-a["n_comments"], -a["out_degree"] - a["in_degree"]))

    # coordination: pairwise text similarity
    sims = []
    keys = list(by_actor.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            ta = tokenize(" ".join(c["content"] for c in by_actor[keys[i]]))
            tb = tokenize(" ".join(c["content"] for c in by_actor[keys[j]]))
            jac = jaccard(ta, tb)
            if jac >= 0.35:
                sims.append(
                    {
                        "a": keys[i],
                        "b": keys[j],
                        "jaccard": round(jac, 3),
                        "a_nick": by_actor[keys[i]][0]["display_name"],
                        "b_nick": by_actor[keys[j]][0]["display_name"],
                    }
                )
    sims.sort(key=lambda x: -x["jaccard"])

    # mutual reply pairs
    edge_set = {(e["from"], e["to"]) for e in edges}
    mutual = []
    seen_p = set()
    for a, b in edge_set:
        if (b, a) in edge_set:
            p = tuple(sorted([a, b]))
            if p not in seen_p:
                seen_p.add(p)
                mutual.append({"a": p[0], "b": p[1]})

    # stance alignment clusters (simple)
    stance_groups = defaultdict(list)
    for a in actors:
        stance_groups[a["stance"]].append(a["display_name"])

    # coordination score
    score = 0
    reasons = []
    if len(sims) >= 2:
        score += 25
        reasons.append(f"high text-similarity pairs: {len(sims)}")
    if len(sims) >= 1 and sims[0]["jaccard"] >= 0.5:
        score += 20
        reasons.append(f"near-duplicate pair jaccard={sims[0]['jaccard']}")
    if len(mutual) >= 2:
        score += 15
        reasons.append(f"mutual @ pairs: {len(mutual)}")
    # same attack frame
    punitive = sum(1 for a in actors if "punitive_call" in a["malice_signals"])
    if punitive >= 3:
        score += 15
        reasons.append(f"shared punitive frame actors: {punitive}")
    cons_n = sum(1 for a in actors if a["intent_primary"] == "conspiracy")
    if cons_n >= 2:
        score += 20
        reasons.append(f"multiple conspiracy-intent actors: {cons_n}")
    # diversity reduces
    distinct_intents = len({a["intent_primary"] for a in actors})
    if distinct_intents >= 4:
        score = max(0, score - 15)
        reasons.append(f"intent diversity {distinct_intents} (anti-coordination)")
    if len(actors) >= 8 and distinct_intents >= 3 and len(sims) == 0:
        score = max(0, score - 10)
        reasons.append("independent phrasing dominates")

    score = max(0, min(100, score))
    if score < 20:
        coord_read = "none"
    elif score < 40:
        coord_read = "weak"
    elif score < 65:
        coord_read = "moderate"
    else:
        coord_read = "strong_signals"

    # focus comment
    focus = None
    if focus_id:
        for c in enriched:
            if c["id"] == focus_id:
                focus = c
                break

    intent_mix = Counter(a["intent_primary"] for a in actors)
    risk_mix = Counter(a["malice_risk"] for a in actors)

    return {
        "thread": {
            "url": thread["url"],
            "title": thread["title"],
            "op": op,
            "ui_comment_count": thread.get("ui_comment_count"),
            "parsed_comments": len(enriched),
        },
        "focus_comment": focus,
        "actors": actors,
        "edges": edges,
        "similarity_pairs": sims[:20],
        "mutual_pairs": mutual,
        "stance_groups": {k: v for k, v in stance_groups.items()},
        "coordination": {
            "score": score,
            "read": coord_read,
            "reasons": reasons,
        },
        "summary": {
            "n_actors": len(actors),
            "n_comments": len(enriched),
            "n_edges": len(edges),
            "intent_mix": dict(intent_mix),
            "malice_risk_mix": dict(risk_mix),
            "one_line": _one_line(coord_read, intent_mix, risk_mix, len(actors)),
        },
        "honesty": {
            "ui_comments": thread.get("ui_comment_count"),
            "parsed_comments": len(enriched),
            "full_thread": (
                thread.get("ui_comment_count") is not None
                and len(enriched) >= thread["ui_comment_count"]
            )
            or thread.get("ui_comment_count") is None,
        },
    }


def _one_line(coord_read, intent_mix, risk_mix, n_actors) -> str:
    top_intent = max(intent_mix, key=intent_mix.get) if intent_mix else "unclear"
    elev = risk_mix.get("elevated", 0) + risk_mix.get("high", 0)
    return (
        f"{n_actors} actors · dominant intent `{top_intent}` · "
        f"malice elevated/high={elev} · coordination `{coord_read}`"
    )


def render_html(result: dict, out_path: Path) -> None:
    sample = (ROOT / "docs" / "sample-community-report.html").read_text(encoding="utf-8")
    css = re.search(r"<style>([\s\S]*?)</style>", sample).group(1)
    th = result["thread"]
    s = result["summary"]
    coord = result["coordination"]
    actors = result["actors"]

    # simple force-ish layout positions on circle
    n = max(len(actors), 1)
    nodes_svg = []
    pos = {}
    for i, a in enumerate(actors):
        ang = 2 * math.pi * i / n - math.pi / 2
        x = 200 + 140 * math.cos(ang)
        y = 200 + 140 * math.sin(ang)
        pos[a["author_id"]] = (x, y)
        color = {
            "low": "#4ade80",
            "elevated": "#fbbf24",
            "high": "#f87171",
        }.get(a["malice_risk"], "#93a4bb")
        label = a["display_name"][:8]
        nodes_svg.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{8+a["n_comments"]*2}" fill="{color}" opacity=".85"/>'
            f'<text x="{x:.1f}" y="{y+22:.1f}" text-anchor="middle" fill="#93a4bb" font-size="10">{label}</text>'
        )
    edges_svg = []
    for e in result["edges"]:
        if e["from"] not in pos or e["to"] not in pos:
            continue
        x1, y1 = pos[e["from"]]
        x2, y2 = pos[e["to"]]
        edges_svg.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155" stroke-width="1.2"/>'
        )

    actor_rows = []
    for a in actors:
        ms = ", ".join(f"{k}:{v}" for k, v in a["malice_signals"].items()) or "—"
        risk_cls = {
            "low": "ok",
            "elevated": "caution",
            "high": "caution",
        }.get(a["malice_risk"], "neutral")
        actor_rows.append(
            f"<tr><td><b>{_esc(a['display_name'])}</b><br><span style='color:#93a4bb;font-size:11px'>{_esc(a['author_id'])}</span></td>"
            f"<td>{a['n_comments']}</td>"
            f"<td>{_esc(a['stance'])}</td>"
            f"<td>{_esc(a['intent_primary'])}</td>"
            f"<td><span class='pill {risk_cls}'>{a['malice_risk']}</span></td>"
            f"<td>{_esc(ms)}</td>"
            f"<td>{a['in_degree']}/{a['out_degree']}</td>"
            f"<td style='font-size:12px'>{_esc(a['sample'][:140])}</td></tr>"
        )

    intent_bars = []
    im = s["intent_mix"]
    mx = max(im.values()) if im else 1
    for k, v in sorted(im.items(), key=lambda x: -x[1]):
        w = max(4, int(100 * v / mx))
        intent_bars.append(
            f'<div class="hbar-row"><span>{_esc(k)}</span><div class="track"><div class="fill teal" style="width:{w}%"></div></div><span>{v}</span></div>'
        )

    sim_rows = "".join(
        f"<tr><td>{_esc(p['a_nick'])}</td><td>{_esc(p['b_nick'])}</td><td>{p['jaccard']}</td></tr>"
        for p in result["similarity_pairs"][:10]
    ) or "<tr><td colspan=3>no high-similarity pairs</td></tr>"

    mutual_txt = (
        ", ".join(f"{m['a']}↔{m['b']}" for m in result["mutual_pairs"]) or "none"
    )
    stance_li = "".join(
        f"<li><b>{_esc(k)}</b>: {_esc(', '.join(v))}</li>"
        for k, v in result["stance_groups"].items()
    )
    reasons_li = (
        "".join(f"<li>{_esc(r)}</li>" for r in coord["reasons"])
        or "<li>no strong coordination signals</li>"
    )

    focus_html = ""
    if result.get("focus_comment"):
        fc = result["focus_comment"]
        focus_html = (
            f"<h3>Focus comment #{fc.get('id')}</h3>"
            f"<blockquote><b>{_esc(fc.get('display_name',''))}</b> · "
            f"{_esc(fc.get('intent',''))} · risk {fc.get('malice_risk')}<br>"
            f"{_esc(fc.get('content','')[:500])}</blockquote>"
        )

    coord_pill = {
        "none": "ok",
        "weak": "neutral",
        "moderate": "caution",
        "strong_signals": "caution",
    }.get(coord["read"], "neutral")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Kampff thread actors · {_esc(th['title'][:60])}</title>
<style>{css}
  .pill.ok {{ color:#bbf7d0; border-color:#16a34a; background:#052e16; }}
</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <p class="kicker">Kampff · THREAD ACTOR ANALYSIS · intent · network · coordination</p>
    <h1>{_esc(th['title'][:100])}</h1>
    <p class="sub"><a href="{_esc(th['url'])}">{_esc(th['url'])}</a></p>
    <div class="meta">
      <div class="chip"><b>OP</b>{_esc(th['op']['display_name'])} ({_esc(th['op']['author_id'])})</div>
      <div class="chip"><b>Comments</b>UI {th.get('ui_comment_count')} · parsed {th.get('parsed_comments')}</div>
      <div class="chip"><b>Actors</b>{s['n_actors']}</div>
      <div class="chip"><b>Reply edges</b>{s['n_edges']}</div>
    </div>
    <div class="distance-banner" style="background:#1c1408;border-color:#7c4a0a">
      <span style="font-size:12px;color:#fde68a">Coordination</span>
      <span class="pill {coord_pill}">{coord['read']} · {coord['score']}/100</span>
      <span style="font-size:12px;color:var(--muted)">{_esc(s['one_line'])}</span>
    </div>
  </header>

  <nav class="toc">
    <a href="#sum">Summary</a>
    <a href="#net">Network</a>
    <a href="#actors">Actors</a>
    <a href="#coord">Coordination</a>
    <a href="#op">OP</a>
    <a href="#method">Method</a>
  </nav>

  <section class="card" id="sum">
    <h2><span class="n">0</span> Summary</h2>
    <div class="grid3">
      <div class="stat"><div class="v">{s['n_actors']}</div><div class="l">actors</div></div>
      <div class="stat"><div class="v">{s['n_comments']}</div><div class="l">comments parsed</div></div>
      <div class="stat"><div class="v">{coord['score']}</div><div class="l">coordination score</div></div>
    </div>
    {focus_html}
    <h3>Intent mix (by actor primary)</h3>
    <div class="hbar">{''.join(intent_bars)}</div>
    <h3>Malice risk mix</h3>
    <p>{' · '.join(f'{k}: {v}' for k,v in s['malice_risk_mix'].items())}</p>
    <div class="one-line"><b>Read —</b> {_esc(s['one_line'])}. Malice labels are <b>signals</b>, not legal findings. Coordination = pattern score only.</div>
  </section>

  <section class="card" id="net">
    <h2><span class="n">1</span> Reply network</h2>
    <div class="chart-box">
      <h3>@mention graph (node color = malice_risk)</h3>
      <svg viewBox="0 0 400 400" role="img">
        {''.join(edges_svg)}
        {''.join(nodes_svg)}
      </svg>
      <div class="legend">
        <span><i style="background:#4ade80"></i>low</span>
        <span><i style="background:#fbbf24"></i>elevated</span>
        <span><i style="background:#f87171"></i>high</span>
      </div>
    </div>
    <p style="font-size:12px;color:var(--muted)">Edge A→B = A mentioned @B. Node size ∝ comments on this thread.</p>
  </section>

  <section class="card" id="actors">
    <h2><span class="n">2</span> Actors</h2>
    <table>
      <tr><th>Actor</th><th>n</th><th>stance</th><th>intent</th><th>malice</th><th>signals</th><th>in/out</th><th>sample</th></tr>
      {''.join(actor_rows)}
    </table>
  </section>

  <section class="card" id="coord">
    <h2><span class="n">3</span> Coordination / 조직성 signals</h2>
    <p>Score <b>{coord['score']}</b> / 100 → <span class="pill {coord_pill}">{coord['read']}</span></p>
    <ul>{reasons_li}</ul>
    <h3>High text-similarity pairs (jaccard ≥ 0.35)</h3>
    <table><tr><th>A</th><th>B</th><th>jaccard</th></tr>{sim_rows}</table>
    <h3>Mutual @ pairs</h3>
    <p>{_esc(mutual_txt)}</p>
    <h3>Stance groups</h3>
    <ul>
      {stance_li}
    </ul>
  </section>

  <section class="card" id="op">
    <h2><span class="n">4</span> OP</h2>
    <p><b>{_esc(th['op']['display_name'])}</b> ({_esc(th['op']['author_id'])})</p>
    <blockquote>{_esc((th['op'].get('content') or '')[:900])}</blockquote>
  </section>

  <section class="card" id="method">
    <h2><span class="n">5</span> Method + honesty</h2>
    <table>
      <tr><th>UI comments</th><td>{th.get('ui_comment_count')}</td></tr>
      <tr><th>Parsed</th><td>{result['honesty']['parsed_comments']}</td></tr>
      <tr><th>Full?</th><td>{result['honesty']['full_thread']}</td></tr>
    </table>
    <p>Spec: <code>kampff/references/thread-actor-analysis.md</code>. Heuristics are transparent keyword+graph features — re-check quotes before action.</p>
  </section>

  <footer>Not medical/legal. No stalking. Signals ≠ proof of conspiracy. Kampff thread-actor feature.</footer>
</div>
</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_md(result: dict, out_path: Path) -> None:
    th = result["thread"]
    s = result["summary"]
    c = result["coordination"]
    lines = [
        f"# Thread actor analysis — {th['title']}",
        "",
        f"**URL:** {th['url']}  ",
        f"**OP:** {th['op']['display_name']} ({th['op']['author_id']})  ",
        f"**Comments:** UI {th.get('ui_comment_count')} · parsed {th.get('parsed_comments')}  ",
        f"**Actors:** {s['n_actors']} · edges {s['n_edges']}  ",
        f"**Coordination:** `{c['read']}` ({c['score']}/100)  ",
        f"**One-liner:** {s['one_line']}",
        "",
        "## Intent mix",
        "",
    ]
    for k, v in sorted(s["intent_mix"].items(), key=lambda x: -x[1]):
        lines.append(f"- `{k}`: {v}")
    lines += ["", "## Actors", ""]
    for a in result["actors"]:
        lines.append(
            f"### {a['display_name']} (`{a['author_id']}`) · n={a['n_comments']} · "
            f"intent={a['intent_primary']} · malice={a['malice_risk']}"
        )
        lines.append("")
        lines.append(f"> {a['sample']}")
        lines.append("")
        if a["malice_signals"]:
            lines.append(f"signals: `{a['malice_signals']}`")
            lines.append("")
    lines += ["## Coordination reasons", ""]
    for r in c["reasons"] or ["none"]:
        lines.append(f"- {r}")
    lines += ["", "## Honesty", ""]
    lines.append(f"- full_thread: {result['honesty']['full_thread']}")
    lines.append("")
    lines.append("Signals only — not legal findings.")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--html", type=Path, default=DEFAULT_HTML)
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--focus", default="151990173")
    args = ap.parse_args()

    html = args.html.read_text(encoding="utf-8", errors="ignore")
    thread = parse_thread(html, args.url)
    # re-parse comments with improved body extraction if many empty
    result = analyze(thread, focus_id=args.focus or None)

    board_sn = "park_19230278"
    m = re.search(r"/board/([a-zA-Z0-9_]+)/(\d+)", args.url)
    if m:
        board_sn = f"{m.group(1)}_{m.group(2)}"

    raw_dir = INBOX / "raw" / f"thread_{board_sn}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "thread.json").write_text(
        json.dumps(thread, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    json_path = OUT / f"{DATE}-thread-{board_sn}-actors.json"
    html_path = OUT / f"{DATE}-thread-{board_sn}-actors.html"
    md_path = OUT / f"{DATE}-thread-{board_sn}-actors.md"
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    render_html(result, html_path)
    render_md(result, md_path)

    # request echo
    (INBOX / "thread-request.json").write_text(
        json.dumps(
            {
                "url": args.url,
                "platform": "community",
                "focus_comment_id": args.focus,
                "analysis": ["actors", "intent", "network", "coordination"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("HTML", html_path)
    print("MD  ", md_path)
    print("JSON", json_path)
    print("one_line:", result["summary"]["one_line"])
    print("coordination:", result["coordination"])
    for a in result["actors"][:12]:
        print(
            f"  {a['display_name']:12} intent={a['intent_primary']:18} malice={a['malice_risk']:8} n={a['n_comments']}"
        )


if __name__ == "__main__":
    main()
