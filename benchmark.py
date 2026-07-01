"""Offline benchmark harness — scores bots against the community prediction.

⚠️ LIMITATION (verified 2026-07-01): Metaculus HIDES community predictions from bot
accounts, so with the bot's METACULUS_TOKEN this harness finds ~1 eligible question
site-wide and cannot score. It works only with a human-account token (read-only eval).
For bot-token-only validation use SHADOW MODE instead: run the candidate alongside the
submitted number on live questions and compare Brier on our own resolutions (resolve.py).

The clearest finding in the AIB data: testing changes on RESOLVED questions is the
single largest correlate of tournament success. This runs the bot over N recently-
resolved questions and scores it against the community prediction (the SDK's
Benchmarker), so we can A/B a change (e.g. geo-odds vs median aggregation, or base-rate
research on/off) BEFORE spending real submissions. It NEVER submits to Metaculus.

Usage:
  .venv/bin/python benchmark.py --questions 120          # score the current bot
  .venv/bin/python benchmark.py --ab --questions 120     # A/B geo_odds vs sdk_default
  .venv/bin/python benchmark.py --ab --no-base-rates     # isolate the aggregation change

Needs METACULUS_TOKEN + an LLM key in .env. Costs LLM calls (publish is OFF).
Aim for 100+ questions — below that there's ~30% chance the worse variant "wins" a
close comparison, so don't trust a small delta on a tiny sample or a single run.
"""
from __future__ import annotations

import argparse
import asyncio
import logging

import dotenv

from bot_helpers import silence_noisy_dependencies

silence_noisy_dependencies()

from forecasting_tools import Benchmarker  # noqa: E402

from main import EdgeForecastBot, _select_llms  # noqa: E402

dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def make_bot(
    aggregation_method: str,
    use_base_rate_research: bool = True,
    use_supervisor: bool = False,
) -> EdgeForecastBot:
    bot = EdgeForecastBot(
        research_reports_per_question=1,
        predictions_per_research_report=5,
        use_research_summary_to_forecast=False,
        publish_reports_to_metaculus=False,  # NEVER submit while benchmarking
        folder_to_save_reports_to=None,
        skip_previously_forecasted_questions=False,
        llms=_select_llms(),
    )
    bot.aggregation_method = aggregation_method
    bot.use_base_rate_research = use_base_rate_research
    bot.use_supervisor = use_supervisor
    return bot


def _score_of(benchmark) -> str:
    # BenchmarkForBot's score attribute name has changed across SDK versions; try a few.
    for attr in (
        "average_expected_baseline_score",
        "average_expected_log_score",
        "expected_baseline_score",
        "average_inverse_expected_log_score",
    ):
        val = getattr(benchmark, attr, None)
        if val is not None:
            return f"{attr}={val:.4f}" if isinstance(val, (int, float)) else f"{attr}={val}"
    return repr(benchmark)[:200]


def _label(benchmark) -> str:
    return (
        getattr(benchmark, "name", None)
        or getattr(benchmark, "bot_name", None)
        or type(getattr(benchmark, "forecast_bot", benchmark)).__name__
    )


async def _fetch_benchmark_questions(n: int):
    """Fetch benchmark-eligible questions ourselves (straight pagination) instead of
    the SDK's randomized sampler, which can exhaust its 3 random pages and raise
    'found 0, needed N'. Strict filter first, then relax until we have enough."""
    import pendulum
    from forecasting_tools import MetaculusClient
    from forecasting_tools.helpers.metaculus_client import ApiFilter

    client = MetaculusClient()
    # cp_reveal_time_lt=now is the load-bearing constraint: the community prediction
    # is HIDDEN on open questions until its reveal time, so without it the
    # community_prediction_exists post-filter drops essentially everything
    # (the cause of the SDK sampler's "found 0, needed 100" crash).
    now = pendulum.now(tz="UTC")
    tiers = [
        ("strict", ApiFilter(allowed_statuses=["open"], allowed_types=["binary"],
                             cp_reveal_time_lt=now, num_forecasters_gte=30,
                             includes_bots_in_aggregates=False,
                             community_prediction_exists=True)),
        ("relaxed", ApiFilter(allowed_statuses=["open"], allowed_types=["binary"],
                              cp_reveal_time_lt=now, num_forecasters_gte=10,
                              community_prediction_exists=True)),
    ]
    for label, api_filter in tiers:
        questions = await client.get_questions_matching_filter(
            api_filter, num_questions=n, randomly_sample=False,
            error_if_question_target_missed=False,
        )
        print(f"question fetch [{label}]: {len(questions)} eligible")
        if len(questions) >= min(n, 60):
            return questions[:n]
    return questions[:n]  # best effort — caller sees the count printed above


async def run(bots, n: int):
    questions = await _fetch_benchmark_questions(n)
    if not questions:
        raise SystemExit("No benchmark-eligible questions found — try again later.")
    benchmarker = Benchmarker(
        forecast_bots=bots,
        questions_to_use=questions,
        file_path_to_save_reports="benchmarks/",
    )
    return await benchmarker.run_benchmark()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline benchmark harness for the forecasting bot")
    parser.add_argument("--questions", type=int, default=120, help="questions to test on (100+ recommended)")
    parser.add_argument("--ab", action="store_true", help="A/B geo_odds vs sdk_default aggregation")
    parser.add_argument("--ab-supervisor", action="store_true", help="A/B supervisor ON vs OFF (both geo_odds)")
    parser.add_argument("--no-base-rates", action="store_true", help="disable the base-rate research pass")
    parser.add_argument("--concurrency", type=int, default=3, help="concurrent questions (research semaphore)")
    args = parser.parse_args()

    # The research semaphore is a class attribute; widen it for benchmark throughput.
    EdgeForecastBot._max_concurrent_questions = args.concurrency
    EdgeForecastBot._concurrency_limiter = asyncio.Semaphore(args.concurrency)

    use_br = not args.no_base_rates
    if args.ab_supervisor:
        labels = ["supervisor-ON", "supervisor-OFF"]
        bots = [make_bot("geo_odds", use_br, use_supervisor=True), make_bot("geo_odds", use_br, use_supervisor=False)]
        print(f"A/B: supervisor ON vs OFF over {args.questions} Qs (geo_odds, base_rates={use_br})")
    elif args.ab:
        labels = ["geo_odds", "sdk_default"]
        bots = [make_bot("geo_odds", use_br), make_bot("sdk_default", use_br)]
        print(f"A/B: geo_odds vs sdk_default aggregation over {args.questions} Qs (base_rates={use_br})")
    else:
        labels = ["current"]
        bots = [make_bot("geo_odds", use_br)]
        print(f"Benchmarking current bot (geo_odds, base_rates={use_br}) over {args.questions} Qs")

    results = asyncio.run(run(bots, args.questions))

    print("\n" + "=" * 72)
    print("BENCHMARK RESULTS (scored vs community prediction; higher = better):")
    for label, b in zip(labels, results):
        print(f"  • {label}: {_score_of(b)}")
    print("Reports saved under benchmarks/. Use 100+ Qs and multiple runs before trusting a small delta.")
    print("=" * 72 + "\n")
