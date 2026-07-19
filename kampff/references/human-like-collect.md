# Human-like collect (anti-bot hygiene)

Clien and similar boards **will** flag aggressive automation. Kampff collectors must behave like a careful human session.

## Hard limits (default)

| Knob | Default | Notes |
|------|---------|-------|
| delay between navigations | **2.5–6.5s random** | never fixed 0.2s loops |
| delay between actors | **8–20s random** | cohort expand |
| max pages / actor / board | **1–2** | not 40 |
| max boards per run | **1–2** (start `park` only) | widen only if needed |
| max actors expanded / run | **5–8** | hot subset first, not all 50 |
| same URL re-fetch | **use disk cache** if < 24h | |
| burst | **forbidden** | no tight for-loops of fetch |

## Browser behaviour

1. **One** persistent headed or headless profile — do not thrash process kill/restart every call.  
2. `ignore_default_args=['--enable-automation']` + `--disable-blink-features=AutomationControlled`.  
3. Real `locale` / `timezone` (ko-KR / Asia/Seoul).  
4. Before read: **scroll** smoothly 2–5 steps (random).  
5. Occasional mouse move / idle 1–3s on page.  
6. Prefer **user-driven login** once; reuse `CL_DEVICE_*` trust cookie.  
7. If login page / captcha / “비정상” banner → **STOP** and report; do not retry storm.

## Request shape

- Navigate like a user: open board → click search → open result (when UI allows).  
- Direct `search/v2` URL OK only with human delays.  
- **No** parallel Playwright contexts on same site.  
- **No** multi-board fan-out in one minute.

## Cohort expand strategy (important)

```text
seed thread (1 page)
  → pick top K actors (by degree / malice / focus)  K≤8
  → for each actor (sleep 8–20s):
        writer search park po=0 only (optional po=1 if needed)
        commenter search park po=0 only
  → STOP if rate-limited
  → later runs continue with remaining actors (resume file)
```

Cross-thread proof does **not** require full history day-one.

## Detected-bot response

| Signal | Action |
|--------|--------|
| sudden login wall | stop expand; keep seed analysis |
| empty 200 / challenge page | stop; cool down **≥30 min** |
| captcha | human only; no brute |

## Resume file

`{KAMPFF_DATA}/inbox/{date}/cohort_resume.json`

```json
{ "done_actors": ["id1"], "next": ["id2"], "last_error": null, "cooldown_until": null }
```

## Code helpers

Use `scripts/human_browse.py` utilities: `human_pause()`, `human_scroll(page)`, `cached_get()`.
