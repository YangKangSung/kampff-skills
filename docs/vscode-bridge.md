# VS Code extension ↔ skills-dev bridge

Local UI: **`extension/`** in this repo (Marketplace id **`YangKangSung.kampff`**).  
Skills / scripts SoT: **repo root** (`kampff-skills`).  
Public product surface: **`kampff-skills`** (includes `extension/`).

## Release flow (formal)

```text
edit extension/ + scripts/  →  private SoT  →  this public repo  →  Marketplace
```

| Step | Where | What |
|------|--------|------|
| 1 | `extension/` + product scripts/docs | change · `npm run package` under `extension/` |
| 2 | private SoT | product-only filter |
| 3 | `kampff-skills` | product-only copy (include `extension/`, no harvest) |
| 4 | Marketplace | VSIX built **from** `extension/` · id `YangKangSung.kampff` |

Build: [../extension/BUILD.md](../extension/BUILD.md).

System map: [ARCHITECTURE.md](ARCHITECTURE.md) §B.  
Docs hub: [README.md](README.md).

The extension does **not** re-implement L1–L5 analysis. It queues jobs, calls Hermes, and runs **this** tree’s scripts.

## Path settings (extension)

| Setting | Points at |
|---------|-----------|
| `kampff.skillsDevRoot` | **this repo root** (required for `run_kampff_job.py`) |
| `kampff.dataRoot` | runtime `KAMPFF_DATA` (e.g. `…/kampff-data`) |
| `kampff.wikiRoot` | durable wiki shelf (`KAMPFF_WIKI`) |
| `kampff.pythonPath` | python that can run `scripts/` |
| `kampff.hermesCommand` | hermes binary (empty = auto-detect) |
| `kampff.sites` | registerable site rows (secrets in SecretStorage) |

Setup order in UI: **dataRoot → wikiRoot → skillsDevRoot** → sites.

## Scripts the extension calls

| Action | Script (under skillsDevRoot) |
|--------|------------------------------|
| Job orchestration | `scripts/run_kampff_job.py` |
| Render HTML | `scripts/render_kampff_report.py` |
| Community draft | `scripts/community_post.py` (CLI SoT; TS twin may exist in extension) |
| Prior / promote | `scripts/wiki_store.py` |

Inventory: [../scripts/README.md](../scripts/README.md).

TS mirrors (extension-only): `communityPost.ts`, `wikiStore.ts`, `jobRunner.ts`, webview.  
When draft tone or dual-store rules change, update **Python + docs here**, then bump extension if UI contracts change.

## Standalone equivalent

Same scripts without UI:

```bash
source .env.local
python scripts/run_kampff_job.py queue/JOB-request.json queue/JOB-hermes-prompt.txt
python scripts/render_kampff_report.py -a out/…-analysis.json -o out/…-report.html
```

See [ARCHITECTURE.md](ARCHITECTURE.md) §A5.

## What stays extension-only

- Webview Analyze UI, job live activity, pause/cancel, SecretStorage passwords  
- Tree views (People / Reports / Inbox / Raw)  
- Dev live-reload (`npm run dev` in `extension/`), VSIX packaging  
- Operator **personal** site rows (real `baseUrl` / username) in User settings  

`extension/src`, `media/`, and `.vsix` **belong here**. Do not ship harvest, `node_modules/`, or `kampff-data/` inside the VSIX.

## Sites — product filter

| kind | Meaning |
|------|---------|
| `sns` | `x` · `facebook` · `instagram` · `reddit` · `linkedin` (`snsId`) |
| `generic` | **Custom URL** — `baseUrl` + `urlTemplates` |

| Examples in this repo | Do not commit |
|----------------------|----------------|
| [sites-default.json](sites-default.json) | Regional community presets as defaults |
| [sites-custom.example.json](sites-custom.example.json) | Your real board login URLs |
| [sites.schema.json](sites.schema.json) | Passwords (SecretStorage only) |

### Custom URL resolution (extension)

1. Read `kampff.sites`  
2. `kind=sns` → `snsId` + default templates  
3. `kind=generic` → require `baseUrl`; expand `{baseUrl}` `{id}` `{handle}` `{username}`  
4. No hard-coded regional origin fallback  

## Dev loop (one repo)

```bash
cd /path/to/kampff-skills
# scripts / skill
# … edit scripts/ docs/ kampff/ …

# UI (same checkout)
cd extension
export NODE_ENV=development
npm run dev          # junction + tsc -watch
# once: Developer: Reload Window
```

`kampff.skillsDevRoot` = **repo root** (parent of `extension/`), not the `extension/` folder.  
Do not open a retired `kampff-vscode` clone.

## Troubleshooting (short)

| Symptom | Check |
|---------|--------|
| Go does nothing | Output → Kampff; `queue/*-request.json` mtime vs webview log |
| Job rc=0 but empty out | analysis.json contract — see skill / job runner logs |
| Login wall | site SecretStorage or agent Edge profile under dataRoot (not user Default Edge) |
| Old UI | version triangle: package.json vs `code --list-extensions` vs junction |

Deep ops: Hermes skill `kampff-vscode` (extension host playbook), not this file.

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md)  
- [usage.md](usage.md)  
- [dual-store-wiki.md](dual-store-wiki.md)  
- [prebuilt-platforms.md](prebuilt-platforms.md)  
- [ARCHITECTURE.md](ARCHITECTURE.md)  
