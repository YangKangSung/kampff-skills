# Kampff

### Read the board. Not the vibes.

Boards are loud. Vibes are cheap.

Someone replies under your post and you already have a feeling. Kampff writes that down as a **distance call**, tied to quotes they actually published.

engage · neutral · caution · avoid

It will not call anyone evil. If a claim has no quote, it is marked low-confidence.

[![Stars](https://img.shields.io/github/stars/YangKangSung/kampff-skills?style=social)](https://github.com/YangKangSung/kampff-skills/stargazers)
[![Sponsor](https://img.shields.io/badge/Sponsor-YangKangSung-ea4aaa?logo=githubsponsors)](https://github.com/sponsors/YangKangSung)
[![VS Marketplace](https://img.shields.io/visual-studio-marketplace/v/YangKangSung.kampff?label=VS%20Code)](https://marketplace.visualstudio.com/items?itemName=YangKangSung.kampff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Skill](https://img.shields.io/badge/agent-SKILL.md-0ea5e9)](kampff/SKILL.md)

[![Kampff demo reel](docs/demo-reel.gif)](https://yangkangsung.github.io/kampff-skills/demo-kampff-walkthrough.html)

GIF plays here. Click it for the <a href="https://yangkangsung.github.io/kampff-skills/demo-kampff-walkthrough.html" target="_blank" rel="noopener noreferrer"><strong>interactive demo</strong></a> (`Space` pauses) · <a href="https://yangkangsung.github.io/kampff-skills/demo-reel.mp4" target="_blank" rel="noopener noreferrer">mp4</a>

---

## Try it first

- <a href="https://yangkangsung.github.io/kampff-skills/sample-community-report.html" target="_blank" rel="noopener noreferrer"><strong>Sample report</strong></a>. Live page, not GitHub source. First screen is `쉬운 말`. Switch to the long analysis if you want the graphs.
- <a href="docs/sample-desk.html"><strong>Distance Desk</strong></a> (this checkout). Mute quotes, pick a situation, scrub time. One person — not a board map.
- <a href="docs/sample-graph.html"><strong>Relation graph</strong></a> (this checkout). Nodes and edges. Slide min level to 4 to leave the comment brigade.
- <a href="https://yangkangsung.github.io/kampff-skills/demo-kampff-walkthrough.html" target="_blank" rel="noopener noreferrer"><strong>How a report is made</strong></a>. Collect → honesty → distance, then a walk through the same sample.
- <a href="https://yangkangsung.github.io/kampff-skills/" target="_blank" rel="noopener noreferrer">Pages home</a>

The sample person is fiction: `relay_ops` @ `forum.example`. Real third-party dossiers do not belong in this repo.

> Loyal to **green that means something**, not to brands. Default distance: `neutral`, soft-`engage` on CI / rollback / observability. Not `avoid`.

The rest of the HTML is the evidence for that call.

---

## Install

Public tree: [`YangKangSung/kampff-skills`](https://github.com/YangKangSung/kampff-skills).

### Any agent

Same skill file. Drop `kampff/` into your harness:

| Agent | Path |
|-------|------|
| Hermes | `~/.hermes/skills/kampff` |
| Claude Code | `~/.claude/skills/kampff` |
| Grok | `~/.grok/skills/kampff` |
| Cursor | `.cursor/skills/kampff` |

```bash
git clone https://github.com/YangKangSung/kampff-skills.git
cp -r kampff-skills/kampff ~/.hermes/skills/kampff   # pick your path
```

```text
/kampff analyze path/to/bundle.json
/kampff desk path/to/analysis.json
/kampff graph path/to/bundle.json
/kampff graph {id}
/kampff member {platform} {id}
/kampff today
```

Optional data dir: `export KAMPFF_DATA=~/kampff-data` (Windows: `setx KAMPFF_DATA "..."`).

### VS Code

[Kampff on the Marketplace](https://marketplace.visualstudio.com/items?itemName=YangKangSung.kampff) (`YangKangSung.kampff` @ **0.9.10**), or:

```text
ext install YangKangSung.kampff
```

The extension queues jobs and opens reports. It does not scrape the web by itself. You still need a `kampff-skills` clone, Hermes, and Python 3. Setup: Activity Bar → Kampff → **Setup…** → point `skillsDevRoot` at that clone → Analyze → Go.

---

## What you get

| | |
|--|--|
| **Distance** | Engage, stay neutral, go cautious, or walk. |
| **Fit** | How their worldview and working style sit next to *yours*. You are in the pool. |
| **Time** | How they changed. One rant is not a trait. |
| **Proof** | A quote, or an honest "we do not have this." |
| **Desk** | Paper-test the call: mute quotes, pick a situation, scrub time. One person. |
| **Graph** | People as nodes, ties as edges. Filter relation level. Thick/rose = stacked or brigade-like. |

Collection is a separate step. Analyze reads files only. It does not invent a crawl mid-report.

```text
posts · comments · mail · chat  →  bundle.json  →  /kampff  →  dossier
```

1. **Collect** lawful text you already have a right to read.
2. **Honesty:** claimed vs collected. Partial crawl stays partial.
3. **Analyze** the patterns. It is not a character roast.
4. **Decide** the engage cost. This is not a persuasion playbook.

---

## vs the rest

| Skill | Who it profiles |
|-------|-----------------|
| customer profilers | Buyers, for marketing |
| i-am / self skills | You, from agent logs |
| chat stats tools | Word counts and vibes |
| **kampff** | The board, you, time, and a distance tag |

---

## Rules

**Do**

- Quote, or mark confidence.
- Run yourself through the same protocol.
- Keep real runs under `$KAMPFF_DATA` (outside git).

**Don’t**

- Medical or legal diagnosis.
- Stalking or covert collection.
- Commit real people, tokens, or host dumps to this repo.
- Confuse “deleted a file” with “gone from git history.”

Samples are fiction: `relay_ops`, `user_42`, `north_packet`.

---

<details>
<summary>Layers, if you want the stack</summary>

Community reports can add fun/low-validity lenses. They never get to be the only reason for `avoid`.

| Layer | Job |
|-------|-----|
| L1 | Psych lean (Big Five-ish, conflict style) |
| L2 | Worldview axes |
| L3 | Behavioral signature (chronic vs one-off) |
| L4 | Alliance / go-together |
| L5 | Timeline and drift |
| L6–L7 | HR / OSINT — only if asked, lawful only |

Default community lenses: [MBTI](docs/lenses-mbti.md) (fun) · [CIA-SAT](docs/lenses-cia-sat.md) (public analytic form, not ops).

```yaml
analysis_lenses: ["personal", "mbti", "cia_sat"]
```

Pipeline notes: [community-member-pipeline.md](docs/community-member-pipeline.md) · [report-template.md](docs/report-template.md)

</details>

<details>
<summary>Layout</summary>

This is the public product tree. Docs: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/README.md](docs/README.md).

VS Code UI lives in `extension/` here. Sibling `kampff-vscode` is retired. Build notes: [docs/vscode-bridge.md](docs/vscode-bridge.md) · [extension/BUILD.md](extension/BUILD.md).

```text
kampff/                 ← the skill (copy this)
extension/              ← VS Code shell (YangKangSung.kampff)
docs/                   ← samples, architecture, lenses
scripts/                ← run_kampff_job · render · wiki_store
collectors/             ← optional YAML packs
```

</details>

---

## Name and license

**Kampff** is independent OSS by [YangKangSung](https://github.com/YangKangSung). Not affiliated with any film or game franchise. The name is closer to *struggle to read sparse evidence*.

**MIT.** Use it, cite quotes, follow local law.  
Third-party tools: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

Star this repo if it is useful. [Issues](https://github.com/YangKangSung/kampff-skills/issues) · [sponsors](https://github.com/sponsors/YangKangSung).

```text
graphify  →  code  →  graph
kampff    →  text  →  human spectrum
```
