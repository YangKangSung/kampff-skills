# bundle.json schema

## Top level

| Field | Required | Description |
|-------|----------|-------------|
| `context` | yes | `workplace` \| `community` \| `mixed` |
| `viewer_id` | yes | 비교 기준 사람 id (보통 `me`) |
| `protocol` | no | default `spectrograph` |
| `analysis_lenses` | no | `personal`, `hr`, `osint` |
| `batch_date` | no | `YYYY-MM-DD` |
| `people` | yes | 분석 대상 (viewer 포함) |
| `collection_targets` | no | 이번 bundle에 쓰인 URL 목록 (추적용) |
| `meta` | no | `language`, `timezone` |

## people[]

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | 안정 식별자 |
| `display_name` | no | 리포트 표시명 |
| `aliases` | no | 수집 매칭용 (@handle, 이메일, 닉네임) |
| `texts` | yes | 발화 배열 |

## texts[]

| Field | Required | Description |
|-------|----------|-------------|
| `content` | yes | 본문 |
| `timestamp` | yes | ISO 8601 |
| `source` | yes | `mail` \| `meeting` \| `chat` \| `messenger` \| `wiki_page` \| `issue` \| `issue_comment` \| `pr_comment` \| `community_post` \| `community_comment` \| `sns_post` \| `sns_comment` |
| `platform` | no | `x` \| `facebook` \| `instagram` \| `reddit` \| `linkedin` \| `confluence` \| `jira` \| `github` \| `internal_web` \| `community` |
| `type` | no | `post` \| `comment` \| `reply` \| `dm` \| `thread` \| `forward` \| `repost` |
| `url` | no | **permalink** — 해당 글/댓글 URL |
| `collected_from` | no | 수집 범위 URL (targets[].url) |
| `thread_id` | no | 스레드·subreddit·게시판 글 id |
| `source_file` | no | 로컬 raw 경로 |

## collection_targets[] (optional, in bundle)

| Field | Description |
|-------|-------------|
| `url` | 수집에 사용한 URL |
| `platform` | 플랫폼 |
| `match_people` | 해당 URL에서 매칭한 id 목록 |

수집 입력 전체: [collection-targets.md](collection-targets.md)

## Daily incremental

- `inbox/YYYY-MM-DD/bundle.json` — 당일 분
- `people/{id}/history.json` — 누적
- URL 타겟은 `targets.json`으로 매일 갱신 가능