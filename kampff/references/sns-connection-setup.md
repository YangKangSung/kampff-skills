# SNS connection setup

Famous social platforms ship with **connection setup** — scaffold an `auth_ref`, env checklist, and `targets.json` snippet. Secrets never go in git or chat.

## Platforms

| id | Preferred mode | Auth style |
|----|----------------|------------|
| `facebook` | `graph_page` | Page access token **or** data download |
| `x` | `api_bearer` | X API v2 Bearer |
| `instagram` | `graph_business` | IG Graph (Business/Creator) **or** export |
| `linkedin` | `member_export` | Official member data export zip |
| `reddit` | `script_oauth` | Reddit script/installed app OAuth |

Also: `kampff-collect catalog --tags sns`

## CLI

```bash
cd collectors
pip install -e ".[all]"

# What can be connected
kampff-collect connect list

# Scaffold profile under $KAMPFF_AUTH_DIR (default: $KAMPFF_DATA/auth)
kampff-collect connect setup --platform x --ref x_api
kampff-collect connect setup --platform reddit --ref reddit_oauth
kampff-collect connect setup --platform facebook --ref facebook_graph
kampff-collect connect setup --platform instagram --ref instagram_graph
kampff-collect connect setup --platform linkedin --ref linkedin_export

# Pick a non-default mode
kampff-collect connect setup --platform facebook --mode data_export --ref facebook_export
kampff-collect connect setup --platform x --mode oauth_user --ref x_user

# Readiness (env present? profile exists?)
kampff-collect connect status
kampff-collect connect status --platform reddit
kampff-collect connect doctor

# Multi-SNS targets skeleton
kampff-collect connect sample-targets --out ../kampff-data/inbox/$(date +%Y-%m-%d)/targets-sns.json
```

Playwright / SSO (non-SNS boards):

```bash
kampff-collect auth login --ref corp_sso --url https://portal.example.local
```

## Where files land

```text
$KAMPFF_AUTH_DIR/                 # or $KAMPFF_DATA/auth
  .gitignore                      # ignore all secrets
  auth.json                       # index: ref → platform/mode (no tokens)
  x_api/profile.yaml
  reddit_oauth/profile.yaml
  ...
```

`targets.json` only stores `"auth_ref": "x_api"`. Tokens live in **environment variables** or OS secret store.

## Env cheat sheet

| Platform | Mode | Variables |
|----------|------|-----------|
| X | `api_bearer` | `X_BEARER_TOKEN` (alt: `TWITTER_BEARER_TOKEN`) |
| X | `oauth_user` | `X_API_KEY` `X_API_SECRET` `X_ACCESS_TOKEN` `X_ACCESS_TOKEN_SECRET` |
| Reddit | `script_oauth` | `REDDIT_CLIENT_ID` `REDDIT_CLIENT_SECRET` `REDDIT_USER_AGENT` `REDDIT_USERNAME` `REDDIT_PASSWORD` |
| Reddit | `installed_app` | `REDDIT_CLIENT_ID` `REDDIT_REFRESH_TOKEN` `REDDIT_USER_AGENT` |
| Facebook | `graph_page` | `FACEBOOK_ACCESS_TOKEN` `FACEBOOK_APP_ID` |
| Facebook | `data_export` | `FACEBOOK_EXPORT_DIR` |
| Instagram | `graph_business` | `INSTAGRAM_ACCESS_TOKEN` `INSTAGRAM_IG_USER_ID` |
| Instagram | `data_export` | `INSTAGRAM_EXPORT_DIR` |
| LinkedIn | `member_export` | `LINKEDIN_EXPORT_DIR` |

Windows tip: `setx X_BEARER_TOKEN "…"` then open a new shell.

## Per-platform notes

### X (Twitter)

1. [developer.x.com](https://developer.x.com/) → Project + App → Bearer Token  
2. `connect setup --platform x`  
3. targets: `platform: x`, `query.username` or `query.user_id`

### Reddit

1. [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) → type **script** (or installed app)  
2. Descriptive `user_agent` required  
3. Prefer a dedicated bot account; **never** paste password into agent chat  

### Facebook

- **Graph:** Page you manage + Page access token (minimum scopes)  
- **Export:** Accounts Center → Download your information  
- Logged-in scrape of other people's profiles is **out of scope**

### Instagram

- **Graph:** Professional account linked to a Facebook Page  
- **Export:** Download your information pack  
- Personal-account scrape without API/export is **out of scope**

### LinkedIn

- Default path is **member data export** (Shares.csv etc.)  
- Marketing/partner APIs only if your org is approved — not the default pack  

## targets.json examples

```json
{
  "url": "https://x.com/their_x",
  "platform": "x",
  "scope": "profile_by_username:their_x",
  "collect": ["post", "reply"],
  "match_people": ["target_id"],
  "auth_ref": "x_api",
  "query": { "username": "their_x", "limit": 100 }
}
```

```json
{
  "url": "https://www.reddit.com/user/example/",
  "platform": "reddit",
  "scope": "user:example",
  "collect": ["post", "comment"],
  "match_people": ["target_id"],
  "auth_ref": "reddit_oauth",
  "query": { "username": "example" }
}
```

```json
{
  "url": "file://linkedin-export",
  "platform": "linkedin",
  "scope": "export_package",
  "collect": ["post"],
  "match_people": ["me"],
  "auth_ref": "linkedin_export",
  "query": { "path": "C:/data/linkedin-export" }
}
```

Full multi-SNS skeleton: `docs/sample-targets-sns.json` or `connect sample-targets`.

## Hard rules

1. Never put tokens/passwords in `targets.json`, git, or agent chat  
2. Never hijack the operator's default browser profile for login harvest  
3. Prefer official API / export; adapters stay lawful  
4. Analysis still reads `bundle.json` only — connect ≠ collect ≠ analyze  
5. Collection honesty triad still applies after SNS collect  

## Skill triggers

```text
/kampff connect
/kampff connect x
SNS 연결, facebook 연결, reddit oauth 세팅
```

Agent should run `kampff-collect connect setup|status` and point the human at env vars — not ask them to paste secrets.

## Related

- [prebuilt-platforms.md](prebuilt-platforms.md)  
- [platform-login-harvest.md](platform-login-harvest.md)  
- [collection-targets.md](collection-targets.md)  
- Platform YAML `connection:` blocks under `collectors/platforms/{id}.yaml`
