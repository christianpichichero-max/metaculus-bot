# Synthesis Judge — Forecasting Bot Delta Sweep

**Verdict: found-new-improvements.** There are genuinely new, primary-source-verified deltas beyond our current stack and roadmap — but none overturn the core architecture. The honest summary: our outside-view discipline, geo-mean-of-odds, coverage, and calibration flywheel are well-aligned with the 2026 frontier; the real lever remains **executing the roadmap + letting the flywheel accrue resolved data.** The new items are worth adding *behind the existing gate*, not as a pivot.

## Grounding (verified in the actual codebase, not just the JSON)
I read the code to confirm every "we don't already do this" claim:
- **Aggregation** — `/Users/christian/metaculus-bot/main.py:155-191`: `geo_odds` is mean-of-log-odds → sigmoid (binary) and per-option pooled+renormalized (MCQ). This is *exactly* α=1 in the frontier shrinkage formula → variance-shrinkage (rank 4) is a clean, minimal generalization with zero downside.
- **Research** — `main.py:195-246`: single-pass (one researcher call + one base-rate call via `_add_base_rate_research`). No belief-state, no iterative loop, no post-draw reconciliation → supervisor (rank 2) and BLF loop (rank 3) are genuinely absent. **Note:** AskNews is *already wired* at `main.py:219-227` (`AskNewsSearcher`), just toggled off → AskNews is a config swap, not new code.
- **Gate** — `/Users/christian/metaculus-bot/benchmark.py`: gates on a *single pooled SDK metric* scored *toward the community prediction*; no variance, no multi-metric, no time-window blocking. `/Users/christian/metaculus-bot/resolve.py:88-99` computes Brier+LogLoss+calibration but only on the measurement side and binary-only → flywheel-integrity (rank 5) is real and the anti-piggyback risk is concrete (live-search research can surface the very community number the gate rewards).
- **CLAUDE.md** confirms the stack, the planned roadmap, and the rejected list exactly as stated in the task.

## De-duplication (the key synthesis step)
The sweep surfaced the **BLF belief-state loop twice** — `blf-scaffold` (new-tools lens) and `F1` (missed-high-value lens) are the **same paper (arXiv 2604.18576) and the same technique**. Merged into one item (rank 3). The agentic supervisor (arXiv 2511.07678) is a *different* paper and a *different* architectural position (post-draw reconciliation vs in-research loop), so it stays distinct (rank 2). Both share the "agentic targeted search" mechanism, which is why I sequence the cheaper supervisor as a stepping stone to the heavier BLF loop.

## The genuinely-new deltas (ranked, after dedup)

| # | Delta | Source | Effort | Nature |
|---|-------|--------|--------|--------|
| 1 | Claim free Metaculus proxy + AskNews credits | EA Forum Summer-2026 announcement; Metaculus notebook 25525; metac-bot-template README | low | **Enabler** (not an edge) |
| 2 | Agentic supervisor / reconciliation pass | AIA Forecaster, arXiv 2511.07678 | medium | **Accuracy** |
| 3 | Belief-state agentic research loop (BLF) | arXiv 2604.18576 (ICML-2026 oral) | high | **Accuracy** |
| 4 | Variance-dependent shrinkage aggregation | arXiv 2604.18576 | low | **Accuracy (cheap, zero-downside)** |
| 5 | Flywheel-integrity / anti-piggyback guard | "Pitfalls in Evaluating LM Forecasters," arXiv 2506.00723 | low | **Insurance (protects the moat)** |

### 1. Free credits (the unlock — do first, time-sensitive)
We run only on the OpenRouter $300 grant. The Metaculus LLM proxy (free Anthropic/Google/OpenAI credits) and the free AskNews feed are **additional, larger, untapped channels**. This falsifies the "$300, can't win a spend war" premise underpinning several rejections, and makes the call-multiplicative supervisor + BLF affordable while de-risking the already-planned multi-family ensemble. **It is a resource unlock, not an accuracy edge** — the bot-maker survey it rests on says scaffolding, not raw tokens, is the differentiator, so spend it on scaffolding and still pass the gate. Action: email `ben@metaculus.com` (proxy) + `rob@asknews.app` (AskNews); use `GeneralLlm(model='metaculus/{model}')`.

### 2. Agentic supervisor (the headline accuracy upgrade)
Our most mechanical step is geo-meaning 5 draws with *nothing reading them*. The AIA Forecaster — the first LLM system to verifiably match superforecasters on ForecastBench — shows an agentic supervisor (reads draws → finds disagreements → runs NEW targeted searches → overrides only on HIGH confidence) beats simple-mean (**Brier 0.1125 vs 0.1140**) and *decisively* beats the non-agentic supervisor (0.1168) and generic multi-agent debate. The discard-unless-high rule means it can't hurt; A/B it via the >=100-Q gate. **Caveats:** modest gain over simple-mean (~1.3% rel.; bigger wins in tail Top@3/Worst@3); AIA fed it diverse-MODEL draws, so its value for our same-model (o4-mini) draws is weaker until the multi-family ensemble lands — it composes far better with that ensemble.

### 3. Belief-state research loop (BLF — bigger ceiling, bigger lift)
Replace single-pass research with an iterative search→update loop carrying one evolving {prob, evidence-for/against, confidence, open-Qs} object. Ablating the belief state cost **−5.1 Brier-Index (p<0.001) — larger than removing web search entirely (−3.4)**; the full system matched the superforecaster median and was the only method to beat the crowd on market questions. The decisive argument *for us*: the scaffold is a **cheap-model force-multiplier (+5.8 BI lifting a 5x-cheaper model to near-frontier)** — exactly the $300-operator lever. **Caveats:** real re-architecture, call-multiplicative (3–10x), the cheap K=1 version is unproven (all ablations were K=5), and gains were on market/sequential Qs so transfer to numeric MiniBench must be proven on our own resolved set. Build the supervisor first.

### 4. Variance-shrinkage aggregation (cheapest, zero-downside)
Generalize geo-odds to `p̂ = σ(α·mean(logit(pₖ)))`, α = 1/(1+λ·var), shrinking toward 0.5 when draws disagree. **α=1 exactly recovers current behavior** (verified at `main.py:165-168`), so downside ≈ nil. Targets our documented overconfidence-at-extremes, and is the *inverse* of the rejected fixed-coefficient extremizing (adaptive de-extremizing, not extremizing). Applies NOW to within-model 5 draws; composes with the ensemble. Treat λ as a flywheel-tuned hyperparameter (paper bundles the effect size).

### 5. Flywheel-integrity / anti-piggyback guard (protect the moat)
The whole strategy rests on the flywheel, yet benchmark.py gates on a *single pooled metric scored toward the community number* while research uses live search that can *read* that number — a change that increases crowd-parroting would score artificially well and the gate would reward contamination. Fix (cheap subset, do now): surface variance + Brier/log/calibration **in the gate decision** (resolve.py already computes them), and add an edge-over-crowd / anti-piggyback guard. **Defer** strict non-overlapping-window blocking — at <100 resolved it shrinks our same-era sample below signal; revisit on the resolved-log flywheel once a few hundred resolutions accrue. (arXiv 2506.00723. Distinct from our rejected look-ahead-leakage item.)

## Marginal / considered but NOT elevated
- **AskNews /deepnews** — marginal/duplicate. Budget conservation, not accuracy (Q2 found no demonstrable AskNews advantage). Already coded (`main.py:219-227`); adopting it is a free config swap the flywheel can test, folded into rank 1.
- **MCQ-specific handling** — marginal. MCQ is *verified* our weakest format under peer scoring (Q2: −32.9 vs binary −14.8, numeric −23.2), so it is our highest-leverage *direction*; but the proposed mechanisms (per-option binary decomposition, cyclic-permutation debiasing) are miscited, unproven for our reasoning-model free-form setting, and cost-multiplicative. Worth a cheap gated experiment (MCQ prompt tightening + light 2-3-permutation position check), not a confident build.
- **Fixed √3 log-odds extremization** — on our rejected list; the only honest move is to let the flywheel reconsider it if ever, not adopt it.

## Confirmed already at the frontier
Geo-mean-of-odds (α=1 of the frontier method); outside-view base-rate-first prompting (Q2-winner technique; further prompt tinkering = negligible gains); the calibration flywheel + hard merge gate (the single biggest AIB success correlate); coverage/never-drop (table stakes); the rejected list (all confirmed dead/crowded); and the planned multi-family ensemble + quant-source numeric data (right next steps, now de-risked by free credits).

## Recommended execution sequence
1. **Today (parallel, cheap/safe):** email for credits (rank 1); ship the variance-shrinkage one-liner behind the gate (rank 4); add the flywheel anti-piggyback guard + variance/multi-metric reporting (rank 5).
2. **Next (medium):** build the agentic supervisor (rank 2) — surgical, gate-it; it's both the headline accuracy upgrade and the stepping stone to BLF.
3. **Later (high, only if supervisor wins the gate + transfer proven):** the full BLF belief-loop (rank 3).
4. **Throughout:** let the flywheel accrue resolved questions and execute the already-planned multi-family ensemble (now affordable) + quant-source numeric data. **Most of "getting better" is execution + data accrual, not new ideas.**

## Sources
- AIA Forecaster (agentic supervisor): https://arxiv.org/abs/2511.07678
- BLF belief-state loop + variance-shrinkage: https://arxiv.org/abs/2604.18576
- Pitfalls in Evaluating LM Forecasters (flywheel integrity): https://arxiv.org/html/2506.00723v1
- Free credits: https://forum.effectivealtruism.org/posts/ZfLAN557rGWACKtmc/announcing-metaculus-summer-2026-futureeval-bot-tournament ; https://www.metaculus.com/notebooks/25525/ ; https://github.com/Metaculus/metac-bot-template
- AskNews /deepnews + Q2 results: https://docs.asknews.app/en/deepnews ; https://www.lesswrong.com/posts/Surnjh8A4WjgtQTkZ/q2-ai-benchmark-results-pros-maintain-clear-lead
- Codebase: `/Users/christian/metaculus-bot/main.py`, `/Users/christian/metaculus-bot/benchmark.py`, `/Users/christian/metaculus-bot/resolve.py`, `/Users/christian/metaculus-bot/CLAUDE.md`