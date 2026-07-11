# bundle.json schema

## Top level

| Field | Required | Description |
|-------|----------|-------------|
| `context` | yes | `workplace` \| `community` \| `mixed` |
| `viewer_id` | yes | 비교 기준 사람 id (보통 `me`) |
| `protocol` | no | default `spectrograph` |
| `analysis_lenses` | no | `personal`, `hr`, `osint` |
| `batch_date` | no | `YYYY-MM-DD` — 오늘 인박스 날짜 |
| `people` | yes | 분석 대상 배열 (viewer 포함) |
| `meta` | no | `language`, `timezone` |

## people[]

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | 안정 식별자 |
| `display_name` | no | 리포트 표시명 |
| `texts` | yes | 발화 배열 |

## texts[]

| Field | Required | Description |
|-------|----------|-------------|
| `content` | yes | 본문 |
| `timestamp` | yes | ISO 8601 |
| `source` | yes | `mail` \| `meeting` \| `chat` \| `messenger` \| `community_post` \| `community_comment` \| `sns_post` \| `sns_comment` |
| `type` | no | `post` \| `comment` \| `reply` \| `dm` \| `thread` \| `forward` |
| `thread_id` | no | 스레드·게시글 묶음 |
| `source_file` | no | 원본 경로 (예: `raw/mail/msg_001.eml`) |
| `url` | no | 공개 URL (community/sns) |

## Daily incremental

같은 `id`에 대해 매일 `texts`를 append. 수집기가:

- `inbox/YYYY-MM-DD/bundle.json` — 그날 분량만, 또는
- `people/{id}/history.json` — 누적 + skill이 merge

skill 실행 시 **누적본 우선**이면 에이전트가 `people/*/history.json`을 읽어 하나의 bundle로 합친 뒤 분석.