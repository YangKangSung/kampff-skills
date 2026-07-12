# GitHub smoke (public collect)

Easiest collector smoke when `gh` is authenticated.

## Steps

1. Resolve login: `gh api user --jq .login`
2. Pull public issues/PRs/comments for target login (self-dossier: same login)
3. Normalize to `bundle.json` under `{KAMPFF_DATA}/inbox/{date}/`
4. `/kampff analyze` that bundle

## Fields

- `content`, `timestamp`, `source` (`community_comment` or map to chat/issue)
- `url` permalink when available
- `meta.platform`: `github`

## Limits

Public API only unless operator provides broader auth scope. Small N → medium confidence.
