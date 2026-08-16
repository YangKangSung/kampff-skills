# Report language

Default language for Kampff product reports is **English**.

HTML is dual-track (`--track both`). Korean is an **optional** second panel, not the first screen.

| Track | Language | Who for |
|-------|----------|---------|
| **English** (`pro`) | EN | default; graphs, matrix, L1–L5, MBTI, CIA/ACH |
| **한국어** (`easy`) | KO | optional; distance in plain Korean, no new facts |

## Generate

```bash
# default: one HTML, English open, 한국어 toggle
python scripts/render_kampff_report.py \
  -a kampff-data/out/DATE-ID-analysis.json \
  -o kampff-data/out/DATE-ID-report.html

# English only
python scripts/render_kampff_report.py -a … -o … --track pro

# Korean-only file
python scripts/render_kampff_report.py -a … -o …-ko.html --track easy
```

## UX

- Top **LANG** buttons: English | 한국어
- Stored in `localStorage` (`kampff-report-track`)
- First visit: **English** unless Settings → Kampff → Language is `한국어` or `auto` and the editor locale is `ko*`
- Hash `#ko` / `#easy` or `#en` / `#pro` still overrides
- Community-post export stays on the English track

## Rules

- Analysis JSON + markdown reports: **English**
- Korean track must not invent facts
- Public text only · not medical/legal
