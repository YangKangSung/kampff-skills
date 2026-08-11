# Kampff architecture

Public product: **this repo** (`kampff-skills`).  
Optional UI shell: **`extension/`** in this repo (Marketplace `YangKangSung.kampff`).

## Two run modes

```text
                    ┌─────────────────────────────────────┐
                    │  kampff-skills (this tree)          │
                    │  skill · scripts · collectors · docs│
                    └───────────────┬─────────────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           ▼                                                 ▼
 ┌─────────────────────┐                          ┌──────────────────────┐
 │ A) STANDALONE       │                          │ B) VS CODE EXTENSION │
 │ CLI / agent / Python│                          │ YangKangSung.kampff        │
 └─────────────────────┘                          └──────────────────────┘
   hermes · slash /kampff                           webview Analyze · queue
   kampff-collect CLI                               jobRunner → run_kampff_job
   render_kampff_report.py                          SecretStorage sites
   wiki_store · community_post                      tree: People/Reports/Inbox
```

Same **data contract**: `KAMPFF_DATA` (+ optional `KAMPFF_WIKI`).  
The extension does **not** re-implement L1–L5 — it orchestrates this tree.

| | Standalone | VS Code |
|--|------------|---------|
| Entry | agent skill · CLI · Python scripts | Activity Bar **Kampff** · Go |
| Auth secrets | env / `KAMPFF_AUTH_DIR` / agent browser profile | Extension SecretStorage |
| Progress UI | terminal / logs | webview + Output **Kampff** |
| Job glue | you call steps (or `run_kampff_job.py`) | `run_kampff_job.py` by default |
| Sites list | `docs/sites-*.json` examples · targets.json | `kampff.sites` settings |
| Live reload | n/a | extension `npm run dev` |

Detail: [usage.md](usage.md) · [vscode-bridge.md](vscode-bridge.md).

---

## Repo layout

```text
kampff-skills/
  kampff/                 # agent skill (SKILL.md + references/)
  collectors/             # kampff-collect (SNS + custom YAML)
  docs/                   # product docs
  scripts/                # see scripts/README.md
  kampff-data/            # gitignored runtime if you create it
```

---

## Data roots

| Root | Env | Holds | Who writes |
|------|-----|--------|------------|
| **dataRoot** | `KAMPFF_DATA` | `inbox/` `queue/` `out/` | collect, jobs, render scratch |
| **wikiRoot** | `KAMPFF_WIKI` | `people/` `reports/` `Index.md` | promote / prior merge |
| **skills root** | cwd or extension `skillsDevRoot` | this git tree | you / extension spawn |

Resolution: `scripts/kampff_paths.data_root()` — **env first**, else repo-local `kampff-data/`.  
Do not commit real dumps. Doc: [dual-store-wiki.md](dual-store-wiki.md).

---

## A) Standalone execution

### A1. Agent skill (analyze)

```bash
cp -r kampff ~/.hermes/skills/kampff   # or your harness path
export KAMPFF_DATA="${KAMPFF_DATA:-$PWD/kampff-data}"
# /kampff analyze $KAMPFF_DATA/inbox/YYYY-MM-DD/bundle.json
# /kampff today
# /kampff drill 01
```

Skill reads **files only**. Spec: [../kampff/SKILL.md](../kampff/SKILL.md) · [usage.md](usage.md).

### A2. Collect CLI (optional)

```bash
# after pip install -e "./collectors[rest]"
kampff-collect catalog
kampff-collect connect setup --platform x --ref x_api
```

[prebuilt-platforms.md](prebuilt-platforms.md) · [sample-targets-sns.json](sample-targets-sns.json).

### A3. Render HTML

```bash
python scripts/render_kampff_report.py \
  -a docs/sample-analysis.json \
  -o /tmp/report.html
# --track pro|easy|both
```

### A4. Dual-store CLI

```bash
export KAMPFF_WIKI="${KAMPFF_WIKI:-$PWD/wiki}"
python scripts/wiki_store.py init-wiki --wiki "$KAMPFF_WIKI"
python scripts/wiki_store.py prior --id member_id --platform reddit --prompt
```

### A5. Job pipeline (same engine as extension)

```bash
python scripts/run_kampff_job.py <request.json> <hermes-prompt.txt> [hermes]
# success = fresh out/*-analysis.json (+ render)
```

Optional member harvest runs only if a matching `scripts/harvest_*_member.py` exists in the tree.

### A6. Synthetic smoke

```bash
# docs/drills/ · sample-analysis → render --track both
```

---

## B) VS Code extension execution

1. Install the Kampff VS Code extension (private/operator distribution).  
2. Setup: `dataRoot` · optional `wikiRoot` · **`skillsDevRoot` = this repo**.  
3. Register sites (SNS or custom URL). Passwords → SecretStorage.  
4. Analyze → Go → `run_kampff_job.py`.

Full bridge: [vscode-bridge.md](vscode-bridge.md).

| Extension-only | This repo |
|----------------|-----------|
| webview, trees, pause/cancel UI | Python SoT for render/wiki/job |
| SecretStorage, VSIX | skill, collectors, docs |

---

## Sites model

| kind | Meaning |
|------|---------|
| `sns` | `x` · `facebook` · `instagram` · `reddit` · `linkedin` |
| `generic` | custom `baseUrl` + `urlTemplates` |

[sites-default.json](sites-default.json) · [sites-custom.example.json](sites-custom.example.json) · [sites.schema.json](sites.schema.json).

---

## Out of scope here

- Regional board login harvest packs as product defaults  
- Real dossiers / tokens / host dumps  
- Extension TypeScript sources  

## Related

[README.md](README.md) · [docs-index.md](docs-index.md) · [../scripts/README.md](../scripts/README.md)
