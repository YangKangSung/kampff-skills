---
name: kampff
description: >-
  Human analysis from published text traces — worldview, alliance fit, temporal
  drift, distance (engage/neutral/caution/avoid). Community-member pipeline:
  collect posts/comments/likes honesty triad → bundle.json → spectrograph L1–L5
  + default MBTI (fun) + CIA/KGB-style public tradecraft persona report.
  Triggers: /kampff, kampff, 사람 분석, 인물 분석, person analysis, community member,
  distance scoring, MBTI, CIA/KGB profile, mail/meeting/chat/sns/github.
  Analyze reads bundle only; collect is a separate lawful step. No stalking.
---

# Kampff

Turn **text someone already published** into a **distance decision** — with optional community collect.

| Layer | Responsibility |
|-------|----------------|
| **Collect** | Lawful public/session surfaces → raw + `bundle.json` |
| **Analyze** | Read `bundle.json` only — no invented scrape mid-analysis |
| **Report** | Matrix + L1–L5; community default adds MBTI + tradecraft persona |

**Data root:** env `KAMPFF_DATA` (default `./kampff-data`).

Spelling: skill name **`kampff`**. Repo may be named `kampff-skills`.

### Typo recognition

| Typed | Treat as |
|-------|----------|
| `kapsmff` / `kaffsm` / `kampsm` / `kamff` / `kampf` / `kampoff` | kampff |
| 사람 분석 / 인물 분석 | this skill |

## Philosophy (generic)

- Goal language: **distance + engage cost**, not therapy or persuasion playbook.
- Viewer is in the pool — same protocol for self-dossier.
- Ego/flex/stress patterns → `caution` / `avoid` without moralizing the operator.
- Refuse: stalking, covert surveillance, illegal collection, “destroy coworker” weaponization.

## Community member pipeline (general feature)

Full steps: `references/community-member-pipeline.md`  
Report shape: `references/report-template.md`

```text
/kampff member {platform} {id|nick|url}
/kampff analyze {path}/bundle.json
/kampff today
```

| Step | Do |
|------|-----|
| 1 Scope | target ≠ viewer; platform; optional trigger thread |
| 2 Collect | lawful surfaces; agent-owned browser profile if login needed |
| 3 Honesty | posts / comments / likes triad → honesty file |
| 4 Bundle | `{KAMPFF_DATA}/inbox/{date}/bundle.json` |
| 5 Analyze | L1–L5 always |
| 6 Lenses | **MBTI + CIA/KGB tradecraft ON by default for community** |
| 7 Report | `{KAMPFF_DATA}/out/{date}-report.md` (+ optional `.html` with graphs) |
| 8 Handoff | open cross-check prompts; do not invent the operator’s gut read |

**Default lenses**

| Context | MBTI | CIA/KGB persona |
|---------|------|-----------------|
| Community member | **ON** | **ON** |
| Workplace mail/meeting batch | off unless asked | off unless asked |
| Operator: skip lenses | off | off |

**Demo samples (public repo only — synthetic):**

| File | Role |
|------|------|
| `docs/sample-community-report.html` | Front-door visual (graphs, force layout) |
| `docs/sample-community-report.md` | Full community dossier template filled with fiction |
| `docs/sample-output.md` | Short workplace matrix |

Never replace samples with real third-party profiling. Real runs write under `$KAMPFF_DATA` outside the git root.

## Collection honesty (mandatory for community)

Always report:

| surface | site/profile claimed | collected | full? |
|---------|----------------------|-----------|-------|
| posts | … | … | Y/N |
| comments | … | … | Y/N |
| likes/reactions | … | … | Y/N |

Rules: answer completeness from **artifacts**, not intent. Tab labels in HTML ≠ collected. Platform caps (e.g. “recent only” APIs) → mark `full? = NO (platform cap)`.

Details: `references/collection-honesty.md`.

## Smoke path

| Rank | Source | Why |
|------|--------|-----|
| 1 | Public GitHub (`gh`) | often already auth’d |
| 2 | RSS / public feeds | no auth |
| 3 | sample-input | dry-run |
| later | community boards / X / etc. | tokens + login |

Self-dossier smoke: `viewer_id: me` = same person as collector login.

## Usage

```text
/kampff collect --targets {path}/targets.json   # if collector wired
/kampff analyze {path}/bundle.json
/kampff today
/kampff person {id} --bundle {path}
```

### bundle.json (minimal)

```json
{
  "context": "workplace|community|mixed",
  "viewer_id": "me",
  "batch_date": "YYYY-MM-DD",
  "analysis_lenses": ["personal", "mbti", "cia_sat"],
  "people": [
    {
      "id": "me",
      "texts": [
        {
          "content": "...",
          "timestamp": "ISO8601",
          "source": "community_post"
        }
      ]
    }
  ],
  "meta": { "language": "en", "timezone": "UTC" }
}
```

`viewer_id` must appear in `people[]`. Every text needs `timestamp` + `source`.

Sources: `mail` · `meeting` · `chat` · `messenger` · `community_post` · `community_comment` · `community_like` · `sns_post` · `sns_comment`

## spectrograph (order)

1. **L1 Psych** — Big Five lean, conflict style; quote evidence  
2. **L2 Worldview** — axes + distance to viewer  
3. **L3 Behavioral** — patterns + stability; never “innately evil”  
4. **L4 Alliance** — trust / reciprocity / go-together  
5. **L5 Ephemeris** — time buckets, drift  
6. **L6 HR** — only if requested  
7. **L7 OSINT** — only if requested; lawful only  

**MBTI** — `references/lenses-mbti.md` (default community ON)  
**CIA/KGB-style tradecraft** — `references/lenses-cia-sat.md` (public analytic hygiene only)

## Distance scale

| Tag | Meaning |
|-----|---------|
| `engage` | Worth time / needed interaction |
| `neutral` | Low signal or transactional |
| `caution` | Ego/flex/stress patterns; limit surface |
| `avoid` | Chronic stress cost; cut preferred |

## Hard rules

- Not medical diagnosis or legal judgment  
- Inference → quote or `low-confidence`  
- Viewer gets same scrutiny  
- No scrape inside analyze; collect is separate and lawful  
- MBTI never sole `avoid`; tradecraft never illegal ops  
- **Public skill repo:** only synthetic samples; never commit real member dossiers, private purpose notes, or host-only paths  
- Prefer **English** for shared sample reports; operator language OK for private chat  

## HTML report (optional visual)

When the operator wants graphs (radar, timeline, force graph, honesty bars):

1. Follow `report-template.md` content in English for public-facing demos  
2. Emit `{KAMPFF_DATA}/out/{date}-report.html` (local data dir)  
3. Use **synthetic** names in anything that might be committed to a public tree  
4. Shape reference: `docs/sample-community-report.html`  

## Support files

- `references/community-member-pipeline.md`
- `references/report-template.md`
- `references/collection-honesty.md`
- `references/community-public-collect.md`
- `references/platform-login-harvest.md`
- `references/lenses-mbti.md`
- `references/lenses-cia-sat.md`
- `references/github-smoke.md`
- Repo demos: `docs/sample-community-report.{md,html}` · `docs/sample-output.md`
- `scripts/` — optional collectors

## License

MIT (see repo LICENSE). Keep third-party NOTICE when vendoring collectors.
