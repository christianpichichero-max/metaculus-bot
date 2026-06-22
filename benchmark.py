"""Offline benchmark harness — the merge gate for any bot change.

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


def make_bot(aggregation_method: str, use_base_rate_research: bool = True) -> EdgeForecastBot:
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


async def run(bots, n: int):
    benchmarker = Benchmarker(
        forecast_bots=bots,
        number_of_questions_to_use=n,
        file_path_to_save_reports="benchmarks/",
    )
    return await benchmarker.run_benchmark()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline benchmark harness for the forecasting bot")
    parser.add_argument("--questions", type=int, default=120, help="resolved questions to test on (100+ recommended)")
    parser.add_argument("--ab", action="store_true", help="A/B geo_odds vs sdk_default aggregation")
    parser.add_argument("--no-base-rates", action="store_true", help="disable the base-rate research pass")
    args = parser.parse_args()

    use_br = not args.no_base_rates
    if args.ab:
        bots = [make_bot("geo_odds", use_br), make_bot("sdk_default", use_br)]
        print(f"A/B: geo_odds vs sdk_default aggregation over {args.questions} resolved Qs (base_rates={use_br})")
    else:
        bots = [make_bot("geo_odds", use_br)]
        print(f"Benchmarking current bot (geo_odds, base_rates={use_br}) over {args.questions} resolved Qs")

    results = asyncio.run(run(bots, args.questions))

    print("\n" + "=" * 72)
    print("BENCHMARK RESULTS (scored vs community prediction; higher = better):")
    for b in results:
        print(f"  • {_label(b)}: {_score_of(b)}")
    print("Reports saved under benchmarks/. Use 100+ Qs and multiple runs before trusting a small delta.")
    print("=" * 72 + "\n")
