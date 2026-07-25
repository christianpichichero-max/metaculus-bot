date: 2026-07-25T13:26:35Z
resolved: 58 (was 27)

185 log lines | 185 unique questions
fetching 185 posts...
first pass: 17 fetch failures — cooling down 30s and retrying those...
WARNING: 1 of 185 posts could not be fetched (rate limit/error). Report is INCOMPLETE — resolved.jsonl NOT overwritten; re-run.

RESOLVED binary: 58 | Brier 0.2111 (lower=better, 0.25=coinflip) | LogLoss 0.6429

Reliability (predicted bucket vs actual yes-rate):
   0- 10% | n= 13 | actual 23%
  10- 20% | n= 13 | actual 23%
  20- 30% | n=  7 | actual 14%
  30- 40% | n=  5 | actual 20%
  40- 50% | n=  6 | actual 50%
  50- 60% | n=  5 | actual 60%
  60- 70% | n=  2 | actual 50%
  70- 80% | n=  5 | actual 60%
  80- 90% | n=  1 | actual 0%
  90-100% | n=  1 | actual 100%

RESOLVED multiple-choice: 3 | avg ln p(winner) -1.439 | multiclass Brier 0.7905

RESOLVED numeric/discrete/date: 38 | P10-P90 coverage 89% (target ~80%) | P2.5-P97.5 coverage 95% (target ~95%) | beyond-declared-tails: 0

OFFICIAL scores captured on 99 question(s): SPOT PEER total = -384.28 (prize share ∝ max(0, total)²)

SUPERVISOR SHADOW A/B (21 resolved fired-questions):
  geo-odds (submitted)        Brier: 0.2449
  ship-policy (high-conf only) Brier: 0.2670  ← geo-odds better/tied
  diagnostic (always-trust)    Brier: 0.2426
  high-confidence overrides (3): geo-odds 0.3862 vs supervisor 0.5409
  Gate: flip use_supervisor=True only if ship-policy wins on ≥30 fired resolutions.

BLF SHADOW A/B (31 resolved):
  submitted (ensemble geo-odds) Brier: 0.1896
  belief-loop (shadow)          Brier: 0.2389  ← ensemble better/tied
  Gate: promote the BLF to the forecaster seat only if it wins on ≥40 resolutions.
