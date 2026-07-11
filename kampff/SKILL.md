---
name: kampff
description: >
  Human analysis from text traces — worldview, alliance fit, temporal drift,
  and distance recommendation. Uses the spectrograph 7-layer protocol. Viewer
  included in the analysis pool. Reads bundle.json or daily inbox paths; no
  scraping. Triggers: /kampff, kampff today, analyze people from mail meeting
  chat messenger community sns posts comments.
---

# Kampff

Analyze people from text they already published. **Collection is out of scope** — read normalized files only.

## Usage

### 0 — URL targets (collection, separate script)

User provides `targets.json` (URL + person search). Collector fetches posts/comments → `bundle.json`.  
Spec: [docs/collection-targets.md](../docs/collection-targets.md) · enterprise: [docs/collectors.md](../docs/collectors.md) (Playwright, Confluence, Jira, GitHub)

```text
/kampff collect --targets {path}/targets.json   # collector, not analysis
/kampff analyze {path}/bundle.json
```

### A — File path

User provides a bundle file:

```text
/kampff analyze {path}/bundle.json
```

Read that JSON, run spectrograph, write report to `{KAMPFF_DATA}/out/{batch_date or today}-report.md`.

### B — Today's inbox (daily drops)

```text
/kampff today
```

1. Resolve data root: env `KAMPFF_DATA`, else `./kampff-data`
2. Read `{root}/inbox/{YYYY-MM-DD}/bundle.json`
3. If missing: read `{root}/inbox/{YYYY-MM-DD}/raw/**` only as fallback; prefer asking user to run collector
4. Optionally merge `{root}/people/*/history.json` for ephemeris depth
5. Output `{root}/out/{YYYY-MM-DD}-report.md`

### C — Single person refresh

```text
/kampff person {id} --bundle {path}
```

Merge bundle with `{root}/people/{id}/history.json` if present; emphasize L5 ephemeris + fit with viewer.

## Supported sources (in bundle `texts[].source`)

`mail` · `meeting` · `chat` · `messenger` · `community_post` · `community_comment` · `sns_post` · `sns_comment`

Optional: `platform` = `x` | `facebook` | `instagram` | `reddit` | `linkedin` | `community`  
Optional: `url` (permalink), `collected_from` (scope URL), `type` = `post` | `comment` | `reply` | ...

Full layout: [docs/usage.md](../docs/usage.md) · schema: [docs/input-schema.md](../docs/input-schema.md)

## Input (bundle.json)

```json
{
  "context": "workplace|community|mixed",
  "viewer_id": "me",
  "batch_date": "2026-07-11",
  "analysis_lenses": ["personal", "hr", "osint"],
  "people": [
    {
      "id": "me",
      "texts": [
        {
          "content": "...",
          "timestamp": "ISO8601",
          "source": "mail|meeting|chat|messenger|community_post|community_comment|sns_post|sns_comment"
        }
      ]
    }
  ],
  "meta": { "language": "ko", "timezone": "Asia/Seoul" }
}
```

**Rules:** `viewer_id` must appear in `people[]`. Every text needs `timestamp` + `source`.

## When to use

- Daily batch after collector drops mail, meetings, chat, messenger, community, SNS
- Worldview / alliance / distance vs viewer
- HR or OSINT lenses when user lists them in `analysis_lenses`

## spectrograph protocol (execute in order)

### L1 — Psych
Big Five tendencies, conflict style, attachment signals, defenses. Quote evidence.

### L2 — Worldview
Axes: authority↔liberty, individual↔collective, sacred↔secular discourse, pragmatic↔idealistic argument. Map distance to **viewer**.

### L3 — Behavioral signature
Harm patterns; **stability** (chronic vs situational). Never label "innately evil."

### L4 — Alliance
Trust, reciprocity, conflict recovery. Go together?

### L5 — Ephemeris
Time buckets, drift, turning points — use timestamps across all `source` types.

### L6 — HR lens (if requested)
Team fit, escalation risk. Not sole hiring verdict.

### L7 — OSINT lens (if requested)
Narrative consistency, position shifts. Lawful sources only.

## Output

1. Write `{KAMPFF_DATA}/out/{date}-report.md` with matrix + per-person dossier
2. Per person: summary, worldview map, ephemeris, fit with viewer, distance (`engage`|`neutral`|`caution`|`avoid`), confidence
3. Matrix columns: `id | worldview_fit | alliance_fit | stability | drift | risk | one_line`

## Hard rules

- Not medical diagnosis or legal judgment
- Every inference tied to a quote or marked low-confidence
- Viewer gets the same scrutiny as everyone else
- Refuse stalking, harassment, or covert surveillance use cases
- Do not scrape; only read user-specified files and paths