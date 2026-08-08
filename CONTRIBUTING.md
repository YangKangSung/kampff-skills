# Contributing to kampff-skills

Thanks for helping. This repo is the **public** window for Kampff / spectrograph agent skills.

## Ground rules

1. **Evidence over vibes.** Claims in sample reports and docs should stay quote-tied or marked low-confidence.
2. **No real third-party dossiers.** Synthetic fixtures only (`relay_ops`, `forum.example`, …).
3. **No secrets.** Tokens, cookies, private harvest dumps, local absolute paths with usernames → reject.
4. **MIT.** By opening a PR you license your contribution under the repo LICENSE.

## Dev loop

```bash
git clone https://github.com/YangKangSung/kampff-skills.git
cd kampff-skills
# optional: Python helpers under scripts/
python -m py_compile scripts/*.py  # smoke; skip if no python
```

Install the skill into your harness (see README). Prefer small PRs over megadiffs.

## PR checklist

- [ ] Product paths only (skill, docs samples, public scripts)
- [ ] No private nicknames / real community scrapes
- [ ] README or docs updated if behavior changes
- [ ] Sample HTML/JSON still coherent if you touched the renderer

## Issues

Bug reports: steps + expected vs actual.  
Feature ideas: who benefits + minimal surface.

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
