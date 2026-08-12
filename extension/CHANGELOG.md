# Changelog

All notable changes to the **Kampff** VS Code extension are documented here.

## [0.9.7] — 2026-08-12

### Fixed
- Person primary = **handle/id only** — nick no longer concatenated into input/URL (`elonmusk Elon Musk` → broken `x.com/…`)
- Explicit `authorId`/`nick` overlay runs without removed `boardLike` gate; SNS profile URL kept on handle
- Job `targetId` prefers `authorId`/`handle` first token (not full input+nick)
- Unix job cancel: spawn detached process group + kill `-pid` fallback to pid

## [0.9.6] — 2026-08-10

### Removed
- Clien-specific adapter surface (`SiteKind`, platform enum, URL parser, harvest prompts, UI defaults)
- Delay settings renamed `harvestDelay*` (legacy `clienDelay*` still read)

## [0.9.5] — 2026-08-10

### Defaults
- Default registered site: **X** (no password)
- Example target form: `@elonmusk` / `https://x.com/elonmusk` (placeholder only)
- Harvest safety + polite delays apply to **all sites**; note X rate limits / 429
- Env aliases `KAMPFF_HARVEST_MIN/MAX_DELAY_MS` (legacy `KAMPFF_CLIEN_*` kept)

## [0.9.4] — 2026-08-09

### Marketplace readiness

- Removed `"private": true`; added `repository` / `homepage` / `bugs`
- Empty defaults for `dataRoot`, `wikiRoot`, `skillsDevRoot` (Setup required)
- No pre-seeded regional sites; `kampff.sites` default `[]`
- Default platform `x`; enabled list favors major SNS + custom
- Stripped host-hardcoded folder defaults from config, Setup dialogs, job runner
- README rewritten for external installers

## [0.9.3] — 2026-08-08

- Do not block Go when site password empty (agent session may suffice)

## [0.9.x]

- Dual-root storage, sites SecretStorage, job runner integration — see git history
