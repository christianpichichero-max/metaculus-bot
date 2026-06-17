# metaculus-bot

An automated forecasting bot for the **Metaculus AI Benchmark / FutureEval** tournaments.
It reads open tournament questions, reasons about each one with an LLM, and submits a
calibrated probability — autonomously, on a schedule, for free, on GitHub Actions.

This is the **task-in / money-out** play: a clear payer (Metaculus, $50k/season pool),
a clear payout (prizes by accuracy), and Claude as the labor engine. The scoring is
**automated accuracy vs. real-world resolution** — no human judges our code, which is
exactly why it fits.

> **No guarantees — this is a power law.** ~80% of entrants earn $0, and the stock
> template bot finishes near the bottom. The payout comes from *iterating the forecasting
> logic*, not from running the default. Budget the first season as calibration that may
> pay $0. Cash at risk to find out: only API credits (often free — see below).

## How it works

Built on the official Metaculus template (`forecasting-tools` SDK), with the **brain re-tuned**:

```
main.py            EdgeForecastBot — a forecasting-tools ForecastBot subclass.
                   The reasoning prompts (binary / multiple-choice / numeric) encode a
                   prediction-market trader's discipline: outside-view base rates FIRST,
                   conservative inside-view adjustment, explicit premortem, hard calibration
                   rules (never 0%/100%, anchor to base rates, discount narrative/recency bias).
forecast_log.py    Appends every forecast to data/forecasts.jsonl ("instrument everything")
                   so we can review calibration and iterate prompts/models each cycle.
bot_helpers.py     Env validation + run banners (from the template, unchanged).
requirements.txt   pip-managed deps (we use pip + venv, not Poetry).
.github/workflows/ Autonomous runners:
                     run_bot_on_tournament.yaml  → every 20 min, seasonal tournament + MiniBench
                     run_bot_on_metaculus_cup.yaml → every 2 days, Metaculus Cup
                     test_bot.yaml               → manual smoke test (bot-testing-area)
reference/         The untouched template (main_with_no_framework.py) + template README.
```

The framework runs each question through research → reasons `predictions_per_research_report`
times → aggregates → submits. We supply the edge (the prompts) and the model choice.

---

## Setup — your ~3-minute part (do this once)

**1. Make a Metaculus bot account + token.**
   - Go to <https://www.metaculus.com/futureeval/participate/> and follow the steps to register a bot and get your **`METACULUS_TOKEN`**.
   - (Bot makers must be willing to let Metaculus inspect the bot — this repo is that.)

**2. Get one LLM key** (pick the easiest):
   - **OpenRouter (recommended, free tournament credits):** request credits at <https://forms.gle/aQdYMq9Pisrf1v7d8>, then get a key at <https://openrouter.ai/keys> → that's your **`OPENROUTER_API_KEY`**.
   - *or* use your **`ANTHROPIC_API_KEY`** / **`OPENAI_API_KEY`**.

**3. (Optional but recommended) Better research:** an AskNews key (`ASKNEWS_CLIENT_ID` + `ASKNEWS_SECRET`) from <https://asknews.app/> meaningfully improves forecasts. Skip for now if you want; the bot falls back to LLM-only research.

That's it. Hand me the token(s) and I'll wire them in, or follow the run steps below.

---

## Run it locally (smoke test, no real submission)

```bash
cd ~/metaculus-bot
cp .env.template .env          # then paste your real keys into .env
.venv/bin/python main.py --mode test_questions
```

`--mode test_questions` targets the public **bot-testing-area** (all question types, safe to
practice on). To dry-run without posting, set `publish_to_metaculus = False` near the bottom
of `main.py`. Forecasts are appended to `data/forecasts.jsonl`.

## Run it autonomously (the real thing — free, on GitHub Actions)

1. Push this repo to GitHub (private is fine).
2. Add your keys under **Settings → Secrets and variables → Actions → New repository secret**:
   `METACULUS_TOKEN` (required), one of `OPENROUTER_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`,
   and optionally `ASKNEWS_CLIENT_ID` + `ASKNEWS_SECRET`.
3. Enable Actions, then trigger **Test Bot** once (Actions tab → Run workflow) to confirm a green run.
4. The **tournament** workflow then runs every 20 minutes on its own, forecasting new questions
   in the live seasonal tournament + MiniBench. `skip_previously_forecasted_questions=True`
   prevents double-forecasting.

Each run uploads `data/forecasts.jsonl` as a workflow **artifact** so we can pull calibration data.

---

## Tending (the ~weekly part)

- **Iterate the brain.** The edge is in the prompts in `main.py` and the model choice. Review
  `data/forecasts.jsonl` (and your bot's Metaculus profile, which shows resolved scores) to see
  where it's mis-calibrated, then adjust.
- **Model choice.** Defaults are picked from whichever keys are set. To pin models, uncomment and
  edit the `llms={...}` block in `main.py` (e.g. a strong Claude/GPT model for `"default"`
  reasoning, a cheap one for `"parser"`/`"summarizer"`, `"asknews/news-summaries"` for `"researcher"`).
- **MiniBench** (~2-week cycles) is the fast feedback loop — use its scores to iterate quickly.
- **Season rollover gotcha:** the `TOURNAMENT_URLS` (display only) in `main.py` are hardcoded per
  season; the actual tournament IDs come from the SDK's `CURRENT_*` constants, so bumping
  `forecasting-tools` each season keeps targeting correct. See `CLAUDE.md`.

Heritage: forked from <https://github.com/Metaculus/metac-bot-template>.
