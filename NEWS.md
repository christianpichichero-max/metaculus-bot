date: 2026-09-12T15:06:50Z
resolved: 96 (was 92)

232 log lines | 232 unique questions
fetching 232 posts...
first pass: 17 fetch failures — cooling down 30s and retrying those...

RESOLVED binary: 96 | Brier 0.1977 (lower=better, 0.25=coinflip) | LogLoss 0.5937

Reliability (predicted bucket vs actual yes-rate):
   0- 10% | n= 23 | actual 17%
  10- 20% | n= 26 | actual 15%
  20- 30% | n= 10 | actual 30%
  30- 40% | n=  9 | actual 22%
  40- 50% | n=  7 | actual 57%
  50- 60% | n=  6 | actual 67%
  60- 70% | n=  5 | actual 20%
  70- 80% | n=  7 | actual 43%
  80- 90% | n=  1 | actual 0%
  90-100% | n=  2 | actual 100%

RESOLVED multiple-choice: 16 | avg ln p(winner) -1.533 | multiclass Brier 0.7470

RESOLVED numeric/discrete/date: 56 | P10-P90 coverage 84% (target ~80%) | P2.5-P97.5 coverage 93% (target ~95%) | beyond-declared-tails: 2

OFFICIAL scores captured on 168 question(s): SPOT PEER total = -458.18 (prize share ∝ max(0, total)²)

Wrote data/resolved.jsonl (168 resolved) — the ground-truth that gates every change.

SUPERVISOR SHADOW A/B (37 resolved fired-questions):
  geo-odds (submitted)        Brier: 0.2186
  ship-policy (high-conf only) Brier: 0.2491  ← geo-odds better/tied
  diagnostic (always-trust)    Brier: 0.2280
  high-confidence overrides (5): geo-odds 0.2951 vs supervisor 0.5210
  Gate: flip use_supervisor=True only if ship-policy wins on ≥30 fired resolutions.

BLF SHADOW A/B (50 resolved):
  submitted (ensemble geo-odds) Brier: 0.1973
  belief-loop (shadow)          Brier: 0.2330  ← ensemble better/tied
  Gate: promote the BLF to the forecaster seat only if it wins on ≥40 resolutions.
