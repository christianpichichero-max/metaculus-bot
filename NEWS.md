date: 2026-07-14T13:33:56Z
resolved: 27 (was 25)

149 log lines | 149 unique questions
fetching 149 posts...
first pass: 13 fetch failures — cooling down 30s and retrying those...

RESOLVED binary: 27 | Brier 0.2357 (lower=better, 0.25=coinflip) | LogLoss 0.7450

Reliability (predicted bucket vs actual yes-rate):
   0- 10% | n=  9 | actual 33%
  10- 20% | n=  4 | actual 50%
  20- 30% | n=  5 | actual 0%
  30- 40% | n=  2 | actual 0%
  40- 50% | n=  1 | actual 100%
  50- 60% | n=  3 | actual 33%
  60- 70% | n=  1 | actual 0%
  70- 80% | n=  1 | actual 100%
  90-100% | n=  1 | actual 100%

OFFICIAL scores captured on 48 question(s): SPOT PEER total = -377.16 (prize share ∝ max(0, total)²)

Wrote data/resolved.jsonl (27 resolved) — the ground-truth that gates every change.

SUPERVISOR SHADOW A/B (1 resolved fired-questions):
  geo-odds (submitted)        Brier: 0.3287
  ship-policy (high-conf only) Brier: 0.3287  ← geo-odds better/tied
  diagnostic (always-trust)    Brier: 0.3249
  Gate: flip use_supervisor=True only if ship-policy wins on ≥30 fired resolutions.
