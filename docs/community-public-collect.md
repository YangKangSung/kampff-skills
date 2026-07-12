# Community public collect (login-walled profiles)

## When

- Third-party person on a community board
- Member profile tabs require login; posts may be guest-readable
- Collector platform adapter may not exist yet

## Hard limits

| Reality | Response |
|---------|----------|
| Guest member tab → login wall | State **full dump unavailable** as guest |
| “All posts and comments” | Deliver public sample + confidence; or agent-session collect after SSO |
| Auth | Never steal cookies / type passwords / bypass auth |

## Generic recipe (guest-OK)

1. **Resolve identities** — viewer vs target; display nick vs platform member id  
2. **Seed URLs** — trigger thread, author recent lists, site search `site:{domain} "{nick}"`  
3. **Fetch** — public post permalinks first; skip spinning on login redirects  
4. **Normalize → bundle** — `context: community`, sources `community_post` / `community_comment`, always `content` + `timestamp` + `url`  
5. **Limits** — `meta.collection_limits[]` list every gap  
6. **Paths** — `{KAMPFF_DATA}/inbox/{YYYY-MM-DD}/bundle.json`, optional `raw/`

## Logged-in collect

See `platform-login-harvest.md` (agent-owned browser profile + SSO wait).

## Ethics

Lawful public / authorized session only. No stalking. No covert mass harvest without explicit scope.
