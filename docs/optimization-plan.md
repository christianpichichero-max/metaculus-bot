# Bot optimization plan & status

Derived from a multi-agent research pass (AIB winner techniques + forecasting science +
framework internals), 2026-06-22. Evidence-driven; each change is A/B-able on the harness.

## The headline insight
Test changes on **resolved questions**, not the live leaderboard — custom-question
testing was the single largest measured correlate of AIB tournament success. The
`benchmark.py` harness is that gate, and it makes Christian's "can't validate code"
gap a non-issue: the benchmark decides what ships, not code-reading.

## ✅ Implemented (works on the current single-model/Anthropic bridge)
1. **Benchmark harness** (`benchmark.py`) — runs the bot over N resolved questions, scores
   vs the community prediction (SDK `Benchmarker`). `--ab` compares geo_odds vs median.
   Use 100+ questions; below that a worse variant "wins" ~30% of the time.
2. **Geometric-mean-of-odds aggregation** (`EdgeForecastBot._aggregate_predictions`) — beats
   the SDK's median(binary)/mean(MC) on ~850 resolved Metaculus binaries (log 0.370 vs 0.380
   vs 0.392). Binary + MC (with renormalize + 0.01 floor); numeric/date keep SDK median.
   Toggle: `aggregation_method = "geo_odds" | "sdk_default"`. *Verified math: geo-odds([.6,.7,.8])=0.707.*
3. **Coverage retry** (`_forecast_with_coverage_retry`) — prize share = (Σ peer scores)², so a
   dropped question contributes 0. Runs a 2nd pass that (via skip_previously_forecasted) retries
   only the failed questions.
4. **Base-rate research decomposition** (`_add_base_rate_research`) — the Q2 winner's technique:
   an outside-view pass generates reference-class sub-questions + historical base rates, prepended
   to the news/situation research so the forecaster doesn't confabulate the rate. Toggle:
   `use_base_rate_research`. Costs +1 LLM call/question.
5. **Numeric/date interval-width floor** — concrete P90−P10 spread instruction (tail miscalibration
   is where bots lose most vs pros, and one overconfident tail can flip a MiniBench round to $0).
6. **AskNews env-gate fix** — `_select_llms` now requires `ASKNEWS_CLIENT_ID` + `ASKNEWS_SECRET`
   together (the SDK needs both), moved to module level so the harness reuses it.

## ⏳ Do the moment free proxy credits + AskNews land (highest single-change EV)
- **Switch the workhorse to a reasoning model**: `metaculus/o4-mini` **temperature=1** (o-series reject
  other temps; GeneralLlm writes temp unconditionally). Use **default** effort, NOT high (AIB: o3-high
  scored *worse* than o3 — overconfidence). "Model > scaffolding" is AIB's strongest regularity.
- **Multi-model ensemble**: make the 5 draws DIVERSE. ⚠️ The 5 draws run **concurrently**, so do NOT
  mutate shared `self._llms["default"]` per draw (race). Implement concurrency-safe (e.g. pass the
  model into the forecast call, or serialize draws). Q2-winner rotation: o4-mini×2 / o3×1 / sonnet×2.
  Aggregate with geo-odds. Drop any weak model that drags the median (Self-MoA).
- **Live AskNews research**: get the free 3k/mo key (my.asknews.app, email rob@asknews.app with the bot
  username). Set the two env vars; `_select_llms` then returns None → SDK auto-selects `asknews/news-summaries`.
  Depth triage: default summaries, escalate to deep-research/low only for fast-moving questions.
- **Re-forecast-before-close pass** for questions closing within ~1-2h (spot-peer scores the *standing*
  forecast at close).
- **Learned calibration**: once ~50+ logged questions resolve, train the SDK's `LogisticRecalibrationAdjuster`
  (validate leave-one-out; deploy only if it beats unadjusted out-of-sample).

## 🚫 Skip (cargo-cult / verified not worth it)
- Fixed-coefficient extremizing (d≈1.73) on correlated same-model draws — amplifies correlated error;
  log score punishes overconfidence asymmetrically. Only consider a mild push *after* real diversity + harness.
- Gemini on the Metaculus proxy — **not served** (OpenAI + Anthropic only).
- Hardcoding `llms["researcher"]="asknews/..."` — breaks the no-key graceful path. Set env vars instead.
- Best-of-k / "pick the single best" aggregation, contrarian anti-median betting, double-digit same-model samples.
