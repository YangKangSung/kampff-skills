# Platform login harvest (member tabs)

## When

- Member activity tabs require login
- Operator authorizes collect on an **agent-owned** browser profile
- Guest extract cannot open posts/comments/likes lists

## Hard rules

- Never type passwords or OAuth secrets into agent chat
- Never hijack the operator’s default browser profile
- Prefer one isolated profile: `{KAMPFF_DATA}/.agent-browser-profile`
- Open login URL → operator completes SSO → agent polls for session (profile chrome / session cookies)
- Analysis still reads `bundle.json` only after collect
- End with honesty triad (posts / comments / likes)

## Generic steps

1. Launch headed agent browser with isolated `user_data_dir` (headless may fail bot checks).
2. Navigate to site login; wait for operator.
3. Open member profile; collect tab lists (posts / comments / likes) with scroll/pagination.
4. If JSON APIs appear in network (e.g. `.../members/{id}/activity`, `.../liked`), page them with same-session `fetch(credentials:'include')` and **document caps** (recent-only windows, sparse pagination).
5. Fetch full bodies for authored post permalinks.
6. Write `raw/` dumps → rebuild bundle + honesty markdown.

## Completeness

| Surface | “Done” means |
|---------|----------------|
| posts | Index ≈ profile total **and** usable bodies |
| comments | All **exposed** comments + honesty if profile total ≫ recent window |
| likes | Tab/API paged; report unique count vs claimed total |

Tab name in DOM without open/page = **not collected**.

## Honesty template

```
| surface  | claimed | collected | full? |
| posts    | N       | …         | Y/N   |
| comments | N       | …         | Y/N   |
| likes    | N       | …         | Y/N   |
```

## Fallbacks

| Blocker | Next |
|---------|------|
| Bot challenge headless | headed agent profile |
| Profile lock | restart **agent** profile processes only |
| Auth required | open login, wait |
| API recent-only | state cap; do not invent missing texts |

## Note on platform examples

Adapters may document real site API shapes **without** embedding third-party person dossiers or private case studies. Keep measured caps generic (e.g. “comments endpoint may hard-cap ~50 recent”).
