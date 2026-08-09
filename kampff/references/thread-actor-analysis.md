# Thread actor analysis (reply network · intent · coordination)

## Modes

| Mode | Unit | Question |
|------|------|----------|
| `seed` | one post | who spoke here, local intent |
| **`cohort` (optional depth)** | seed actors across their other posts/comments | relations, co-appearance, time |
| `member` | one person long arc | full Kampff dossier (separate) |

Seed-only is weak for organization/intent. Expand cohort only when the operator has a **lawful session** and site-specific collectors (not shipped as regional presets here).

## Trigger

```text
/kampff thread {post_url}
/kampff thread {post_url} --depth cohort
/kampff actors {post_url}
```

## Inputs

```json
{
  "url": "https://forum.example/t/12345",
  "platform": "generic",
  "focus_comment_id": null,
  "depth": "seed",
  "max_actors": 30,
  "max_pages_per_actor": 3,
  "boards": [],
  "since": null,
  "until": null,
  "analysis": ["actors", "intent", "network", "coordination", "temporal", "cross_thread"]
}
```

Use **synthetic or operator-owned URLs** in docs and tests. Do not hard-code third-party board origins in the public tree.

## Pipeline

```text
seed post_url (+ saved HTML or lawful fetch)
  → thread.json (OP + comments + directed @replies)
  → actor roster (author_id, nick)
  → [cohort, optional] site-specific expand via operator collectors
  → directed multigraph + temporal layers
  → out/{date}-thread-{id}-actors.html
  → .md twin · .json machine
```

### Public runner

| | |
|--|--|
| Spec | this file |
| Runner | `scripts/thread_actor_analyze.py` (seed HTML/URL → graph) |
| Cohort expand | **not** shipped as a site-locked script; implement against `docs/sites-custom.example.json` / private collectors |

## Directed reply network (**required**)

Edges are **directed**. Never undirected-only.

| Edge type | Direction | Meaning |
|-----------|-----------|---------|
| `reply_to` | **A → B** | A’s comment mentions/replies to B (`@B`) |
| `op_address` | **A → OP** | A addresses OP author |
| `cross_thread_reply` | **A → B** | A replies to B on a **non-seed** thread both appear in |
| `co_comment` | store as optional undirected `co_presence` | same thread, no @ — **not** a reply edge |

### Display rules (HTML)

- Arrow **A → B** = A acted toward B
- Node size ∝ activity
- Edge thickness ∝ count of directed events
- Legend: “arrow points to **target** of reply”

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
      "thread_url": "https://forum.example/t/12345",
      "comment_id": "c1",
      "timestamp": "2026-07-19T12:01:00+09:00",
      "weight": 1
    }
  ]
}
```

Aggregate: `weight` = number of directed events A→B (optionally by type).

## Ethics

- Lawful text only. No stalking, no bulk third-party harvest without explicit scope.
- Output is **signals + graph**, not a guilt verdict.
- Prefer synthetic drills under `docs/drills/` for demos.
