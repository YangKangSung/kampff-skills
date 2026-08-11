# Build Kampff VS Code extension (in-repo)

This folder is the **product** extension shell for Marketplace  
`YangKangSung.kampff`. Skill/CLI/scripts live one level up (`../`).

```text
kampff-skills(-dev)/
  extension/     ← this package (vsce)
  kampff/        ← agent skill
  scripts/       ← run_kampff_job, render, …
  collectors/
```

## Build VSIX

```bash
cd extension
# Hermes/agent shells often set NODE_ENV=production — force dev deps
export NODE_ENV=development
npm ci
npm run lint
npm run compile
npx @vscode/vsce package --no-dependencies
# → extension/kampff-0.9.x.vsix   (gitignored; build artifact)
```

Publish (publisher must exist: `YangKangSung`):

```bash
export VSCE_PAT='…'   # Marketplace Manage scope; never commit
npx @vscode/vsce publish -p "$VSCE_PAT"
```

Or Manage UI: upload the VSIX from **this** directory only.

## Operator setup

`kampff.skillsDevRoot` = **parent** of `extension/` (repo root), not this folder.

Daily private SoT remains `kampff-skills-dev`. Public window: `kampff-skills`.
