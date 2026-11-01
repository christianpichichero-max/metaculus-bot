date: 2026-11-01T17:51:36Z
resolved: 175 (was 170)

380 log lines | 380 unique questions
fetching 380 posts...
first pass: 25 fetch failures — cooling down 30s and retrying those...
WARNING: 1 of 380 posts could not be fetched (rate limit/error). Report is INCOMPLETE — resolved.jsonl NOT overwritten; re-run.

RESOLVED binary: 175 | Brier 0.1779 (lower=better, 0.25=coinflip) | LogLoss 0.5400

Reliability (predicted bucket vs actual yes-rate):
   0- 10% | n= 24 | actual 17%
  10- 20% | n= 50 | actual 12%
  20- 30% | n= 26 | actual 23%
  30- 40% | n= 15 | actual 40%
  40- 50% | n= 14 | actual 43%
  50- 60% | n= 12 | actual 67%
  60- 70% | n= 10 | actual 40%
  70- 80% | n= 15 | actual 67%
  80- 90% | n=  5 | actual 60%
  90-100% | n=  4 | actual 100%

RESOLVED multiple-choice: 27 | avg ln p(winner) -1.449 | multiclass Brier 0.7365

RESOLVED numeric/discrete/date: 126 | P10-P90 coverage 82% (target ~80%) | P2.5-P97.5 coverage 94% (target ~95%) | beyond-declared-tails: 3

OFFICIAL scores captured on 328 question(s): SPOT PEER total = -49.50 (prize share ∝ max(0, total)²)

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
