# VS Code extension ↔ skills repo bridge

Local UI: **`extension/`** in this repo (Marketplace id **`YangKangSung.kampff`**).  
Skills / scripts SoT: **repo root** (`kampff-skills`).

## Release flow (formal)

```text
edit extension/ + scripts/  →  (private skills-dev)  →  kampff-skills (this repo)  →  Marketplace
```

| Step | Where | What |
|------|--------|------|
| 1 | `extension/` + product scripts/docs | change · build under `extension/` |
| 2 | private SoT | filter / product-only |
| 3 | `kampff-skills` | this public tree includes `extension/` |
| 4 | Marketplace | VSIX from **`extension/kampff-*.vsix`** · id `YangKangSung.kampff` |

Build: [../extension/BUILD.md](../extension/BUILD.md).

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
- Dev live-reload (`npm run dev`), VSIX packaging  
- Operator **personal** site rows (real `baseUrl` / username) in User settings  

Do **not** copy `media/**`, `src/`, or `.vsix` into this git tree.

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

## Dev loop (two folders)

```bash
# skills / scripts
cd /path/to/kampff-skills repo
# … edit scripts/docs …

# UI
cd /path/to/kampff-vscode
npm run compile   # or: npm run dev
# Reload Window once if host is stale
```

`kampff.skillsDevRoot` must point at the skills repo path you edited.

## Troubleshooting (short)

| Symptom | Check |
|---------|--------|
| Go does nothing | Output → Kampff; `queue/*-request.json` mtime vs webview log |
| Job rc=0 but empty out | analysis.json contract — see skill / job runner logs |
| Login wall | site SecretStorage or agent Edge profile under dataRoot (not user Default Edge) |
| Old UI | version triangle: package.json vs `code --list-extensions` vs junction |

Deep ops: extension skill `kampff-vscode` (Hermes), not this file.

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md)  
- [usage.md](usage.md)  
- [dual-store-wiki.md](dual-store-wiki.md)  
- [prebuilt-platforms.md](prebuilt-platforms.md)  
- [ARCHITECTURE.md](ARCHITECTURE.md)  
