---
name: kampff
description: >
  Human analysis from text traces — worldview, alliance fit, temporal drift,
  and distance recommendation. Uses the spectrograph 7-layer protocol. Viewer
  included in the analysis pool. No scraping; analysis only. Use for /kampff,
  profile person from posts, worldview fit, workplace board, community comments,
  team fit assist, narrative consistency on open text.
---

# Kampff

Analyze people from text they already published. Collection is out of scope — pass structured bundles only.

## When to use

- Community or workplace board: who fits, who to avoid, why they act that way
- Worldview alignment: politics, ideology, religion, philosophy signals
- Temporal change: drift and turning points over months/years
- Optional lenses: `personal`, `hr`, `osint`

## Input

```json
{
  "context": "community|workplace|mixed",
  "viewer_id": "me",
  "protocol": "spectrograph",
  "analysis_lenses": ["personal", "hr", "osint"],
  "people": [
    {
      "id": "me",
      "texts": [
        { "content": "...", "timestamp": "ISO8601", "type": "post|comment|reply" }
      ]
    }
  ],
  "meta": { "language": "ko" }
}
```

## spectrograph protocol (execute in order)

### L1 — Psych
Big Five tendencies, conflict style, attachment signals, defenses. Quote evidence.

### L2 — Worldview
Axes: authority↔liberty, individual↔collective, sacred↔secular discourse, pragmatic↔idealistic argument. Map distance to **viewer**. No stereotype from demographics.

### L3 — Behavioral signature
Harm patterns: aggression, manipulation, triangulation, broken commitments. Score **stability** (chronic vs situational). Never label "innately evil."

### L4 — Alliance
Trust, reciprocity, conflict recovery, power dynamics. Answer: go together?

### L5 — Ephemeris
Time buckets, drift, turning points with dates and quotes.

### L6 — HR lens (if requested)
Team fit, escalation risk. **Not** sole hiring verdict. No adverse action from religion/politics/gender inference.

### L7 — OSINT lens (if requested)
Narrative consistency, rapid position shifts, influence cues. Lawful, consented sources only.

## Output per person

1. Executive summary (3 sentences)
2. Psych + worldview map + behavioral stability
3. Ephemeris timeline
4. Fit with viewer (worldview, alliance, trust)
5. Distance: `engage` | `neutral` | `caution` | `avoid`
6. Confidence and sample-size warnings

## Matrix (all people)

| id | worldview_fit | alliance_fit | stability | drift | risk | one_line |

## Hard rules

- Not medical diagnosis or legal judgment
- Every inference tied to a quote or marked low-confidence
- Viewer gets the same scrutiny as everyone else
- Refuse stalking, harassment, or covert surveillance use cases

See [docs/spectrograph.md](../docs/spectrograph.md).