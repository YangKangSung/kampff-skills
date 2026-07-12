# collection targets (수집 logic 스펙)

skill **밖** — 수집기가 URL·검색 조건을 읽고 `bundle.json`을 만든다.

## targets.json

`kampff-data/inbox/{date}/targets.json` 또는 `kampff-data/config/targets.json`

```json
{
  "batch_date": "2026-07-11",
  "viewer_id": "me",
  "people": [
    {
      "id": "me",
      "aliases": ["@myhandle", "홍길동", "me@company.com"]
    },
    {
      "id": "user_42",
      "aliases": ["@their_x", "김OO", "user42"]
    }
  ],
  "targets": [
    {
      "url": "https://www.reddit.com/r/example/",
      "platform": "reddit",
      "scope": "subreddit",
      "collect": ["post", "comment"],
      "match_people": ["user_42"],
      "search": {
        "author": "@their_x",
        "query": null
      }
    },
    {
      "url": "https://x.com/their_x",
      "platform": "x",
      "scope": "profile",
      "collect": ["post", "reply"],
      "match_people": ["user_42"]
    },
    {
      "url": "https://internal.company.com/board/team-a",
      "platform": "community",
      "scope": "board",
      "collect": ["post", "comment"],
      "match_people": ["me", "user_42"],
      "search": {
        "author_display": "김OO"
      }
    }
  ],
  "meta": { "since": "2025-01-01", "until": null }
}
```

## targets[] 필드

| Field | Required | Description |
|-------|----------|-------------|
| `url` | yes | 수집 시작 URL (게시판, subreddit, 프로필, 글 Permalink) |
| `platform` | yes | 아래 플랫폼 표 |
| `scope` | yes | 플랫폼별 범위 |
| `collect` | yes | 수집 유형 (플랫폼별) |
| `match_people` | yes | 이 URL에서 긁을 `people[].id` 목록 |
| `auth_ref` | no | `KAMPFF_AUTH_DIR` 인증 프로필 (사내 필수) |
| `search` | no | 플랫폼별 검색·필터 |
| `playwright` | no | `internal_web` 전용 — selectors, storage_state |

### platform

**외부:** `x` · `facebook` · `instagram` · `reddit` · `linkedin` · `community`  
**사내:** `internal_web` (Playwright) · `confluence` · `jira` · `github`

상세: [collectors.md](collectors.md)

## search (플랫폼별)

| platform | search 필드 | 동작 |
|----------|-------------|------|
| `x` | `author` (handle) | 프로필 타임라인·리플 |
| `reddit` | `author`, `query` | author= u/name 글·댓글; query= subreddit 내 키워드+author 교차 |
| `facebook` | `author_display`, `profile_url` | 페이지/그룹 URL + 작성자 표시명 |
| `instagram` | `handle` | 캡션·댓글 (본인 export/API 범위) |
| `community` | `author_display`, `author_id` | 사내 게시판 (API 있을 때) |
| `internal_web` | `author_display` | Playwright DOM 검색·페이지네이션 |
| `confluence` | `cql`, `contributor` | CQL / REST |
| `jira` | `jql` | JQL issues + comments |
| `github` | `author_login`, `since` | issues, PRs, reviews |

## 수집기 파이프라인

```
targets.json
    → adapter 선택 (API vs Playwright)
    → URL별 fetch
    → aliases로 작성자 매칭
    → texts[] 정규화
    → bundle.json + raw/snapshots/
```

사내: [collectors.md](collectors.md) — SSO, allowlist, `--no-egress`

## bundle에 남길 URL 필드

수집된 각 발화:

```json
{
  "content": "...",
  "timestamp": "...",
  "source": "sns_comment",
  "platform": "reddit",
  "url": "https://reddit.com/r/example/comments/abc/...",
  "type": "comment",
  "thread_id": "r/example/post_abc",
  "collected_from": "https://www.reddit.com/r/example/"
}
```

- `url` — 해당 글·댓글 permalink (kampff 인용·검증)
- `collected_from` — targets[].url (어떤 범위에서 수집했는지)

## 사용자 호출 (수집 → 분석)

```text
/kampff collect --targets $KAMPFF_DATA/inbox\2026-07-11\targets.json
/kampff analyze $KAMPFF_DATA/inbox\2026-07-11\bundle.json
```

또는 한 번에:

```text
/kampff run --targets ...\targets.json
```

(`collect`는 **별도 수집 스크립트**; skill은 `bundle`만 분석)

## 법·ToS

- URL 수집은 **API·export·권한 있는 범위**만
- 로그인 필요 사이트는 사용자 자격증명·export 전제
- skill/kampff는 **이미 수집된** bundle만 분석