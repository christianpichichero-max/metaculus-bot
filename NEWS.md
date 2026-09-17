date: 2026-09-17T16:14:56Z
resolved: 107 (was 106)

232 log lines | 232 unique questions
fetching 232 posts...

RESOLVED binary: 107 | Brier 0.2042 (lower=better, 0.25=coinflip) | LogLoss 0.6057

Reliability (predicted bucket vs actual yes-rate):
   0- 10% | n= 24 | actual 17%
  10- 20% | n= 26 | actual 15%
  20- 30% | n= 14 | actual 36%
  30- 40% | n= 11 | actual 27%
  40- 50% | n=  8 | actual 62%
  50- 60% | n=  7 | actual 71%
  60- 70% | n=  5 | actual 20%
  70- 80% | n=  9 | actual 44%
  80- 90% | n=  1 | actual 0%
  90-100% | n=  2 | actual 100%

RESOLVED multiple-choice: 16 | avg ln p(winner) -1.533 | multiclass Brier 0.7470

RESOLVED numeric/discrete/date: 59 | P10-P90 coverage 85% (target ~80%) | P2.5-P97.5 coverage 93% (target ~95%) | beyond-declared-tails: 2

OFFICIAL scores captured on 182 question(s): SPOT PEER total = -673.07 (prize share ∝ max(0, total)²)

Wrote data/resolved.jsonl (182 resolved) — the ground-truth that gates every change.

SUPERVISOR SHADOW A/B (46 resolved fired-questions):
  geo-odds (submitted)        Brier: 0.2266
  ship-policy (high-conf only) Brier: 0.2782  ← geo-odds better/tied
  diagnostic (always-trust)    Brier: 0.2614
  high-confidence overrides (7): geo-odds 0.3018 vs supervisor 0.6411
  Gate: flip use_supervisor=True only if ship-policy wins on ≥30 fired resolutions.

BLF SHADOW A/B (59 resolved):
  submitted (ensemble geo-odds) Brier: 0.2150
  belief-loop (shadow)          Brier: 0.2283  ← ensemble better/tied
  Gate: promote the BLF to the forecaster seat only if it wins on ≥40 resolutions.
