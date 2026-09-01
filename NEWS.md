date: 2026-09-01T16:09:28Z
resolved: 75 (was 67)

185 log lines | 185 unique questions
fetching 185 posts...
first pass: 17 fetch failures — cooling down 30s and retrying those...
WARNING: 1 of 185 posts could not be fetched (rate limit/error). Report is INCOMPLETE — resolved.jsonl NOT overwritten; re-run.

RESOLVED binary: 75 | Brier 0.2247 (lower=better, 0.25=coinflip) | LogLoss 0.6687

Reliability (predicted bucket vs actual yes-rate):
   0- 10% | n= 18 | actual 22%
  10- 20% | n= 18 | actual 22%
  20- 30% | n=  8 | actual 25%
  30- 40% | n=  6 | actual 33%
  40- 50% | n=  7 | actual 57%
  50- 60% | n=  6 | actual 67%
  60- 70% | n=  4 | actual 25%
  70- 80% | n=  6 | actual 50%
  80- 90% | n=  1 | actual 0%
  90-100% | n=  1 | actual 100%

RESOLVED multiple-choice: 15 | avg ln p(winner) -1.579 | multiclass Brier 0.7652

RESOLVED numeric/discrete/date: 53 | P10-P90 coverage 87% (target ~80%) | P2.5-P97.5 coverage 94% (target ~95%) | beyond-declared-tails: 1

OFFICIAL scores captured on 143 question(s): SPOT PEER total = -551.19 (prize share ∝ max(0, total)²)

SUPERVISOR SHADOW A/B (30 resolved fired-questions):
  geo-odds (submitted)        Brier: 0.2571
  ship-policy (high-conf only) Brier: 0.2948  ← geo-odds better/tied
  diagnostic (always-trust)    Brier: 0.2688
  high-confidence overrides (4): geo-odds 0.3677 vs supervisor 0.6507
  Gate: flip use_supervisor=True only if ship-policy wins on ≥30 fired resolutions.

BLF SHADOW A/B (40 resolved):
  submitted (ensemble geo-odds) Brier: 0.2251
  belief-loop (shadow)          Brier: 0.2771  ← ensemble better/tied
  Gate: promote the BLF to the forecaster seat only if it wins on ≥40 resolutions.
