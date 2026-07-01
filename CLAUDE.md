# CLAUDE.md — metaculus-bot

Context for future sessions tending this project.

## What this is
Christian's forecasting bot for the Metaculus AI Benchmark / FutureEval tournaments — the
**task-in/money-out** income play (the one that cleared his constraints: automated scoring
means his code-validation gap is irrelevant; it monetizes his prediction-market edge; Claude
is the labor engine; <$1k, NY-eligible). See `~/research/income-opportunities/paid-work-task-in-money-out.md`.

## Stack & conventions
- Built on the official Metaculus template (`forecasting-tools` SDK, a `ForecastBot` subclass).
- **pip + venv** (`.venv/`), NOT Poetry — matches the polymarket-bot workflow. Deps in `requirements.txt`.
- Python 3.13 locally; GitHub Actions pins 3.11.
- Run: `.venv/bin/python main.py [--mode tournament|test_questions|metaculus_cup]`.

## Where the edge lives (this is what we iterate)
- The reasoning **prompts** in `main.py` (`_run_forecast_on_binary` / `_multiple_choice` / `_numeric`):
  outside-view base-rates first → conservative inside-view → premortem → hard calibration rules.
- **Model choice** via the commented `llms={...}` block in `main.py`.
- Aggregation knobs in the `EdgeForecastBot(...)` constructor (`predictions_per_research_report`,
  `research_reports_per_question`).
- `forecast_log.py` writes `data/forecasts.jsonl` — the calibration record to iterate against.

## Do NOT
- Don't reinvent the Metaculus API/submission plumbing — it's the SDK's, and it's the part that
  silently loses submissions if broken. Customize the brain, not the framework.
- Don't commit `.env` or `data/*.jsonl` (gitignored).

## Known gotchas
- **Season rollover:** `TOURNAMENT_URLS` in `main.py` are display-only and hardcoded per season;
  the real targets are the SDK's `client.CURRENT_AI_COMPETITION_ID` / `CURRENT_MINIBENCH_ID` /
  `CURRENT_METACULUS_CUP_ID`. Bump `forecasting-tools` each season so those stay current.
- Power-law payout: the stock template finishes near the bottom. Default ≠ paid. Iterate.

## The one real EDGE (per the competitive-edge research — see docs/competitive-edge-plan.md)
We cannot win on raw model power (free o4-mini vs rivals' o3/GPT-5; "model >> scaffolding"). The
only DEFENSIBLE edge for a free solo operator is the **calibration flywheel**: a private record of
every forecast joined to its real resolution, used to gate every change. Code is copyable; the
accumulated ground-truth + validated knob-settings are not, and they compound each season.
- **Flywheel plumbing:** the tournament workflow appends each run's forecasts to the **`data` branch**
  (NOT main; `data/*.jsonl` is gitignored locally). Pull it: `git fetch origin data && git show
  origin/data:forecasts.jsonl > data/forecasts.jsonl`. `resolve.py` joins forecasts→resolutions and
  reports Brier + a reliability table. `benchmark.py --ab` is the fast community-proxy A/B gate.
- **HARD MERGE GATE:** no prompt/model/aggregation change ships unless it wins on data. Discipline IS the edge.
  ⚠️ **CP is HIDDEN from bot accounts** (verified: 0 of our first 54 logged forecasts ever saw a community
  prediction; the SDK Benchmarker's score-vs-CP therefore CANNOT run on our token — its question fetch
  returns ~1 question site-wide). Gates that work: (1) **shadow mode** — run a candidate alongside the
  submitted number on live questions, log both, compare Brier on our own resolutions via `resolve.py`
  (leakage-free; the supervisor uses this). (2) `benchmark.py` vs CP only if a HUMAN-account token is
  ever used for read-only eval (flag to Christian first).
- **Roadmap (next edges, all in docs/competitive-edge-plan.md):** (1) multi-FAMILY ensemble
  (o4-mini + claude-sonnet-4-6 + another) governed by a private accuracy+divergence ledger — FIX the
  concurrency bug (5 draws run concurrently; don't mutate shared `self._llms`); (2) quant-source-data
  for MiniBench numeric (FRED/yfinance/Trends) = Christian's judgment mechanized; (3) calibration
  diagnosis once ≥100 resolved; (4) reliability hardening (dead-man's-switch, redundant trigger).
- **AVOID (crowded / NOT edges — don't over-invest):** prompt-wording wars, chasing premium models on
  every draw, global recalibration/extremizing, coverage-as-edge, static-NO tilt, re-forecast-before-close
  (dead for FutureEval), naive backtesting on resolved Qs (look-ahead leakage). The whole search+model+
  ensemble+base-rate+geo-odds stack is table stakes, not differentiation.

## Status
- v0.1 scaffolded 2026-06-17; v0.2 optimized 2026-06-22 (geo-odds, base-rate research, benchmark harness).
- **LIVE & FREE 2026-06-27:** $300 OpenRouter grant from Ben; config = o4-mini forecaster (temp 1) +
  gpt-4o-search-preview live research + gpt-4o-mini parsing. Smoke-tested clean (9/9); first REAL
  forecast posted to the $50k Summer tournament; autopilot active (every 20 min, full tournament mode).
- NEXT: flywheel now persists data; let it accrue, run `resolve.py`/`benchmark.py` as questions resolve,
  then implement the roadmap edges above (benchmark-gated).
