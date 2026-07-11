# Launch copy (draft)

Repo: https://github.com/YangKangSung/kampff-skills

---

## Show HN

**Title (pick one)**

1. `Kampff – Agent skill that profiles everyone on a board from text traces`
2. `Show HN: spectrograph – 7-layer human analysis protocol for agent skills`
3. `Text → human dossier: worldview fit, ephemeris, distance – open SKILL.md`

**First comment**

> sickn33 profiles customers. i-am profiles you. **Kampff profiles everyone on the board — including you.**
>
> Feed posts, comments, mail, chat — get worldview fit, alliance fit, how someone changed over time (ephemeris), and engage/caution/avoid with **quoted evidence**.
>
> No scraping in the skill. Your collector → `bundle.json` → `/kampff analyze`.
>
> MIT · Grok / Claude / Hermes SKILL.md · [sample output](https://github.com/YangKangSung/kampff-skills/blob/main/docs/sample-output.md)
>
> Star-gated roadmap: HR lens @ 300⭐, OSINT @ 500⭐.

---

## r/LocalLLaMA

**Title:** `[Project] Kampff – human spectrum analysis agent skill (spectrograph protocol)`

**Body**

Built an agent skill for analyzing people from text they already published — workplace boards, Slack/Jira exports, SNS comments.

- **Not** customer profiling (sickn33) or self-only (i-am)
- **spectrograph** 7 layers: psych, worldview, behavior, alliance, ephemeris
- Viewer is in the pool — comparison with evidence quotes
- Collectors are separate YAML-driven package (15 prebuilt platforms; adapters still WIP)

```bash
cp -r kampff ~/.grok/skills/kampff      # or ~/.claude/skills/kampff · ~/.hermes/skills/kampff
/kampff analyze path/to/bundle.json
```

https://github.com/YangKangSung/kampff-skills — feedback welcome.

---

## X thread (5 posts)

1. sickn33 profiles customers. i-am profiles you. Kampff profiles **everyone on the board** — including you. 🧵

2. Input: posts, comments, mail, chat, messenger. Output: worldview fit, alliance fit, ephemeris (how they *changed*), distance: engage · neutral · caution · avoid — with quotes.

3. No scraping inside the skill. Collector → `bundle.json` → `/kampff today` or `/kampff analyze`. Protocol: **spectrograph** (7 layers, optional HR/OSINT lenses).

4. ``` graphify → code → graph · kampff → text → human spectrum ```

5. OSS, MIT: https://github.com/YangKangSung/kampff-skills — sample dossier in docs. ⭐ unlocks next modules (HR pack, OSINT pack).

---

## GeekNews / OKKY (한국어 한 줄)

**GeekNews:** Agent skill `kampff` — 게시판·Slack·메일 텍스트로 동료/커뮤니티 스펙트럼 분석 (세계관 fit, 시간축 drift, evidence 인용). https://github.com/YangKangSung/kampff-skills

**OKKY:** Grok / Claude / Hermes SKILL.md — 텍스트 trace → human dossier. 수집기 분리, spectrograph 7-layer. Star 캠페인 중.