# Thread actor analysis (댓글 네트워크 · 의도 · 조직성 · **횡단·시간**)

## Modes

| Mode | Unit | Question |
|------|------|----------|
| `seed` | one post | who spoke here, local intent |
| **`cohort` (default depth)** | seed actors **across** their other posts/comments | relations, co-appearance, **time** |
| `member` | one person long arc | full Kampff dossier (separate) |

**Important:** seed-only is not enough for organization/intent. Always expand cohort when login allows.

## Trigger

```text
/kampff thread {post_url}
/kampff thread {post_url} --depth cohort
/kampff actors {post_url}
스레드 분석 / 댓글 네트워크 / 조직성 / 횡단 추적 / 시간 추적
```

## Inputs

```json
{
  "url": "https://www.clien.net/service/board/park/19230278",
  "platform": "community",
  "focus_comment_id": "151990173",
  "depth": "cohort",
  "max_actors": 30,
  "max_pages_per_actor": 3,
  "boards": ["park"],
  "since": null,
  "until": null,
  "analysis": ["actors", "intent", "network", "coordination", "temporal", "cross_thread"]
}
```

## Pipeline

```text
seed post_url
  → seed thread.json (OP + comments + directed @replies)
  → actor roster (author_id, nick)
  → [cohort] for each actor:
        writer search  → their posts
        commenter search → threads they commented
        sample fetch bodies/times when needed
  → unify event log (timestamped)
  → directed multigraph + co-thread + temporal layers
  → out/{date}-thread-{id}-actors.html   ← DEFAULT
  → .md twin · .json machine
```

Clien adapters (login):

- writer: `/service/search/v2/board/{board}?sk=id&sv={author_id}`
- commenter: `/service/search/v2/board/{board}?sk=commenter&sv={author_id}`

## Directed reply network (**required**)

Edges are **directed**. Never undirected-only.

| Edge type | Direction | Meaning |
|-----------|-----------|---------|
| `reply_to` | **A → B** | A’s comment mentions/replies to B (`@B`) |
| `op_address` | **A → OP** | A addresses OP author |
| `cross_thread_reply` | **A → B** | A replies to B on a **non-seed** thread both appear in |
| `co_comment` | A ↔ B (store as **two** optional undirected link type `co_presence`, separate from reply) | same thread, no @ — **not** a reply edge |

### Display rules (HTML)

- Arrow **A → B** = A acted toward B  
- Node size ∝ activity  
- Edge thickness ∝ count of directed events  
- Toggle/filter by edge type  
- Legend must say: “arrow points to **target** of reply”

### Machine schema

```json
{
  "edges": [
    {
      "from_id": "alice",
      "to_id": "bob",
      "from_nick": "Alice",
      "to_nick": "Bob",
      "type": "reply_to",
      "thread_url": "https://…/park/19230278",
      "comment_id": "151990003",
      "timestamp": "2026-07-19T12:01:00+09:00",
      "weight": 1
    }
  ]
}
```

Aggregate: `weight` = number of directed events A→B (optionally by type).

## Cross-thread relations

| Signal | Definition |
|--------|------------|
| `co_thread_count` | distinct non-seed threads where both actors left text |
| `shared_targets` | same OP authors they both engage |
| `recurring_reply_pair` | A→B appears on ≥2 threads |
| `one_way_hunter` | A→B high, B→A ~0 across time |
| `mutual_persistent` | A↔B across multiple days/threads |

## Temporal layer (**required**)

Event log (sorted):

```text
{ts, actor_id, event: post|comment|reply, thread_id, target_id?, url}
```

| View | Use |
|------|-----|
| Timeline per actor | burst vs steady |
| Pair timeline | when A→B edges fire |
| Seed burst window | comments in first N minutes (if ts density) |
| Rolling co-appearance | weekly/monthly heat |

Coordination temporal signals:

- near-simultaneous first comments (same stance)  
- A always replies within short lag after B  
- synchronized phrase debut across accounts  

## Intent / malice (unchanged hygiene)

Per seed comment + optional cohort sample. Labels are **signals**, not verdicts.

## Coordination score inputs (expanded)

| Signal | Weight |
|--------|--------|
| Near-duplicate text across accounts | high |
| Recurring directed clique A→B→C on many threads | high |
| Mutual persistent pairs + aligned stance | medium |
| Burst timing lockstep | medium |
| Shared attack frame | medium–high |
| Independent phrasing + diverse intent | **anti** |

## Outputs

| File | Role |
|------|------|
| `{date}-thread-{board}_{sn}-actors.html` | **default** — directed graph, temporal, cohort table |
| `.md` | twin |
| `.json` | full graph + events |
| `cohort/` raw | per-actor index HTML/json |

## Honesty

| Field | Required |
|-------|----------|
| seed comments UI vs parsed | yes |
| cohort depth | seed_only / partial / expanded |
| actors expanded / capped | yes |
| login vs guest | yes |
| time fields missing? | yes |

## Refuse

Off-platform stalking, doxx, weaponized “destroy user” ops, illegal collection.
