# Security Policy

## Supported surface

| Surface | Supported |
|---------|-----------|
| Current `main` on [kampff-skills](https://github.com/YangKangSung/kampff-skills) | Yes |
| Older commits / forks | Best-effort only |

This project is an **agent skill + docs + sample tooling**, not a hosted multi-tenant service.

## What to report

- Secret leakage in the public tree (tokens, cookies, private paths)
- Unsafe defaults in public scripts that could damage a user's machine when run as documented
- XSS or unexpected script execution in **checked-in** HTML samples under `docs/`

## Out of scope (usual)

- Prompt-injection against third-party agent hosts (report to that host)
- Abuse of Kampff **as a concept** on third-party people (social policy, not a CVSS bug)
- Issues that only appear with private harvest overlays not in this repo

## How to report

1. Prefer [GitHub Security Advisories](https://github.com/YangKangSung/kampff-skills/security/advisories/new) (private).
2. If Advisories are unavailable, open a **minimal** public issue without exploit detail and ask for a private channel.

Please include: impact, repro path, and whether any secret already leaked.

## Response expectation

Maintainer is often async. Acknowledge when possible within ~7 days; fix timing depends on severity and whether a coordinated disclosure is needed.

## Safe contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Never commit real third-party dossiers or live credentials.
