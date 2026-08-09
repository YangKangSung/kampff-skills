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

## Scripts the extension may call (product-safe)

| Action | Script / module |
|--------|------------------|
| Render HTML | `scripts/render_kampff_report.py -a … -o …` |
| Community draft (CLI SoT) | `scripts/community_post.py` |
| Prior / promote | `scripts/wiki_store.py` |
| Job orchestration | `scripts/run_kampff_job.py` (when present) |

TS mirrors live only in the extension repo. Keep Python + docs here as CLI SoT when tone/store rules change.

## What stays extension-only

- Webview Analyze UI, job live activity, SecretStorage passwords
- Tree views (People / Reports / Inbox), dev live-reload
- Operator site rows with **personal** `baseUrl` / username
- Host-local path defaults

Do **not** expect `media/**` or extension host sources in this public tree.

## Sites — product filter

| kind | Meaning |
|------|---------|
| `sns` | Famous network only: `x` · `facebook` · `instagram` · `reddit` · `linkedin` (`snsId`) |
| `generic` | **Custom URL** — operator `baseUrl` + `urlTemplates` |

| Ship | Do not ship |
|------|-------------|
| [sites-default.json](sites-default.json) SNS seeds | Regional community presets |
| [sites-custom.example.json](sites-custom.example.json) synthetic `forum.example` | Real board login/member URLs |
| [sites.schema.json](sites.schema.json) | Passwords, personal notes |

Passwords never live in JSON — only `hasPassword` + SecretStorage in the extension.

### Custom URL resolution (extension should)

1. Read `kampff.sites`
2. If `kind=sns` → use `snsId` adapter + default templates
3. If `kind=generic` → require `baseUrl`; expand `urlTemplates.*` with `{baseUrl}` `{id}` `{handle}` `{username}`
4. Never fall back to a hard-coded regional origin when templates missing

## Related

- [prebuilt-platforms.md](prebuilt-platforms.md)
- [dual-store-wiki.md](dual-store-wiki.md)
- [community-post.md](community-post.md)
