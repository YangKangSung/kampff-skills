# Kampff for VS Code

**Marketplace-ready local operator shell** for the [Kampff](https://github.com/YangKangSung/kampff-skills) distance/dossier workflow.

This extension does **not** ship the analysis skill or scrape the web by itself. It:

- Points at your **kampff-skills** clone + runtime data folder  
- Queues Analyze jobs (Hermes)  
- Shows progress and opens **dual-track** HTML reports  
- Opens a **Distance Desk** to paper-test the call (mute quotes · situation · time)  
- Opens a **relation graph** (people as nodes, level filter, Hide/Dim) from an inbox bundle  
- Optionally promotes outputs to a wiki shelf  

Skill / CLI SoT: [kampff-skills](https://github.com/YangKangSung/kampff-skills) · architecture: [docs/ARCHITECTURE.md](https://github.com/YangKangSung/kampff-skills/blob/main/docs/ARCHITECTURE.md)

---

## Requirements

| Need | Why |
|------|-----|
| [VS Code](https://code.visualstudio.com/) 1.85+ | Extension host |
| [kampff-skills](https://github.com/YangKangSung/kampff-skills) clone | `scripts/run_kampff_job.py`, render, skill text |
| [Hermes](https://github.com/NousResearch/hermes-agent) (or compatible CLI) | One-click analyze jobs |
| Python 3 | Job + render helpers |

Optional: wiki folder for durable `people/` + `reports/`.

---

## Install

### Marketplace (when published)

```text
ext install YangKangSung.kampff
```

Or search **Kampff** in Extensions.

### From VSIX

```bash
npm run package
code --install-extension ./kampff-0.9.7.vsix --force
```

Reload Window after install.

---

## Defaults (privacy-minded)

No regional-board adapter ships in the extension (generic sites + default **X** only).


| | |
|--|--|
| Default site | **X** (`https://x.com`) — no password prefilled |
| Example handle | `@elonmusk` / `https://x.com/elonmusk` as **input shape only** (not a bundled analysis) |
| Depth | **quick** by default — full crawls hit rate limits fast |
| Pacing | `harvestPolite` on — X and other sites rate-limit / 429 |

Do not commit real dossiers. Respect each platform’s terms and limits.

## First run

1. Activity Bar → **Kampff**  
2. **Kampff: Setup…** (or Command Palette)  
3. Pick folders (all optional until you run a job):  
   - **dataRoot** — runtime `inbox/` `queue/` `out/`  
   - **wikiRoot** — durable shelf (optional)  
   - **skillsDevRoot** — **this repo root** (parent of `extension/`; public clones use `kampff-skills`) — **required** for Go  
4. **Register site…** if you need a logged-in board (optional). Passwords go to **SecretStorage**, never settings JSON.  
5. Analyze → target → **Go**

Empty defaults on purpose: no machine-specific paths ship in the VSIX.

---

## Settings (`kampff.*`)

| Setting | Role |
|---------|------|
| `dataRoot` | Runtime scratch |
| `wikiRoot` | Durable people/reports |
| `skillsDevRoot` | This repo root (parent of `extension/`) |
| `hermesCommand` | Empty = auto-detect |
| `sites` | Registered sites (no passwords) |
| `defaultPlatform` | Default `x` (change freely) |

---

## Privacy

- Do not commit real dossiers under `dataRoot`  
- Do not put passwords in `settings.json`  
- Regional board adapters are **opt-in** via site registration, not pre-seeded  

---

## Dev

```bash
npm install
npm run compile
npm run dev          # link + watch (see package scripts)
```

`npm run lint` → `tsc --noEmit`.

---

## License

MIT — see [LICENSE](LICENSE).
