# Metaculus Bot — Synthesis Judge: the defensible-edge plan

**Date:** 2026-06-27 · **Repo:** `/Users/christian/metaculus-bot` · **Bot:** `EdgeForecastBot` (forecasting-tools SDK)
**Config verified live:** forecaster `5x openrouter/openai/o4-mini` (temp 1), research `gpt-4o-search-preview`, summarizer/parser `gpt-4o-mini`; geo-odds aggregation; base-rate research pass; coverage retry; 20-min Actions cron.

---

## 1. The one-line verdict

Across four independent lenses and their adversarial verdicts, **exactly one idea survived as a genuine, durable edge** — and two separate lenses landed on it independently: a **resolution-grounded calibration/benchmark flywheel**. Everything else the lenses proposed was downgraded to *marginal* (worth doing, copyable, no moat) or *not-an-edge* (table-stakes). That convergence is the signal. Our headline edge is therefore not a clever technique — it is **a private, compounding, leakage-free record of our own forecasts vs. real outcomes, plus the discipline of gating every change on it.** The harness is copyable in a day; the accumulated dataset and the validated decisions it produces are invisible in the repo and get stronger every season.

---

## 2. Honest reality check (don't oversell)

- **We cannot win and probably can't crack the very top.** AIB's most-replicated finding over four seasons is *"the underlying model matters more than scaffolding"* — o3 won Q2/Q3 on near-raw power, and Metaculus's own minimal-scaffolding in-house bots place top-6 with the best models ([Q2 results](https://forum.effectivealtruism.org/posts/F2stjK9wHSy3HPEC9/q2-ai-benchmark-results-pros-maintain-clear-lead)). We are deliberately on **free o4-mini**; that ceiling is real and structural. Human pros still beat every bot.
- **The payout is power-law.** ~206 bots in Summer; ~20% paid; winner ~25% of pool; ~80% earn $0; prize ∝ `(Σ spot peer scores)²` with a zero floor ([scores FAQ](https://www.metaculus.com/help/scores-faq/)). Our own `CLAUDE.md` says it: *"the stock template finishes near the bottom. Default ≠ paid."*
- **What IS realistic:** clear the median reliably and land in the paid ~20% tier in some seasons — most plausibly via **MiniBench** (cheap, bi-weekly ~$1k, ~60 Qs, data-source-exploitable, fastest feedback). Feasible because most of the field is broken/abandoned template forks, and the separators are *process* edges we can run at ~zero marginal cost.
- **Three caveats that keep this grounded:** (1) the flywheel only tunes **second-order** knobs — pair it with spending the $300 on the forecaster model, the first-order lever; (2) it's **slow** — need ~100+ resolved binaries before trusting any tuning, so real compounding is season-2+; (3) **it isn't running yet** (see §3).

---

## 3. What I verified in the actual repo (this sharpens — and corrects — the lenses)

| Claim | Status in our code |
|---|---|
| Forecast log accumulates a resolved track record | **FALSE today.** `forecast_log.py` logs `community_prediction` at access time but has **no resolution/outcome field**; `data/forecasts.jsonl` has **18 records**, is **gitignored**, and the workflow only **uploads it as an ephemeral per-run artifact** → on Actions it starts empty every run. **The moat-fuel is being thrown away.** |
| Recalibration is a rare edge | **FALSE.** SDK ships `forecasting_tools/calibration_adjustment/logistic_recalibration_adjuster.py`. Built-in, Metaculus-recommended to the whole field, symmetric. |
| The 0.2/bin numeric CDF cap is a "free lunch" | **FALSE.** SDK enforces `MAX_NUMERIC_PMF_VALUE = 0.2` + `standardize_cdf=True` (`data_models/numeric_report.py`) for the entire template field. |
| benchmark.py scores vs ground truth | **No — by design.** It scores vs the **community prediction on OPEN questions** (low-variance, leakage-free). Correct for fast A/B; don't "fix" it. |
| Coverage cron is hardened | **Partially.** Every-20-min cron + concurrency guard + coverage retry exist, but **no alerting, no redundancy, no dead-man's-switch**; the retry re-runs identical logic (fixes transient, not deterministic format, failures). |
| Ensemble is diverse | **No.** `main.py:773` = `5x openrouter/openai/o4-mini`. `optimization-plan.md` already flags the concurrency race for multi-model and lists a dead "re-forecast before close" TODO. |

**The key reconciliation:** Lens 1 & Lens 3 rated "resolution-grounded testing" a *real edge*; Lens 2 pushed back that swapping benchmark.py to score resolved outcomes imports **look-ahead leakage** (a live-search bot reads the known answer — the same bug class that burned the ORB project) and **high variance**. Both are right, and they resolve cleanly: **keep benchmark.py's community-proxy as the fast gate; get leakage-free ground truth from our own PRODUCTION forecasts on still-open questions, joined to their later resolution.** That is what `forecast_log.py` was meant to enable and currently doesn't.

---

## 4. Ranked edge plan

### Rank 1 — The leakage-free resolution flywheel (durable) — *the real edge*
**Why:** Custom-question testing/resolution was the **largest** measured success correlate in the Q2 survey (**+2,216 coverage-adjusted pts, 95% CI +912..+3,519** — the only top lever whose CI excludes zero), beating aggregation (+1,799) and manual review (+1,041) ([LessWrong mirror](https://www.lesswrong.com/posts/Surnjh8A4WjgtQTkZ/q2-ai-benchmark-results-pros-maintain-clear-lead)). Defensibility lives in the **accumulated private data + validated knob-settings + discipline**, not the copyable harness.
**How (concrete):**
1. **Prerequisite #0 — stop discarding data.** Persist `data/forecasts.jsonl` durably (append-commit to an orphan `data` branch each run, or a free Supabase/private gist). Right now it's gitignored + artifact-only.
2. **Resolution join.** Add outcome fields to `forecast_log.py` + a scheduled job that re-pulls each logged question's resolution via `MetaculusClient` and writes realized log/peer score. Production forecasts on open questions are inherently leakage-free.
3. **Keep the fast gate.** Leave `benchmark.py` scoring vs community on open Qs; do **not** re-score old resolved Qs (leakage).
4. **Hard rule** in `CLAUDE.md`: no prompt/model/aggregation change merges unless it beats current over **≥100 Qs × ≥2 runs**, segmented by type.

### Rank 2 — Decorrelated multi-family ensemble governed by a private ledger (moderate)
**Why:** `5x o4-mini` cancels noise, not bias. Aggregation is the #2 lever (+1,799, CI excludes zero); every paid winner mixes families (Panshul42 = 2×Sonnet/2×o4-mini/1×o3, [public repo](https://github.com/Panshul42/Forecasting_Bot_Q2)); Mantic's edge is **JS-divergence decorrelation** ([Thinking Machines](https://thinkingmachines.ai/news/training-llms-to-predict-world-events/)); a 12-LLM ensemble reaches human-crowd parity ([Science Advances](https://www.science.org/doi/10.1126/sciadv.adp1528)). **Honest:** this is **catch-up to par**, not ahead — the config is copyable/our own TODO. The durable sliver is the **accuracy+divergence selection ledger**. This is also where the **$300 belongs** (model = first-order lever).
**How:** Route the 5 draws across families we hold keys for (o4-mini anchor + `claude-sonnet-4-6` — `ANTHROPIC_API_KEY` present — + one more reasoning family) in `_select_llms`/the forecast call (`main.py:756-800`); **fix the concurrency race** (don't mutate shared `self._llms['default']` per draw); keep geo-odds (`main.py:155-191`); gate each member on an **accuracy floor AND divergence** from the anchor; drop weak-and-correlated members (Self-MoA); reserve the strongest affordable model for a **double-weighted slot**.

### Rank 3 — Christian's quant judgment, made mechanical (MiniBench data-source + shape calibration) (mixed)
**Why:** MiniBench auto-generates numerics from FRED/yfinance/Google Trends; pulling the **actual series** beats fuzzy search and kills hallucinated anchors; it's the cheapest/fastest/most-paid-realistic lane and uses his existing tooling. **Honest corrections from the verdicts:** numeric is bots' **strongest** category (Q1 −8.7), not weakest (**MC is**, −37.5/−32.9); the 0.2/bin cap means a precise point estimate can't become a spike; near-random-walk series mean the fetch edge **erodes** once peers copy. So the durable residue is **vol-aware band width + tail calibration** (his edge), not the copyable fetch.
**How:** Add a data-source branch in `run_research` (`main.py:195`) detecting FRED/yfinance/Trends numerics → feed latest value/path/realized vol into the numeric prompt (`main.py:429`); set P10–P90 width from realized vol, calibrated on the harness; route MiniBench numerics through it. Secondary: harness-gated crypto/markets/macro base-rate priors. Judge over many noisy 60-Q rounds.

### Rank 4 — Conditional calibration DIAGNOSIS, not a global remap (moderate)
**Why:** A global 30%→40% remap is **not-an-edge** (SDK-built-in, Metaculus-recommended, symmetric, perishable, recovers only calibration → zero sharpness). The defensible use of Rank-1 data is **finding the segments (type/domain/horizon) we systematically mis-resolve and fixing them upstream**, which adds the discrimination the field lacks (Q3: bots 21pp vs humans 36pp, [Q3 analysis](https://www.lesswrong.com/posts/LHdNtJCm93pxNHJKb/can-ai-outpredict-humans-results-from-metaculus-s-q3-ai)).
**How:** With 100+ resolved binaries, compute calibration **and discrimination by segment**; fix upstream research/routing/prompt per weak segment, re-gate. Only if a residual GLOBAL miscalibration persists on a **fixed** model for a full season, apply the SDK `LogisticRecalibrationAdjuster` as a capped, leave-one-out-validated final transform — re-fit on every model change. No fixed-coefficient extremizing (already flagged cargo-cult in `optimization-plan.md`).

### Rank 5 — Reliability hardening + precision tail-blunder guard (low / hygiene)
**Why:** Coverage is a **multiplicative floor** (90% vs 100% ≈ −19% of an equal prize) and GH Actions crons are best-effort + **auto-disable after 60 days of repo inactivity** → a silent season-zeroing risk; today there's no alerting/redundancy. Separately, the field's #1 error is **wrong facts, not reasoning** (the 99%-on-Walz case, [Q4 writeup](https://www.lesswrong.com/posts/P8YwCvHoF2FHQoHjF/metaculus-q4-ai-benchmarking-bots-are-closing-the-gap)), and one confident-wrong blunder flips a noisy MiniBench round to $0.
**How:** dead-man's-switch ping (healthchecks.io) + alert on 0-new-forecast/errored runs; redundant `workflow_dispatch` trigger; keep repo active; harden numeric/MC parsing so format failures don't forfeit coverage. Tail guard: fire **only** on extreme aggregates resting on a single load-bearing current fact → one fresh targeted search → pull toward base rate **only if contradicted**; never touch correctly-confident forecasts; **A/B-gate it** (intrinsic self-critique can be net-negative, [LLMs-Cannot-Self-Correct](https://arxiv.org/abs/2310.01798)). **Delete** the dead "re-forecast before close" TODO.

---

## 5. Don't over-invest here (crowded / table-stakes / actively wrong)

Search + frontier model + N-draw single-model ensemble + base-rate decomposition + geo-odds prompts (template/public); prompt-wording wars (model >> scaffolding); chasing premium models on every draw (spend war we lose); **global recalibration/fixed extremizing** as a "rare edge" (SDK-built-in, symmetric); coverage/early-cron as a *differentiator* (it's a floor); **static NO/status-quo tilt** (anti-calibrated, loses the 20% YES); **variance-control shrinkage of calibrated forecasts** (backwards — payout is convex, rewards the right tail); **re-forecast-before-close** (dead lever here); the **0.2/bin CDF cap** as a free lunch (SDK gives it to everyone); **naive backtesting on old resolved Qs** / re-targeting benchmark.py to resolved outcomes (leakage); generic "think like a trader" text and live per-question human override (copyable / unscalable). Full reasoning in the structured `avoidCrowded` list.

---

## 6. Sequencing

1. **Now (plumbing):** Rank-1 persistence + resolution-join + hard merge-gate rule, and Rank-5 alerting/redundancy. Prerequisites; without them the rest is aspirational.
2. **This season:** Rank-2 decorrelated ensemble (fix the race) + spend the $300 on the forecaster slot; Rank-3 MiniBench data-source branch (fast feedback).
3. **Season 2+ (once 100+ resolved):** Rank-4 conditional diagnosis; revisit ensemble membership and any residual global recalibration with real data.

## 7. Sources
Q1 [forum](https://forum.effectivealtruism.org/posts/mwcWxwdsEMexm98GF/q1-ai-benchmarking-results-human-pros-crush-bots) / [LessWrong](https://www.lesswrong.com/posts/rDy5z8ZEtMrEGnfBd/q1-ai-benchmark-results-pro-forecasters-crush-bots) · Q2 [forum](https://forum.effectivealtruism.org/posts/F2stjK9wHSy3HPEC9/q2-ai-benchmark-results-pros-maintain-clear-lead) / [LessWrong](https://www.lesswrong.com/posts/Surnjh8A4WjgtQTkZ/q2-ai-benchmark-results-pros-maintain-clear-lead) · [Q3](https://www.lesswrong.com/posts/LHdNtJCm93pxNHJKb/can-ai-outpredict-humans-results-from-metaculus-s-q3-ai) · [Q4](https://www.lesswrong.com/posts/P8YwCvHoF2FHQoHjF/metaculus-q4-ai-benchmarking-bots-are-closing-the-gap) · [Mantic/Thinking Machines](https://thinkingmachines.ai/news/training-llms-to-predict-world-events/) · [Panshul42 winner repo](https://github.com/Panshul42/Forecasting_Bot_Q2) · [scores FAQ](https://www.metaculus.com/help/scores-faq/) / [tournament rules](https://www.metaculus.com/tournament-rules/) · [FutureEval resources](https://www.metaculus.com/notebooks/38928/futureeval-resources-page/) · [Summer 2026 announcement](https://forum.effectivealtruism.org/posts/ZfLAN557rGWACKtmc/announcing-metaculus-summer-2026-futureeval-bot-tournament) · [LLM-vs-experts](https://arxiv.org/html/2507.04562v3) · [LLMs Cannot Self-Correct](https://arxiv.org/abs/2310.01798) · [AIA Forecaster](https://arxiv.org/abs/2511.07678) · [wisdom of silicon crowd](https://www.science.org/doi/10.1126/sciadv.adp1528) · SDK internals (local): `calibration_adjustment/logistic_recalibration_adjuster.py`, `data_models/numeric_report.py` (`MAX_NUMERIC_PMF_VALUE=0.2`), `cp_benchmarking/benchmarker.py`.