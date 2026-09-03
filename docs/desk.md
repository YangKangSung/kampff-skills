# Distance Desk

Paper-test **one person's** distance call. Not a board map. Not a crowd graph.

```text
you (center)  →  rings: engage · neutral · caution · avoid  →  this person
quotes        →  mute  →  confidence drops; lead H can flip
situation     →  node moves (same person, different cost)
L5 slider     →  where the call sat at that time
```

The distance **tag does not auto-rewrite** when you mute. You decide. The desk only shows that the call is now vibe, soft, or rival-led.

## Render

```bash
python scripts/render_kampff_desk.py -a docs/sample-analysis.json -o docs/sample-desk.html

# or with the dossier (writes sibling *-desk.html unless --no-desk)
python scripts/render_kampff_report.py -a docs/sample-analysis.json -o docs/sample-community-report.html
```

Job pipeline (`run_kampff_job.py`) uses the report renderer, so a desk file appears next to `*-report.html`.

## Skill

```text
/kampff desk path/to/analysis.json
```

After analyze, write `{KAMPFF_DATA}/out/{date}-{id}-desk.html` and open it **before** arguing the long dossier.

## Schema (optional `desk` on analysis.json)

If omitted, the desk infers from `distance_ops`, `timeline`, `quotes`, `ach`.

| Field | Role |
|-------|------|
| `desk.synthetic` | demo flag |
| `desk.viewer_fit.big5` | overlay radar (viewer in the pool) |
| `desk.history[]` | `{t,label,distance}` for the L5 slider |
| `desk.claims[]` | ACH rows with `quote_ids` — mute math |
| `quotes[].supports` | claim ids a quote holds up |

## Anti-goal

Do **not** put third-party edges / ego-nets / cohort maps on this page. That stays `docs/lab/` (Layer 2 practice). Kampff product unit is **one person + distance**.
