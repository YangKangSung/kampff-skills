# Kampff run input (general)

Public skill SoT: `C:\prjs\kampff-skills`  
Template: [targets.template.json](targets.template.json) · Schema: [collection-targets.md](collection-targets.md) · Bundle: [input-schema.md](input-schema.md)

## 1) Fill this first (minimum)

| Field | What |
|-------|------|
| **Site URL** | Board / community home / profile root to collect from |
| **Target id** | Stable id used in report (`clipboard`, `user_42`, …) |
| **Target aliases** | Nick, handle, member id, email — for matching |
| **Viewer** | Usually `me` (+ optional nick) |
| **Collect axes** | posts / comments / likes (platform-dependent) |
| **Auth** | `null` guest · or `auth_ref` / agent browser profile |

## 2) `targets.json` shape

```json
{
  "batch_date": "2026-07-19",
  "viewer_id": "me",
  "context": "community",
  "analysis_lenses": ["personal", "mbti", "cia_sat"],
  "people": [
    { "id": "me", "display_name": "viewer", "aliases": [] },
    {
      "id": "TARGET_ID",
      "display_name": "Display Nick",
      "aliases": ["nick", "member_id", "@handle"]
    }
  ],
  "targets": [
    {
      "url": "https://SITE/",
      "platform": "community",
      "scope": "site",
      "collect": ["post", "comment"],
      "match_people": ["TARGET_ID"],
      "auth_ref": null,
      "query": {
        "author_display": "nick",
        "author_id": "nick_or_id",
        "max_pages": 50
      }
    }
  ],
  "meta": { "language": "ko", "timezone": "Asia/Seoul" }
}
```

Copy template:

```bash
cp docs/targets.template.json kampff-data/inbox/$(date +%Y-%m-%d)/targets.json
# edit targets.json
```

## 3) Platforms (common)

| platform | url example | query keys |
|----------|-------------|------------|
| `community` | `https://www.clien.net/service/` | `author_id`, `author_display` |
| `reddit` | `https://www.reddit.com/r/…/` | `username` / `author` |
| `x` | `https://x.com/handle` | `username` / `user_id` |
| `facebook` | Page URL | `page_id` |
| `instagram` | profile URL | `ig_user_id`, `handle` |
| `linkedin` | `file://linkedin-export` | `path` (export dir) |
| `github` | `https://github.com/org/repo` | `author_login` |
| `internal_web` | corp board URL | selectors + `author_display` |

SNS OAuth/token/export 연결:

```bash
kampff-collect connect setup --platform x|reddit|facebook|instagram|linkedin
kampff-collect connect status
```

→ [sns-connection-setup.md](sns-connection-setup.md) · sample: [sample-targets-sns.json](sample-targets-sns.json)

## 4) Pipeline

```text
targets.json  →  collect (lawful)  →  bundle.json + COLLECTION_HONESTY.md
              →  /kampff analyze   →  out/{date}-report.html  (DEFAULT)
                                   →  out/{date}-report.md    (twin)
                                   →  out/{date}-debate-ref.md (if threads)
```

Data root: env `KAMPFF_DATA` or `./kampff-data` under this repo.

```bash
cd C:/prjs/kampff-skills
export KAMPFF_DATA="C:/prjs/kampff-skills/kampff-data"
# collect using your adapters / agent scripts
# then:
# /kampff analyze $KAMPFF_DATA/inbox/YYYY-MM-DD/bundle.json
```

## 5) Honesty (mandatory for community)

| Axis | claimed | collected | full? |
|------|---------|-----------|-------|
| posts | | | |
| comments | | | |
| likes | | | |

## 6) Worked example (this run)

| File | Role |
|------|------|
| `kampff-data/inbox/2026-07-19/targets.json` | site + target input |
| `kampff-data/inbox/2026-07-19/bundle.json` | OP + target comments |
| `kampff-data/out/2026-07-19-clipboard-debate-ref.md` | **major ref** — full debate threads |
| `kampff-data/out/2026-07-19-clipboard-report.md` | Kampff report (L1–L5 + debate) |

Debate is a first-class analysis input (conflict style, alliance under fire, engage-cost), not optional flavor.
