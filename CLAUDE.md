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

## Status
- v0.1 scaffolded 2026-06-17: template forked, Poetry→pip, brain re-tuned, forecast logging wired,
  3 workflows converted, local imports/construction verified.
- NEXT (gated on Christian's keys): smoke-test `--mode test_questions` end-to-end, then push to
  GitHub + add Actions secrets + enable the 20-min tournament workflow.
