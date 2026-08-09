# Dual store: dataRoot vs wikiRoot

Product model shared with the optional **Kampff VS Code** extension (`wikiStore`, dual-path settings), with CLI helpers in this repo.

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
export KAMPFF_DATA="${KAMPFF_DATA:-$PWD/kampff-data}"
export KAMPFF_WIKI="${KAMPFF_WIKI:-$PWD/wiki}"   # optional durable shelf

python scripts/wiki_store.py init-wiki --wiki "$KAMPFF_WIKI"

python scripts/wiki_store.py prior --id member_id --platform reddit --prompt

python scripts/wiki_store.py promote \
  --id member_id --platform reddit \
  -a "$KAMPFF_DATA/out/YYYY-MM-DD-member_id-analysis.json" \
  -r "$KAMPFF_DATA/out/YYYY-MM-DD-member_id-report.html"
```

## Do not

| Don't | Why |
|-------|-----|
| Commit real `people/` or `out/` dumps into git | PII / forever history |
| Treat `out/` as SoT | scratch only |
| Skip prior merge on re-analyze | loses continuity |

## Related

- [vscode-bridge.md](vscode-bridge.md)
- [RUN-INPUT.md](RUN-INPUT.md)
