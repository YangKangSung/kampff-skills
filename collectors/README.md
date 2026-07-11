# kampff-collect (generic)

**플랫폼별 코드 X → `platforms/*.yaml` + transport 3종**

| transport | adapter |
|-----------|---------|
| `rest` | Confluence, Jira, GitHub, any API |
| `playwright` | 사내 웹 (SSO) |
| `file` | export / eml / dump |

## Add a system (no fork)

1. Copy `platforms/_template.yaml` → `platforms/your_portal.yaml`
2. Set `transport`, `selectors` or `endpoints` + `mapping`
3. `targets.json` → `"platform": "your_portal"`

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