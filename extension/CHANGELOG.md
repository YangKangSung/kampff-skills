# Changelog

All notable changes to the **Kampff** VS Code extension are documented here.

## [0.9.14] — 2026-09-02

### Changed
- Ego graph **attaches already-harvested 1-hop alters** (no new scrape). Their other threads become hop-2 (cyan).
- Analyze with `harvestMaxFetch` ≤ 15 uses park-only / 1 search page (quieter 1-hop).
- Graph opens by nick or `STATE.author_id`, not folder name only.

## [0.9.13] — 2026-08-19

### Changed
- **관계 그래프** with an ID is an **ego** graph: people on that id’s posts, comments, and likes (if liker ids are in saved harvest HTML). Analyze first so `inbox/*/raw/{id}/posts` exists. No harvest → error, not the sample board.

## [0.9.12] — 2026-08-19

### Added
- **Relation graph** in the operator shell: Analyze **관계 그래프**, command `kampff.openGraph`, inbox bundle / Reports `*-graph.html`. Builds from `inbox/*/bundle.json` (sample fallback).

## [0.9.11] — 2026-08-19

### Added
- **Distance Desk** — paper-test one person's call (mute quotes, situation chips, L5 slider). Command `kampff.openDesk` + Analyze button. Not a crowd graph.

## [0.9.10] — 2026-08-16

### Changed
- Marketplace publish path: `vsce-publish` + `VSCE_PAT` (no Manage UI)

## [0.9.9] — 2026-08-16

### Added
- Browser open for quick / FULL reports as separate snapshots

## [0.9.8] — 2026-08-14

### Added
- Settings → Kampff → **Language**: `auto` (follow VS Code locale) / `en` / `ko`
- Reports open English unless language is Korean (`auto` + editor `ko*`, or explicit `ko`)

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
