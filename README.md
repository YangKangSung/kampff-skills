# Kampff

> **sickn33 profiles customers. i-am profiles you. Kampff profiles everyone on the board — including you.**

Human spectrum analysis from text — for communities, workplace boards, and teams.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

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

## Quick start

```bash
cp -r kampff ~/.grok/skills/kampff
setx KAMPFF_DATA "D:\data\kampff"   # optional data root
```

**매일:** 수집기 → `kampff-data/inbox/오늘/bundle.json` → 에이전트:

```text
/kampff today
```

**파일 지정:**

```text
/kampff analyze D:\data\kampff\inbox\2026-07-11\bundle.json
```

입력 소스: `mail` · `meeting` · `chat` · `messenger` · `community_*` · `sns_*`  
→ [docs/usage.md](docs/usage.md) · [docs/input-schema.md](docs/input-schema.md)

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

---

## Compare

| Skill | Profiles |
|-------|----------|
| [customer-psychographic-profiler](https://github.com/sickn33/agentic-awesome-skills) | Target **customers** for marketing |
| [i-am](https://github.com/LeoYeAI/openclaw-master-skills) | **You** from agent sessions |
| [ChatAnalysis.SKILL](https://github.com/JularDepick/ChatAnalysis.SKILL) | Chat stats + personality HTML |
| **kampff** | **Everyone on the board** + **you** + worldview + time + distance |

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
├── docs/spectrograph.md
├── docs/sample-input.json
└── LICENSE
```

---

## Trademark notice

**Kampff** is an independent open-source project by [YangKangSung](https://github.com/YangKangSung).

- Not affiliated with, endorsed by, or sponsored by any film studio, game publisher, or media franchise.
- The name evokes *reading people from sparse evidence* (German *Kampf* — struggle/contest of interpretation), not a licensed fictional test or character.
- Do not use studio logos, stills, or trademarked test names in forks or marketing without permission.

---

## License

MIT — use wisely, cite evidence quotes, respect privacy law in your jurisdiction.