#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dual-store layout helpers (runtime dataRoot vs durable wikiRoot).

Ported concepts from kampff-vscode/src/wikiStore.ts + config dual roots.
No VS Code dependency — usable from CLI / Hermes jobs.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union
from zoneinfo import ZoneInfo


def normalize_path(p: Union[str, Path, None]) -> Optional[Path]:
    """Accept Windows, POSIX, and MSYS (/d/prjs/...) paths."""
    if p is None:
        return None
    if isinstance(p, Path) and p.drive:
        return p
    s = str(p).strip()
    if not s:
        return None
    s_unix = s.replace("\\", "/")
    m = re.match(r"^/([A-Za-z])/(.*)$", s_unix)
    if m:
        return Path(f"{m.group(1).upper()}:/{m.group(2)}")
    # already D:/ or relative
    return Path(s)


@dataclass
class PriorHit:
    kind: str
    path: str
    mtime_ms: float = 0.0
    label: str = ""


@dataclass
class PromoteResult:
    ok: bool
    wiki_root: str = ""
    reports_dir: str = ""
    people_dir: str = ""
    copied: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    error: str = ""


def _exists_dir(p: Path) -> bool:
    try:
        return p.is_dir()
    except OSError:
        return False


def _exists_file(p: Path) -> bool:
    try:
        return p.is_file()
    except OSError:
        return False


def _mtime_ms(p: Path) -> float:
    try:
        return p.stat().st_mtime * 1000.0
    except OSError:
        return 0.0


def data_root(explicit: Optional[str] = None) -> Path:
    raw = explicit or os.environ.get("KAMPFF_DATA") or ""
    if not raw:
        # default beside repo
        here = Path(__file__).resolve().parents[1]
        return here / "kampff-data"
    return normalize_path(raw) or Path(raw)


def out_dir(root: Optional[Path] = None) -> Path:
    return (root or data_root()) / "out"


def inbox_dir(root: Optional[Path] = None) -> Path:
    return (root or data_root()) / "inbox"


def queue_dir(root: Optional[Path] = None) -> Path:
    return (root or data_root()) / "queue"


def wiki_root(explicit: Optional[str] = None) -> Optional[Path]:
    raw = explicit or os.environ.get("KAMPFF_WIKI") or os.environ.get("KAMPFF_WIKI_ROOT") or ""
    if not raw:
        return None
    return normalize_path(raw)


def people_dir(wiki: Optional[Path] = None, override: Optional[str] = None) -> Optional[Path]:
    if override:
        return normalize_path(override)
    w = wiki if wiki is not None else wiki_root()
    if not w:
        return None
    return w / "people"


def wiki_reports_dir(wiki: Optional[Path] = None) -> Optional[Path]:
    w = wiki if wiki is not None else wiki_root()
    if not w:
        return None
    return w / "reports"


def ensure_wiki_layout(wiki: Path) -> None:
    wiki.mkdir(parents=True, exist_ok=True)
    (wiki / "people").mkdir(exist_ok=True)
    (wiki / "reports").mkdir(exist_ok=True)
    readme = wiki / "README.md"
    if not readme.is_file():
        readme.write_text(
            "\n".join(
                [
                    "# Kampff · LLM Wiki shelf",
                    "",
                    "Durable Kampff outputs (not runtime scratch).",
                    "",
                    "| Path | Role |",
                    "|------|------|",
                    "| `people/{platform}/{id}/` | accumulate SoT (NOTES, profile, history) |",
                    "| `reports/` | final analysis.json + report.html/.md copies |",
                    "",
                    "Runtime harvest lives under `KAMPFF_DATA` (`inbox/`, `queue/`, `out/`).",
                    "Re-analyze merges priors from this shelf + runtime out/.",
                    "",
                ]
            ),
            encoding="utf-8",
        )


def _id_tokens(platform: str, sid: str, nick: str = "") -> List[str]:
    out = set()
    for s in (sid, nick, platform):
        t = (s or "").strip().lower()
        if t:
            out.add(t)
    return [x for x in out if x]


def _name_looks_like_target(name: str, tokens: Sequence[str]) -> bool:
    n = name.lower()
    return any(len(t) >= 2 and t in n for t in tokens)


def find_prior_evidence(
    *,
    platform: str = "clien",
    sid: str = "",
    nick: str = "",
    data: Optional[Path] = None,
    wiki: Optional[Path] = None,
    people_override: Optional[Path] = None,
) -> List[PriorHit]:
    """Collect prior evidence paths for merge-into-next-analysis."""
    sid = (sid or "").strip()
    nick = (nick or "").strip()
    platform = (platform or "clien").lower()
    if not sid and not nick:
        return []

    tokens = _id_tokens(platform, sid, nick)
    hits: List[PriorHit] = []
    seen = set()

    def push(kind: str, p: Path, label: str = "") -> None:
        try:
            abs_p = p.resolve()
        except OSError:
            abs_p = p
        key = str(abs_p).lower() if os.name == "nt" else str(abs_p)
        if key in seen:
            return
        if not (_exists_file(abs_p) or _exists_dir(abs_p)):
            return
        seen.add(key)
        hits.append(
            PriorHit(
                kind=kind,
                path=str(abs_p),
                mtime_ms=_mtime_ms(abs_p),
                label=label or abs_p.name,
            )
        )

    p_root = people_override or people_dir(wiki)
    if sid and p_root and _exists_dir(p_root):
        person = p_root / platform / sid
        if _exists_dir(person):
            push("people_dir", person, f"{platform}/{sid}")
            for name in (
                "NOTES.md",
                "notes.md",
                "profile.json",
                "history.json",
                "authorship_integrity.json",
                "LATEST.json",
            ):
                fp = person / name
                if not _exists_file(fp):
                    continue
                low = name.lower()
                kind = (
                    "notes"
                    if low.startswith("notes")
                    else "profile"
                    if low.startswith("profile")
                    else "history"
                    if low.startswith("history")
                    else "other"
                )
                push(kind, fp, name)
            try:
                for f in person.iterdir():
                    if not f.is_file():
                        continue
                    if f.name.endswith("-analysis.json") or f.name == "analysis.json":
                        push("analysis", f, f.name)
                    elif f.name.endswith("-report.md"):
                        push("report_md", f, f.name)
                    elif f.name.endswith("-report.html"):
                        push("report_html", f, f.name)
            except OSError:
                pass

    w_reports = wiki_reports_dir(wiki)
    if w_reports and _exists_dir(w_reports):
        try:
            for f in w_reports.iterdir():
                if not f.is_file() or not _name_looks_like_target(f.name, tokens):
                    continue
                if f.name.endswith("-analysis.json") or f.name.endswith("analysis.json"):
                    push("analysis", f, f.name)
                elif f.name.endswith("-report.md") or f.suffix == ".md":
                    push("report_md", f, f.name)
                elif f.name.endswith("-report.html") or f.suffix == ".html":
                    push("report_html", f, f.name)
                else:
                    push("other", f, f.name)
        except OSError:
            pass

    out = out_dir(data)
    if _exists_dir(out):
        try:
            for f in out.iterdir():
                if not f.is_file() or not _name_looks_like_target(f.name, tokens):
                    continue
                if f.name.endswith("-analysis.json") or f.name.endswith("analysis.json"):
                    push("analysis", f, f.name)
                elif f.name.endswith("-report.md"):
                    push("report_md", f, f.name)
                elif f.name.endswith("-report.html"):
                    push("report_html", f, f.name)
        except OSError:
            pass

    hits.sort(key=lambda h: h.mtime_ms, reverse=True)
    return hits


def promote_outputs_to_wiki(
    *,
    target_id: str,
    platform: str = "clien",
    nick: str = "",
    analysis_path: Optional[Path] = None,
    report_path: Optional[Path] = None,
    date: Optional[str] = None,
    wiki: Optional[Path] = None,
) -> PromoteResult:
    """Copy finished job artifacts into wiki shelf."""
    w = wiki if wiki is not None else wiki_root()
    if not w:
        return PromoteResult(ok=False, error="wikiRoot empty — set KAMPFF_WIKI")

    try:
        ensure_wiki_layout(w)
        reports = wiki_reports_dir(w)
        people = people_dir(w)
        assert reports and people
        platform = (platform or "clien").lower()
        sid = (target_id or "").strip()
        if not date:
            date = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
        base = f"{date}-{sid or 'unknown'}"
        copied: List[str] = []
        skipped: List[str] = []

        def copy_named(src: Optional[Path], dest_name: str) -> None:
            if not src or not _exists_file(src):
                if src:
                    skipped.append(str(src))
                return
            dest = reports / dest_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied.append(str(dest))

        if analysis_path:
            bn = analysis_path.name
            copy_named(analysis_path, bn if bn.endswith(".json") else f"{base}-analysis.json")
        if report_path:
            bn = report_path.name
            copy_named(report_path, bn if bn.endswith(".html") else f"{base}-report.html")
            md = report_path.with_suffix(".md") if report_path.suffix == ".html" else None
            if md and _exists_file(md):
                copy_named(md, md.name)

        if sid:
            person = people / platform / sid
            person.mkdir(parents=True, exist_ok=True)
            latest = {
                "id": sid,
                "nick": nick or "",
                "platform": platform,
                "date": date,
                "analysis": str(analysis_path) if analysis_path else "",
                "report": str(report_path) if report_path else "",
                "promoted_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
            }
            (person / "LATEST.json").write_text(
                json.dumps(latest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            for src in (analysis_path, report_path):
                if src and _exists_file(src):
                    dest = person / src.name
                    shutil.copy2(src, dest)
                    copied.append(str(dest))

            idx = w / "Index.md"
            line = f"- {date} · {platform}/{sid}" + (f" · {nick}" if nick else "") + "\n"
            if idx.is_file():
                prev = idx.read_text(encoding="utf-8")
                if line.strip() not in prev:
                    with idx.open("a", encoding="utf-8") as fh:
                        fh.write(line)
            else:
                idx.write_text("# Kampff wiki index\n\n" + line, encoding="utf-8")
            copied.append(str(idx))

        return PromoteResult(
            ok=True,
            wiki_root=str(w),
            reports_dir=str(reports),
            people_dir=str(people),
            copied=copied,
            skipped=skipped,
        )
    except Exception as e:  # noqa: BLE001 — CLI surface
        return PromoteResult(ok=False, error=str(e))


def format_prior_for_prompt(hits: Iterable[PriorHit], limit: int = 24) -> str:
    lines = ["## PRIOR EVIDENCE (merge)", ""]
    n = 0
    for h in hits:
        lines.append(f"- [{h.kind}] {h.path}" + (f" ({h.label})" if h.label else ""))
        n += 1
        if n >= limit:
            break
    if n == 0:
        lines.append("(none)")
    return "\n".join(lines) + "\n"


def _main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Kampff dual-store wiki helpers")
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("prior", help="list prior evidence paths")
    pe.add_argument("--id", required=True)
    pe.add_argument("--platform", default="clien")
    pe.add_argument("--nick", default="")
    pe.add_argument("--data", default=None)
    pe.add_argument("--wiki", default=None)
    pe.add_argument("--prompt", action="store_true")

    pr = sub.add_parser("promote", help="copy analysis/report into wiki shelf")
    pr.add_argument("--id", required=True)
    pr.add_argument("--platform", default="clien")
    pr.add_argument("--nick", default="")
    pr.add_argument("-a", "--analysis", type=Path)
    pr.add_argument("-r", "--report", type=Path)
    pr.add_argument("--wiki", default=None)
    pr.add_argument("--date", default=None)

    init = sub.add_parser("init-wiki", help="create people/ reports/ README")
    init.add_argument("--wiki", required=True)

    args = p.parse_args(argv)
    if args.cmd == "init-wiki":
        w = normalize_path(args.wiki)
        assert w is not None
        ensure_wiki_layout(w)
        print(w.resolve())
        return 0
    if args.cmd == "prior":
        hits = find_prior_evidence(
            platform=args.platform,
            sid=args.id,
            nick=args.nick,
            data=normalize_path(args.data) if args.data else None,
            wiki=normalize_path(args.wiki) if args.wiki else wiki_root(),
        )
        if args.prompt:
            sys.stdout.write(format_prior_for_prompt(hits))
        else:
            for h in hits:
                print(f"{h.kind}\t{h.path}")
        return 0
    if args.cmd == "promote":
        res = promote_outputs_to_wiki(
            target_id=args.id,
            platform=args.platform,
            nick=args.nick,
            analysis_path=normalize_path(args.analysis) if args.analysis else None,
            report_path=normalize_path(args.report) if args.report else None,
            date=args.date,
            wiki=normalize_path(args.wiki) if args.wiki else wiki_root(),
        )
        print(json.dumps(res.__dict__, ensure_ascii=False, indent=2))
        return 0 if res.ok else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
