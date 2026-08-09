# report analysis.json (for HTML renderer)

Pass to `scripts/render_kampff_report.py --analysis …`.

```json
{
  "meta": { "date": "YYYY-MM-DD", "platform": "clien|damoang|…", "language": "ko", "protocol": "L1–L5 · MBTI · CIA-SAT" },
  "target": { "id": "member_id", "nick": "display" },
  "viewer": { "id": "me" },
  "distance": "engage|neutral|caution|avoid",
  "confidence": "low|medium|high",
  "confidence_score": 0-100,
  "tldr": "one paragraph for hero",
  "recommendation": "ops line",
  "corpus": { "posts": 0, "comments": 0, "likes": "n/a"|0 },
  "honesty": {
    "posts_pct": 0-100, "comments_pct": 0-100, "likes_pct": null|0-100,
    "posts_status": "", "comments_status": "", "likes_status": "n/a",
    "posts_note": "", "comments_note": "", "likes_note": "", "note": ""
  },
  "matrix": {
    "worldview_fit": "", "alliance_fit": "", "stability": "", "drift": "", "risk": "", "one_line": "",
    "worldview_score": 0-100, "alliance_score": 0-100, "stability_score": 0-100, "risk_score": 0-100
  },
  "big5": { "O": 0-100, "C": 0-100, "E": 0-100, "A": 0-100, "N": 0-100 },
  "identity": { "bullets": ["…"], "not_seen": "" },
  "trigger": { "url": "", "summary": "" },
  "spectrograph": { "L1": "", "L2": "", "L3": "", "L4": "", "L5": "" },
  "timeline": [{ "t": "label", "label": "event", "color": "#hex", "note": "" }],
  "distance_ops": [{ "tag": "neutral", "when": "…" }],
  "alliance_bars": [["label", 0-100, "teal|sky|amber|rose|violet"]],
  "mbti": {
    "type": "INTJ",
    "leans": { "E": 0-100, "I": 0-100, "S": 0-100, "N": 0-100, "T": 0-100, "F": 0-100, "J": 0-100, "P": 0-100 },
    "engage_cost": "", "confidence": "low"
  },
  "drivers": { "resource": 0-3, "control": 0-3, "status": 0-3, "belonging": 0-3, "autonomy": 0-3 },
  "ach": [{ "id": "H1", "label": "", "status": "lead|weak|fail", "score": 0-100 }],
  "cia": { "drivers": {}, "ach": [], "card": "SUBJECT … plain text dossier" },
  "quotes": [{ "label": "POST|CMT", "timestamp": "", "text": "" }],
  "cross_check": ["…"],
  "files": { "bundle": "", "html": "" },
  "source_mix": null
}
```

**Render**

```bash
python scripts/render_kampff_report.py \
  -a kampff-data/out/{date}-{id}-analysis.json \
  -b kampff-data/inbox/{date}/bundle.json \
  -o kampff-data/out/{date}-{id}-report.html
```

HTML is the **default** operator deliverable. Markdown twin optional.
