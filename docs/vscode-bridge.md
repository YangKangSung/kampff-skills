# VS Code extension ↔ skills-dev bridge

Local UI: **`D:\prjs\kampff-vscode`** (private extension `ksyang.kampff`, v0.9.x).  
Skills SoT: **this repo** (`kampff-skills-dev`).

The extension does **not** re-implement L1–L5 analysis. It queues jobs, calls Hermes, and runs **this** tree’s scripts.

## Path settings (extension)

| Setting | Points at |
|---------|-----------|
| `kampff.skillsDevRoot` | this repo root |
| `kampff.dataRoot` | runtime `KAMPFF_DATA` (e.g. `…/kampff-data`) |
| `kampff.wikiRoot` | durable wiki shelf |
| `kampff.pythonPath` | python that can run `scripts/` |
| `kampff.hermesCommand` | hermes.exe (optional auto-detect) |
| `kampff.sites` | registerable site rows (secrets in SecretStorage) |

## Scripts the extension calls

| Action | Script / module |
|--------|------------------|
| Render HTML | `scripts/render_kampff_report.py -a … -o …` |
| Community draft (UI may use TS twin) | `scripts/community_post.py` (Python SoT for CLI) |
| Prior / promote | `scripts/wiki_store.py` |
| Job orchestration | `scripts/run_kampff_job.py` (when used) |

TS mirrors (extension-only):

- `src/communityPost.ts` ↔ `scripts/community_post.py`
- `src/wikiStore.ts` ↔ `scripts/wiki_store.py`
- `src/renderReport.ts` → spawns `render_kampff_report.py`
- `src/sites.ts` → settings schema; see `docs/sites.schema.json`

When you change draft tone or dual-store rules, update **both** sides or at least the skills-dev Python + docs, then bump the extension.

## What stays in the extension only

- Webview Analyze UI, job live activity, SecretStorage passwords
- VS Code tree views (People / Reports / Inbox)
- Dev live-reload (`npm run dev`)

Do **not** copy `media/**`, `src/extension.ts`, or `.vsix` into this repo.

## Sites (registerable)

Default kind:

| kind | Meaning |
|------|---------|
| `clien` | 4-axis member harvest path |
| `generic` | URL-first site |

Schema: [sites.schema.json](sites.schema.json) · example: [sites-default.json](sites-default.json)

Passwords never live in JSON — only `hasPassword` flags + SecretStorage keys in the extension.

## Dev loop (two folders)

```bash
# skills product
cd ~/kampff-skills
# … edit scripts/docs …

# UI
cd /d/prjs/kampff-vscode
npm run compile   # or npm run dev
```

Point `kampff.skillsDevRoot` at the skills-dev path you edited, then Reload Window.

## Related

- [dual-store-wiki.md](dual-store-wiki.md)
- [community-post.md](community-post.md)
- [LOCAL_DEV.md](LOCAL_DEV.md)
- [DEV_RELEASE_WORKFLOW.md](DEV_RELEASE_WORKFLOW.md)
