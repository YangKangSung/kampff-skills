# Kampff drills — deliberate practice

Synthetic cases only. Train **distance + quote discipline + clinical formulation**.  
Not diagnosis class. Not real people.

## Commands

```text
/kampff drill              # list cases
/kampff drill 01           # run case 01 (hide GOLD until after draft)
/kampff drill 02
/kampff drill score 01     # open rubric + compare to GOLD
```

Natural: “드릴 해줘”, “profiling practice”, “연습 케이스”.

## Agent procedure

1. **Do not** open `GOLD-analysis.json` until operator finishes draft (or explicitly says “채점/score”).  
2. Show only `brief.md` + `texts.json` (or mini bundle).  
3. Operator (or agent-as-student if user asks “너가 먼저”) writes **short** draft:
   - `distance` + one-line TL;DR  
   - L1 + L3 (stability)  
   - clinical `one_line` + top 2 defenses  
   - ≥2 quote refs  
   - ACH H1 lead + one rival  
4. Then load GOLD → score with [`rubric.md`](rubric.md).  
5. Write score sheet to **gitignored** path if desired:  
   `{KAMPFF_DATA}/drills/{date}-{id}-score.md`  
   Never commit real self-scores with private notes that name real people.

## Cases

| ID | Folder | Gold distance (hint after score) | Trains |
|----|--------|----------------------------------|--------|
| **01** | [`01-criteria-peer/`](01-criteria-peer/) | soft-engage / neutral | criteria-bound affect · brand flip ≠ flip-flop |
| **02** | [`02-status-flex/`](02-status-flex/) | caution | empty flex · ego threat · meeting cost |

## File layout per case

```text
NN-slug/
  brief.md              # scenario + viewer stance (no answers)
  texts.json            # synthetic corpus
  GOLD-analysis.json    # scoring key (partial analysis shape)
```

## Rules

- Fiction handles only (`relay_ops`-class, `forum.example`)  
- clinical = 비진단  
- If user pastes a **real** nick for “drill” → switch to normal lawful collect path; do not invent a GOLD for them  
- After 2 drills: optional real self-dossier smoke (GitHub) — separate from this folder  

## Study map

[`../profiling-craft.md`](../profiling-craft.md)
