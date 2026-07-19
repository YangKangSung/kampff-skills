#!/usr/bin/env python3
"""Human-like browsing helpers for Kampff collectors."""
from __future__ import annotations

import hashlib
import json
import random
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable


def human_pause(lo: float = 2.5, hi: float = 6.5) -> None:
    """Sleep a jittered duration (seconds)."""
    time.sleep(random.uniform(lo, hi))


def human_pause_actor() -> None:
    """Longer pause between different people."""
    time.sleep(random.uniform(8.0, 18.0))


def human_scroll(page: Any, steps: int | None = None) -> None:
    steps = steps if steps is not None else random.randint(2, 5)
    for i in range(steps):
        try:
            page.evaluate(
                f"window.scrollBy(0, {random.randint(200, 550)})"
            )
        except Exception:
            break
        time.sleep(random.uniform(0.35, 1.1))
    # sometimes scroll back a bit
    if random.random() < 0.4:
        try:
            page.evaluate(f"window.scrollBy(0, -{random.randint(80, 200)})")
        except Exception:
            pass
        time.sleep(random.uniform(0.2, 0.6))


def human_idle(page: Any) -> None:
    """Small mouse-ish idle via hover if possible."""
    try:
        page.mouse.move(random.randint(80, 400), random.randint(100, 500))
    except Exception:
        pass
    time.sleep(random.uniform(0.8, 2.2))


class UrlCache:
    def __init__(self, root: Path, ttl_hours: float = 24.0):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        self.meta_path = self.root / "_cache_meta.json"
        self.meta = {}
        if self.meta_path.exists():
            try:
                self.meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
            except Exception:
                self.meta = {}

    def _key(self, url: str) -> str:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]

    def get(self, url: str) -> str | None:
        k = self._key(url)
        ent = self.meta.get(k)
        path = self.root / f"{k}.html"
        if not ent or not path.exists():
            return None
        try:
            ts = datetime.fromisoformat(ent["ts"])
        except Exception:
            return None
        if datetime.now() - ts > self.ttl:
            return None
        return path.read_text(encoding="utf-8", errors="ignore")

    def put(self, url: str, html: str) -> Path:
        k = self._key(url)
        path = self.root / f"{k}.html"
        path.write_text(html, encoding="utf-8")
        self.meta[k] = {"ts": datetime.now().isoformat(timespec="seconds"), "url": url}
        self.meta_path.write_text(
            json.dumps(self.meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path


def goto_human(
    page: Any,
    url: str,
    cache: UrlCache | None = None,
    lo: float = 2.8,
    hi: float = 6.8,
) -> str:
    """Navigate with cache + human pause/scroll. Returns HTML."""
    if cache:
        hit = cache.get(url)
        if hit is not None:
            return hit
    human_pause(lo, hi)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    human_idle(page)
    human_scroll(page)
    html = page.content()
    # bot wall heuristics
    low = html.lower()
    if any(
        x in html
        for x in (
            "비정상적인 접근",
            "자동 입력",
            "captcha",
            "Access Denied",
            "잠시 후 다시",
        )
    ) or ("로그인" in (page.title() or "") and "auth/login" in (page.url or "")):
        # still return but caller should check
        pass
    if cache:
        cache.put(url, html)
    return html


def is_bot_wall(html: str, url: str = "", title: str = "") -> bool:
    """True only on real challenge/block pages — not normal pages that load captcha JS."""
    blob = html or ""
    title = title or ""
    url = url or ""
    # hard blocks
    hard = [
        "비정상적인 접근",
        "자동등록방지를 위해",
        "Access Denied",
        "요청이 너무 많",
        "잠시 후 다시 시도",
        "차단되었습니다",
        "cloud플레어",
        "cf-browser-verification",
        "Just a moment...",
    ]
    if any(k in blob for k in hard) or any(k in title for k in hard):
        return True
    # login forced while expecting content
    if "auth/login" in url and "search" not in url:
        return False  # login is not bot wall; caller handles session
    # empty / tiny error shell
    if len(blob) < 2000 and ("error" in title.lower() or "오류" in title):
        return True
    # captcha alone is NOT enough (clien embeds captcha assets on normal pages)
    if re.search(r"g-recaptcha|h-captcha", blob, re.I) and len(blob) < 8000:
        return True
    return False


class Resume:
    def __init__(self, path: Path):
        self.path = path
        self.data = {
            "done_actors": [],
            "next": [],
            "last_error": None,
            "cooldown_until": None,
        }
        if path.exists():
            try:
                self.data.update(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def in_cooldown(self) -> bool:
        cu = self.data.get("cooldown_until")
        if not cu:
            return False
        try:
            return datetime.now() < datetime.fromisoformat(cu)
        except Exception:
            return False

    def set_cooldown_minutes(self, m: float = 30.0) -> None:
        self.data["cooldown_until"] = (
            datetime.now() + timedelta(minutes=m)
        ).isoformat(timespec="seconds")
        self.save()
