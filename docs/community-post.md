# Community post (optional draft export)

**Dossier ≠ board post.** This is a **select export** only.

Parity with:

| Source | Role |
|--------|------|
| ``communityPost.ts` (private VS Code UI)` | VS Code generator |
| Internal tone law notes | peer / short / board voice |
| `scripts/render_kampff_report.py` § CP JS | HTML report UI |

CLI / library: **`scripts/community_post.py`**

## Tone keys

| value | When | Length |
|-------|------|--------|
| `peer` | **default** — your own account, peer voice | 3 short paras / 4–6 lines |
| `short` | comment-sized | 2–3 lines |
| `board` | use prepared `text_ko` / `preset` as-is | seed length |

Private performance tones (`/pangyo`, `/wuxia`, …) are **not** used here.

## Skeleton (peer / short)

1. **mechanism** — why it can look that way (public pattern only)
2. **no overclaim** — weak signals alone ≠ org/trading/theft verdict
3. **anchor** — judgment stays on checkable original text / date / filings

Endings: **합니다 / 봅니다 / 생각합니다.**

## Forbidden in body

- ops tags: caution, avoid, engage, distance, L1–L5, MBTI, ACH, clinical, CONFIRMED…
- meta: 표본, 수집, 분석 결과, 리포트, dossier, harvest, matrix
- tag salad only (`park/kin/공유형…`)
- AI meta: 「이 한 줄은…」「다음과 같습니다」「결론적으로」
- Long 안녕하세요/감사합니다 openers
- Fake semiconductor filler when seed has none

## Empty seed → refuse

If there is no usable mechanism/claim/point/preset, generators return a **refuse** string and must **not** invent a draft. Same rule as VS Code.

## analysis.json seed

```json
"community_post": {
  "board": "park",
  "tone": "peer",
  "mechanism": "…",
  "claim": "…",
  "anchor": "…",
  "point": "…",
  "text_ko": "board/peer body",
  "text_ko_short": "short option",
  "preset": "alias of text_ko",
  "preset_short": "alias of text_ko_short"
}
```

## CLI

```bash
# from seed JSON
python scripts/community_post.py --json-seed '{"mechanism":"…","claim":"…","anchor":"원문 날짜","nick":"relay","id":"r1"}' -t peer

# from analysis.json
python scripts/community_post.py -a kampff-data/out/2026-07-01-relay-analysis.json -t short -o /tmp/draft.txt
```

Exit code `1` if refuse text; `0` if draft produced.

## Related

- [dual-store-wiki.md](dual-store-wiki.md)
- [vscode-bridge.md](vscode-bridge.md)
- [report-analysis.schema.md](report-analysis.schema.md)
