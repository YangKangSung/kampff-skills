#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Optional community *draft* export — NOT the person dossier.

Ported from kampff-vscode/src/communityPost.ts (v0.9.x).
Tone SoT: docs/community-post.md

Never invent generic market/semiconductor filler when seed is empty.
Write like a human peer: 합니다/봅니다, no AI meta, no ops tags.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional

OPS = re.compile(
    r"\b(caution|avoid|engage|ops|ROI|distance|worldview|alliance|stability|drift|risk|"
    r"L[1-5]|MBTI|ACH|CIA|SAT|Big ?Five|clinical|diagnosis|doxx?|"
    r"CONFIRMED|PROBABLE|SPECULATIVE)\b",
    re.I,
)
AI_META = re.compile(
    r"(이 한 줄은|전반 분석|독시어|dossier 요약|게시용으로 다듬|다음과 같습니다|"
    r"나아가|결론적으로|요약하자면|정리하면 다음과|AI가|언어모델)",
    re.I,
)
META_NOISE = re.compile(
    r"(표본|수집분?|분석\s*결과|리포트|dossier|권고\s*태그|matrix|honesty|bundle|harvest)",
    re.I,
)

REFUSE = (
    "[게시 초안 생성 불가]\n"
    "이 버튼은 회원 전반 분석(dossier)이 아닙니다.\n"
    "analysis에 쓸 만한 문장(seed)이 없어 일반 템플릿으로 채우지 않습니다.\n"
    "→ 위 리포트 TL;DR · L1–L5 · Distance · Evidence 가 본 분석입니다.\n"
    "→ 게시 초안이 필요하면 analysis.community_post 에 문장을 넣거나, dossier를 보고 직접 쓰세요."
)

Tone = str  # "peer" | "short" | "board"


def normalize_tone(t: Optional[str] = None) -> Tone:
    v = str(t or "peer").strip().lower()
    if v in {"short", "s", "brief", "댓글"}:
        return "short"
    if v in {"board", "b", "full", "modeb", "본문"}:
        return "board"
    return "peer"


def looks_like_tag_salad(s: str) -> bool:
    t = (s or "").strip()
    if not t or len(t) < 8:
        return True
    has_stop = bool(re.search(r"[.。?!]|다\.|요\.|임\.|음\.|습니다|거든요|봅니다", t))
    parts = [p for p in re.split(r"[\s·|/,:;]+", t) if p]
    if not has_stop and len(parts) >= 3 and all(len(p) <= 12 for p in parts):
        return True
    if re.search(r"\b(park|kin|use|cm_stock|hongbo)\b", t, re.I) and not has_stop:
        return True
    if re.search(r"(공유형|논객형|생활형|문제해결형|열기\s*중간|공손\s*톤|뉴스공유)", t) and not has_stop:
        return True
    return False


def clean_ops(s: str) -> str:
    out = OPS.sub("", s or "")
    out = AI_META.sub("", out)
    out = META_NOISE.sub("", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def humanize_preset(s: str) -> str:
    t = (s or "").strip()
    if not t:
        return ""
    t = AI_META.sub("", t)
    t = re.sub(r"^>\s*.+$", "", t, flags=re.M)
    t = re.sub(r"^(#+\s*|##\s*본문.*|##\s*짧은.*|##\s*법적.*).*$", "", t, flags=re.M)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    if re.match(r"^#\s", t) or re.search(r"\n##\s", t):
        m = re.search(r"##\s*본문[^\n]*\n([\s\S]*?)(?=\n##\s|$)", t)
        if m and len(m.group(1).strip()) >= 40:
            t = m.group(1).strip()
    return t.strip()


def distill_point(seed: Mapping[str, Any]) -> str:
    candidates = [
        seed.get("point"),
        seed.get("mechanism"),
        seed.get("claim"),
        seed.get("one_line"),
        seed.get("tldr"),
        seed.get("trigger"),
    ]
    for raw0 in candidates:
        raw = clean_ops(str(raw0 or ""))
        if not raw or looks_like_tag_salad(raw):
            continue
        parts = re.split(r"(?<=[.。?!])\s+|(?<=다\.)\s+|(?<=요\.)\s+|(?<=습니다\.)\s+|(?<=거든요\.)\s+", raw)
        parts = [re.sub(r"^[\s,.:;·/\-]+|[\s,.:;·/\-]+$", "", p).strip() for p in parts if p]
        try_list = parts or [raw]
        for t in try_list:
            if looks_like_tag_salad(t):
                continue
            if len(t) > 110:
                t = re.sub(r"\s+\S*$", "", t[:108]) + "…"
            if len(t) >= 16:
                return t
    return ""


def end_human(s: str) -> str:
    s = str(s or "").strip()
    if not s:
        return s
    if re.search(r"[다요임]$|[.。]$|습니다$|거든요$|봅니다$|생각합니다$", s):
        return s
    return f"{s}."


def who_label(seed: Mapping[str, Any]) -> str:
    nick = str(seed.get("nick") or "").strip()
    sid = str(seed.get("id") or "").strip()
    if nick and sid and nick != sid:
        return f"{nick}(id {sid})"
    return nick or sid or ""


def strip_quotes(s: str) -> str:
    return re.sub(r"^[\"'「『]|[\"'」』]$", "", s).strip()


def peer_body(mech: str, claim: str, anchor: str, point: str, seed: Mapping[str, Any]) -> str:
    who = who_label(seed)
    nick_only = str(seed.get("nick") or "").strip() or (who.split("(")[0] if who else "")
    m = end_human(mech)
    if who and nick_only and nick_only not in m:
        m = f"{who} 님 쪽 공개 글을 기준으로만 보면, {m}"
    c = strip_quotes(claim or point)
    mid = (
        f"그래서 {c}만 보고 단정까지는 잘 안 갑니다."
        if c
        else "그래서 겉으로 보이는 빈도만 보고 단정까지는 잘 안 갑니다."
    )
    if anchor:
        tail = "" if re.search(r"쪽|근거|원문|분포|공시|실적|가격", anchor) else " 쪽"
        a = f"판단은 {anchor}{tail}에 두는 편이 낫다고 봅니다."
    else:
        a = "판단은 확인 가능한 원문·날짜 쪽에 두는 편이 낫다고 봅니다."
    return "\n".join([m, "", mid, a, "전제 다른 부분 있으면 그 부분만 짚어 주시면 됩니다."])


def short_body(mech: str, claim: str, anchor: str, point: str) -> str:
    line1 = end_human(mech or point)
    c = strip_quotes(claim or point)
    line2 = f"그래서 {c}만 보고 단정까지는 잘 안 갑니다." if c else "단정까지는 잘 안 갑니다."
    if anchor:
        tail = "" if re.search(r"쪽|근거|원문", anchor) else " 쪽"
        line3 = f"판단은 {anchor}{tail}에 두는 편이 낫다고 봅니다."
    else:
        line3 = "판단은 확인 가능한 근거 쪽에 두는 편이 낫다고 봅니다."
    return "\n".join(x for x in (line1, line2, line3) if x)


def seed_from_analysis(analysis: Mapping[str, Any]) -> Dict[str, Any]:
    """Map analysis.json (+ community_post block) into a seed dict."""
    cp = analysis.get("community_post") if isinstance(analysis.get("community_post"), dict) else {}
    target = analysis.get("target") if isinstance(analysis.get("target"), dict) else {}
    trigger = analysis.get("trigger") if isinstance(analysis.get("trigger"), dict) else {}
    matrix = analysis.get("matrix") if isinstance(analysis.get("matrix"), dict) else {}

    seed: Dict[str, Any] = {
        "nick": cp.get("nick") or target.get("nick") or "",
        "id": cp.get("id") or target.get("id") or "",
        "platform": cp.get("platform") or (analysis.get("meta") or {}).get("platform") or "",
        "board": cp.get("board") or cp.get("board_hint") or "",
        "tldr": cp.get("tldr") or analysis.get("tldr") or "",
        "one_line": cp.get("one_line") or matrix.get("one_line") or "",
        "trigger": cp.get("trigger") or trigger.get("summary") or "",
        "recommendation": cp.get("recommendation") or analysis.get("recommendation") or "",
        "point": cp.get("point") or "",
        "claim": cp.get("claim") or "",
        "mechanism": cp.get("mechanism") or "",
        "anchor": cp.get("anchor") or "",
        "tone": cp.get("tone") or "peer",
        "preset": cp.get("preset") or cp.get("text_ko") or "",
        "preset_short": cp.get("preset_short") or cp.get("text_ko_short") or "",
        "quotes": cp.get("quotes") or [],
    }
    return seed


def generate_community_post(
    seed: Mapping[str, Any],
    tone_override: Optional[str] = None,
) -> str:
    """Optional export only. Empty/weak seed → refuse (no fake analysis tone)."""
    tone = normalize_tone(tone_override or seed.get("tone"))

    full_preset = humanize_preset(str(seed.get("preset") or ""))
    short_preset = humanize_preset(str(seed.get("preset_short") or ""))

    if tone == "board":
        if (
            full_preset
            and 24 <= len(full_preset) <= 8000
            and not looks_like_tag_salad(full_preset)
        ):
            return full_preset

    if tone == "short" and short_preset and len(short_preset) >= 16:
        return short_preset

    if full_preset and 24 <= len(full_preset) <= 8000 and not looks_like_tag_salad(full_preset):
        if tone == "short":
            paras = [p for p in re.split(r"\n\s*\n", full_preset) if p.strip()]
            if len(paras) >= 2:
                return "\n\n".join(paras[:2])
            lines = [ln for ln in full_preset.split("\n") if ln.strip()]
            return "\n".join(lines[:3])
        return full_preset

    mech = clean_ops(str(seed.get("mechanism") or ""))
    claim = clean_ops(str(seed.get("claim") or ""))
    anchor = clean_ops(str(seed.get("anchor") or ""))
    point = distill_point(seed)

    if mech and (claim or point):
        return (
            short_body(mech, claim, anchor, point)
            if tone == "short"
            else peer_body(mech, claim, anchor, point, seed)
        )

    if point and not looks_like_tag_salad(point):
        if tone == "short":
            return "\n".join(
                [end_human(point), "판단은 확인 가능한 근거 쪽에 두는 편이 낫다고 봅니다."]
            )
        return peer_body(point, "", anchor, point, seed)

    return REFUSE


def _main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Generate optional community draft from seed/analysis JSON")
    p.add_argument("-a", "--analysis", type=Path, help="analysis.json path")
    p.add_argument("-s", "--seed", type=Path, help="seed JSON path")
    p.add_argument("-t", "--tone", default=None, help="peer|short|board")
    p.add_argument("-o", "--out", type=Path, help="write text here")
    p.add_argument("--json-seed", help="inline seed JSON string")
    args = p.parse_args(argv)

    seed: Dict[str, Any] = {}
    if args.analysis:
        data = json.loads(args.analysis.read_text(encoding="utf-8"))
        seed = seed_from_analysis(data)
    if args.seed:
        seed.update(json.loads(args.seed.read_text(encoding="utf-8")))
    if args.json_seed:
        seed.update(json.loads(args.json_seed))
    if not seed:
        print("need --analysis, --seed, or --json-seed", file=sys.stderr)
        return 2

    text = generate_community_post(seed, args.tone)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
    return 0 if not text.startswith("[게시 초안 생성 불가]") else 1


if __name__ == "__main__":
    raise SystemExit(_main())
