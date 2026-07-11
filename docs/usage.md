# kampff 사용법

수집은 **별도 logic**. skill/agent는 **정규화된 입력 파일**만 읽는다.

## 호출 방법 (3가지)

### 1) 슬래시 + 파일 경로 (가장 흔함)

```text
/kampff analyze D:\data\kampff\inbox\2026-07-11\bundle.json
```

```text
/kampff
bundle: D:\data\kampff\inbox\2026-07-11\bundle.json
lenses: personal, hr
viewer: me
```

### 2) 오늘 인박스 (매일 자동 적재 가정)

```text
/kampff today
```

에이전트 동작:

1. `{KAMPFF_DATA}/inbox/{YYYY-MM-DD}/bundle.json` 존재 확인
2. 없으면 `{KAMPFF_DATA}/inbox/{YYYY-MM-DD}/raw/` 아래 소스 파일을 읽어 **임시 정규화** 후 분석
3. 결과 → `{KAMPFF_DATA}/out/{YYYY-MM-DD}-report.md`

기본 데이터 루트: `KAMPFF_DATA` 환경변수, 없으면 `./kampff-data`

### 3) 특정 사람만 갱신

```text
/kampff person user_42 --bundle D:\data\kampff\inbox\2026-07-11\bundle.json
```

기존 `people/user_42/history.json` 과 병합 후 ephemeris(L5) 강조.

---

## 디렉터리 레이아웃 (권장)

```
kampff-data/
├── inbox/                      # 매일 수집기가 채움
│   └── 2026-07-11/
│       ├── bundle.json         # ★ skill이 우선 읽는 파일
│       └── raw/                # 수집기 원본 (선택)
│           ├── mail/
│           ├── meeting/
│           ├── chat/
│           ├── messenger/
│           ├── community/
│           └── sns/
├── people/                     # 누적 저장 (선택)
│   ├── me/
│   │   └── history.json
│   └── user_42/
│       └── history.json
└── out/
    └── 2026-07-11-report.md    # skill 출력
```

**매일 흐름**

1. 수집 logic → `inbox/오늘/raw/` 또는 바로 `bundle.json`
2. 사용자 또는 cron: `/kampff today`
3. 리포트 확인 → `out/`

---

## 소스 종류 (`source` 필드)

| source | 예시 |
|--------|------|
| `mail` | 이메일 본문·인용 |
| `meeting` | 회의록, AI 회의 요약 |
| `chat` | Slack/Teams 채널, DM export |
| `messenger` | 사내 메신저 |
| `community_post` | 사내/외부 게시판 글 |
| `community_comment` | 게시판 댓글 |
| `sns_post` | SNS 본문 |
| `sns_comment` | SNS 댓글·리플 |

`type` (발화 형태): `post` | `comment` | `reply` | `dm` | `thread` | `forward`

---

## bundle.json 최소 규칙

- `people[].id` — 안정 ID (이메일 해시, 사번, 닉네임 slug)
- **viewer는 반드시 포함** (`viewer_id`와 동일한 `id`)
- `texts[].timestamp` — ISO 8601 (시계열 필수)
- `texts[].source` — 위 표 중 하나
- `texts[].content` — 분석 본문
- 선택: `source_file` — 원본 파일 경로 (추적용)

전체 스키마: [input-schema.md](input-schema.md) · 예시: [sample-input.json](sample-input.json)

---

## 수집기 → bundle 변환 (별도 logic 책임)

skill은 변환 로직을 **포함하지 않음**. 수집기가:

1. mail/meeting/chat/messenger/community/sns export 파싱
2. 작성자 식별 → `people[].id` 매핑
3. 일별 append → `bundle.json` 또는 `people/*/history.json`

에이전트는 `raw/`만 있을 때 **최소한의 읽기**는 가능하나, 운영에서는 **항상 bundle.json 생성**을 권장.

---

## 출력

- 기본: `out/{date}-report.md` (매트릭스 + 인물별 dossier)
- 요청 시: `out/{date}-matrix.json` (기계 판독용)

---

## 설치

```bash
cp -r kampff ~/.grok/skills/kampff
# optional
setx KAMPFF_DATA "D:\data\kampff"
```