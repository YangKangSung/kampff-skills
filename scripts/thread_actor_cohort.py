#!/usr/bin/env python3
"""
Kampff thread actors — seed + cohort cross-thread + temporal + DIRECTED reply network.

Usage:
  python scripts/thread_actor_cohort.py --seed-html path.html --url URL --focus ID
  python scripts/thread_actor_cohort.py --url URL --expand  # needs logged-in agent Edge
"""
from __future__ import annotations

import argparse
import json
import math
import re
import time
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

DATE = date.today().isoformat()
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "kampff-data"
INBOX = DATA / "inbox" / DATE
OUT = DATA / "out"
OUT.mkdir(parents=True, exist_ok=True)
PROFILE = Path(__import__("os").environ.get("KAMPFF_EDGE_PROFILE", str(Path.home() / ".kampff" / "agent-edge-profile")))
BASE = "https://www.clien.net"


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


def iso_ts(ts: str) -> str:
    if not ts:
        return ""
    if len(ts) == 16:
        ts += ":00"
    if "T" not in ts:
        ts = ts.replace(" ", "T")
    if "+" not in ts and "Z" not in ts:
        ts += "+09:00"
    return ts


def parse_seed_thread(html: str, url: str) -> dict:
    url = url.split("?")[0].split("#")[0]
    title_m = re.search(r"post_subject[^>]*>([\s\S]*?)</h3>", html, re.I)
    title = re.sub(r"\s+", " ", strip_tags(title_m.group(1) if title_m else "")).strip()
    title = re.sub(r"\s+\d+\s*$", "", title).strip()

    op_block = html.split("post_comment")[0] if "post_comment" in html else html[:80000]
    op_id = ""
    id_m = re.search(r"popup\.userInfoPopup\('basic',\s*'([^']+)'\)", op_block)
    if id_m:
        op_id = id_m.group(1)
    nick_m = re.search(r'class="nickname"[^>]*>\s*<span title="([^"]+)"', op_block)
    op_nick = nick_m.group(1) if nick_m else (op_id or "OP")
    if not op_id:
        op_id = op_nick

    body_m = re.search(
        r'class="[^"]*post_article[^"]*"[^>]*>([\s\S]*?)(?:<div class="[^"]*post_writer|<div class="[^"]*post_button|<div class="[^"]*post_comment)',
        html,
        re.I,
    )
    op_body = strip_tags(body_m.group(1)) if body_m else ""

    ui_cmt = None
    cm = re.search(r"댓글\s*[•·]?\s*\[?\s*<strong>(\d+)</strong>", html)
    if cm:
        ui_cmt = int(cm.group(1))

    comments = []
    for row in re.split(r'(?=<div class="comment_row)', html)[1:]:
        cid_m = re.search(r'data-comment-sn="(\d+)"', row)
        cid = cid_m.group(1) if cid_m else ""
        aid_m = re.search(r"popup\.userInfoPopup\('basic',\s*'([^']+)'\)", row)
        author_id = aid_m.group(1) if aid_m else ""
        nick_m = re.search(r'class="nickname"[^>]*>\s*<span title="([^"]+)"', row)
        nick = nick_m.group(1) if nick_m else ""
        if not nick:
            for t in re.findall(r'title="([^"]+)"', row[:1800]):
                if t.startswith("댓글") or "바로가기" in t:
                    continue
                if len(t) < 40:
                    nick = t
                    break
        if not author_id:
            author_id = nick or "unknown"
        if not nick:
            nick = author_id

        content_m = re.search(
            r'class="[^"]*comment_view[^"]*"[^>]*>([\s\S]*?)(?:<input|</div>\s*<div class="comment_)',
            row,
            re.I,
        )
        body = strip_tags(content_m.group(1)) if content_m else ""
        if len(body) < 2:
            continue
        ts_m = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", row)
        if not ts_m:
            ts_m = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", row)
        ts = iso_ts(ts_m.group(1) if ts_m else "")
        mentions = [m.strip(".,!?") for m in re.findall(r"@([^\s님]+)(?:\s*님)?", body)]
        depth = 1 if re.search(r"comment_row\s+re", row[:80], re.I) else 0
        comments.append(
            {
                "id": cid,
                "author_id": author_id,
                "display_name": nick,
                "timestamp": ts,
                "content": body[:4000],
                "depth": depth,
                "mentions": mentions,
                "url": f"{url}#{cid}" if cid else url,
                "thread_url": url,
                "is_seed": True,
            }
        )

    return {
        "url": url,
        "title": title,
        "op": {
            "author_id": op_id,
            "display_name": op_nick,
            "content": op_body[:12000],
        },
        "ui_comment_count": ui_cmt,
        "comments": comments,
    }


def kill_agent_edge() -> None:
    import subprocess

    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" |"
                " Where-Object { $_.CommandLine -match 'agent-edge-profile' } |"
                " ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
            ),
        ],
        capture_output=True,
    )
    time.sleep(2)


def parse_search_paths(html: str) -> list[dict]:
    items = []
    seen = set()
    for m in re.finditer(
        r'href="(/service/board/([a-zA-Z0-9_]+)/(\d+))(?:\?[^"#]*)?(?:#[^"]*)?"',
        html,
    ):
        path, board, sn = m.group(1), m.group(2), m.group(3)
        if board == "annonce" or path in seen:
            continue
        seen.add(path)
        items.append({"path": path, "board": board, "sn": sn, "url": BASE + path})
    return items


def expand_cohort(
    actors: list[dict],
    boards: list[str],
    max_pages: int,
    raw_dir: Path,
    max_actors: int = 6,
) -> dict:
    """Login search/v2 for a SMALL actor subset — human-paced."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        return {"ok": False, "error": f"playwright missing: {e}", "by_actor": {}}

    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from human_browse import (
        Resume,
        UrlCache,
        goto_human,
        human_pause,
        human_pause_actor,
        is_bot_wall,
    )

    raw_dir.mkdir(parents=True, exist_ok=True)
    cache = UrlCache(raw_dir / "http_cache", ttl_hours=24)
    resume = Resume(raw_dir / "cohort_resume.json")
    if resume.in_cooldown():
        return {
            "ok": False,
            "error": "cooldown_active",
            "by_actor": {},
            "cooldown_until": resume.data.get("cooldown_until"),
        }

    # do not kill edge every time if avoidable — only if lock fails we kill once
    try:
        kill_agent_edge()
    except Exception:
        pass

    done = set(resume.data.get("done_actors") or [])
    # prioritize first max_actors not done
    queue = [a for a in actors if a["author_id"] not in done][:max_actors]
    if not queue:
        # all done — return empty ok with note
        return {
            "ok": True,
            "by_actor": {},
            "note": "all_queued_actors_already_done",
            "resume": resume.data,
        }

    by_actor: dict[str, dict] = {}
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            channel="msedge",
            headless=True,
            ignore_default_args=["--enable-automation"],
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
            ),
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        # warm-up: home like a human, not straight myInfo hammer
        try:
            html = goto_human(
                page, f"{BASE}/service/", cache=cache, lo=2.0, hi=4.0
            )
            if is_bot_wall(html, page.url, page.title() or ""):
                resume.set_cooldown_minutes(45)
                ctx.close()
                return {
                    "ok": False,
                    "error": "bot_wall_home",
                    "by_actor": {},
                }
            human_pause(1.5, 3.0)
            html = goto_human(
                page,
                f"{BASE}/service/mypage/myInfo",
                cache=None,
                lo=2.0,
                hi=4.5,
            )
        except Exception as e:
            try:
                ctx.close()
            except Exception:
                pass
            return {"ok": False, "error": f"nav_fail:{e}", "by_actor": {}}

        title = ""
        try:
            title = page.title() or ""
        except Exception:
            title = ""
        if "나의정보" not in title:
            try:
                ctx.close()
            except Exception:
                pass
            return {
                "ok": False,
                "error": "not_logged_in",
                "by_actor": {},
                "session_title": title,
            }

        # only park by default boards already limited
        boards = boards[:1]  # hard cap 1 board per expand wave
        max_pages = min(max_pages, 2)

        for ai, a in enumerate(queue):
            if ai > 0:
                human_pause_actor()
            aid = a["author_id"]
            nick = a["display_name"]
            posts: list[dict] = []
            cmt_threads: list[dict] = []
            seen_p, seen_c = set(), set()
            bot_hit = False
            for b in boards:
                for po in range(max_pages):
                    u = f"{BASE}/service/search/v2/board/{b}?sk=id&sv={aid}&po={po}"
                    html = goto_human(page, u, cache=cache, lo=3.0, hi=7.0)
                    if is_bot_wall(html, page.url, page.title() or ""):
                        bot_hit = True
                        break
                    (raw_dir / f"w_{aid}_{b}_po{po}.html").write_text(
                        html, encoding="utf-8"
                    )
                    items = parse_search_paths(html)
                    new = 0
                    for it in items:
                        if it["path"] in seen_p:
                            continue
                        seen_p.add(it["path"])
                        posts.append(it)
                        new += 1
                    if new == 0:
                        break
                if bot_hit:
                    break
                for po in range(max_pages):
                    u = (
                        f"{BASE}/service/search/v2/board/{b}"
                        f"?sk=commenter&sv={aid}&po={po}"
                    )
                    html = goto_human(page, u, cache=cache, lo=3.0, hi=7.0)
                    if is_bot_wall(html, page.url, page.title() or ""):
                        bot_hit = True
                        break
                    (raw_dir / f"c_{aid}_{b}_po{po}.html").write_text(
                        html, encoding="utf-8"
                    )
                    items = parse_search_paths(html)
                    new = 0
                    for it in items:
                        if it["path"] in seen_c:
                            continue
                        seen_c.add(it["path"])
                        cmt_threads.append(it)
                        new += 1
                    if new == 0:
                        break
                if bot_hit:
                    break

            if bot_hit:
                resume.data["last_error"] = "bot_wall"
                resume.set_cooldown_minutes(45)
                resume.save()
                try:
                    ctx.close()
                except Exception:
                    pass
                return {
                    "ok": False,
                    "error": "bot_wall",
                    "by_actor": by_actor,
                    "stopped_at": aid,
                }

            by_actor[aid] = {
                "author_id": aid,
                "display_name": nick,
                "posts": posts[:40],
                "comment_threads": cmt_threads[:40],
            }
            done.add(aid)
            resume.data["done_actors"] = sorted(done)
            resume.data["last_error"] = None
            resume.save()
            print(
                f"cohort {nick}/{aid}: posts={len(posts)} "
                f"cmt_threads={len(cmt_threads)} (human-paced)"
            )

        try:
            ctx.close()
        except Exception:
            pass
    return {"ok": True, "by_actor": by_actor, "resume": resume.data}


def build_directed_edges(seed: dict, nick_to_id: dict[str, str]) -> list[dict]:
    """A → B means A replies toward B."""
    edges = []
    op_id = seed["op"]["author_id"]
    op_nick = seed["op"]["display_name"]
    for c in seed["comments"]:
        src = c["author_id"]
        src_nick = c["display_name"]
        # mentions
        resolved = []
        for m in c.get("mentions") or []:
            m2 = m.lstrip("@")
            dst = nick_to_id.get(m2)
            if not dst:
                for nick, aid in nick_to_id.items():
                    if nick == m2 or nick.startswith(m2) or m2.startswith(nick):
                        dst = aid
                        break
            if dst and dst != src:
                resolved.append(dst)
                edges.append(
                    {
                        "from_id": src,
                        "to_id": dst,
                        "from_nick": src_nick,
                        "to_nick": next(
                            (
                                x["display_name"]
                                for x in seed["comments"]
                                if x["author_id"] == dst
                            ),
                            dst,
                        ),
                        "type": "reply_to",
                        "direction": "A_to_B",
                        "thread_url": c["thread_url"],
                        "comment_id": c["id"],
                        "timestamp": c["timestamp"],
                        "weight": 1,
                        "snippet": c["content"][:160],
                    }
                )
        # depth-based reply without @ — weak: only if single parent pattern not available
        # address OP if mentions op nick or explicit
        if op_nick in c["content"] or op_id in c.get("mentions", []):
            if op_id != src and op_id not in resolved:
                edges.append(
                    {
                        "from_id": src,
                        "to_id": op_id,
                        "from_nick": src_nick,
                        "to_nick": op_nick,
                        "type": "op_address",
                        "direction": "A_to_B",
                        "thread_url": c["thread_url"],
                        "comment_id": c["id"],
                        "timestamp": c["timestamp"],
                        "weight": 1,
                        "snippet": c["content"][:160],
                    }
                )
    return edges


def aggregate_edges(edges: list[dict]) -> list[dict]:
    key_w: dict[tuple, dict] = {}
    for e in edges:
        k = (e["from_id"], e["to_id"], e["type"])
        if k not in key_w:
            key_w[k] = {**e, "weight": 0, "events": []}
        key_w[k]["weight"] += e.get("weight", 1)
        key_w[k]["events"].append(
            {
                "timestamp": e.get("timestamp"),
                "comment_id": e.get("comment_id"),
                "thread_url": e.get("thread_url"),
                "snippet": e.get("snippet"),
            }
        )
        # keep earliest ts as primary
        ts = e.get("timestamp") or ""
        if ts and (
            not key_w[k].get("timestamp") or ts < (key_w[k].get("timestamp") or "9999")
        ):
            key_w[k]["timestamp"] = ts
    return sorted(key_w.values(), key=lambda x: -x["weight"])


def cohort_relations(cohort: dict, seed_url: str) -> dict:
    """Cross-thread co-presence from activity indices."""
    by = cohort.get("by_actor") or {}
    # thread -> set(actors) for comment threads + posts as participation
    thread_actors: dict[str, set[str]] = defaultdict(set)
    actor_threads: dict[str, set[str]] = defaultdict(set)
    for aid, blob in by.items():
        for it in blob.get("comment_threads") or []:
            u = it.get("url") or (BASE + it["path"])
            if u.rstrip("/") == seed_url.rstrip("/"):
                continue
            thread_actors[u].add(aid)
            actor_threads[aid].add(u)
        for it in blob.get("posts") or []:
            u = it.get("url") or (BASE + it["path"])
            actor_threads[aid].add("POST:" + u)

    co_pairs = Counter()
    for u, acts in thread_actors.items():
        acts = sorted(acts)
        for i in range(len(acts)):
            for j in range(i + 1, len(acts)):
                co_pairs[(acts[i], acts[j])] += 1

    co_list = [
        {
            "a": a,
            "b": b,
            "co_thread_count": n,
            "type": "co_presence",  # NOT a directed reply
            "undirected": True,
        }
        for (a, b), n in co_pairs.most_common(50)
        if n >= 1
    ]
    return {
        "co_presence_pairs": co_list,
        "actor_thread_counts": {k: len(v) for k, v in actor_threads.items()},
        "n_cross_threads_indexed": len(thread_actors),
    }


def classify_comment(text: str) -> dict:
    ANTI = ["사퇴", "짤려", "경솔", "졸속", "책임", "사과", "느긋", "패착", "악재"]
    PRO = ["상폐는 안", "상폐 불가", "당연히 안", "어려워"]
    CONS = ["손잡고", "감옥", "짜고", "배후"]
    INFO = ["자산운용사", "신청", "제도", "규제", "거래대금", "외국인", "기관"]
    t = text
    malice = []
    intent = "unclear"
    stance = "unclear"
    cons = sum(1 for k in CONS if k in t)
    anti = sum(1 for k in ANTI if k in t)
    pro = sum(1 for k in PRO if k in t)
    info = sum(1 for k in INFO if k in t)
    if cons:
        intent, stance = "conspiracy", "attack_person"
        malice.append("conspiracy_unsourced")
    elif anti >= 2 or "사퇴" in t or "짤려" in t:
        intent = "partisan" if "정치" in t or "짤려" in t else "policy_argument"
        stance = "anti_policy"
        if "사퇴" in t or "짤려" in t:
            malice.append("punitive_call")
    elif info:
        intent, stance = "information", "meta"
    elif pro:
        intent, stance = "policy_argument", "pro_policy_claim"
    elif "?" in t and len(t) < 80:
        intent, stance = "challenge_question", "meta"
    elif len(t) > 60:
        intent, stance = "policy_argument", "mixed"
    risk = "low"
    if "conspiracy_unsourced" in malice:
        risk = "elevated"
    if len(malice) >= 2:
        risk = "high"
    return {
        "intent": intent,
        "stance": stance,
        "malice_signals": malice,
        "malice_risk": risk,
    }


def build_events(seed: dict, edges: list[dict], cohort: dict) -> list[dict]:
    events = []
    # OP as post event (unknown ts)
    events.append(
        {
            "timestamp": "",
            "actor_id": seed["op"]["author_id"],
            "actor_nick": seed["op"]["display_name"],
            "event": "post",
            "thread_url": seed["url"],
            "target_id": None,
            "label": "OP",
        }
    )
    for c in seed["comments"]:
        events.append(
            {
                "timestamp": c["timestamp"],
                "actor_id": c["author_id"],
                "actor_nick": c["display_name"],
                "event": "comment",
                "thread_url": c["thread_url"],
                "target_id": None,
                "label": c["content"][:80],
                "comment_id": c["id"],
            }
        )
    for e in edges:
        if e.get("type") in ("reply_to", "op_address", "cross_thread_reply"):
            events.append(
                {
                    "timestamp": e.get("timestamp") or "",
                    "actor_id": e["from_id"],
                    "actor_nick": e.get("from_nick"),
                    "event": "reply",
                    "thread_url": e.get("thread_url"),
                    "target_id": e["to_id"],
                    "target_nick": e.get("to_nick"),
                    "label": f"{e.get('from_nick')} → {e.get('to_nick')}",
                    "edge_type": e.get("type"),
                }
            )
    # sort: empty ts last
    def sk(ev):
        t = ev.get("timestamp") or "9999"
        return t

    events.sort(key=sk)
    return events


def analyze(seed: dict, cohort: dict | None, focus_id: str | None) -> dict:
    comments = seed["comments"]
    nick_to_id = {seed["op"]["display_name"]: seed["op"]["author_id"]}
    nick_to_id[seed["op"]["author_id"]] = seed["op"]["author_id"]
    for c in comments:
        nick_to_id[c["display_name"]] = c["author_id"]
        nick_to_id[c["author_id"]] = c["author_id"]

    raw_edges = build_directed_edges(seed, nick_to_id)
    edges = aggregate_edges(raw_edges)

    # actors
    by_a: dict[str, list] = defaultdict(list)
    for c in comments:
        cl = classify_comment(c["content"])
        by_a[c["author_id"]].append({**c, **cl})

    out_w = Counter()
    in_w = Counter()
    for e in edges:
        out_w[e["from_id"]] += e["weight"]
        in_w[e["to_id"]] += e["weight"]

    actors = []
    for aid, clist in by_a.items():
        intents = Counter(c["intent"] for c in clist)
        stances = Counter(c["stance"] for c in clist)
        malice = Counter()
        for c in clist:
            for m in c["malice_signals"]:
                malice[m] += 1
        risks = [c["malice_risk"] for c in clist]
        risk = (
            "high"
            if "high" in risks
            else ("elevated" if "elevated" in risks else "low")
        )
        # directed neighbors
        replies_to = sorted(
            {
                (e["to_id"], e["to_nick"], e["weight"])
                for e in edges
                if e["from_id"] == aid and e["type"] == "reply_to"
            }
        )
        replied_by = sorted(
            {
                (e["from_id"], e["from_nick"], e["weight"])
                for e in edges
                if e["to_id"] == aid and e["type"] == "reply_to"
            }
        )
        actors.append(
            {
                "author_id": aid,
                "display_name": clist[0]["display_name"],
                "n_comments_seed": len(clist),
                "intent_primary": intents.most_common(1)[0][0],
                "stance": stances.most_common(1)[0][0],
                "malice_risk": risk,
                "malice_signals": dict(malice),
                "out_weight": out_w.get(aid, 0),
                "in_weight": in_w.get(aid, 0),
                "directed_replies_to": [
                    {"id": i, "nick": n, "weight": w} for i, n, w in replies_to
                ],
                "directed_replied_by": [
                    {"id": i, "nick": n, "weight": w} for i, n, w in replied_by
                ],
                "sample": clist[0]["content"][:240],
                "timestamps": [c["timestamp"] for c in clist if c.get("timestamp")],
            }
        )

    # cohort attach
    cross = {"co_presence_pairs": [], "actor_thread_counts": {}, "n_cross_threads_indexed": 0}
    cohort_ok = False
    if cohort and cohort.get("ok"):
        cohort_ok = True
        cross = cohort_relations(cohort, seed["url"])
        for a in actors:
            blob = (cohort.get("by_actor") or {}).get(a["author_id"]) or {}
            a["cohort_posts"] = len(blob.get("posts") or [])
            a["cohort_comment_threads"] = len(blob.get("comment_threads") or [])
            a["cohort_thread_index"] = cross["actor_thread_counts"].get(a["author_id"], 0)

    actors.sort(
        key=lambda a: (
            -(a["out_weight"] + a["in_weight"]),
            -a["n_comments_seed"],
        )
    )

    events = build_events(seed, raw_edges, cohort or {})
    # temporal pair series for directed edges
    pair_series = defaultdict(list)
    for e in raw_edges:
        if e["type"] not in ("reply_to", "op_address"):
            continue
        pair_series[f"{e['from_nick']}→{e['to_nick']}"].append(
            {
                "timestamp": e.get("timestamp"),
                "type": e["type"],
                "thread_url": e.get("thread_url"),
                "snippet": e.get("snippet"),
            }
        )

    # coordination
    score = 0
    reasons = []
    # recurring directed (weight>=2)
    heavy = [e for e in edges if e["weight"] >= 2 and e["type"] == "reply_to"]
    if heavy:
        score += 15
        reasons.append(f"repeated directed replies: {len(heavy)}")
    # mutual directed
    es = {(e["from_id"], e["to_id"]) for e in edges if e["type"] == "reply_to"}
    mutual = 0
    for a, b in list(es):
        if (b, a) in es:
            mutual += 1
    mutual //= 2
    if mutual:
        score += 10
        reasons.append(f"mutual directed pairs: {mutual}")
    # cross co-presence
    strong_co = [p for p in cross["co_presence_pairs"] if p["co_thread_count"] >= 2]
    if strong_co:
        score += min(40, 10 * len(strong_co))
        reasons.append(f"cross-thread co-presence pairs (≥2): {len(strong_co)}")
    punitive = sum(1 for a in actors if "punitive_call" in a["malice_signals"])
    if punitive >= 3:
        score += 10
        reasons.append(f"shared punitive frame: {punitive}")
    di = len({a["intent_primary"] for a in actors})
    if di >= 4:
        score = max(0, score - 15)
        reasons.append(f"intent diversity {di} (anti-coord)")
    if not cohort_ok:
        reasons.append("cohort not expanded (login/depth) — coordination incomplete")
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

    focus = None
    if focus_id:
        for c in comments:
            if c["id"] == focus_id:
                focus = {**c, **classify_comment(c["content"])}
                break

    intent_mix = Counter(a["intent_primary"] for a in actors)
    risk_mix = Counter(a["malice_risk"] for a in actors)

    return {
        "seed": {
            "url": seed["url"],
            "title": seed["title"],
            "op": seed["op"],
            "ui_comment_count": seed.get("ui_comment_count"),
            "parsed_comments": len(comments),
        },
        "focus_comment": focus,
        "actors": actors,
        "edges_directed": edges,
        "edges_raw_events": raw_edges,
        "edge_legend": {
            "reply_to": "A → B : A mentions/replies to B",
            "op_address": "A → OP : A addresses original poster",
            "co_presence": "undirected co-thread (NOT a reply)",
        },
        "events_temporal": events,
        "pair_timelines": {k: v for k, v in pair_series.items()},
        "cross_thread": cross,
        "cohort": {
            "expanded": cohort_ok,
            "error": None if cohort_ok else (cohort or {}).get("error"),
            "n_actors_indexed": len((cohort or {}).get("by_actor") or {}),
        },
        "coordination": {"score": score, "read": read, "reasons": reasons},
        "summary": {
            "n_actors": len(actors),
            "n_directed_edges": len(edges),
            "n_directed_events": len(raw_edges),
            "intent_mix": dict(intent_mix),
            "malice_risk_mix": dict(risk_mix),
            "one_line": (
                f"{len(actors)} actors · directed reply events={len(raw_edges)} · "
                f"coord `{read}` · cohort={'on' if cohort_ok else 'off'}"
            ),
        },
        "honesty": {
            "ui_comments": seed.get("ui_comment_count"),
            "parsed_comments": len(comments),
            "full_seed": seed.get("ui_comment_count") == len(comments)
            if seed.get("ui_comment_count") is not None
            else None,
            "cohort_depth": "expanded" if cohort_ok else "seed_only",
            "directionality": "directed A→B required",
        },
    }


def render_html(result: dict, path: Path) -> None:
    sample = (ROOT / "docs" / "sample-community-report.html").read_text(encoding="utf-8")
    css = re.search(r"<style>([\s\S]*?)</style>", sample).group(1)
    seed = result["seed"]
    s = result["summary"]
    coord = result["coordination"]
    actors = result["actors"]
    edges = result["edges_directed"]

    # layout positions
    n = max(len(actors), 1)
    pos = {}
    # include OP node
    op_id = seed["op"]["author_id"]
    ids = [op_id] + [a["author_id"] for a in actors if a["author_id"] != op_id]
    # unique preserve
    seen = set()
    ids2 = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            ids2.append(i)
    ids = ids2
    n = max(len(ids), 1)
    nick = {op_id: seed["op"]["display_name"]}
    risk = {op_id: "low"}
    for a in actors:
        nick[a["author_id"]] = a["display_name"]
        risk[a["author_id"]] = a["malice_risk"]

    for i, aid in enumerate(ids):
        ang = 2 * math.pi * i / n - math.pi / 2
        pos[aid] = (220 + 160 * math.cos(ang), 220 + 160 * math.sin(ang))

    def esc(x):
        return (
            str(x)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    # directed edges as arrows (marker)
    edge_svg = []
    for e in edges:
        if e["from_id"] not in pos or e["to_id"] not in pos:
            continue
        x1, y1 = pos[e["from_id"]]
        x2, y2 = pos[e["to_id"]]
        # shorten for arrow head
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1
        ux, uy = dx / L, dy / L
        # stop before target circle
        x2s, y2s = x2 - ux * 14, y2 - uy * 14
        x1s, y1s = x1 + ux * 12, y1 + uy * 12
        w = 1 + min(4, e["weight"])
        color = "#38bdf8" if e["type"] == "reply_to" else "#fbbf24"
        edge_svg.append(
            f'<line x1="{x1s:.1f}" y1="{y1s:.1f}" x2="{x2s:.1f}" y2="{y2s:.1f}" '
            f'stroke="{color}" stroke-width="{w}" marker-end="url(#arrow)"/>'
        )
        # mid label weight if >1
        if e["weight"] > 1:
            mx, my = (x1s + x2s) / 2, (y1s + y2s) / 2
            edge_svg.append(
                f'<text x="{mx:.1f}" y="{my:.1f}" fill="#93a4bb" font-size="9">{e["weight"]}</text>'
            )

    node_svg = []
    for aid, (x, y) in pos.items():
        col = {"low": "#4ade80", "elevated": "#fbbf24", "high": "#f87171"}.get(
            risk.get(aid, "low"), "#94a3b8"
        )
        r = 14 if aid == op_id else 10
        lab = (nick.get(aid) or aid)[:8]
        node_svg.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{col}" stroke="#0b0f14" stroke-width="2"/>'
            f'<text x="{x:.1f}" y="{y+24:.1f}" text-anchor="middle" fill="#e7eef8" font-size="10">{esc(lab)}</text>'
        )

    # edge table rows (directed)
    erows = []
    for e in edges[:40]:
        erows.append(
            f"<tr><td><b>{esc(e['from_nick'])}</b></td>"
            f"<td style='color:#5eead4;font-weight:700'>→</td>"
            f"<td><b>{esc(e['to_nick'])}</b></td>"
            f"<td>{esc(e['type'])}</td><td>{e['weight']}</td>"
            f"<td style='font-size:11px'>{esc(e.get('timestamp') or '')}</td>"
            f"<td style='font-size:11px'>{esc((e.get('snippet') or '')[:100])}</td></tr>"
        )

    arows = []
    for a in actors:
        to = ", ".join(
            f"{x['nick']}←{x['weight']}" if False else f"→{x['nick']}({x['weight']})"
            for x in a["directed_replies_to"]
        ) or "—"
        frm = ", ".join(
            f"{x['nick']}→({x['weight']})" for x in a["directed_replied_by"]
        ) or "—"
        # fix display: from means others point to me
        frm = ", ".join(f"{x['nick']}→me({x['weight']})" for x in a["directed_replied_by"]) or "—"
        to = ", ".join(f"me→{x['nick']}({x['weight']})" for x in a["directed_replies_to"]) or "—"
        cp = a.get("cohort_comment_threads", "—")
        pp = a.get("cohort_posts", "—")
        arows.append(
            f"<tr><td><b>{esc(a['display_name'])}</b><br><span style='color:#93a4bb;font-size:11px'>{esc(a['author_id'])}</span></td>"
            f"<td>{a['n_comments_seed']}</td>"
            f"<td>{esc(a['intent_primary'])}</td>"
            f"<td><span class='pill {'caution' if a['malice_risk']!='low' else 'neutral'}'>{a['malice_risk']}</span></td>"
            f"<td style='font-size:11px'>{esc(to)}</td>"
            f"<td style='font-size:11px'>{esc(frm)}</td>"
            f"<td>{pp}/{cp}</td>"
            f"<td style='font-size:11px'>{esc(a['sample'][:100])}</td></tr>"
        )

    # temporal list
    trows = []
    for ev in result["events_temporal"]:
        if not ev.get("timestamp") and ev.get("event") != "post":
            continue
        arrow = ""
        if ev.get("event") == "reply":
            arrow = f" <b style='color:#5eead4'>{esc(ev.get('actor_nick'))} → {esc(ev.get('target_nick'))}</b>"
        trows.append(
            f"<tr><td style='font-family:var(--mono);font-size:11px'>{esc(ev.get('timestamp') or '—')}</td>"
            f"<td>{esc(ev.get('event'))}</td>"
            f"<td>{esc(ev.get('actor_nick'))}{arrow}</td>"
            f"<td style='font-size:11px'>{esc((ev.get('label') or '')[:100])}</td></tr>"
        )

    co_rows = []
    for p in result["cross_thread"].get("co_presence_pairs", [])[:20]:
        na = next((a["display_name"] for a in actors if a["author_id"] == p["a"]), p["a"])
        nb = next((a["display_name"] for a in actors if a["author_id"] == p["b"]), p["b"])
        co_rows.append(
            f"<tr><td>{esc(na)}</td><td style='color:#93a4bb'>co</td><td>{esc(nb)}</td>"
            f"<td>{p['co_thread_count']} threads</td>"
            f"<td style='font-size:11px;color:#fbbf24'>undirected co_presence (not reply)</td></tr>"
        )

    coord_pill = {
        "none": "ok",
        "weak": "neutral",
        "moderate": "caution",
        "strong_signals": "caution",
    }.get(coord["read"], "neutral")

    reasons = "".join(f"<li>{esc(r)}</li>" for r in coord["reasons"]) or "<li>—</li>"
    cohort_badge = (
        "expanded"
        if result["cohort"]["expanded"]
        else f"seed_only ({result['cohort'].get('error') or 'no expand'})"
    )

    pair_blocks = []
    for pair, evs in list(result["pair_timelines"].items())[:12]:
        items = "".join(
            f"<li><code>{esc(e.get('timestamp') or '')}</code> · {esc(e.get('type'))} · {esc((e.get('snippet') or '')[:80])}</li>"
            for e in evs
        )
        pair_blocks.append(f"<h4 style='margin:10px 0 4px'>{esc(pair)}</h4><ul>{items}</ul>")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Kampff directed network · {esc(seed['title'][:50])}</title>
<style>{css}
  .pill.ok {{ color:#bbf7d0; border-color:#16a34a; background:#052e16; }}
  .dir {{ color:#5eead4; font-weight:700; font-family:var(--mono); }}
</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <p class="kicker">THREAD ACTORS · DIRECTED REPLY NETWORK · CROSS-THREAD · TEMPORAL</p>
    <h1>{esc(seed['title'][:110])}</h1>
    <p class="sub"><a href="{esc(seed['url'])}">{esc(seed['url'])}</a></p>
    <div class="meta">
      <div class="chip"><b>OP</b>{esc(seed['op']['display_name'])}</div>
      <div class="chip"><b>Seed comments</b>{seed.get('parsed_comments')} / UI {seed.get('ui_comment_count')}</div>
      <div class="chip"><b>Directed edges</b>{s['n_directed_edges']} (events {s['n_directed_events']})</div>
      <div class="chip"><b>Cohort</b>{esc(cohort_badge)}</div>
    </div>
    <div class="distance-banner" style="background:#0c1a24;border-color:#1e4d6b">
      <span style="font-size:12px;color:#7dd3fc">Direction</span>
      <span class="pill engage">A → B = A replies to B</span>
      <span class="pill {coord_pill}">coord {coord['read']} · {coord['score']}</span>
      <span style="font-size:12px;color:var(--muted)">{esc(s['one_line'])}</span>
    </div>
  </header>

  <nav class="toc">
    <a href="#net">Directed graph</a>
    <a href="#edges">Edge list</a>
    <a href="#time">Temporal</a>
    <a href="#cross">Cross-thread</a>
    <a href="#actors">Actors</a>
    <a href="#coord">Coordination</a>
  </nav>

  <section class="card" id="net">
    <h2><span class="n">1</span> Directed reply network</h2>
    <p><span class="dir">Arrow A → B</span> means <b>A acted toward B</b> (mention/reply). Blue = reply_to · Amber = op_address. Thickness ∝ weight.</p>
    <div class="chart-box">
      <svg viewBox="0 0 440 440" role="img" aria-label="Directed reply graph">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#7dd3fc"/>
          </marker>
        </defs>
        {''.join(edge_svg)}
        {''.join(node_svg)}
      </svg>
      <div class="legend">
        <span><i style="background:#38bdf8"></i>reply_to (A→B)</span>
        <span><i style="background:#fbbf24"></i>op_address (A→OP)</div>
        <span><i style="background:#4ade80"></i>malice low</span>
        <span><i style="background:#fbbf24"></i>elevated</span>
        <span><i style="background:#f87171"></i>high</span>
      </div>
    </div>
  </section>

  <section class="card" id="edges">
    <h2><span class="n">2</span> Directed edge list</h2>
    <table>
      <tr><th>from</th><th></th><th>to</th><th>type</th><th>w</th><th>time</th><th>snippet</th></tr>
      {''.join(erows) or '<tr><td colspan=7>no directed edges</td></tr>'}
    </table>
  </section>

  <section class="card" id="time">
    <h2><span class="n">3</span> Temporal trace</h2>
    <p>Events sorted by timestamp. Reply rows show <span class="dir">from → to</span>.</p>
    <table>
      <tr><th>time</th><th>event</th><th>actor / direction</th><th>label</th></tr>
      {''.join(trows) or '<tr><td colspan=4>no timestamps parsed</td></tr>'}
    </table>
    <h3>Pair timelines (directed)</h3>
    {''.join(pair_blocks) or '<p>no pair series</p>'}
  </section>

  <section class="card" id="cross">
    <h2><span class="n">4</span> Cross-thread relations</h2>
    <p>Cohort depth: <b>{esc(cohort_badge)}</b>. Co-presence = same non-seed thread activity index — <b>not</b> a reply arrow.</p>
    <table>
      <tr><th>A</th><th></th><th>B</th><th>count</th><th>note</th></tr>
      {''.join(co_rows) or '<tr><td colspan=5>no cohort expand yet — login + --expand</td></tr>'}
    </table>
    <p style="font-size:12px;color:var(--muted)">Indexed cross threads: {result['cross_thread'].get('n_cross_threads_indexed', 0)}</p>
  </section>

  <section class="card" id="actors">
    <h2><span class="n">5</span> Actors</h2>
    <table>
      <tr><th>actor</th><th>seed n</th><th>intent</th><th>malice</th><th>out (me→)</th><th>in (→me)</th><th>cohort posts/cmtThr</th><th>sample</th></tr>
      {''.join(arows)}
    </table>
  </section>

  <section class="card" id="coord">
    <h2><span class="n">6</span> Coordination signals</h2>
    <p>Score <b>{coord['score']}</b> · <span class="pill {coord_pill}">{coord['read']}</span></p>
    <ul>{reasons}</ul>
    <div class="one-line">Signals only. Directed graph + time + cross-thread required for organization claims. Seed-only is insufficient.</div>
  </section>

  <footer>Kampff thread-actor cohort · direction A→B = A replies to B · not legal findings</footer>
</div>
</body>
</html>
"""
    # fix broken legend div
    html = html.replace(
        '<span><i style="background:#fbbf24"></i>op_address (A→OP)</div>',
        '<span><i style="background:#fbbf24"></i>op_address (A→OP)</span>',
    )
    path.write_text(html, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--seed-html", type=Path, default=None)
    ap.add_argument("--focus", default="")
    ap.add_argument("--expand", action="store_true")
    ap.add_argument("--max-pages", type=int, default=1)
    ap.add_argument("--max-actors", type=int, default=5)
    ap.add_argument("--boards", default="park")
    args = ap.parse_args()

    url = args.url.split("?")[0].split("#")[0]
    m = re.search(r"/board/([a-zA-Z0-9_]+)/(\d+)", url)
    board_sn = f"{m.group(1)}_{m.group(2)}" if m else "thread"
    raw_dir = INBOX / "raw" / f"thread_{board_sn}"
    raw_dir.mkdir(parents=True, exist_ok=True)

    if args.seed_html and args.seed_html.exists():
        html = args.seed_html.read_text(encoding="utf-8", errors="ignore")
    else:
        raise SystemExit("provide --seed-html for now (or implement fetch)")

    seed = parse_seed_thread(html, url)
    (raw_dir / "thread.json").write_text(
        json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # actor roster for expand — prioritize people who already have directed edges
    roster = []
    seen = set()
    for c in seed["comments"]:
        if c["author_id"] in seen:
            continue
        seen.add(c["author_id"])
        roster.append(
            {"author_id": c["author_id"], "display_name": c["display_name"]}
        )
    # degree hint from seed mentions
    deg = Counter()
    for c in seed["comments"]:
        deg[c["author_id"]] += 1 + len(c.get("mentions") or [])
    roster.sort(key=lambda a: -deg.get(a["author_id"], 0))

    cohort = {"ok": False, "error": "not_requested", "by_actor": {}}
    if args.expand:
        print(
            "expanding cohort HUMAN-PACED "
            f"(max_actors={args.max_actors}, pages≤{args.max_pages}, board cap 1)…"
        )
        print("If bot wall → auto cooldown 45m. Prefer cache/resume.")
        cohort = expand_cohort(
            roster,
            boards=[b.strip() for b in args.boards.split(",") if b.strip()],
            max_pages=args.max_pages,
            raw_dir=raw_dir / "cohort",
            max_actors=args.max_actors,
        )
        # merge with previous cohort index (multi-wave)
        idx_path = raw_dir / "cohort_index.json"
        if idx_path.exists() and cohort.get("ok"):
            try:
                prev = json.loads(idx_path.read_text(encoding="utf-8"))
                merged = dict(prev.get("by_actor") or {})
                merged.update(cohort.get("by_actor") or {})
                cohort["by_actor"] = merged
                cohort["merged_waves"] = True
            except Exception:
                pass
        idx_path.write_text(
            json.dumps(cohort, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # also write parent cohort_index for rebuild scripts
        try:
            (raw_dir.parent / "cohort_index.json").write_text(
                json.dumps(cohort, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
        print("cohort", cohort.get("ok"), cohort.get("error"))

    result = analyze(seed, cohort, focus_id=args.focus or None)
    base = OUT / f"{DATE}-thread-{board_sn}-actors"
    json_path = Path(str(base) + ".json")
    html_path = Path(str(base) + ".html")
    md_path = Path(str(base) + ".md")
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    render_html(result, html_path)

    # short md
    lines = [
        f"# Thread actors (directed) — {seed['title']}",
        "",
        f"URL: {seed['url']}",
        f"Direction rule: **A → B = A replies to B**",
        f"One-liner: {result['summary']['one_line']}",
        f"Coordination: {result['coordination']['read']} ({result['coordination']['score']})",
        f"Cohort: {result['honesty']['cohort_depth']}",
        "",
        "## Directed edges",
        "",
    ]
    for e in result["edges_directed"]:
        lines.append(
            f"- **{e['from_nick']} → {e['to_nick']}** · {e['type']} · w={e['weight']} · {e.get('timestamp','')}"
        )
    lines += ["", "## Actors", ""]
    for a in result["actors"]:
        lines.append(
            f"- {a['display_name']} (`{a['author_id']}`) intent={a['intent_primary']} "
            f"out={a['out_weight']} in={a['in_weight']}"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("HTML", html_path)
    print("JSON", json_path)
    print(result["summary"]["one_line"])
    print("edges:")
    for e in result["edges_directed"][:15]:
        print(f"  {e['from_nick']} → {e['to_nick']} [{e['type']}] w={e['weight']}")


if __name__ == "__main__":
    main()
