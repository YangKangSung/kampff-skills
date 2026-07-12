# spectrograph protocol

Internal analysis engine for the **kampff** skill. Seven core layers + optional fun/tradecraft lenses.

| Layer | Name | Output |
|-------|------|--------|
| L1 | Psych | Personality and communication tendencies (Big Five, conflict, defenses) |
| L2 | Worldview | Ideology, religion, philosophy axes |
| L3 | Signature | Behavioral pattern stability |
| L4 | Alliance | Trust and go-together fit |
| L5 | Ephemeris | Temporal drift and turning points |
| L6 | HR | Team and conflict signals (assist only) |
| L7 | OSINT | Narrative consistency (lawful scope) |

Distance scale: `engage` · `neutral` · `caution` · `avoid`

## Optional lenses (after L1–L5; with L6/L7 if requested)

| Lens | `analysis_lenses` value | Doc |
|------|-------------------------|-----|
| MBTI (fun) | `mbti` | [lenses-mbti.md](lenses-mbti.md) |
| CIA-style SAT | `cia_sat` or `tradecraft` | [lenses-cia-sat.md](lenses-cia-sat.md) |

Execute core layers first. Optional lenses never override evidence rules or hard refusals.
