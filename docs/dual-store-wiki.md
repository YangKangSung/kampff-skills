# Dual store: dataRoot vs wikiRoot

Product model from **Kampff VS Code 0.8.3+** (`wikiStore.ts`, dual-path settings), now documented + CLI-backed in skills-dev.

## Two roots

| Root | Env / setting | Holds | Role |
|------|----------------|--------|------|
| **dataRoot** | `KAMPFF_DATA` · VS Code `kampff.dataRoot` | `inbox/`, `queue/`, `out/` | harvest + job poll + scratch HTML/JSON |
| **wikiRoot** | `KAMPFF_WIKI` · VS Code `kampff.wikiRoot` | `people/`, `reports/`, `Index.md` | durable LLM Wiki shelf |

```
harvest → dataRoot/inbox
job run → dataRoot/queue + dataRoot/out/{date}-{id}-*
promote → wikiRoot/reports + wikiRoot/people/{platform}/{id}/
re-analyze → PRIOR EVIDENCE merge from people + wiki reports + out
```

## people/

```
{wikiRoot}/people/{platform}/{id}/
  NOTES.md
  profile.json
  history.json
  LATEST.json          # pointer written on promote
  *-analysis.json      # optional copies
  *-report.html
```

Optional override: VS Code `kampff.peopleRoot` (default = `{wikiRoot}/people`).

## Prior merge order (VS Code + `wiki_store.py prior`)

1. `{peopleRoot}/{platform}/{id}/`
2. `{wikiRoot}/reports/*` name-matched to id/nick
3. `{dataRoot}/out/*` name-matched

Newest first. Extension injects paths into Hermes prompt as **PRIOR EVIDENCE (merge)**.

## Promote (on job success)

Copy analysis + report into:

- `{wikiRoot}/reports/`
- `{peopleRoot}/{platform}/{id}/` (+ `LATEST.json`)
- append one line to `{wikiRoot}/Index.md`

## CLI (`scripts/wiki_store.py`)

```bash
export KAMPFF_DATA="~/kampff-skills/kampff-data"
export KAMPFF_WIKI="~/kampff-wiki"   # example shelf

python scripts/wiki_store.py init-wiki --wiki "$KAMPFF_WIKI"

python scripts/wiki_store.py prior --id member_id --platform clien --prompt

python scripts/wiki_store.py promote \
  --id member_id --platform clien \
  -a kampff-data/out/2026-08-08-member_id-analysis.json \
  -r kampff-data/out/2026-08-08-member_id-report.html
```

## Do not

| Don't | Why |
|-------|-----|
| Commit real `people/` or `out/` dumps into git | PII / forever history |
| Treat `out/` as SoT | scratch only |
| Skip prior merge on re-analyze | loses continuity |

## Related

- [vscode-bridge.md](vscode-bridge.md)
- [LOCAL_DEV.md](LOCAL_DEV.md)
- [RUN-INPUT.md](RUN-INPUT.md)
