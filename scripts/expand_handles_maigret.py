#!/usr/bin/env python3
"""Expand public usernames via Maigret → kampff identity map (not full texts).

Requires: pip install maigret (optional; see THIRD_PARTY_NOTICES.md)

Usage:
  python expand_handles_maigret.py YangKangSung
  python expand_handles_maigret.py user1 user2 --person-id me
  set KAMPFF_DATA=D:\\data\\kampff
  set BATCH_DATE=2026-07-13
  set MAIGRET_TOP=50   # keep smoke small (default 50; set 500 for fuller)

Outputs:
  $KAMPFF_DATA/inbox/{batch}/raw/maigret_{label}.json   — expand report
  $KAMPFF_DATA/inbox/{batch}/raw/maigret_{label}_aliases.json — merge hints
  Optionally merges aliases into existing bundle.json if --merge-bundle

Hard rules:
  - Self / authorized public handles only in automation.
  - Does not scrape private data; does not bypass site auth.
  - Collision: hits are candidates, not proof of same person.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


def _batch() -> str:
    return os.environ.get("BATCH_DATE", date.today().isoformat())


def _root() -> Path:
    return Path(os.environ.get("KAMPFF_DATA", r"{KAMPFF_DATA}"))


def _find_maigret() -> list[str]:
    exe = shutil.which("maigret")
    if exe:
        return [exe]
    # Windows scripts dir next to python
    return [sys.executable, "-m", "maigret"]


def _run_maigret(
    username: str,
    out_dir: Path,
    *,
    top: int,
    all_sites: bool,
    tags: str | None,
    timeout: int,
) -> Path | None:
    """Run maigret; return path to produced JSON if found."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = _find_maigret() + [
        username,
        "--json",
        "simple",
        "--folderoutput",
        str(out_dir),
        "--timeout",
        str(timeout),
        "--no-recursion",
        "--no-extracting",
        # Windows/VPN/corp DNS: async aiodns often fails hard (0 hits).
        "--dns-resolver",
        "threaded",
    ]
    if all_sites:
        cmd.append("-a")
    # Maigret uses site rank; --top-sites if available
    if not all_sites and top > 0:
        cmd.extend(["--top-sites", str(top)])
    if tags:
        cmd.extend(["--tags", tags])

    print("RUN", " ".join(cmd), flush=True)
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(120, timeout * max(top // 10, 5)),
        )
    except FileNotFoundError:
        print("FAIL: maigret not found. pip install maigret", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print("FAIL: maigret timeout", file=sys.stderr)
        return None

    if r.returncode != 0:
        # Maigret sometimes returns non-zero with partial results
        print("WARN exit", r.returncode, (r.stderr or r.stdout or "")[:500])

    # Discover JSON artifacts
    candidates = sorted(out_dir.glob("**/*"), key=lambda p: p.stat().st_mtime, reverse=True)
    json_files = [
        p
        for p in candidates
        if p.is_file() and p.suffix.lower() == ".json" and username.lower() in p.name.lower()
    ]
    if not json_files:
        json_files = [p for p in candidates if p.is_file() and p.suffix.lower() == ".json"]
    if not json_files:
        # Fallback: parse stdout for URLs
        print("WARN: no JSON file from maigret; using stdout scrape")
        return _stdout_fallback(username, out_dir, r.stdout or "")
    return json_files[0]


def _stdout_fallback(username: str, out_dir: Path, stdout: str) -> Path:
    hits = []
    for line in stdout.splitlines():
        m = re.search(r"(https?://\S+)", line)
        if m:
            hits.append(
                {
                    "site": "unknown",
                    "url": m.group(1).rstrip(").,]"),
                    "status": "Claimed",
                    "username": username,
                }
            )
    path = out_dir / f"report_{username}_stdout.json"
    path.write_text(json.dumps(hits, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _normalize_hits(raw: Any, username: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []

    def add(site: str, url: str | None, status: str | None, extra: dict | None = None):
        if not url and not site:
            return
        row = {
            "site": site or "unknown",
            "url": url,
            "status": status or "unknown",
            "username": username,
        }
        if extra:
            for k in ("ids", "tags", "http_status"):
                if k in extra:
                    row[k] = extra[k]
        hits.append(row)

    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            add(
                str(item.get("sitename") or item.get("site") or item.get("name") or ""),
                item.get("url_user") or item.get("url") or item.get("link"),
                str(item.get("status") or item.get("claim") or "Claimed"),
                item,
            )
        return hits

    if isinstance(raw, dict):
        # common shapes: {username: {site: {...}}} or {site: {...}}
        if username in raw and isinstance(raw[username], dict):
            raw = raw[username]
        for site, val in raw.items():
            if not isinstance(val, dict):
                continue
            # skip meta keys
            if site.startswith("_"):
                continue
            status = val.get("status")
            if hasattr(status, "name"):
                status = status.name
            status_s = str(status) if status is not None else str(val.get("status_text") or "")
            url = val.get("url_user") or val.get("url") or val.get("link")
            add(str(site), url, status_s or "Claimed", val)
        return hits

    return hits


def _filter_claimed(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for h in hits:
        st = (h.get("status") or "").lower()
        # Keep claimed / claimed-like; drop explicit negatives when obvious
        if any(x in st for x in ("not", "false", "illegal", "error", "unknown")):
            # still keep if URL present and "claimed" somewhere
            if "claimed" not in st and "found" not in st:
                continue
        if not h.get("url"):
            continue
        out.append(h)
    return out


def _aliases_from_hits(username: str, hits: list[dict[str, Any]]) -> dict[str, Any]:
    sites = sorted({h["site"] for h in hits if h.get("site")})
    urls = [h["url"] for h in hits if h.get("url")]
    # Site-local handles rarely differ; keep seed username + high-signal domains
    aliases = [username]
    for h in hits:
        u = h.get("url") or ""
        # github.com/x, x.com/x, etc.
        m = re.search(
            r"(?:github\.com|x\.com|twitter\.com|reddit\.com/user|instagram\.com|gitlab\.com)/([^/?#]+)",
            u,
            re.I,
        )
        if m:
            handle = m.group(1)
            if handle.lower() not in {a.lower() for a in aliases}:
                aliases.append(handle)
    return {
        "seed_username": username,
        "aliases": aliases,
        "candidate_urls": urls,
        "sites": sites,
        "hit_count": len(hits),
        "note": "Candidates only — username collision possible; do not merge persons without evidence.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "maigret",
    }


def _presence_texts(username: str, hits: list[dict[str, Any]], batch: str) -> list[dict[str, Any]]:
    """Optional short markers for bundle (not a substitute for real posts)."""
    texts = []
    # Cap to avoid polluting spectrograph with hundreds of empty presence lines
    for h in hits[:40]:
        site = h.get("site") or "site"
        url = h.get("url") or ""
        texts.append(
            {
                "content": f"[maigret account presence] site={site} status={h.get('status')} url={url}",
                "timestamp": f"{batch}T00:00:00+00:00",
                "source": "sns_post",
                "platform": "maigret",
                "type": "account_presence",
                "url": url,
                "collected_from": f"maigret:{username}",
                "note": "presence marker only; low weight for L1–L5",
            }
        )
    return texts


def _merge_bundle(
    bundle_path: Path,
    person_id: str,
    aliases_info: dict[str, Any],
    texts: list[dict[str, Any]],
    *,
    include_presence_texts: bool,
) -> None:
    if not bundle_path.is_file():
        print("SKIP merge: no bundle at", bundle_path)
        return
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    people = data.get("people") or []
    found = False
    for p in people:
        if p.get("id") == person_id:
            found = True
            existing = list(p.get("aliases") or [])
            for a in aliases_info.get("aliases") or []:
                if a.lower() not in {x.lower() for x in existing}:
                    existing.append(a)
            p["aliases"] = existing
            meta = p.get("meta") or {}
            meta["maigret"] = {
                "hit_count": aliases_info.get("hit_count"),
                "sites": aliases_info.get("sites"),
                "candidate_urls_sample": (aliases_info.get("candidate_urls") or [])[:20],
                "note": aliases_info.get("note"),
            }
            p["meta"] = meta
            if include_presence_texts:
                p.setdefault("texts", []).extend(texts)
            break
    if not found:
        print("WARN: person_id not in bundle:", person_id)
        return
    bundle_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MERGED aliases into", bundle_path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Maigret → kampff handle expansion")
    ap.add_argument("usernames", nargs="+", help="Public usernames to expand")
    ap.add_argument("--person-id", default="me", help="people[].id for merge")
    ap.add_argument("--top", type=int, default=int(os.environ.get("MAIGRET_TOP", "50")))
    ap.add_argument("--all-sites", action="store_true")
    ap.add_argument("--tags", default=None)
    ap.add_argument("--timeout", type=int, default=15)
    ap.add_argument("--merge-bundle", action="store_true", help="Merge into inbox bundle.json")
    ap.add_argument(
        "--include-presence-texts",
        action="store_true",
        help="Also append short presence markers into bundle texts (default off)",
    )
    args = ap.parse_args()

    batch = _batch()
    root = _root()
    raw_dir = root / "inbox" / batch / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    label = args.person_id if len(args.usernames) == 1 else args.person_id + "_multi"
    all_hits: list[dict[str, Any]] = []
    per_user: dict[str, Any] = {}

    with tempfile.TemporaryDirectory(prefix="kampff_maigret_") as tmp:
        tmp_path = Path(tmp)
        for username in args.usernames:
            jpath = _run_maigret(
                username,
                tmp_path / username,
                top=args.top,
                all_sites=args.all_sites,
                tags=args.tags,
                timeout=args.timeout,
            )
            if not jpath or not jpath.is_file():
                print("FAIL no result for", username)
                per_user[username] = {"hits": [], "error": "no_json"}
                continue
            try:
                raw = json.loads(jpath.read_text(encoding="utf-8", errors="replace"))
            except Exception as e:
                print("JSON parse fail", username, e)
                per_user[username] = {"hits": [], "error": str(e)}
                continue
            hits = _filter_claimed(_normalize_hits(raw, username))
            all_hits.extend(hits)
            per_user[username] = {
                "hits": hits,
                "aliases": _aliases_from_hits(username, hits),
                "source_json": jpath.name,
            }
            # Keep a copy of raw maigret file
            dest = raw_dir / f"maigret_raw_{username}.json"
            dest.write_text(jpath.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
            print("HITS", username, len(hits), "→", dest)

    report = {
        "batch_date": batch,
        "person_id": args.person_id,
        "usernames": args.usernames,
        "top_sites": None if args.all_sites else args.top,
        "all_sites": args.all_sites,
        "per_user": per_user,
        "total_hits": len(all_hits),
        "ethics": "candidates only; lawful public OSINT; no stalking",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    report_path = raw_dir / f"maigret_{label}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Combined aliases
    combined_aliases = [args.person_id]
    combined_urls: list[str] = []
    combined_sites: list[str] = []
    for u, block in per_user.items():
        al = block.get("aliases") or _aliases_from_hits(u, block.get("hits") or [])
        for a in al.get("aliases") or [u]:
            if a.lower() not in {x.lower() for x in combined_aliases}:
                combined_aliases.append(a)
        combined_urls.extend(al.get("candidate_urls") or [])
        combined_sites.extend(al.get("sites") or [])
    aliases_info = {
        "person_id": args.person_id,
        "aliases": combined_aliases,
        "candidate_urls": combined_urls,
        "sites": sorted(set(combined_sites)),
        "hit_count": len(all_hits),
        "note": "Candidates only — username collision possible; do not merge persons without evidence.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "maigret",
    }
    aliases_path = raw_dir / f"maigret_{label}_aliases.json"
    aliases_path.write_text(json.dumps(aliases_info, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WROTE", report_path)
    print("WROTE", aliases_path)
    print("SUMMARY hits=", len(all_hits), "aliases=", aliases_info["aliases"][:10])

    texts = []
    for u in args.usernames:
        texts.extend(_presence_texts(u, (per_user.get(u) or {}).get("hits") or [], batch))

    if args.merge_bundle:
        bundle = root / "inbox" / batch / "bundle.json"
        _merge_bundle(
            bundle,
            args.person_id,
            aliases_info,
            texts,
            include_presence_texts=args.include_presence_texts,
        )

    return 0 if all_hits or any((per_user.get(u) or {}).get("hits") for u in args.usernames) else 2


if __name__ == "__main__":
    raise SystemExit(main())
