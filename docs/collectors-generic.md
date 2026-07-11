# Generic collector design

**원칙:** 플랫폼마다 코드 fork 금지. **설정(platform YAML) + transport 2종** 만 확장.

```
targets.json
    → pipeline (generic)
        → resolve platform config (platforms/*.yaml)
        → pick transport: rest | playwright | file
        → normalize → bundle.json
```

## Transport (3개만 유지)

| transport | 용도 | 설정 키 |
|-----------|------|---------|
| `rest` | Confluence, Jira, GitHub, any OpenAPI | `endpoints`, `mapping`, `pagination` |
| `playwright` | 사내 웹, API 없음, SSO | `selectors`, `navigation`, `pagination` |
| `file` | export ZIP, .eml, Slack dump | `glob`, `parser` |

새 사내 시스템 = **YAML 추가** (+ 필요 시 `parser` 플러그인 1개). skill/kampff 무변경.

## targets.json (generic)

```json
{
  "people": [{ "id": "user_42", "aliases": ["kim.oo@company.com", "user42"] }],
  "targets": [
    {
      "platform": "jira",
      "url": "https://jira.example.com",
      "scope": "project:PROJ",
      "collect": ["issue", "comment"],
      "match_people": ["user_42"],
      "auth_ref": "atlassian",
      "query": {
        "jql": "project = PROJ AND updated >= 2025-01-01"
      }
    },
    {
      "platform": "internal_web",
      "url": "https://portal.example.local/board",
      "scope": "board",
      "collect": ["post", "comment"],
      "match_people": ["user_42"],
      "auth_ref": "sso",
      "query": { "author": "김OO" }
    }
  ]
}
```

- `platform` → `platforms/{platform}.yaml` 로드
- `url` → base or entry point (YAML이 해석)
- `scope` · `collect` · `query` → **문자열 자유** (YAML template에 치환)
- 플랫폼 고유 필드는 `query` 안에만

## platform YAML (예: `platforms/jira.yaml`)

```yaml
id: jira
label: Atlassian Jira
transport: rest
auth: atlassian
base_url_from: target.url

capabilities:
  - issue
  - comment

scopes:
  - "project:{key}"
  - "issue:{key}"

collect_types:
  issue:
    source: issue
    type: post
  comment:
    source: issue_comment
    type: comment

endpoints:
  search:
    method: GET
    path: /rest/api/3/search
    params:
      jql: "{{ query.jql }}"
      maxResults: 100

mapping:
  issue:
    content: "{{ fields.summary }}\n\n{{ fields.description }}"
    author: "{{ fields.reporter.displayName }}"
    author_email: "{{ fields.reporter.emailAddress }}"
    timestamp: "{{ fields.updated }}"
    url: "{{ base_url }}/browse/{{ key }}"
    thread_id: "{{ key }}"
  comment:
    list_path: fields.comment.comments
    content: "{{ body }}"
    author: "{{ author.displayName }}"
    timestamp: "{{ created }}"
```

`{{ }}` = generic template engine (Jinja2-style).

## Playwright generic (`platforms/_playwright_base.yaml` merge)

```yaml
transport: playwright
navigation:
  entry: "{{ target.url }}"
  item_link: "{{ item.url_attr }}"
pagination:
  strategy: click_next
  next_selector: "a.next"
selectors:
  item: "article.post"
  fields:
    content: ".body"
    author: ".author"
    timestamp: "time[datetime]"
filters:
  author_matches: "{{ query.author }}"  # against people.aliases
```

사내 게시판마다 **selectors만 오버라이드** 한 `platforms/portal_acme.yaml`.

## Normalizer (공통)

모든 transport 출력 → 동일 `TextItem`:

```json
{
  "content": "...",
  "timestamp": "ISO8601",
  "source": "...",
  "platform": "...",
  "type": "...",
  "url": "...",
  "collected_from": "...",
  "thread_id": "..."
}
```

→ `people[].texts[]` 에 aliases 매칭 후 append.

## Auth (generic)

`auth_ref` → `auth/{ref}.yaml` (비밀 없음) + env:

```yaml
type: atlassian  # rest | bearer | basic | playwright_storage
env:
  email: JIRA_EMAIL
  token: JIRA_API_TOKEN
```

## 확장 절차

1. `platforms/foo.yaml` 추가
2. `capabilities` / `endpoints` or `selectors` 정의
3. targets.json 에 `"platform": "foo"` — **코드 변경 없음** (transport 기존)

## kampff skill 경계

- collector: generic pipeline + config
- kampff: `bundle.json` 만 — platform 이름 무관