# Collection honesty (community triad)

## Always print

| surface | profile claimed | collected | full? |
|---------|-----------------|-----------|-------|
| posts | total if shown | index + bodies | Y/N |
| comments | total if shown | count collected | Y/N |
| likes/reactions | total if shown | unique enumerable | Y/N |

## Rules

1. Completeness from **artifacts** (`bundle.json`, `raw/*`, API dumps), never intent memory.
2. Incomplete axis → say **NO** + numbers + next step.
3. UI tab label alone ≠ collected.
4. If platform only exposes “recent” windows or sparse pagination, mark `full? = NO (platform cap)` and ship best effort.

## Partial vs full

| Axis | Partial | Full |
|------|---------|------|
| posts | titles only | index matches profile **and** usable bodies |
| comments | snips / recent window | all profile comments (often impossible) |
| likes | 0 or sparse unique | all profile reactions (often impossible) |

## Bundle meta (recommended)

```json
"collection": {
  "site_claimed": { "posts": 0, "comments": 0, "likes": 0 },
  "collected": { "posts_index": 0, "post_bodies_ok": 0, "comments": 0, "likes_unique": 0 },
  "limits": { "posts": "", "comments": "", "likes": "" }
}
```

Authored text: `community_post` / `community_comment`.  
Engagement graph (target **gave** like): `community_like` + note “not authored”.

## Related

`community-member-pipeline.md` · `platform-login-harvest.md`
