date: 2026-07-13T14:32:08Z
resolved: 25 (was 14)

121 log lines | 121 unique questions
fetching 121 posts...
WARNING: 12 of 121 posts could not be fetched (rate limit/error). Report is INCOMPLETE — resolved.jsonl NOT overwritten; re-run.

RESOLVED binary: 25 | Brier 0.2398 (lower=better, 0.25=coinflip) | LogLoss 0.7606

Reliability (predicted bucket vs actual yes-rate):
   0- 10% | n=  9 | actual 33%
  10- 20% | n=  4 | actual 50%
  20- 30% | n=  4 | actual 0%
  30- 40% | n=  2 | actual 0%
  50- 60% | n=  3 | actual 33%
  60- 70% | n=  1 | actual 0%
  70- 80% | n=  1 | actual 100%
  90-100% | n=  1 | actual 100%

OFFICIAL scores captured on 43 question(s): SPOT PEER total = -418.30 (prize share ∝ max(0, total)²)

SUPERVISOR SHADOW A/B (1 resolved fired-questions):
  geo-odds (submitted)        Brier: 0.3287
  ship-policy (high-conf only) Brier: 0.3287  ← geo-odds better/tied
  diagnostic (always-trust)    Brier: 0.3249
  Gate: flip use_supervisor=True only if ship-policy wins on ≥30 fired resolutions.
