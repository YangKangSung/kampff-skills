# Relation graph (Layer 2)

One-person Kampff stays the **Distance Desk / dossier**.  
This page is the **board**: people as nodes, observed ties as edges, coordination as a *hypothesis* overlay.

```text
ID + harvest HTML  (posts / comments / likes on that id)
    │
    ▼
build_relation_bundle.py --seed {id}  →  relation bundle
    │
bundle.json  (many people, same threads)
    │
    ▼
build_kampff_graph.py [--seed {id}]  →  graph.json
    │
    ├─ nodes  ← optional join of L1 distance from *-analysis.json
    └─ edges  ← replies / co-thread / burst / near-dup / likes
    │
    ▼
render_kampff_graph.py  →  *-graph.html
    filter by relation level · thickness = weight · color = level
```

**Ego (one id):** type an id, then Graph. Nodes are that person plus IDs on their **posts**, **comments**, and **likes** (if liker ids were in the saved HTML). Gold node = seed. If a 1-hop alter already has harvest HTML in inbox, those threads are **attached** (hop 2, cyan) — no new scrape. This is still Layer 2 — not the Distance Desk.

**Board (no id):** a multi-person `bundle.json` as before.

**Anti-collapse:** do not draw this graph inside the Distance Desk.  
**Anti-proof:** L4–L5 is “looks coordinated,” not “they are a bot farm.” Quote or mark low confidence.

## Why this exists

A single dossier cannot show a comment brigade. The tell is **between** accounts:

- same thread, same hour
- copy-close talking points
- they reply to each other more than to the OP
- the pile-on disappears when you raise the level filter

## Relation levels (filter)

| Level | Name | What it is | Confidence |
|-------|------|------------|------------|
| **1** | Observe | One reply, or both spoke ≥2 times on the same thread | observed |
| **2** | Repeat | Same kind stacks (replies ≥3 **or** shared threads ≥3) | observed |
| **3** | Reciprocal | A↔B replies | observed |
| **4** | Sync | Same calendar day + same thread, both active (≥2 comments each) | hypothesis |
| **5** | Brigade | Near-duplicate text **and** burst/sync | hypothesis |

UI: **min level** slider. `4` leaves sync/brigade in focus.

**Below min level:** switch `Hide` (drop weaker ties) or `Dim` (keep them faded).  
**Min edge width:** floor in px; weight still thickens above that floor.

A **coordination cluster** is a connected component of `near_dup` / L5 edges only. Sharing a hot thread with the OP (`burst_sync`) does **not** put the OP in the brigade.

## Edge kinds

| `kind` | Directed? | Built from |
|--------|-----------|------------|
| `replies_to` | yes | `texts[].reply_to` (person id) |
| `co_thread` | no | same `thread_id`, both have ≥2 comments |
| `burst_sync` | no | same `thread_id` + same UTC date, both ≥2 |
| `near_dup` | no | token Jaccard ≥ 0.45 on distinct authors |
| `mention` | yes | explicit `@id` / `@nick` in body (optional) |
| `likes` | yes | `type: like` / `source: community_like` (`reply_to` = liked person) |

A drawn line is **one pair**. It may stack several kinds.  
**Thickness** = log of combined weight. **Color** = max level on that pair.

| Level | Color |
|-------|--------|
| 1 | slate |
| 2 | sky |
| 3 | teal |
| 4 | amber |
| 5 | rose |

## graph.json

```json
{
  "meta": {
    "date": "YYYY-MM-DD",
    "platform": "forum.example",
    "protocol": "relation-v1",
    "synthetic": true
  },
  "viewer": { "id": "north_packet" },
  "nodes": [
    {
      "id": "relay_ops",
      "nick": "relay_ops",
      "distance": "neutral",
      "n_texts": 4,
      "coord_score": 12
    }
  ],
  "edges": [
    {
      "source": "brigade_w1",
      "target": "brigade_w2",
      "level": 5,
      "weight": 9,
      "kinds": ["replies_to", "burst_sync", "near_dup"],
      "confidence": "hypothesis",
      "parts": []
    }
  ],
  "coordination": {
    "clusters": [
      {
        "id": "C1",
        "member_ids": ["brigade_w1", "brigade_w2", "brigade_w3"],
        "score": 78,
        "read": "strong_signals",
        "reasons": ["near_dup + burst on two threads"]
      }
    ],
    "disclaimer": "Public-text hypothesis. Not legal proof of a coordinated campaign."
  }
}
```

## Bundle fields this layer needs

Already in [input-schema.md](input-schema.md): `people[]`, `texts[]`, `thread_id`, `timestamp`, `content`.

**Add (optional, for directed edges):**

| Field | Meaning |
|-------|---------|
| `reply_to` | Person id this comment answers |
| `parent_url` | Permalink of the parent comment/post |

Without `reply_to`, the builder still gets `co_thread` / `burst_sync` / `near_dup`.

## Commands

```bash
python scripts/build_relation_bundle.py --seed {id}
python scripts/build_kampff_graph.py -b docs/sample-relation-bundle.json -o docs/sample-graph.json
python scripts/render_kampff_graph.py -g docs/sample-graph.json -o docs/sample-graph.html
```

```text
/kampff graph path/to/bundle.json
/kampff relations
```

VS Code (`YangKangSung.kampff` ≥ 0.9.13): Analyze → type an **ID** → **관계 그래프**. Uses `inbox/*/raw/{id}/posts` (rebuilds the ego bundle). No harvest for that id → error, not the sample. Empty id → board `bundle.json` or synthetic sample.

## Join to L1 (optional)

If `out/*-{id}-analysis.json` exists, copy `distance` onto the node.  
Centrality is **not** a distance call. Do not `avoid` someone because they are a hub.

## What this is not

| Don't | Why |
|-------|-----|
| Draw the graph on the Distance Desk | Unit collapse (one person vs board) |
| Color nodes “evil” | Distance ≠ moral verdict |
| Treat L5 as proof | Need quotes + more boards + honesty |
| Commit real-person graphs | Private `KAMPFF_DATA` only |
| IP / login / device graph | Out of product scope |

Operator-only cohort scripts (`rebuild_cross_from_cohort.py`, harvest) stay private. This file is the **product** contract they should eventually emit.
