import argparse
import asyncio
import json
import logging
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import dotenv

# Runtime helpers (env validation, banners, dependency-warning suppression).
from bot_helpers import (
    check_environment,
    print_run_summary_banner,
    print_startup_banner,
    silence_noisy_dependencies,
)
from forecast_log import log_forecasts

silence_noisy_dependencies()

from forecasting_tools import (
    AskNewsSearcher,
    BinaryQuestion,
    ForecastBot,
    GeneralLlm,
    MetaculusClient,
    MetaculusQuestion,
    MultipleChoiceQuestion,
    NumericDistribution,
    NumericQuestion,
    DateQuestion,
    DatePercentile,
    Percentile,
    ConditionalQuestion,
    ConditionalPrediction,
    PredictionTypes,
    PredictionAffirmed,
    BinaryPrediction,
    PredictedOption,
    PredictedOptionList,
    ReasonedPrediction,
    SmartSearcher,
    clean_indents,
    structure_output,
)

dotenv.load_dotenv()
logger = logging.getLogger(__name__)


class EdgeForecastBot(ForecastBot):
    """
    Christian's forecasting bot for the Metaculus AI Benchmark / FutureEval tournaments.

    Built on the official Metaculus template (a ForecastBot subclass from the
    `forecasting-tools` SDK), but with the *brain* re-tuned: the reasoning prompts
    encode a prediction-market trader's discipline (outside-view base rates first,
    conservative inside-view adjustment, explicit premortem, hard calibration rules)
    rather than the generic "interviewing for a job" framing. Every forecast is
    logged to data/forecasts.jsonl for calibration review (see forecast_log.py).

    --- original template notes below ---
    This is a copy of what is used by Metaculus to run the Metac Bots in our benchmark, provided as a template for new bot makers.
    This template is given as-is, and is use-at-your-own-risk.
    We have covered most test cases in forecasting-tools it may be worth double checking key components locally.
    So far our track record has been 1 mentionable bug per season (affecting forecasts for 1-2% of total questions)

    Main changes since Fall:
    - Additional prompting has been added to numeric questions to emphasize putting pecentile values in the correct order.
    - Support for conditional and date questions has been added
    - Note: Summer AIB will not use date/conditional questions, so these are only for forecasting on the main site as you wish.

    The main entry point of this bot is `bot.forecast_on_tournament(tournament_id)` in the parent class.
    See the script at the bottom of the file for more details on how to run the bot.
    Ignoring the finer details, the general flow is:
    - Load questions from Metaculus
    - For each question
        - Execute run_research a number of times equal to research_reports_per_question
        - Execute respective run_forecast function `predictions_per_research_report * research_reports_per_question` times
        - Aggregate the predictions
        - Submit prediction (if publish_reports_to_metaculus is True)
    - Return a list of ForecastReport objects

    Alternatively, you can use the MetaculusClient to make a custom filter of questions to forecast on
    and forecast them with `bot.forecast_questions(questions)`

    Only the research and forecast functions need to be implemented in ForecastBot subclasses,
    though you may want to override other ForecastBot functions.
    In this example, you can change the prompts to be whatever you want since,
    structure_output uses an LLM to intelligently reformat the output into the needed structure.

    By default (i.e. 'tournament' mode), when you run this script, it will forecast on any open questions in the
    primary bot tournament and MiniBench. If you want to forecast on only one or the other, you can remove one
    of them from the 'tournament' mode code at the bottom of the file.

    You can experiment with what models work best with your bot by using the `llms` parameter when initializing the bot.
    You can initialize the bot with any number of models. For example,
    ```python
    my_bot = MyBot(
        ...
        llms={  # choose your model names or GeneralLlm llms here, otherwise defaults will be chosen for you
            "default": GeneralLlm(
                model="openrouter/openai/gpt-4o", # "anthropic/claude-sonnet-4-20250514", etc (see docs for litellm)
                temperature=0.3,
                timeout=40,
                allowed_tries=2,
            ),
            "summarizer": "openai/gpt-4o-mini",
            "researcher": "asknews/news-summaries",
            "parser": "openai/gpt-4o-mini",
        },
    )
    ```

    Then you can access the model in custom functions like this:
    ```python
    research_strategy = self.get_llm("researcher", "model_name"
    if research_strategy == "asknews/news-summaries":
        ...
    # OR
    summarizer = await self.get_llm("summarizer", "llm").invoke(prompt)
    # OR
    reasoning = await self.get_llm("default", "llm").invoke(prompt)
    ```

    If you end up having trouble with rate limits and want to try a more sophisticated rate limiter try:
    ```python
    from forecasting_tools import RefreshingBucketRateLimiter
    rate_limiter = RefreshingBucketRateLimiter(
        capacity=2,
        refresh_rate=1,
    ) # Allows 1 request per second on average with a burst of 2 requests initially. Set this as a class variable
    await self.rate_limiter.wait_till_able_to_acquire_resources(1) # 1 because it's consuming 1 request (use more if you are adding a token limit)
    ```
    Additionally OpenRouter has large rate limits immediately on account creation
    """

    _max_concurrent_questions = (
        1  # Set this to whatever works for your search-provider/ai-model rate limits
    )
    _concurrency_limiter = asyncio.Semaphore(_max_concurrent_questions)
    _structure_output_validation_samples = 2

    # ── Tuning knobs (A/B-able on the benchmark harness) ──
    # Aggregation: geometric mean of odds beats the SDK's median(binary)/mean(MC)
    # on ~850 resolved Metaculus binaries (log score 0.370 vs 0.380 vs 0.392).
    # Unlike the median it keeps information from every draw. Set "sdk_default" to A/B.
    aggregation_method: str = "geo_odds"  # "geo_odds" | "sdk_default"
    # Prepend an explicit outside-view base-rate research section (the Q2 winner's
    # technique). Costs one extra LLM call per question; closes the gap where the
    # news dump lacks base rates so the forecaster would otherwise confabulate them.
    use_base_rate_research: bool = True
    # Agentic supervisor (binary-only v1, AIA-Forecaster pattern, arXiv 2511.07678):
    # when the 5 draws DISAGREE, run fresh targeted searches on the specific
    # disagreement, then override the geo-mean ONLY on a high-confidence verdict —
    # otherwise fall back, so it cannot make a forecast worse by design.
    # use_supervisor=True  -> supervisor verdict is SUBMITTED (gate must pass first).
    # supervisor_shadow=True -> supervisor runs + logs its verdict but geo-odds is
    #   still submitted. Community predictions are HIDDEN from bot accounts, so the
    #   community-proxy benchmark can't score us — shadow mode makes the tournament
    #   itself the A/B: resolve.py compares Brier(supervisor) vs Brier(geo-odds) on
    #   our own resolved questions, leakage-free.
    use_supervisor: bool = False
    supervisor_shadow: bool = False
    supervisor_min_spread: float = 0.15  # only fire when max-min draw spread ≥ this
    SUPERVISOR_LOG = Path("data/supervisor.jsonl")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Per-question draw rationales for the supervisor (instance-level so A/B
        # bot pairs in the Benchmarker don't cross-contaminate).
        self._draw_notes: dict[str, list[dict]] = {}
        self._draw_notes_lock = asyncio.Lock()

    @staticmethod
    def _question_key(question: MetaculusQuestion) -> str:
        return getattr(question, "page_url", "") or str(getattr(question, "id_of_post", id(question)))

    async def _make_prediction(self, question, research):
        """Record each binary draw's probability + rationale so the supervisor can
        read WHERE the draws disagree (the framework only hands values to the
        aggregator, not reasonings)."""
        reasoned = await super()._make_prediction(question, research)
        try:
            if isinstance(question, BinaryQuestion) and isinstance(reasoned.prediction_value, float):
                async with self._draw_notes_lock:
                    self._draw_notes.setdefault(self._question_key(question), []).append(
                        {"p": reasoned.prediction_value, "reasoning": str(reasoned.reasoning or "")[:600]}
                    )
        except Exception:  # bookkeeping must never break a forecast
            pass
        return reasoned

    async def _aggregate_predictions(self, predictions, question):
        """Geometric mean of odds for binary + multiple-choice; SDK default
        (per-percentile median) for numeric/date. Pooling odds is better-calibrated
        than the median on real Metaculus questions and uses every draw. Binary can
        additionally route through the agentic supervisor when enabled."""
        notes: list[dict] = []
        if isinstance(question, BinaryQuestion):
            async with self._draw_notes_lock:  # always drain, even on non-geo paths
                notes = self._draw_notes.pop(self._question_key(question), [])

        if self.aggregation_method != "geo_odds" or not predictions:
            return await super()._aggregate_predictions(predictions, question)

        def clamp(p: float) -> float:
            return max(0.01, min(0.99, float(p)))

        if isinstance(question, BinaryQuestion):
            log_odds = [math.log(clamp(p) / (1.0 - clamp(p))) for p in predictions]
            o = math.exp(sum(log_odds) / len(log_odds))
            p0 = clamp(o / (1.0 + o))
            if (self.use_supervisor or self.supervisor_shadow) and len(predictions) >= 3:
                try:
                    p_supervised = await self._supervise_binary(
                        question, [clamp(p) for p in predictions], notes, p0
                    )
                    if self.use_supervisor:  # live: submit the supervised number
                        return p_supervised
                except Exception as exc:
                    logger.warning(f"supervisor failed ({exc}); using geo-odds aggregate")
            return p0  # shadow mode (or supervisor off/failed): submit geo-odds

        if isinstance(question, MultipleChoiceQuestion):
            option_names = [opt.option_name for opt in predictions[0].predicted_options]
            pooled: dict[str, float] = {}
            for name in option_names:
                ps = [
                    clamp(opt.probability)
                    for option_list in predictions
                    for opt in option_list.predicted_options
                    if opt.option_name == name
                ]
                o = math.exp(sum(math.log(p / (1.0 - p)) for p in ps) / len(ps))
                pooled[name] = max(0.01, o / (1.0 + o))  # per-option floor
            total = sum(pooled.values()) or 1.0
            return PredictedOptionList(
                predicted_options=[
                    PredictedOption(option_name=name, probability=prob / total)  # renormalize to 1
                    for name, prob in pooled.items()
                ]
            )

        # numeric / date / conditional → SDK's per-percentile median (don't extremize tails)
        return await super()._aggregate_predictions(predictions, question)

    ################################## SUPERVISOR ##################################

    async def _supervise_binary(
        self,
        question: BinaryQuestion,
        draw_ps: list[float],
        notes: list[dict],
        p0: float,
    ) -> float:
        """Agentic reconciliation of disagreeing draws (AIA-Forecaster pattern):
        (1) skip when draws already agree; (2) a search model investigates the
        SPECIFIC disagreement with fresh live searches; (3) a judge model issues a
        verdict that only overrides the geo-mean at high confidence. Every decision
        is logged to data/supervisor.jsonl for the flywheel."""
        spread = max(draw_ps) - min(draw_ps)
        record: dict = {
            "at": datetime.now(timezone.utc).isoformat(),
            "url": getattr(question, "page_url", None),
            "question_id": getattr(question, "id_of_post", None),
            "mode": "live" if self.use_supervisor else "shadow",
            "p0": round(p0, 4),
            "draws": [round(p, 3) for p in draw_ps],
            "spread": round(spread, 3),
            "fired": False,
            "used": "geo_odds",
        }
        if spread < self.supervisor_min_spread:
            self._log_supervisor(record)
            return p0

        record["fired"] = True
        gists = "\n".join(
            f"- Draw {i + 1} said {n['p']:.0%}: {n['reasoning'][:350]}"
            for i, n in enumerate(notes)
        ) or "\n".join(f"- Draw {i + 1} said {p:.0%}" for i, p in enumerate(draw_ps))

        search_prompt = clean_indents(
            f"""
            Several independent forecasters disagree on this question. Your job is to
            resolve their SPECIFIC disagreement with fresh, current information.

            Question: {question.question_text}
            Resolution criteria: {question.resolution_criteria}
            Today is {datetime.now().strftime("%Y-%m-%d")}.

            The forecasters' positions:
            {gists}

            First, name the 1-3 pivotal factual cruxes their disagreement turns on.
            Then search the live web to resolve each crux, and report concrete,
            dated findings. Use primary news/data sources; do NOT cite prediction-market
            or forecasting-aggregator pages (Metaculus, Polymarket, Kalshi). Do not
            output a probability — findings only.
            """
        )
        researcher = self.get_llm("researcher")
        search_llm = researcher if isinstance(researcher, GeneralLlm) else self.get_llm("default", "llm")
        findings = await search_llm.invoke(search_prompt)

        judge_prompt = clean_indents(
            f"""
            You are the supervising forecaster reconciling disagreeing estimates.

            Question: {question.question_text}
            Resolution criteria: {question.resolution_criteria}
            Today is {datetime.now().strftime("%Y-%m-%d")}.

            Independent estimates: {", ".join(f"{p:.0%}" for p in draw_ps)}
            Their current pooled aggregate: {p0:.0%}

            Fresh targeted research on their disagreement:
            {findings}

            Decide whether the fresh evidence clearly resolves the disagreement.
            Report confidence "high" ONLY if the findings decisively favor one side;
            if the evidence is mixed, stale, or inconclusive, report "low" — the
            pooled aggregate will then stand, which is the safe default.

            The last two lines you write must be exactly:
            Probability: ZZ%
            Confidence: high|medium|low
            """
        )
        verdict = await self.get_llm("default", "llm").invoke(judge_prompt)
        prob_match = re.search(r"Probability:\s*([0-9]+(?:\.[0-9]+)?)\s*%", verdict or "")
        conf_match = re.search(r"Confidence:\s*(high|medium|low)", verdict or "", re.IGNORECASE)
        record["confidence"] = conf_match.group(1).lower() if conf_match else None
        if prob_match:
            record["revised"] = round(max(0.01, min(0.99, float(prob_match.group(1)) / 100.0)), 4)

        if record.get("confidence") == "high" and "revised" in record:
            record["used"] = "supervisor"
            self._log_supervisor(record)
            logger.info(
                f"supervisor OVERRIDE {record['url']}: {p0:.2f} -> {record['revised']:.2f} (spread {spread:.2f})"
            )
            return float(record["revised"])
        self._log_supervisor(record)
        return p0

    def _log_supervisor(self, record: dict) -> None:
        try:
            self.SUPERVISOR_LOG.parent.mkdir(parents=True, exist_ok=True)
            with self.SUPERVISOR_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception as exc:
            logger.warning(f"supervisor log write failed: {exc}")

    ##################################### RESEARCH #####################################

    async def run_research(self, question: MetaculusQuestion) -> str:
        async with self._concurrency_limiter:
            research = ""
            researcher = self.get_llm("researcher")

            prompt = clean_indents(
                f"""
                You are an assistant to a superforecaster.
                The superforecaster will give you a question they intend to forecast on.
                To be a great assistant, you generate a concise but detailed rundown of the most relevant news, including if the question would resolve Yes or No based on current information.
                You do not produce forecasts yourself.

                Question:
                {question.question_text}

                This question's outcome will be determined by the specific criteria below:
                {question.resolution_criteria}

                {question.fine_print}
                """
            )

            if isinstance(researcher, GeneralLlm):
                research = await researcher.invoke(prompt)
            elif (
                researcher == "asknews/news-summaries"
                or researcher == "asknews/deep-research/low-depth"
                or researcher == "asknews/deep-research/medium-depth"
                or researcher == "asknews/deep-research/high-depth"
            ):
                research = await AskNewsSearcher().call_preconfigured_version(
                    researcher, prompt
                )
            elif researcher.startswith("smart-searcher"):
                model_name = researcher.removeprefix("smart-searcher/")
                searcher = SmartSearcher(
                    model=model_name,
                    temperature=0,
                    num_searches_to_run=2,
                    num_sites_per_search=10,
                    use_advanced_filters=False,
                )
                research = await searcher.invoke(prompt)
            elif not researcher or researcher == "None" or researcher == "no_research":
                research = ""
            else:
                research = await self.get_llm("researcher", "llm").invoke(prompt)

            if self.use_base_rate_research:
                research = await self._add_base_rate_research(question, research)
            logger.info(f"Found Research for URL {question.page_url}:\n{research}")
            return research

    async def _add_base_rate_research(
        self, question: MetaculusQuestion, situation_research: str
    ) -> str:
        """Outside-view leg: have the model generate reference-class sub-questions and
        answer each with the historical base rate, then prepend it to the news/situation
        research. The forecast prompts demand a base rate in step (a); this supplies the
        evidence so the model doesn't confabulate it."""
        prompt = clean_indents(
            f"""
            You are a base-rate analyst for a superforecaster. Do NOT give a final forecast.
            For the question below, identify 3-5 reference classes / comparison sets, and
            for each state the historical BASE RATE: how often this kind of event happened,
            with the count, the sample size, and the time period. Be concrete and numeric.
            If a base rate is genuinely unknown, say so rather than inventing one.

            Question: {question.question_text}

            Resolution criteria: {question.resolution_criteria}
            """
        )
        try:
            base_rates = await self.get_llm("default", "llm").invoke(prompt)
        except Exception as exc:  # never let the extra pass kill the forecast
            logger.warning(f"base-rate research failed ({exc}); using situation research only")
            return situation_research
        return clean_indents(
            f"""
            ## Base rates / reference class (outside view)
            {base_rates}

            ## Current situation (inside view)
            {situation_research}
            """
        )

    ##################################### BINARY QUESTIONS #####################################

    async def _run_forecast_on_binary(
        self, question: BinaryQuestion, research: str
    ) -> ReasonedPrediction[float]:
        prompt = clean_indents(
            f"""
            You are a calibrated superforecaster with a prediction-market trader's discipline.
            You are scored on accuracy and calibration over many questions — not on sounding confident.
            Your edge comes from anchoring on base rates and resisting the pull of vivid narratives.

            Question:
            {question.question_text}

            Question background:
            {question.background_info}


            This question's outcome will be determined by the specific criteria below. These criteria have not yet been satisfied:
            {question.resolution_criteria}

            {question.fine_print}


            Your research assistant says:
            {research}

            Today is {datetime.now().strftime("%Y-%m-%d")}.

            Reason in this exact order, writing each step:
            (a) OUTSIDE VIEW — the reference class and its base rate. In similar past situations, how often did this kind of event actually happen? State the base rate as your starting probability, BEFORE looking at the specifics.
            (b) Time left until resolution, and the status quo outcome if nothing changed. Good forecasters put extra weight on the status quo, because the world changes slowly most of the time.
            (c) A concrete scenario that resolves NO.
            (d) A concrete scenario that resolves YES.
            (e) INSIDE VIEW — how far, and in which direction, does the specific evidence justify moving off the base rate? Move conservatively; most situations end up closer to the base rate than the current narrative suggests.
            (f) PREMORTEM — the single strongest reason your forecast could be wrong, and whether that should pull your probability back toward 50%.

            Calibration rules: never output 0% or 100%. Discount recency and narrative bias — a dramatic recent headline rarely moves a well-anchored base rate as much as it feels like it should. When genuinely uncertain, stay closer to the base rate than to the extremes.
            {self._get_conditional_disclaimer_if_necessary(question)}

            The last thing you write is your final answer as: "Probability: ZZ%", 0-100
            """
        )

        return await self._binary_prompt_to_forecast(question, prompt)

    async def _binary_prompt_to_forecast(
        self,
        question: BinaryQuestion,
        prompt: str,
    ) -> ReasonedPrediction[float]:
        reasoning = await self.get_llm("default", "llm").invoke(prompt)
        logger.info(f"Reasoning for URL {question.page_url}: {reasoning}")
        binary_prediction: BinaryPrediction = await structure_output(
            reasoning,
            BinaryPrediction,
            model=self.get_llm("parser", "llm"),
            num_validation_samples=self._structure_output_validation_samples,
        )
        decimal_pred = max(0.01, min(0.99, binary_prediction.prediction_in_decimal))

        logger.info(
            f"Forecasted URL {question.page_url} with prediction: {decimal_pred}."
        )
        return ReasonedPrediction(prediction_value=decimal_pred, reasoning=reasoning)

    ##################################### MULTIPLE CHOICE QUESTIONS #####################################

    async def _run_forecast_on_multiple_choice(
        self, question: MultipleChoiceQuestion, research: str
    ) -> ReasonedPrediction[PredictedOptionList]:
        prompt = clean_indents(
            f"""
            You are a calibrated superforecaster with a prediction-market trader's discipline.
            You are scored on accuracy and calibration across many questions, not on confidence.

            Question:
            {question.question_text}

            The options are: {question.options}


            Background:
            {question.background_info}

            {question.resolution_criteria}

            {question.fine_print}


            Your research assistant says:
            {research}

            Today is {datetime.now().strftime("%Y-%m-%d")}.

            Reason in this exact order, writing each step:
            (a) OUTSIDE VIEW — the base rate across these options from the relevant reference class. Start from this distribution before adjusting.
            (b) The time left until resolution and the status quo outcome if nothing changed.
            (c) A scenario that produces an unexpected outcome.
            (d) PREMORTEM — which option are you most likely overconfident about, and why.

            {self._get_conditional_disclaimer_if_necessary(question)}
            You write your rationale remembering that (1) good forecasters put extra weight on the status quo outcome since the world changes slowly most of the time, and (2) good forecasters leave some moderate probability on most options to account for unexpected outcomes — never drive an option to 0% or 100%.

            The last thing you write is your final probabilities for the N options in this order {question.options} as:
            Option_A: Probability_A
            Option_B: Probability_B
            ...
            Option_N: Probability_N
            """
        )
        return await self._multiple_choice_prompt_to_forecast(question, prompt)

    async def _multiple_choice_prompt_to_forecast(
        self,
        question: MultipleChoiceQuestion,
        prompt: str,
    ) -> ReasonedPrediction[PredictedOptionList]:
        parsing_instructions = clean_indents(
            f"""
            Make sure that all option names are one of the following:
            {question.options}

            The text you are parsing may prepend these options with some variation of "Option" which you should remove if not part of the option names I just gave you.
            Additionally, you may sometimes need to parse a 0% probability. Please do not skip options with 0% but rather make it an entry in your final list with 0% probability.
            """
        )
        reasoning = await self.get_llm("default", "llm").invoke(prompt)
        logger.info(f"Reasoning for URL {question.page_url}: {reasoning}")
        predicted_option_list: PredictedOptionList = await structure_output(
            text_to_structure=reasoning,
            output_type=PredictedOptionList,
            model=self.get_llm("parser", "llm"),
            num_validation_samples=self._structure_output_validation_samples,
            additional_instructions=parsing_instructions,
        )

        logger.info(
            f"Forecasted URL {question.page_url} with prediction: {predicted_option_list}."
        )
        return ReasonedPrediction(
            prediction_value=predicted_option_list, reasoning=reasoning
        )

    ##################################### NUMERIC QUESTIONS #####################################

    async def _run_forecast_on_numeric(
        self, question: NumericQuestion, research: str
    ) -> ReasonedPrediction[NumericDistribution]:
        upper_bound_message, lower_bound_message = (
            self._create_upper_and_lower_bound_messages(question)
        )
        prompt = clean_indents(
            f"""
            You are a calibrated superforecaster with a prediction-market trader's discipline.
            You are scored on accuracy and calibration across many questions, not on confidence.

            Your question is:
            {question.question_text}

            Background:
            {question.background_info}

            {question.resolution_criteria}

            {question.fine_print}

            Units for answer: {question.unit_of_measure if question.unit_of_measure else "Not stated (please infer this)"}

            Your research assistant says:
            {research}

            Today is {datetime.now().strftime("%Y-%m-%d")}.

            {lower_bound_message}
            {upper_bound_message}

            Formatting Instructions:
            - Please notice the units requested and give your answer in these units (e.g. whether you represent a number as 1,000,000 or 1 million).
            - Never use scientific notation.
            - Always start with a smaller number (more negative if negative) and then increase from there. The value for percentile 10 should always be less than the value for percentile 20, and so on.

            Reason in this exact order, writing each step:
            (a) OUTSIDE VIEW — the reference class and what history / base rates suggest for a quantity like this. Anchor here first, before the specifics.
            (b) The time left until the outcome is known, and the outcome if nothing changed.
            (c) The outcome if the current trend continued.
            (d) The expectations of experts and markets.
            (e) An unexpected scenario that results in a LOW outcome.
            (f) An unexpected scenario that results in a HIGH outcome.

            {self._get_conditional_disclaimer_if_necessary(question)}
            You remind yourself that good forecasters are humble and set WIDE 90/10 confidence intervals to account for unknown unknowns — under-confident (too-narrow) intervals are punished hard when reality lands in the tail. Concretely: your Percentile-90 minus Percentile-10 spread should be at least as wide as the realized range of this quantity over the past ~5 comparable periods; when unsure, err WIDER.

            The last thing you write is your final answer as:
            "
            Percentile 10: XX (lowest number value)
            Percentile 20: XX
            Percentile 40: XX
            Percentile 60: XX
            Percentile 80: XX
            Percentile 90: XX (highest number value)
            "
            """
        )
        return await self._numeric_prompt_to_forecast(question, prompt)

    async def _numeric_prompt_to_forecast(
        self,
        question: NumericQuestion,
        prompt: str,
    ) -> ReasonedPrediction[NumericDistribution]:
        reasoning = await self.get_llm("default", "llm").invoke(prompt)
        logger.info(f"Reasoning for URL {question.page_url}: {reasoning}")
        parsing_instructions = clean_indents(
            f"""
            The text given to you is trying to give a forecast distribution for a numeric question.
            - This text is trying to answer the numeric question: "{question.question_text}".
            - When parsing the text, please make sure to give the values (the ones assigned to percentiles) in terms of the correct units.
            - The units for the forecast are: {question.unit_of_measure}
            - Your work will be shown publicly with these units stated verbatim after the numbers your parse.
            - As an example, someone else guessed that the answer will be between {question.lower_bound} {question.unit_of_measure} and {question.upper_bound} {question.unit_of_measure}, so the numbers parsed from an answer like this would be verbatim "{question.lower_bound}" and "{question.upper_bound}".
            - If the answer doesn't give the answer in the correct units, you should parse it in the right units. For instance if the answer gives numbers as $500,000,000 and units are "B $" then you should parse the answer as 0.5 (since $500,000,000 is $0.5 billion).
            - If percentiles are not explicitly given (e.g. only a single value is given) please don't return a parsed output, but rather indicate that the answer is not explicitly given in the text.
            - Turn any values that are in scientific notation into regular numbers.
            """
        )
        percentile_list: list[Percentile] = await structure_output(
            reasoning,
            list[Percentile],
            model=self.get_llm("parser", "llm"),
            additional_instructions=parsing_instructions,
            num_validation_samples=self._structure_output_validation_samples,
        )
        prediction = NumericDistribution.from_question(percentile_list, question)
        logger.info(
            f"Forecasted URL {question.page_url} with prediction: {prediction.declared_percentiles}."
        )
        return ReasonedPrediction(prediction_value=prediction, reasoning=reasoning)

    ##################################### DATE QUESTIONS #####################################

    async def _run_forecast_on_date(
        self, question: DateQuestion, research: str
    ) -> ReasonedPrediction[NumericDistribution]:
        upper_bound_message, lower_bound_message = (
            self._create_upper_and_lower_bound_messages(question)
        )
        prompt = clean_indents(
            f"""
            You are a calibrated superforecaster with a prediction-market trader's discipline.
            You are scored on accuracy and calibration across many questions, not on confidence.

            Your question is:
            {question.question_text}

            Background:
            {question.background_info}

            {question.resolution_criteria}

            {question.fine_print}

            Your research assistant says:
            {research}

            Today is {datetime.now().strftime("%Y-%m-%d")}.

            {lower_bound_message}
            {upper_bound_message}

            Formatting Instructions:
            - This is a date question, and as such, the answer must be expressed in terms of dates.
            - The dates must be written in the format of YYYY-MM-DD. If hours matter, please append the date with the hour in UTC and military time: YYYY-MM-DDTHH:MM:SSZ.No other formatting is allowed.
            - Always start with a lower date chronologically and then increase from there.
            - Do NOT forget this. The dates must be written in chronological order starting at the earliest time at percentile 10 and increasing from there.

            Reason in this exact order, writing each step:
            (a) OUTSIDE VIEW — the reference class and what history / base rates suggest for a quantity like this. Anchor here first, before the specifics.
            (b) The time left until the outcome is known, and the outcome if nothing changed.
            (c) The outcome if the current trend continued.
            (d) The expectations of experts and markets.
            (e) An unexpected scenario that results in a LOW outcome.
            (f) An unexpected scenario that results in a HIGH outcome.

            {self._get_conditional_disclaimer_if_necessary(question)}
            You remind yourself that good forecasters are humble and set WIDE 90/10 confidence intervals to account for unknown unknowns — under-confident (too-narrow) intervals are punished hard when reality lands in the tail. Concretely: your Percentile-90 minus Percentile-10 spread should be at least as wide as the realized range of this quantity over the past ~5 comparable periods; when unsure, err WIDER.

            The last thing you write is your final answer as:
            "
            Percentile 10: YYYY-MM-DD (oldest date)
            Percentile 20: YYYY-MM-DD
            Percentile 40: YYYY-MM-DD
            Percentile 60: YYYY-MM-DD
            Percentile 80: YYYY-MM-DD
            Percentile 90: YYYY-MM-DD (newest date)
            "
            """
        )
        forecast = await self._date_prompt_to_forecast(question, prompt)
        return forecast

    async def _date_prompt_to_forecast(
        self,
        question: DateQuestion,
        prompt: str,
    ) -> ReasonedPrediction[NumericDistribution]:
        reasoning = await self.get_llm("default", "llm").invoke(prompt)
        logger.info(f"Reasoning for URL {question.page_url}: {reasoning}")
        parsing_instructions = clean_indents(
            f"""
            The text given to you is trying to give a forecast distribution for a date question.
            - This text is trying to answer the question: "{question.question_text}".
            - As an example, someone else guessed that the answer will be between {question.lower_bound} and {question.upper_bound}, so the numbers parsed from an answer like this would be verbatim "{question.lower_bound}" and "{question.upper_bound}".
            - The output is given as dates/times please format it into a valid datetime parsable string. Assume midnight UTC if no hour is given.
            - If percentiles are not explicitly given (e.g. only a single value is given) please don't return a parsed output, but rather indicate that the answer is not explicitly given in the text.
            """
        )
        date_percentile_list: list[DatePercentile] = await structure_output(
            reasoning,
            list[DatePercentile],
            model=self.get_llm("parser", "llm"),
            additional_instructions=parsing_instructions,
            num_validation_samples=self._structure_output_validation_samples,
        )

        percentile_list = [
            Percentile(
                percentile=percentile.percentile,
                value=percentile.value.timestamp(),
            )
            for percentile in date_percentile_list
        ]
        prediction = NumericDistribution.from_question(percentile_list, question)
        logger.info(
            f"Forecasted URL {question.page_url} with prediction: {prediction.declared_percentiles}."
        )
        return ReasonedPrediction(prediction_value=prediction, reasoning=reasoning)

    def _create_upper_and_lower_bound_messages(
        self, question: NumericQuestion | DateQuestion
    ) -> tuple[str, str]:
        if isinstance(question, NumericQuestion):
            if question.nominal_upper_bound is not None:
                upper_bound_number = question.nominal_upper_bound
            else:
                upper_bound_number = question.upper_bound
            if question.nominal_lower_bound is not None:
                lower_bound_number = question.nominal_lower_bound
            else:
                lower_bound_number = question.lower_bound
            unit_of_measure = question.unit_of_measure
        elif isinstance(question, DateQuestion):
            upper_bound_number = question.upper_bound.date().isoformat()
            lower_bound_number = question.lower_bound.date().isoformat()
            unit_of_measure = ""
        else:
            raise ValueError()

        if question.open_upper_bound:
            upper_bound_message = f"The question creator thinks the number is likely not higher than {upper_bound_number} {unit_of_measure}."
        else:
            upper_bound_message = f"The outcome can not be higher than {upper_bound_number} {unit_of_measure}."

        if question.open_lower_bound:
            lower_bound_message = f"The question creator thinks the number is likely not lower than {lower_bound_number} {unit_of_measure}."
        else:
            lower_bound_message = f"The outcome can not be lower than {lower_bound_number} {unit_of_measure}."
        return upper_bound_message, lower_bound_message

    ##################################### CONDITIONAL QUESTIONS #####################################

    async def _run_forecast_on_conditional(
        self, question: ConditionalQuestion, research: str
    ) -> ReasonedPrediction[ConditionalPrediction]:
        parent_info, full_research = await self._get_question_prediction_info(
            question.parent, research, "parent"
        )
        child_info, full_research = await self._get_question_prediction_info(
            question.child, research, "child"
        )
        yes_info, full_research = await self._get_question_prediction_info(
            question.question_yes, full_research, "yes"
        )
        no_info, full_research = await self._get_question_prediction_info(
            question.question_no, full_research, "no"
        )
        full_reasoning = clean_indents(
            f"""
            ## Parent Question Reasoning
            {parent_info.reasoning}
            ## Child Question Reasoning
            {child_info.reasoning}
            ## Yes Question Reasoning
            {yes_info.reasoning}
            ## No Question Reasoning
            {no_info.reasoning}
        """
        )
        full_prediction = ConditionalPrediction(
            parent=parent_info.prediction_value,  # type: ignore
            child=child_info.prediction_value,  # type: ignore
            prediction_yes=yes_info.prediction_value,  # type: ignore
            prediction_no=no_info.prediction_value,  # type: ignore
        )
        return ReasonedPrediction(
            reasoning=full_reasoning, prediction_value=full_prediction
        )

    async def _get_question_prediction_info(
        self, question: MetaculusQuestion, research: str, question_type: str
    ) -> tuple[ReasonedPrediction[PredictionTypes | PredictionAffirmed], str]:
        from forecasting_tools.data_models.data_organizer import DataOrganizer

        previous_forecasts = question.previous_forecasts
        if (
            question_type in ["parent", "child"]
            and previous_forecasts
            and question_type not in self.force_reforecast_in_conditional
        ):
            # TODO: add option to not affirm current parent/child forecasts, create new forecast
            previous_forecast = previous_forecasts[-1]
            current_utc_time = datetime.now(timezone.utc)
            if (
                previous_forecast.timestamp_end is None
                or previous_forecast.timestamp_end > current_utc_time
            ):
                pretty_value = DataOrganizer.get_readable_prediction(previous_forecast)  # type: ignore
                prediction = ReasonedPrediction(
                    prediction_value=PredictionAffirmed(),
                    reasoning=f"Already existing forecast reaffirmed at {pretty_value}.",
                )
                return (prediction, research)  # type: ignore
        info = await self._make_prediction(question, research)
        full_research = self._add_reasoning_to_research(research, info, question_type)
        return info, full_research  # type: ignore

    def _add_reasoning_to_research(
        self,
        research: str,
        reasoning: ReasonedPrediction[PredictionTypes],
        question_type: str,
    ) -> str:
        from forecasting_tools.data_models.data_organizer import DataOrganizer

        question_type = question_type.title()
        return clean_indents(
            f"""
            {research}
            ---
            ## {question_type} Question Information
            You have previously forecasted the {question_type} Question to the value: {DataOrganizer.get_readable_prediction(reasoning.prediction_value)}
            This is relevant information for your current forecast, but it is NOT your current forecast, but previous forecasting information that is relevant to your current forecast.
            The reasoning for the {question_type} Question was as such:
            ```
            {reasoning.reasoning}
            ```
            This is absolutely essential: do NOT use this reasoning to re-forecast the {question_type} question.
            """
        )

    def _get_conditional_disclaimer_if_necessary(
        self, question: MetaculusQuestion
    ) -> str:
        if question.conditional_type not in ["yes", "no"]:
            return ""
        return clean_indents(
            """
            As you are given a conditional question with a parent and child, you are to only forecast the **CHILD** question, given the parent question's resolution.
            You never re-forecast the parent question under any circumstances, but you use probabilistic reasoning, strongly considering the parent question's resolution, to forecast the child question.
            """
        )


def _select_llms():
    """Pick the llms config from whichever credentials exist — robust against the SDK's
    default researcher, which reaches for a *-search-preview model that fails on the
    Metaculus proxy. Module-level so the benchmark harness can import and reuse it.
    Once free proxy credits land, switch the workhorse to a reasoning model
    (metaculus/o4-mini, temperature=1) and add the multi-model ensemble."""
    has_asknews = bool(os.getenv("ASKNEWS_CLIENT_ID") and os.getenv("ASKNEWS_SECRET"))
    has_search_backend = has_asknews or any(
        os.getenv(k)
        for k in ("PERPLEXITY_API_KEY", "OPENROUTER_API_KEY", "EXA_API_KEY", "OPENAI_API_KEY")
    )
    # OpenRouter (free tournament credits): pin the high-EV free config — a REASONING
    # model as the forecaster (AIB's #1 finding: "model > scaffolding") + gpt-4o-search-
    # preview for LIVE web research + cheap gpt-4o-mini for the mechanical steps. All
    # verified working on this key. (o4-mini is an o-series model → temperature MUST be 1.)
    if os.getenv("OPENROUTER_API_KEY"):
        return {
            "default": GeneralLlm(model="openrouter/openai/o4-mini", temperature=1, timeout=120),
            "researcher": GeneralLlm(model="openrouter/openai/gpt-4o-search-preview", temperature=0.1, timeout=90),
            "summarizer": GeneralLlm(model="openrouter/openai/gpt-4o-mini", temperature=0.3),
            "parser": GeneralLlm(model="openrouter/openai/gpt-4o-mini", temperature=0.3),
        }
    # Plain OpenAI key (no OpenRouter): the SDK's own defaults are fine.
    if os.getenv("OPENAI_API_KEY"):
        return None
    # Anthropic key present. The SDK's own Anthropic defaults use BARE model strings
    # (e.g. "claude-3-7-sonnet-latest") that litellm rejects ("LLM Provider NOT
    # provided"), so pin every role to a verified, provider-prefixed model: a strong
    # reasoning model (Sonnet 4.6) for forecasting + base-rate research, cheap Haiku
    # for the mechanical summarize/parse steps.
    if os.getenv("ANTHROPIC_API_KEY"):
        sonnet = "anthropic/claude-sonnet-4-6"  # verified available on this account
        haiku = "anthropic/claude-haiku-4-5"
        llms = {
            "default": GeneralLlm(model=sonnet, temperature=0.4, timeout=90),
            "summarizer": GeneralLlm(model=haiku, temperature=0.3),
            "parser": GeneralLlm(model=haiku, temperature=0.3),
        }
        if not has_search_backend:
            # No live search → research LLM-only on Sonnet. With AskNews set, leave
            # researcher unset so the SDK auto-selects asknews/news-summaries.
            llms["researcher"] = GeneralLlm(model=sonnet, temperature=0.1)
        return llms
    # Metaculus-proxy-only fallback (works ONLY if the token has proxy credits).
    return {"researcher": GeneralLlm(model="metaculus/gpt-4o", temperature=0.1)}


async def _forecast_with_coverage_retry(bot, tournament_id):
    """Forecast a tournament, then run ONE retry pass for any question that errored.
    Coverage matters: prize share = (sum of per-question peer scores)^2, so a question
    dropped by a transient error contributes 0 to the base that gets squared.
    skip_previously_forecasted_questions makes the retry hit only the failed questions."""
    reports = await bot.forecast_on_tournament(tournament_id, return_exceptions=True)
    failures = [r for r in reports if isinstance(r, BaseException)]
    if failures:
        logger.warning(
            f"{len(failures)} question(s) errored on the first pass; running a retry pass..."
        )
        retry = await bot.forecast_on_tournament(tournament_id, return_exceptions=True)
        reports = [r for r in reports if not isinstance(r, BaseException)] + retry
    return reports


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Run the template forecasting bot")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["tournament", "minibench", "metaculus_cup", "test_questions"],
        default="tournament",
        help="What to forecast on (default: tournament). 'minibench' = the bi-weekly MiniBench only (cheap, fast feedback).",
    )
    args = parser.parse_args()
    run_mode: Literal["tournament", "minibench", "metaculus_cup", "test_questions"] = args.mode

    check_environment(strict=True)
    publish_to_metaculus = True
    print_startup_banner(run_mode, will_publish=publish_to_metaculus)

    # Model selection lives at module level (_select_llms) so the benchmark harness reuses it.
    bot = EdgeForecastBot(
        research_reports_per_question=1,
        predictions_per_research_report=5,
        use_research_summary_to_forecast=False,
        publish_reports_to_metaculus=publish_to_metaculus,
        folder_to_save_reports_to=None,
        skip_previously_forecasted_questions=True,
        extra_metadata_in_explanation=True,
        llms=_select_llms(),
    )
    # Supervisor runs in SHADOW: it investigates disagreements and logs its verdict,
    # but geo-odds is what gets submitted. resolve.py compares the two on our own
    # resolved questions; the supervisor goes live only if it wins that comparison.
    bot.supervisor_shadow = True

    # Per-mode tournament URL shown in the summary banner footer. These
    # piggyback on the forecasting_tools SDK constants and need updating
    # whenever those rotate seasons.
    TOURNAMENT_URLS = {
        "tournament": "https://www.metaculus.com/tournament/summer-futureeval-2026/",
        "minibench": "https://www.metaculus.com/aib/minibench/",
        "metaculus_cup": "https://www.metaculus.com/tournament/metaculus-cup-summer-2025/",
        "test_questions": "https://www.metaculus.com/tournament/bot-testing-area/",
    }

    # Dispatch on mode. Each branch produces a list of ForecastReport (or
    # exceptions, since return_exceptions=True) which then flows into the
    # summary printers below.
    client = MetaculusClient()
    if run_mode == "tournament":
        seasonal_tournament_reports = asyncio.run(
            _forecast_with_coverage_retry(bot, client.CURRENT_AI_COMPETITION_ID)
        )
        minibench_reports = asyncio.run(
            _forecast_with_coverage_retry(bot, client.CURRENT_MINIBENCH_ID)
        )
        forecast_reports = seasonal_tournament_reports + minibench_reports
    elif run_mode == "minibench":
        # MiniBench only — the bi-weekly ~$1k / ~60-question rounds. Cheapest lane
        # and fastest scored feedback (every ~2 weeks vs a 4-month season).
        forecast_reports = asyncio.run(
            _forecast_with_coverage_retry(bot, client.CURRENT_MINIBENCH_ID)
        )
    elif run_mode == "metaculus_cup":
        # The Metaculus Cup may be uninitialized near the start of a season
        # (Jan/May/Sep). AXC_2025_TOURNAMENT_ID = 32564 and
        # AI_2027_TOURNAMENT_ID = "ai-2027" are also valid targets here.
        bot.skip_previously_forecasted_questions = False
        forecast_reports = asyncio.run(
            bot.forecast_on_tournament(
                client.CURRENT_METACULUS_CUP_ID, return_exceptions=True
            )
        )
    elif run_mode == "test_questions":
        # The bot-testing-area tournament contains all question types and is
        # the recommended target for smoke-testing your bot.
        # https://www.metaculus.com/tournament/bot-testing-area/
        bot.skip_previously_forecasted_questions = False
        forecast_reports = asyncio.run(
            bot.forecast_on_tournament(
                "bot-testing-area", return_exceptions=True
            )
        )

    bot.log_report_summary(forecast_reports)
    # Instrument everything: append every forecast to data/forecasts.jsonl for
    # calibration review and prompt/model iteration between cycles.
    log_forecasts(forecast_reports)
    print_run_summary_banner(
        forecast_reports,
        will_publish=publish_to_metaculus,
        tournament_url=TOURNAMENT_URLS.get(run_mode),
    )
