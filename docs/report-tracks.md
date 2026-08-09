# Report tracks: pro + easy

HTML reports are **dual-track** by default (`--track both`).

| Track | Who for | Content |
|-------|---------|---------|
| **쉬운 말** (`easy`) | 빠른 판단, 비분석 독자 | 거리 뜻, 해도/피하기, 상황표, 수집 한계, 인용 몇 개 |
| **전문 분석** (`pro`) | 분석가 | graphs, matrix, L1–L5, MBTI, clinical, CIA/ACH, honesty… |

## Generate

```bash
# default: one HTML, top toggle (쉬운 말 | 전문 분석)
python scripts/render_kampff_report.py \
  -a kampff-data/out/DATE-ID-analysis.json \
  -o kampff-data/out/DATE-ID-report.html

# pro only (legacy single track)
python scripts/render_kampff_report.py -a … -o … --track pro

# easy only file
python scripts/render_kampff_report.py -a … -o …-easy.html --track easy

# wrap an already-built pro HTML
python scripts/kampff_report_easy.py -a … --wrap-pro path/to-report.html
```

## UX

- Top **TRACK** buttons; choice stored in `localStorage` (`kampff-report-track`).
- Default open: **쉬운 말** (first visit). Hash `#pro` / `#easy` overrides.
- Community-post export stays on the **pro** track only.

## Rules

- Easy track **must not invent** facts: only simplify distance/reco/identity/quotes from analysis.json.
- Jargon (ACH, L1–L5, harvest…) stripped or moved to “전문 분석”.
- Still: public text only · not medical/legal.
