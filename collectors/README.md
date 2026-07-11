# kampff-collect (generic)

**플랫폼별 코드 X → `platforms/*.yaml` + transport 3종**

| transport | adapter |
|-----------|---------|
| `rest` | Confluence, Jira, GitHub, any API |
| `playwright` | 사내 웹 (SSO) |
| `file` | export / eml / dump |

## Prebuilt (유명 플랫폼)

```bash
kampff-collect catalog
kampff-collect catalog --tags workplace
kampff-collect show jira
```

Jira · Confluence · GitHub · GitLab · Slack · Notion · Teams/Graph · X · Reddit · LinkedIn export · Discord export · Playwright 사내웹 · RSS …

→ [docs/prebuilt-platforms.md](../docs/prebuilt-platforms.md)

## Custom (no fork)

1. Copy nearest prebuilt or `platforms/_template.yaml`
2. `targets.json` → `"platform": "your_id"`

## CLI

```bash
cd collectors
pip install -e ".[all]"
playwright install chromium

kampff-collect platforms
kampff-collect collect --targets ../kampff-data/inbox/2026-07-11/targets.json --out ../kampff-data/inbox/2026-07-11/bundle.json
```

Adapters are **stubs** until REST/Playwright mapping engine is wired — architecture is generic.

Design: [docs/collectors-generic.md](../docs/collectors-generic.md)