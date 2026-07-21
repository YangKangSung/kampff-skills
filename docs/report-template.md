# Report template (community default)

## Deliverables

| Priority | Path | Role |
|----------|------|------|
| **1 · default** | `{KAMPFF_DATA}/out/{date}-{id}-report.html` | Operator dossier (graphs, pills, honesty) |
| 2 · analysis | `{KAMPFF_DATA}/out/{date}-{id}-analysis.json` | Structured input to renderer |
| 3 · twin | `{KAMPFF_DATA}/out/{date}-{id}-report.md` | Optional git/diff |
| 4 · debate | `{KAMPFF_DATA}/out/{date}-debate-ref.md` | When thread comments collected |

**HTML is default.** Do not stop at markdown-only for community runs.

## Render pipeline (required)

1. Write **analysis.json** (see `docs/report-analysis.schema.md`)
2. Run renderer:

```bash
python scripts/render_kampff_report.py \
  -a {KAMPFF_DATA}/out/{date}-{id}-analysis.json \
  -b {KAMPFF_DATA}/inbox/{date}/bundle.json \
  -o {KAMPFF_DATA}/out/{date}-{id}-report.html
```

3. Open HTML for operator. Optional md twin from same analysis.

Graphs included automatically: drivers radar · MBTI radar · Big Five bars · defense levels · confidence gauge · honesty triad · ACH · source donut · alliance bars · L5 timeline · distance map · fit snapshot.

## Content order (analysis fields → HTML sections)

### Header / TL;DR
`tldr`, `distance`, `confidence_score`, corpus chips, MBTI type, ACH lead

### §G Visual summary
Auto from scores in analysis.json

### §0 Collection honesty
`honesty.*` triad — mandatory when community collect ran

### §1 Matrix + distance ops
`matrix` + `distance_ops`

### §2 Identity
`identity.bullets`

### §3 Trigger / Debate
`trigger` when present; debate ref when comments/others collected

### §4 spectrograph L1–L5
`spectrograph.L1` … `L5` always

### §5 Distance ops
merged into §1 in HTML; keep explicit in md twin

### §6 MBTI (fun · low validity)
`mbti` — default ON community

### §6b Clinical / psychologist (비진단 · formulation)
`clinical_psych` — default ON community; see `docs/lenses-clinical-psych.md`  
**Not DSM/ICD.** Defenses · affect · attachment signals · interpersonal script · C-hypotheses.

### §7 CIA / KGB-style card
`cia.card` + drivers + ACH — default ON community

### §8 Cross-check prompts
`cross_check` 3–4 open questions

### §9 Files
`files` paths

### Footer
Not medical/legal. MBTI entertainment. Clinical_psych = public-text formulation only. Tradecraft public form only.

## Distance tags

`engage` · `neutral` · `caution` · `avoid`

## UX rules

- Sticky TOC · hero distance banner · TL;DR above fold
- Offline-first (pure SVG/CSS — no CDN)
- Print-friendly CSS included
- Public demos: synthetic names only (`docs/sample-analysis.json` → `sample-community-report.html`)
