#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse saved forum-thread HTML into OP / comments / like ids.

Looks for common markers (`data-author-id`, `comment_row`, sympathy/like blocks).
No network. Used to build an ego relation bundle around one seed id.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

COMMENT_SPLIT = re.compile(
    r'<div class="comment_row([^"]*)"([^>]*)>',
    re.I,
)
NEXT_ROW = re.compile(r'<div class="comment_row|id="comment-write"', re.I)
AUTHOR_ATTR = re.compile(r'data-author-id="([^"]+)"', re.I)
SN_ATTR = re.compile(r'data-comment-sn="([^"]+)"', re.I)
PARENT_SN_ATTR = re.compile(
    r'data-(?:parent-comment-sn|parent-sn|comment-parent-sn)="([^"]+)"',
    re.I,
)
NICK_TITLE = re.compile(r'class="nickname"[^>]*title="([^"]+)"', re.I)
TS_CLASS = re.compile(r'class="timestamp"[^>]*>([^<]+)', re.I)
TS_ISO = re.compile(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)")
LIKE_BLOCK = re.compile(
    r'class="[^"]*(?:symph|sympathy|like_list|liked_user|recommend_list)[^"]*"[\s\S]{0,8000}?(?=class="(?:post_|comment_|btn_)|$)',
    re.I,
)


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


def thread_id_from_url(url: str, filename: str = "") -> str:
    u = str(url or "")
    m = re.search(r"/board/([^/?#]+)/(\d+)", u)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    parts = [p for p in re.split(r"[/?#]", u) if p]
    if len(parts) >= 2 and parts[-1].isdigit():
        return f"{parts[-2]}/{parts[-1]}"
    stem = Path(filename).stem if filename else ""
    m2 = re.match(r"([A-Za-z0-9_]+)_(\d+)$", stem)
    if m2:
        return f"{m2.group(1)}/{m2.group(2)}"
    return stem or u


def to_iso(ts: str, fallback_day: str = "") -> str:
    raw = (ts or "").split("/")[0].strip()
    m = TS_ISO.search(raw)
    if m:
        s = m.group(1).replace(" ", "T")
        if len(s) == 16:
            s += ":00"
        if "+" not in s and "Z" not in s:
            s += "+09:00"
        return s
    if fallback_day:
        return f"{fallback_day[:10]}T00:00:00+09:00"
    return ""


def _comment_text(block: str) -> str:
    for pat in (
        r'class="comment_view"[^>]*>([\s\S]*?)</div>',
        r'class="comment_content"[^>]*>([\s\S]*?)</div>',
        r'class="[^"]*comment_content[^"]*"[^>]*>([\s\S]*?)</div>',
    ):
        m = re.search(pat, block, re.I)
        if m:
            return strip_tags(m.group(1))
    return ""


def _extract_likes(html: str, op_id: str) -> tuple[list[dict[str, str]], str]:
    ids: list[str] = []
    for blk in LIKE_BLOCK.findall(html):
        ids.extend(AUTHOR_ATTR.findall(blk))
    # compact like chips sometimes sit next to a count, not a named list
    if not ids:
        for m in re.finditer(
            r'(?:symph|sympathy|like)[^>]{0,120}data-author-id="([^"]+)"',
            html,
            re.I,
        ):
            ids.append(m.group(1))
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for aid in ids:
        aid = aid.strip()
        if not aid or aid in seen or aid == op_id:
            continue
        seen.add(aid)
        rows.append({"author_id": aid, "target_id": op_id})
    status = "collected" if rows else "not_collected"
    return rows, status


def _op_from_html(html: str, hint_op_id: str = "") -> tuple[str, str]:
    nick = ""
    nm = re.search(
        r'class="post_contact"[\s\S]{0,800}?class="nickname"[^>]*title="([^"]+)"',
        html,
        re.I,
    )
    if nm:
        nick = nm.group(1).strip()
    for pat in (
        r'class="post_contact"[\s\S]{0,2000}?data-author-id="([^"]+)"',
        r'class="post_info"[\s\S]{0,2000}?data-author-id="([^"]+)"',
        r'comment_row[^"]*by-author[^>]*data-author-id="([^"]+)"',
        r'data-author-id="([^"]+)"[^>]*by-author',
    ):
        m = re.search(pat, html, re.I)
        if m and m.group(1).strip():
            return m.group(1).strip(), nick
    if hint_op_id:
        return hint_op_id.strip(), nick
    return "", nick


def parse_thread_html(
    html: str,
    *,
    url: str = "",
    filename: str = "",
    hint_op_id: str = "",
) -> dict[str, Any]:
    title_m = re.search(
        r'class="post_subject"[^>]*>[\s\S]*?<span>([\s\S]*?)</span>',
        html,
        re.I,
    )
    if not title_m:
        title_m = re.search(r"<title>([^<:]+)", html, re.I)
    title = strip_tags(title_m.group(1)) if title_m else ""
    date_m = re.search(r'class="view_count date"[\s\S]*?</span>\s*([^<]+)', html, re.I)
    if not date_m:
        date_m = TS_ISO.search(html)
        ts = date_m.group(1) if date_m else ""
    else:
        ts = date_m.group(1).strip()
    body_m = re.search(
        r'class="post_article"[^>]*>([\s\S]*?)(?:class="post_writer|class="post_button|post_comment|id="comment")',
        html,
        re.I,
    )
    body = strip_tags(body_m.group(1)) if body_m else ""
    op_id, op_nick = _op_from_html(html, hint_op_id)
    tid = thread_id_from_url(url, filename)

    comments: list[dict[str, Any]] = []
    matches = list(COMMENT_SPLIT.finditer(html))
    by_sn: dict[str, str] = {}
    last_top_id = op_id
    last_top_sn = ""
    for i, m in enumerate(matches):
        extra, attrs = m.group(1), m.group(2)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        tail = html[m.end() : end]
        if NEXT_ROW.search(tail):
            cut = NEXT_ROW.search(tail)
            if cut:
                tail = tail[: cut.start()]
        aid = ""
        am = AUTHOR_ATTR.search(attrs) or AUTHOR_ATTR.search(tail[:400])
        if am:
            aid = am.group(1).strip()
        if not aid:
            continue
        sn_m = SN_ATTR.search(attrs) or SN_ATTR.search(tail[:400])
        sn = sn_m.group(1).strip() if sn_m else ""
        parent_m = PARENT_SN_ATTR.search(attrs) or PARENT_SN_ATTR.search(tail[:400])
        parent_sn = parent_m.group(1).strip() if parent_m else ""
        nick_m = NICK_TITLE.search(tail[:800])
        nick = nick_m.group(1).strip() if nick_m else aid
        tsm = TS_CLASS.search(tail) or TS_ISO.search(tail[:800])
        cts = tsm.group(1).strip() if tsm else ts
        is_reply = bool(re.search(r"(?:^|[\s_])re(?:[\s_]|$)", extra, re.I))
        if "by-author" in extra and not op_id:
            op_id = aid
            last_top_id = last_top_id or aid
        if parent_sn and parent_sn in by_sn:
            reply_to = by_sn[parent_sn]
        elif is_reply:
            reply_to = last_top_id
        else:
            reply_to = op_id
            last_top_id = aid
            last_top_sn = sn
        if sn:
            by_sn[sn] = aid
        if aid == op_id and not is_reply:
            last_top_id = aid
            last_top_sn = sn
        comments.append(
            {
                "sn": sn,
                "author_id": aid,
                "nick": nick,
                "text": _comment_text(tail),
                "timestamp": cts,
                "reply_to": reply_to if reply_to != aid else "",
                "parent_sn": parent_sn or (last_top_sn if is_reply else ""),
                "is_reply": is_reply,
                "by_author": "by-author" in extra,
            }
        )

    if not op_id:
        for c in comments:
            if c.get("by_author"):
                op_id = c["author_id"]
                break
    if not op_nick:
        for c in comments:
            if c["author_id"] == op_id and c.get("nick"):
                op_nick = c["nick"]
                break

    likes, likes_status = _extract_likes(html, op_id)
    return {
        "url": url,
        "thread_id": tid,
        "title": title,
        "timestamp": ts,
        "body": body,
        "op_id": op_id,
        "op_nick": op_nick,
        "comments": comments,
        "likes": likes,
        "likes_status": likes_status,
        "filename": filename,
    }


def parse_thread_file(path: str | Path, *, hint_op_id: str = "") -> dict[str, Any]:
    p = Path(path)
    html = p.read_text(encoding="utf-8", errors="ignore")
    canon = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',
        html,
        re.I,
    )
    if not canon:
        canon = re.search(
            r'property=["\']og:url["\'][^>]+content=["\']([^"\']+)',
            html,
            re.I,
        )
    url = canon.group(1).strip() if canon else ""
    return parse_thread_html(html, url=url, filename=p.name, hint_op_id=hint_op_id)
