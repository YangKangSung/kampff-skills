# Clinical / psychologist lens (public-text formulation · NOT diagnosis)

**Not medicine. Not a clinical interview. Not DSM/ICD coding.**  
Observational **formulation** from lawful public text traces only — for operator **distance / engage-cost**, never for treatment, labeling illness, or weaponized HR.

## Default policy

| Context | Default |
|---------|---------|
| Community member pipeline | **ON** (with MBTI + CIA) |
| Workplace mail/meeting batch | OFF unless requested |
| Operator: `렌즈 빼` / `clinical off` | OFF |
| User asks 정신과 / 심리학자 관점 | **ON** force |

## Hard rules

1. Title must include **「비진단 · formulation」**
2. Never assert disorder names as fact (`우울증이다`, `NPD 확정`). Prefer **signals consistent with…** / **hypothesis**.
3. Every PROBABLE+ claim needs a **quote** or mark `confidence: low`.
4. **Never sole reason** for `avoid` — pair with L3 harm stability + L4 alliance cost.
5. Refuse: diagnosis shopping, “destroy this person with psych jargon,” covert clinical use.
6. Self-harm / violence ideation in corpus → **safety note only** (observe + distance); no treatment plan.
7. Satire, roleplay, news paste ≠ personality evidence.

## Formulation axes (fill what evidence supports)

| Axis | Look for (text) | Report as |
|------|-----------------|-----------|
| **Affect regulation** | rage spikes, contempt stacks, soothing via in-group, numbing humor | under-/over-control · triggers |
| **Defense style** | splitting, projection, rationalization, intellectualization, humor, denial | dominant 2–4 defenses |
| **Attachment / bond** | idealize leader, chase reply, discard on slight, anxious re-ping | secure-ish / anxious / avoidant / mixed **signals** |
| **Cognitive style** | black-white, conspiracy frame, verification, concrete vs abstract | rigidity · mentalization depth |
| **Self / other** | grandiosity, shame dumps, devaluation of out-group, victim/hero | self-esteem regulation mode |
| **Interpersonal script** | recruit, lecture, pile-on, empty @mention, repair | role in threads |
| **Stress / ego threat** | when attacked: double-down, flee, moralize, label | ego threat response |
| **Functioning hint** | work/sport hobbies vs all-politics identity | domain breadth (not impairment claim) |

## Structured output (`analysis.clinical_psych`)

```json
{
  "enabled": true,
  "disclaimer": "Public-text formulation only — not diagnosis, not treatment.",
  "confidence": "low|medium|high",
  "one_line": "…",
  "affect": { "pattern": "", "triggers": [], "score_volatility": 0-100 },
  "defenses": [{ "name": "splitting|projection|…", "level": 0-3, "evidence": "quote ref" }],
  "attachment": { "signals": "anxious|avoidant|secure-lean|mixed", "note": "" },
  "cognition": { "style": "", "rigidity": 0-100, "mentalization": 0-100 },
  "self_other": { "pattern": "", "note": "" },
  "interpersonal": { "script": "", "repair": "low|mid|high" },
  "ego_threat": { "response": "", "note": "" },
  "hypotheses": [
    { "id": "C1", "label": "…", "status": "lead|weak|fail", "score": 0-100 }
  ],
  "not_claimed": ["No DSM diagnosis", "…"],
  "distance_bridge": "How this raises/lowers engage cost (1–2 sentences)"
}
```

## Relation to other layers

| Layer | Role |
|-------|------|
| L1 Big Five | Trait **tendencies** |
| MBTI | Fun engage-cost color only |
| **clinical_psych** | Dynamic defenses / affect / bond **process** |
| CIA ACH | Intent hypotheses for ops distance |
| Distance tag | Still `engage|neutral|caution|avoid` — clinical never overrides honesty of harm patterns |

If clinical formulation conflicts with L1, **prefer multi-quote behavioral L3** for distance.

## Renderer

HTML section **「Clinical / psychologist (비진단)」** after MBTI:
- disclaimer banner
- one_line + defenses bars
- attachment / cognition / interpersonal cards
- C-hypotheses mini ACH
- distance_bridge

## Pitfalls

- Long political rants ≠ “psychosis”
- Out-group slurs ≠ personality disorder proof (still L3 harm)
- Empty @mentions = interpersonal script signal, not diagnosis
- Thin corpus → confidence **low**, fewer axes filled
