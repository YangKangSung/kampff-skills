# Report template (community default)

## Deliverables

| Priority | Path | Role |
|----------|------|------|
| **1 · default** | `{KAMPFF_DATA}/out/{date}-report.html` | Operator-facing dossier (graphs, pills, debate) |
| 2 · twin | `{KAMPFF_DATA}/out/{date}-report.md` | Source/diff/archive (optional but recommended) |
| 3 · debate | `{KAMPFF_DATA}/out/{date}-debate-ref.md` | When thread comments collected — **major ref** |

Skin: `docs/sample-community-report.html`  
Name infix OK: `{date}-{target_id}-report.html`

**HTML is default.** Do not stop at markdown-only for community runs.

---

## Content order (md twin and HTML sections)

Same section order in both formats.

### Header

```markdown
# Kampff report — {date} ({platform} / {target_id})

**Source:** bundle path  
**Protocol:** L1–L5 · lenses: personal + mbti + cia_sat  
**Viewer:** …  
**Target:** nick · member id · meta  
**Trigger:** optional thread URLs  
**N texts:** posts / comments / likes (claimed vs collected)
```

HTML: hero + meta chips + **distance banner** (pill: engage · neutral · caution · avoid).

### §0 Collection honesty

Mandatory triad table when community collect ran.

### §1 Matrix + distance

Columns: `id | worldview_fit | alliance_fit | stability | drift | risk | one_line`  
Distance tags: engage · neutral · caution · avoid

### §2 Identity

What they **do** (operator vs reviewer vs flex). Quote-backed.

### §3 Trigger / Debate

- Trigger interaction if any (viewer vs target thread).  
- **Debate ref** when other-comments exist: stats, hot threads, quote samples, move mix.  
  Link full `{date}-debate-ref.md`. Debate is first-class, not flavor.

### §4 spectrograph L1–L5

Always. L6/L7 only if requested.

### §5 Distance ops

Engage-cost table + one-line recommendation.

### §6 MBTI (fun · low validity)

Default ON for community. See `lenses-mbti.md`.

### §7 CIA / KGB-style tradecraft persona

Default ON for community. Public analytic hygiene only. See `lenses-cia-sat.md`.

T1–T7 + optional dossier card:

```
SUBJECT / ALIASES
BIO LINE
CHARACTER
STRENGTHS
PRESSURE POINTS (engage-cost for operator)
APPROACH / AVOID channels
ASSESSMENT (distance + confidence)
```

### §8 Cross-check prompts

3–4 open questions; do not fill the operator’s private read.

### §9 Files

Paths to bundle, honesty, raw, **html**, md twin, debate ref.

### Footer

Not medical/legal. MBTI entertainment. Tradecraft = public form only. Lawful sources only.

---

## HTML requirements (minimum)

| Element | Required |
|---------|----------|
| Dark sample skin (or equivalent) | yes |
| Distance pill banner | yes |
| Honesty table | yes |
| Matrix + distance map | yes |
| L1–L5 sections | yes |
| MBTI + CIA/dossier | yes (community default) |
| Graphs (drivers / completeness / optional force) | yes when data allows |
| Debate block | yes if comments/others collected |
| Openable local file under `$KAMPFF_DATA/out/` | yes |

Generator pattern (this repo runs): reuse CSS from `docs/sample-community-report.html`, fill live stats from `bundle.json` + debate ref.
