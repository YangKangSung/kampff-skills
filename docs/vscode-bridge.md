# VS Code extension ↔ this repo

Optional local UI: private **Kampff VS Code** extension (`ksyang.kampff`).  
Skills SoT for OSS: **this public repo**.

The extension does **not** re-implement L1–L5 analysis. It queues jobs, calls Hermes, and runs **this** tree’s scripts.

## Path settings (extension)

| Setting | Points at |
|---------|-----------|
| `kampff.skillsDevRoot` | clone of this repo (or private fork) |
| `kampff.dataRoot` | runtime `KAMPFF_DATA` |
| `kampff.wikiRoot` | durable wiki shelf |
| `kampff.pythonPath` | python that can run `scripts/` |
| `kampff.hermesCommand` | hermes binary (optional auto-detect) |
| `kampff.sites` | registerable site rows (secrets in SecretStorage) |

## Scripts the extension calls

| Action | Script / module |
|--------|------------------|
| Render HTML | `scripts/render_kampff_report.py -a … -o …` |
| Community draft (CLI SoT) | `scripts/community_post.py` |
| Prior / promote | `scripts/wiki_store.py` |
| Job orchestration | `scripts/run_kampff_job.py` (when present) |

TS mirrors live only in the extension repo (`communityPost.ts`, `wikiStore.ts`, …). Keep Python + docs here as CLI SoT when tone/store rules change.

## What stays in the extension only

- Webview Analyze UI, job live activity, SecretStorage passwords
- VS Code tree views (People / Reports / Inbox)
- Dev live-reload

Do **not** expect `media/**` or extension host sources in this public tree.

## Sites (registerable)

| kind | Meaning |
|------|---------|
| `clien` | specialized member harvest path |
| `generic` | URL-first site |

Schema: [sites.schema.json](sites.schema.json) · example: [sites-default.json](sites-default.json)

Passwords never live in JSON — only `hasPassword` flags + SecretStorage in the extension.

## Related

- [dual-store-wiki.md](dual-store-wiki.md)
- [community-post.md](community-post.md)
