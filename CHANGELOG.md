# Changelog

All notable **public** changes to [kampff-skills](https://github.com/YangKangSung/kampff-skills).

Format inspired by [Keep a Changelog](https://keepachangelog.com/). Dates are UTC merge days when known.

## [Unreleased]

### Added

- Dual-track HTML reports: `scripts/kampff_report_easy.py` + `render_kampff_report.py --track both|pro|easy` (쉬운 말 default open)
- Docs: [report-tracks.md](docs/report-tracks.md), deliberate-practice [drills/](docs/drills/) (`gate_runner`, status-flex)
- Clinical lens doc on public tree; sample HTML regenerated dual-track
- `scripts/kampff_paths.py` — `KAMPFF_DATA` / repo-local `kampff-data/` only (no host hardcodes)

### Fixed

- `render_kampff_report.py` accepts `source_mix` as dict or `[label, n, color]` rows

### Added (earlier)

- `scripts/community_post.py` — optional peer/short/board community draft (VS Code parity)
- `scripts/wiki_store.py` — dual-store prior evidence + wiki promote helpers
- Docs: community-post, dual-store-wiki, vscode-bridge, sites schema
- `CONTRIBUTING.md`, issue/PR templates, `docs/README.md` index

## [0.1.x] — 2026-07

### Added

- Kampff agent skill (`kampff/SKILL.md`) + spectrograph framing
- Sample community HTML report + walkthrough Pages demos
- Report analysis schema, graph-oriented HTML renderer path
- Optional lenses: MBTI (fun), CIA-SAT/ACH, clinical-psych (non-diagnostic)
- Community draft tones for peer / short / board export paths
- Collectors docs (generic / public-oriented)

### Notes

- Daily development may live on a private mirror; this changelog tracks the **public** tree only.
- Real third-party dossiers are never part of releases.
