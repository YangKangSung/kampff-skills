# Prebuilt platforms

유명 시스템은 **`collectors/platforms/{id}.yaml`** 로 미리 제공.  
조직마다 다른 건 **`query` / selector override** 만 — 새 YAML fork 불필요.

## Workplace & dev

| id | 이름 | transport | 인증 |
|----|------|-----------|------|
| `jira` | Jira | rest | atlassian |
| `confluence` | Confluence | rest | atlassian |
| `github` | GitHub / GHE | rest | github token |
| `gitlab` | GitLab | rest | bearer |
| `slack` | Slack | rest | bot token |
| `notion` | Notion | rest | integration token |
| `microsoft_graph` | Teams / M365 | rest | azure app |
| `internal_web` | 사내 웹 (SSO) | playwright | storage_state |

## SNS & public

| id | 이름 | transport | 비고 |
|----|------|-----------|------|
| `x` | X | rest | API v2 |
| `reddit` | Reddit | rest | OAuth |
| `linkedin` | LinkedIn | file | member export |
| `rss` | RSS/Atom | rest | 블로그·공지 |
| `maigret` | Maigret username map | **cli** (optional) | 계정 존재·URL 확장만. 본문 수집 아님. `scripts/expand_handles_maigret.py` · [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md) |

## Export / file packs

| id | 이름 | transport |
|----|------|-----------|
| `discord` | Discord | file (data export) |
| `google_workspace` | Gmail Takeout | file (.mbox) |

전체 목록: `kampff-collect catalog`

## 사용 예

```json
{
  "platform": "slack",
  "url": "https://slack.com/api",
  "scope": "channel:C012345",
  "collect": ["message"],
  "match_people": ["user_42"],
  "auth_ref": "slack_bot",
  "query": { "channel_id": "C012345", "oldest": "1704067200" }
}
```

```json
{
  "platform": "internal_web",
  "url": "https://portal.company.local/board",
  "scope": "board",
  "collect": ["post", "comment"],
  "auth_ref": "corp_sso",
  "query": { "author": "김OO", "content_selector": ".post-body" }
}
```

## Custom

목록에 없으면:

1. 가장 가까운 prebuilt 복사 (예: `internal_web` ← 사내 게시판)
2. 또는 `platforms/_template.yaml` → `platforms/my_crm.yaml`
3. `catalog.yaml` 에는 등록 안 해도 됨 — `platforms/my_crm.yaml` 만 있으면 동작

## kampff skill

Prebuilt 여부와 무관 — 출력은 항상 동일 `bundle.json`.