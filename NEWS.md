date: 2026-09-03T15:48:44Z
resolved: 78 (was 76)

185 log lines | 185 unique questions
fetching 185 posts...

RESOLVED binary: 78 | Brier 0.2235 (lower=better, 0.25=coinflip) | LogLoss 0.6639

Reliability (predicted bucket vs actual yes-rate):
   0- 10% | n= 17 | actual 24%
  10- 20% | n= 21 | actual 19%
  20- 30% | n=  9 | actual 33%
  30- 40% | n=  6 | actual 33%
  40- 50% | n=  7 | actual 57%
  50- 60% | n=  6 | actual 67%
  60- 70% | n=  4 | actual 25%
  70- 80% | n=  6 | actual 50%
  80- 90% | n=  1 | actual 0%
  90-100% | n=  1 | actual 100%

RESOLVED multiple-choice: 15 | avg ln p(winner) -1.579 | multiclass Brier 0.7652

RESOLVED numeric/discrete/date: 55 | P10-P90 coverage 85% (target ~80%) | P2.5-P97.5 coverage 93% (target ~95%) | beyond-declared-tails: 2

OFFICIAL scores captured on 148 question(s): SPOT PEER total = -555.04 (prize share ∝ max(0, total)²)

Wrote data/resolved.jsonl (148 resolved) — the ground-truth that gates every change.

SUPERVISOR SHADOW A/B (31 resolved fired-questions):
  geo-odds (submitted)        Brier: 0.2494
  ship-policy (high-conf only) Brier: 0.2859  ← geo-odds better/tied
  diagnostic (always-trust)    Brier: 0.2608
  high-confidence overrides (4): geo-odds 0.3677 vs supervisor 0.6507
  Gate: flip use_supervisor=True only if ship-policy wins on ≥30 fired resolutions.

BLF SHADOW A/B (42 resolved):
  submitted (ensemble geo-odds) Brier: 0.2151
  belief-loop (shadow)          Brier: 0.2654  ← ensemble better/tied
  Gate: promote the BLF to the forecaster seat only if it wins on ≥40 resolutions.
