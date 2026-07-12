# Community member pipeline (general)

Any community board member → collect → honesty → analyze → distance report.

## Triggers

| Signal | Action |
|--------|--------|
| Person analysis + nick/URL | Full pipeline |
| Member profile URL | Community path |
| posts/comments/likes completeness | Honesty triad before “done” |
| MBTI / CIA / KGB / profile | Lenses on (default for community) |
| `/kampff member {platform} {id}` | Explicit |

## Pipeline order

```
1) Scope     target · viewer_id · platform
2) Collect   lawful surfaces → raw/ + APIs
3) Honesty   posts / comments / likes → COLLECTION_HONESTY.md
4) Bundle    inbox/{date}/bundle.json
5) Analyze   L1–L5 always
6) Lenses    MBTI + CIA/KGB tradecraft default ON for community
7) Report    out/{date}-report.md · distance first
8) Handoff   cross-check prompts (optional)
```

## Platform abstraction

| Axis | Generic | Examples of UI names |
|------|---------|----------------------|
| posts | authored long form | posts, 글, threads |
| comments | authored short form | comments, 댓글, replies |
| likes | engagement graph | likes, 공감, reactions, upvotes |
| meta | profile counts | level, join date, totals |

If a platform has no likes surface, mark axis `n/a`.

## Collect rules

1. Prefer **agent-owned browser profile** under `{KAMPFF_DATA}/.agent-browser-profile` (or equivalent). Do not hijack the operator’s default browser.
2. Login walls: operator completes SSO in the agent window; agent never types passwords.
3. Prefer official/member APIs with session cookies when available; document caps.
4. Public permalink extract when guest-readable.
5. Analyze reads **files only**.
6. Refuse stalking / covert / bulk third-party without explicit lawful scope.

## Default report sections

See `report-template.md`.

## Done criteria

| Claim | Requires |
|-------|----------|
| Collect done | Honesty numbers + platform caps stated |
| Analyze done | Report path + distance one-liner |
| Site-parity | Each axis full **or** marked platform-impossible |

## Related

`collection-honesty.md` · `platform-login-harvest.md` · `community-public-collect.md` · `lenses-*.md` · `report-template.md`
