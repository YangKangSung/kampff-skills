# Kampff

> **sickn33 profiles customers. i-am profiles you. Kampff profiles everyone on the board — including you.**

Human spectrum analysis from text — for communities, workplace boards, and teams.

[![Stars](https://img.shields.io/github/stars/YangKangSung/kampff-skills?style=social)](https://github.com/YangKangSung/kampff-skills/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Contents

- [What is Kampff?](#what-is-kampff)
- [How it works](#how-it-works)
- [Quick start](#quick-start)
- [Workflow](#workflow)
- [Example output](#example-output)
- [Star = next module](#star--next-module)
- [spectrograph](#spectrograph-7-layers)
- [Compare](#compare)
- [Philosophy](#philosophy)
- [What this is NOT](#what-this-is-not)
- [Structure](#structure)
- [Security](#security)
- [Contributing](#contributing)
- [Support](#support)
- [License](#license)

---

## What is Kampff?

**Kampff** is an agent skill. Feed it text traces — posts, comments, replies — get back a **human dossier**:

- **Worldview fit** — politics, ideology, religion, philosophy (from language patterns, not stereotypes)
- **Alliance fit** — can you work or go together?
- **Ephemeris** — how someone **changed over time** (drift, turning points)
- **Distance** — `engage` · `neutral` · `caution` · `avoid` (with quoted evidence)
- **You too** — the viewer is in the pool. Comparison, not judgment from nowhere.

**No scraping built in.** Your collector gathers text. Kampff analyzes.

Analysis engine: **spectrograph** — 7 layers, optional HR and OSINT lenses.

```
graphify     → code → graph
kampff       → text → human spectrum (spectrograph)
```

---

## How it works

```
[optional collector] → bundle.json → /kampff → out/{date}-report.md
```

1. **Collect** (your pipeline or `kampff-collect`) — mail, meeting, chat, Jira, Confluence, SNS → normalized `bundle.json`
2. **Analyze** — agent loads `kampff/SKILL.md`, runs spectrograph L1–L7
3. **Report** — matrix + per-person dossiers with quotes under `{KAMPFF_DATA}/out/`

---

## Quick start

### Install skill

| Agent | Path |
|-------|------|
| Grok | `~/.grok/skills/kampff` |
| Claude Code | `~/.claude/skills/kampff` or `.claude/skills/kampff` |
| Hermes | `~/.hermes/skills/kampff` |
| Cursor | `.cursor/skills/kampff` |

Same `kampff/SKILL.md` — copy to **your** agent’s skills folder (install per harness you use):

```bash
# Grok
cp -r kampff ~/.grok/skills/kampff

# Claude Code (user-level; or .claude/skills/kampff in a project)
cp -r kampff ~/.claude/skills/kampff

# Hermes
cp -r kampff ~/.hermes/skills/kampff
```

Early drafts showed only Grok because this repo was bootstrapped in **Grok Build**; the skill is not Grok-specific.

Optional data root:

```bash
# Windows
setx KAMPFF_DATA "D:\data\kampff"
# macOS / Linux
export KAMPFF_DATA=~/kampff-data
```

### Collector (optional)

```bash
cd collectors && pip install -e ".[all]"
kampff-collect collect --targets path/to/targets.json --out path/to/bundle.json
```

REST/Playwright adapters are **stubs** — architecture and YAML packs ship first. See [collectors/README.md](collectors/README.md).

### Data layout

```
kampff-data/
├── inbox/{YYYY-MM-DD}/bundle.json
├── people/{id}/history.json    # optional, ephemeris depth
└── out/{YYYY-MM-DD}-report.md
```

### Daily use

```text
/kampff today
/kampff analyze D:\data\kampff\inbox\2026-07-11\bundle.json
```

Input sources: `mail` · `meeting` · `chat` · `messenger` · `confluence` · `jira` · `github` · Playwright · SNS  
Docs: [usage](docs/usage.md) · [input schema](docs/input-schema.md) · [platforms](docs/prebuilt-platforms.md)

---

## Workflow

| Command | When |
|---------|------|
| `/kampff collect --targets …` | URL/person search → `bundle.json` (collector) |
| `/kampff today` | Daily inbox drop |
| `/kampff analyze {path}` | Explicit bundle file |
| `/kampff person {id}` | One-person refresh + ephemeris |

---

## Example output

Anonymized dossier from [sample-input.json](docs/sample-input.json):

→ **[docs/sample-output.md](docs/sample-output.md)** (matrix + per-person reports with evidence quotes)

---

## Star = next module

| Stars | Unlock |
|-------|--------|
| Ship | kampff + spectrograph L1–L5 |
| 100 | Ephemeris timeline template |
| 300 | HR lens pack |
| 500 | OSINT lens pack |
| 1000 | Skill #2 |

---

## spectrograph (7 layers)

| Layer | What |
|-------|------|
| L1 | Psych — Big Five, conflict, attachment |
| L2 | Worldview — politics · religion · philosophy |
| L3 | Behavioral signature — chronic vs situational patterns |
| L4 | Alliance — trust, reciprocity |
| L5 | Ephemeris — timeline, drift, turning points |
| L6 | HR lens — team signals (assist only) |
| L7 | OSINT lens — narrative consistency (lawful scope) |

Full protocol: [docs/spectrograph.md](docs/spectrograph.md)

---

## Compare

| Skill | Profiles |
|-------|----------|
| [customer-psychographic-profiler](https://github.com/sickn33/agentic-awesome-skills) | Target **customers** for marketing |
| [i-am](https://github.com/LeoYeAI/openclaw-master-skills) | **You** from agent sessions |
| [ChatAnalysis.SKILL](https://github.com/JularDepick/ChatAnalysis.SKILL) | Chat stats + personality HTML |
| **kampff** | **Everyone on the board** + **you** + worldview + time + distance |

---

## Philosophy

- **Evidence over vibes** — every inference tied to a quote or marked low-confidence
- **Viewer in the pool** — you get the same scrutiny as everyone else
- **Pattern stability, not soul verdicts** — chronic vs situational; no "born evil"
- **Lawful scope** — refuse stalking, harassment, covert surveillance
- **Collection ≠ analysis** — skill reads files you point at; no built-in scraping

---

## What this is NOT

- Medical or psychiatric diagnosis
- Sole hiring / firing decision
- Stalking or harassment tooling
- "Born evil" labels — **pattern stability**, not soul verdicts

---

## Structure

```
kampff-skills/
├── kampff/SKILL.md
├── collectors/                 # kampff-collect (optional)
│   ├── kampff_collect/
│   └── platforms/              # 15 prebuilt YAML packs
├── docs/
│   ├── usage.md
│   ├── sample-input.json
│   ├── sample-output.md
│   ├── launch-copy.md
│   └── spectrograph.md
└── LICENSE
```

---

## Security

- **Never commit** tokens, `.env`, or `kampff-data/` (gitignored). Use `auth_ref` + `KAMPFF_AUTH_DIR` — [collectors.md](docs/collectors.md).
- **Maintainers:** [GitHub CLI](https://cli.github.com/) (`gh auth login --web`). Never paste tokens in AI chats or scripts that echo credentials.
- Enable **2FA**: [github.com/settings/security](https://github.com/settings/security)
- Issues: [github.com/YangKangSung/kampff-skills/issues](https://github.com/YangKangSung/kampff-skills/issues)

---

## Contributing

Issues and PRs welcome. Keep skills focused, document real use cases, cite evidence in examples.

Launch copy draft: [docs/launch-copy.md](docs/launch-copy.md)

---

## Support

If Kampff saves you time reading a board:

- **[Sponsor on GitHub](https://github.com/sponsors/YangKangSung)** — recurring support
- **⭐ Star** the repo — unlocks the next spectrograph module ([roadmap](#star--next-module))

---

## Trademark notice

**Kampff** is an independent open-source project by [YangKangSung](https://github.com/YangKangSung).

- Not affiliated with any film studio, game publisher, or media franchise.
- The name evokes *reading people from sparse evidence* (German *Kampf* — struggle/contest of interpretation).
- Do not use studio logos, stills, or trademarked test names in forks or marketing without permission.

---

## License

MIT — use wisely, cite evidence quotes, respect privacy law in your jurisdiction.