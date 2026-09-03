# Kampff architecture (dev SoT)

Public product: **this repo** (`kampff-skills`).  
Maintainers may keep a private operator checkout; consumers only need this tree.  
UI shell: **`extension/`** in this repo (Marketplace `YangKangSung.kampff` @ **0.9.7**).  
Sibling `kampff-vscode` is **retired**. Product UI is **`extension/`** here.

## Two run modes

```text
                    ┌─────────────────────────────────────┐
                    │  kampff-skills-dev (this tree)      │
                    │  skill · scripts · collectors · docs│
                    └───────────────┬─────────────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           ▼                                                 ▼
 ┌─────────────────────┐                          ┌──────────────────────┐
 │ A) STANDALONE       │                          │ B) VS CODE EXTENSION │
 │ CLI / agent / Python│                          │ YangKangSung.kampff  │
 └─────────────────────┘                          └──────────────────────┘
   hermes · slash /kampff                           webview Analyze · queue
   kampff-collect CLI                               jobRunner → run_kampff_job
   render_kampff_report.py                          SecretStorage sites
   wiki_store · community_post                      tree: People/Reports/Inbox
```

Same **data contract**: `KAMPFF_DATA` (+ optional `KAMPFF_WIKI`).  
Extension does **not** re-implement L1–L5 — it orchestrates this tree.

| | Standalone | VS Code |
|--|------------|---------|
| Entry | agent skill · CLI · Python scripts | Activity Bar **Kampff** · Go |
| Auth secrets | env / `KAMPFF_AUTH_DIR` / agent Edge profile | Extension SecretStorage + optional site-auth file |
| Progress UI | terminal / logs | webview + Output **Kampff** |
| Job glue | you call steps (or `run_kampff_job.py`) | `run_kampff_job.py` by default |
| Sites list | `docs/sites-*.json` as examples; env/targets | `kampff.sites` settings |
| Live reload | n/a | `npm run dev` in **`extension/`** of this repo |

Detail: [usage.md](usage.md) · [vscode-bridge.md](vscode-bridge.md).

---

## Repo layout

```text
kampff-skills/
  kampff/                 # agent skill (SKILL.md + references/)
  extension/              # VS Code shell — YangKangSung.kampff (daily UI SoT)
  collectors/             # kampff-collect package (SNS + custom YAML)
  docs/                   # product + operator workflow docs (this folder)
  scripts/
    # --- product / dual-mode (standalone + extension) ---
    render_kampff_report.py
    render_kampff_desk.py       # Distance Desk (paper-test one call)
    kampff_graph.py · build_kampff_graph.py · render_kampff_graph.py
    kampff_report_easy.py
    kampff_paths.py
    wiki_store.py
    community_post.py
    run_kampff_job.py          # extension job path; CLI-callable
    # --- standalone helpers ---
    expand_handles_maigret.py
    # --- release / dev tooling ---
    setup-local-dev.sh · dev-status.sh
    release-check.sh · release-to-public.sh
  kampff-data/            # gitignored runtime (inbox/queue/out)
  .venv/                  # gitignored
```

Script classes: [scripts/README.md](../scripts/README.md).  

---

## Data roots

| Root | Env | Holds | Who writes |
|------|-----|--------|------------|
| **dataRoot** | `KAMPFF_DATA` | `inbox/` `queue/` `out/` | collect, jobs, render scratch |
| **wikiRoot** | `KAMPFF_WIKI` | `people/` `reports/` `Index.md` | promote / prior merge |
| **skills root** | (cwd or extension `skillsDevRoot`) | this git tree | you / extension spawn |

Resolution: `scripts/kampff_paths.data_root()` — **env first**, else repo-local `kampff-data/`.  
Do not commit real dumps. Doc: [dual-store-wiki.md](dual-store-wiki.md).

---

## A) Standalone execution

### A1. Agent skill only (analyze)

```bash
# skill installed into harness (Hermes example)
cp -r kampff ~/.hermes/skills/kampff   # or external_dirs

export KAMPFF_DATA="$PWD/kampff-data"
# put bundle at inbox/YYYY-MM-DD/bundle.json  OR pass path

# in agent:
#   /kampff analyze $KAMPFF_DATA/inbox/YYYY-MM-DD/bundle.json
#   /kampff today
#   /kampff drill 01
```

Skill reads **files only** — no mid-analysis scrape. Spec: [kampff/SKILL.md](../kampff/SKILL.md) · [usage.md](usage.md).

### A2. Collect CLI (optional)

```bash
source .venv/Scripts/activate
export KAMPFF_DATA="$PWD/kampff-data"
kampff-collect catalog
kampff-collect connect setup --platform x --ref x_api   # SNS
# targets.json → collect → bundle.json
```

Platforms: [prebuilt-platforms.md](prebuilt-platforms.md) (SNS five + custom).  
Targets: [RUN-INPUT.md](RUN-INPUT.md) · [sample-targets-sns.json](sample-targets-sns.json).

### A3. Render HTML (offline)

```bash
python scripts/render_kampff_report.py \
  -a docs/sample-analysis.json \
  -o /tmp/report.html
# dual-track default (쉬운 말 + 전문); --track pro|easy|both
# also writes sibling Distance Desk unless --no-desk
python scripts/render_kampff_desk.py -a docs/sample-analysis.json -o docs/sample-desk.html
```

### A4. Dual-store CLI

```bash
export KAMPFF_WIKI="${KAMPFF_WIKI:-$PWD/wiki}"
python scripts/wiki_store.py init-wiki --wiki "$KAMPFF_WIKI"
python scripts/wiki_store.py prior --id member_id --platform reddit --prompt
python scripts/wiki_store.py promote --id member_id --platform reddit \
  -a "$KAMPFF_DATA/out/…-analysis.json" \
  -r "$KAMPFF_DATA/out/…-report.html"
```

### A5. One-shot job pipeline (same as extension engine)

```bash
python scripts/run_kampff_job.py <request.json> <hermes-prompt.txt> [hermes.exe]
# needs: KAMPFF_DATA, optional KAMPFF_SKILLS / KAMPFF_WIKI / KAMPFF_PEOPLE
# success = fresh out/*-analysis.json (+ render)
```

Operator harvest steps inside the job may call **private** scripts (clien/…).  
Those stay on dev; they are **not** public product surface.

### A6. Smoke (synthetic)

```bash
# drill 01 / sample-analysis → render --track both
# see docs/drills/README.md
```

---

## B) VS Code extension execution

In-repo package: **`extension/`** · Marketplace id `YangKangSung.kampff`. Build: [../extension/BUILD.md](../extension/BUILD.md).

### Setup

1. Install / `npm run dev` + Reload Window (extension README).  
2. **Kampff: Setup** — order: `dataRoot` → `wikiRoot` → **`skillsDevRoot` = this repo**.  
3. Sites: SNS seeds or **custom URL** (`kind=generic` + `urlTemplates`). Passwords → SecretStorage only.  
4. Point python/hermes or leave auto-detect.

### Run

1. Analyze panel → site → member/thread → **Go**.  
2. Extension writes `queue/*-request.json` + prompt, spawns `run_kampff_job.py` when present under `skillsDevRoot/scripts/`.  
3. Progress via webview + Output **Kampff**.  
4. On success: open report; if `wikiRoot` set → promote.

### Boundary (extension vs Python SoT)

The UI **lives in this tree** (`extension/`). Do not reopen a sibling clone.

| Extension-only | Repo root (this SoT) |
|----------------|----------------------|
| webview, tree views, job pause/cancel UI | Python SoT for render/wiki/community_post |
| SecretStorage, `npm run dev` / VSIX | skill text, collectors, docs, harvest |
| host User settings paths | portable env + docs |

Full bridge: [vscode-bridge.md](vscode-bridge.md).

---

## Sites model (both modes)

| kind | Meaning |
|------|---------|
| `sns` | `x` · `facebook` · `instagram` · `reddit` · `linkedin` |
| `generic` | custom `baseUrl` + `urlTemplates` |

- Defaults (examples): [sites-default.json](sites-default.json)  
- Custom template: [sites-custom.example.json](sites-custom.example.json)  
- Schema: [sites.schema.json](sites.schema.json)  
- No regional board presets in product defaults. Operator personal URLs → machine settings / private overlay only.

---

## What stays private on dev

Even on private git, prefer not to treat these as “product”:

- `harvest_*`, `clien_*`, `build_mahdi_*`, real-run builders  
- `references/user-purpose.md`, board-specific login runbooks  
- Anything under `kampff-data/`

Release = **product-only copy**, never full FF. [PUBLIC_OPEN_AUDIT.md](PUBLIC_OPEN_AUDIT.md).

---

## Related index

Docs hub: [README.md](README.md) · [docs-index.md](docs-index.md).
