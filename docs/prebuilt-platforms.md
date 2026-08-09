# Prebuilt platforms

Product surface: **famous SNS only**.  
Everything else is **custom URL** (register `baseUrl` + `urlTemplates`) or a private `_template.yaml` fork — not a shipped preset.

## SNS (prebuilt)

| id | 이름 | transport | 비고 |
|----|------|-----------|------|
| `x` | X | rest | API v2 · `connect setup --platform x` |
| `facebook` | Facebook | rest/file | Graph Page token 또는 data download |
| `instagram` | Instagram | rest/file | Business Graph 또는 export |
| `reddit` | Reddit | rest | OAuth · `connect setup --platform reddit` |
| `linkedin` | LinkedIn | file | member export · `connect setup --platform linkedin` |

**Connection setup:** [sns-connection-setup.md](sns-connection-setup.md)

```bash
kampff-collect connect list
kampff-collect connect setup --platform x --ref x_api
kampff-collect connect status
```

Catalog SoT: `collectors/platforms/catalog.yaml`

## Custom URL (not prebuilt)

No regional board pack ships in this tree. Operator brings the origin.

1. **Sites config** (extension / JSON) — preferred for Analyze dropdown  
   - Schema: [sites.schema.json](sites.schema.json)  
   - SNS seeds: [sites-default.json](sites-default.json)  
   - Custom example: [sites-custom.example.json](sites-custom.example.json)

```json
{
  "id": "my_forum",
  "label": "My forum",
  "baseUrl": "https://forum.example",
  "loginUrl": "https://forum.example/login",
  "kind": "generic",
  "enabled": true,
  "urlTemplates": {
    "profile": "{baseUrl}/u/{handle}",
    "member": "{baseUrl}/member/{id}",
    "post": "{baseUrl}/t/{id}",
    "searchAuthor": "{baseUrl}/search?author={id}"
  }
}
```

Placeholders: `{baseUrl}` `{id}` `{handle}` `{username}`.

2. **Collector YAML** (optional deep adapter)  
   - Copy `collectors/platforms/_template.yaml` → `platforms/my_forum.yaml`  
   - `prebuilt: false`  
   - No need to edit `catalog.yaml`

```json
{
  "platform": "generic",
  "url": "https://forum.example/u/alice",
  "scope": "profile",
  "collect": ["post", "comment"],
  "match_people": ["target_id"],
  "query": {
    "base_url": "https://forum.example",
    "author_id": "alice",
    "profile_template": "{baseUrl}/u/{handle}"
  }
}
```

## Not in product catalog

Workplace packs (Jira, Slack, …), RSS, Maigret, intranet crawl YAMLs may still exist as files for private experiments — they are **not** product prebuilts. Do not re-add Korean community origins to defaults.

## kampff skill

Prebuilt vs custom does not change analyze output shape — always the same `bundle.json` / analysis contract.
