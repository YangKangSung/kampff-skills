# collectors — 수집기 아키텍처

> **Generic first:** [collectors-generic.md](collectors-generic.md) — 플랫폼 = YAML, transport 3종만.

kampff **skill 밖**. 구현: `collectors/kampff_collect/`

```
targets.json  →  collector CLI  →  adapter(platform)  →  bundle.json
                      │
                      ├─ API (GitHub, Jira, Confluence REST)
                      └─ Playwright (사내 웹, API 없는 게시판)
```

## CLI (예정)

```bash
kampff-collect --targets inbox/2026-07-11/targets.json --out inbox/2026-07-11/bundle.json
```

환경:

| Env | 용도 |
|-----|------|
| `KAMPFF_DATA` | 데이터 루트 |
| `KAMPFF_AUTH_DIR` | 인증 파일 (gitignore) |
| `GITHUB_TOKEN` | GitHub API |
| `JIRA_EMAIL` + `JIRA_API_TOKEN` | Jira Cloud/DC REST |
| `CONFLUENCE_EMAIL` + `CONFLUENCE_API_TOKEN` | Confluence REST |
| `PLAYWRIGHT_STORAGE_STATE` | 로그인 세션 JSON 경로 |

**targets.json에 비밀번호·토큰 넣지 않음** — `auth_ref`만 참조.

---

## 어댑터 목록

| platform | 방식 | 사내 적합 |
|----------|------|-----------|
| `internal_web` | **Playwright** | ⭐ API 없는 사내 게시판·포털 |
| `confluence` | REST API (+ Playwright fallback) | 위키·댓글 |
| `jira` | REST API (JQL) | 이슈·댓글·changelog 발화 |
| `github` | REST/GraphQL | 이슈·PR·리뷰·discussion |
| `messenger` | Playwright / export | 사내 메신저 |
| `x` · `reddit` · … | API/export | 외부 SNS |

---

## Playwright (`internal_web`)

**언제:** 사내 URL, SSO 로그인, 공개 API 없음, 보안팀이 **브라우저 자동화만 허용**할 때.

```json
{
  "url": "https://portal.company.local/community/team",
  "platform": "internal_web",
  "scope": "board",
  "collect": ["post", "comment"],
  "match_people": ["user_42"],
  "auth_ref": "corp_sso",
  "playwright": {
    "storage_state": "%KAMPFF_AUTH_DIR%/corp_sso/state.json",
    "headless": true,
    "selectors": {
      "post_list": "[data-testid=post-item]",
      "post_author": ".author-name",
      "post_body": ".post-content",
      "post_time": "time",
      "comment_thread": ".comments"
    },
    "search": {
      "author_display": "김OO",
      "max_pages": 20
    }
  }
}
```

**보안 관행**

- 수집기는 **사내망/VPN**에서만 실행
- `storage_state`·스크린샷은 `raw/` 로컬, **외부 업로드 금지** 옵션 (`--no-egress`)
- 도메인 allowlist: `targets.json`의 `url` host만 방문
- kampff 분석도 **온프렘** 에이전트에서 bundle만 읽기

**초기 로그인 (1회)**

```bash
kampff-collect auth login --ref corp_sso --url https://portal.company.local
# 브라우저 수동 SSO → state.json 저장
```

---

## Confluence

**API 우선** (Atlassian REST).

```json
{
  "url": "https://wiki.company.com/wiki/spaces/ENG",
  "platform": "confluence",
  "scope": "space",
  "collect": ["wiki_page", "comment"],
  "match_people": ["user_42"],
  "auth_ref": "confluence_prod",
  "search": {
    "cql": "type in (page,blogpost) AND creator = \"kim.oo@company.com\"",
    "contributor": "kim.oo@company.com"
  }
}
```

| scope | 수집 대상 |
|-------|-----------|
| `space` | 스페이스 내 페이지·블로그 |
| `page` | 단일 페이지 + footer comments |
| `cql` | CQL 결과 집합 |

bundle 매핑: `source: wiki_page` | `community_comment`, `platform: confluence`

---

## Jira

**JQL**로 이슈·댓글·(선택) changelog 요약.

```json
{
  "url": "https://jira.company.com/browse/PROJ",
  "platform": "jira",
  "scope": "project",
  "collect": ["issue", "comment"],
  "match_people": ["user_42"],
  "auth_ref": "jira_prod",
  "search": {
    "jql": "project = PROJ AND (reporter = user42 OR assignee = user42) ORDER BY updated DESC",
    "include_changelog": false
  }
}
```

| collect | bundle |
|---------|--------|
| `issue` | description + summary → `source: issue` |
| `comment` | comment body → `source: issue_comment` |

`platform: jira`, `url`: `https://jira.../browse/KEY-123`

---

## GitHub (사내 GitHub Enterprise 포함)

```json
{
  "url": "https://github.company.com/org/team-repo",
  "platform": "github",
  "scope": "repo",
  "collect": ["issue", "issue_comment", "pr_comment", "discussion"],
  "match_people": ["user_42"],
  "auth_ref": "github_enterprise",
  "search": {
    "author_login": "user42corp",
    "since": "2025-01-01"
  }
}
```

| scope | 수집 |
|-------|------|
| `repo` | issues, PRs, reviews, discussions |
| `org` | org-wide search (권한 필요) |
| `user` | `https://github.com/user42` 활동 |

bundle: `source: issue` | `issue_comment` | `pr_comment`, `platform: github`

---

## people[].aliases — 사내 매칭

한 사람에 여러 계정 매핑:

```json
{
  "id": "user_42",
  "aliases": [
    "김OO",
    "kim.oo@company.com",
    "user42corp",
    "jira_account_id:712020:xxx",
    "confluence:kmoo"
  ]
}
```

어댑터는 `aliases`로 작성자 필드 매칭.

---

## auth_ref (`KAMPFF_AUTH_DIR/auth.json` 예)

```json
{
  "confluence_prod": { "type": "atlassian", "base_url": "https://wiki.company.com" },
  "jira_prod": { "type": "atlassian", "base_url": "https://jira.company.com" },
  "github_enterprise": { "type": "github", "api_url": "https://github.company.com/api/v3" },
  "corp_sso": { "type": "playwright", "allowed_hosts": ["portal.company.local"] }
}
```

토큰은 **환경변수** 또는 OS secret store.

---

## source · platform 매핑 (bundle)

| platform | source | type |
|----------|--------|------|
| confluence | `wiki_page` | `post` |
| confluence | `community_comment` | `comment` |
| jira | `issue` | `post` |
| jira | `issue_comment` | `comment` |
| github | `issue` | `post` |
| github | `issue_comment` / `pr_comment` | `comment` |
| internal_web | `community_post` / `community_comment` | `post` / `comment` |

---

## 파이프라인 (매일)

```
1. targets.json (URL + JQL/CQL + people)
2. kampff-collect --targets ... --out bundle.json
3. /kampff analyze bundle.json
```

## 레포 구조 (수집기 구현 시)

```
collectors/
├── README.md
├── cli.py
└── adapters/
    ├── playwright_web.py
    ├── confluence.py
    ├── jira.py
    └── github.py
```

구현은 **별도 패키지** `kampff-collect` 권장 — skill 레포는 SKILL + 스펙만 유지.