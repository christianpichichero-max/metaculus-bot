"""
Append-only forecast logger.

Christian's "instrument everything = proprietary data" principle (same one
behind the polymarket-bot): every forecast the bot makes is written to
data/forecasts.jsonl so we can review calibration (our forecast vs. the
eventual real-world resolution) and iterate the prompts/models each cycle
instead of guessing.

Design rule: this must NEVER crash a run. Forecasting is the job; logging is
bookkeeping. Every extraction is wrapped so a missing/renamed SDK attribute
degrades to a null field, not an exception.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

logger = logging.getLogger(__name__)

LOG_PATH = Path(os.getenv("FORECAST_LOG_PATH", "data/forecasts.jsonl"))
_MAX_REASONING_CHARS = 4000


def _truncate(text: Any) -> str | None:
    if text is None:
        return None
    text = str(text)
    return text if len(text) <= _MAX_REASONING_CHARS else text[:_MAX_REASONING_CHARS] + " …[truncated]"


def _readable_prediction(report: Any) -> Any:
    """Best-effort pull of the final prediction value, format-agnostic."""
    for attr in ("prediction", "prediction_value", "binary_prediction"):
        val = getattr(report, attr, None)
        if val is not None:
            try:
                # NumericDistribution / PredictedOptionList have rich reprs;
                # floats/ints pass straight through.
                return val if isinstance(val, (int, float, str, list, dict)) else repr(val)
            except Exception:
                return repr(val)
    return None


def _structured_prediction(report: Any) -> Any:
    """Machine-readable prediction for the flywheel scorers (the repr in 'prediction'
    is for humans; this one is for resolve.py). Binary → float; MC → {option: p};
    numeric/date → declared percentiles + bounds. None if unrecognized."""
    try:
        val = None
        for attr in ("prediction", "prediction_value", "binary_prediction"):
            v = getattr(report, attr, None)
            if v is not None:
                val = v
                break
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        po = getattr(val, "predicted_options", None)
        if po is not None:
            return {o.option_name: float(o.probability) for o in po}
        dp = getattr(val, "declared_percentiles", None)
        if dp is not None:
            return {
                "declared_percentiles": [[float(p.percentile), float(p.value)] for p in dp],
                "lower_bound": getattr(val, "lower_bound", None),
                "upper_bound": getattr(val, "upper_bound", None),
                "open_lower_bound": getattr(val, "open_lower_bound", None),
                "open_upper_bound": getattr(val, "open_upper_bound", None),
                "zero_point": getattr(val, "zero_point", None),
                "cdf_size": getattr(val, "cdf_size", None),
                "is_date": getattr(val, "is_date", None),
            }
        return None
    except Exception:
        return None


def _community_prediction(question: Any) -> Any:
    for attr in (
        "community_prediction_at_access_time",
        "community_prediction",
        "api_json",
    ):
        val = getattr(question, attr, None)
        if val is not None and not isinstance(val, dict):
            return val
    return None


def _record(report: Any) -> dict | None:
    try:
        q = getattr(report, "question", None)
        return {
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "url": getattr(q, "page_url", None),
            "question_id": getattr(q, "id_of_post", None) or getattr(q, "id", None),
            "question_sub_id": getattr(q, "id_of_question", None),  # group subquestions
            "question_type": type(q).__name__ if q is not None else None,
            "question_text": getattr(q, "question_text", None),
            "prediction": _readable_prediction(report),
            "prediction_structured": _structured_prediction(report),
            "community_prediction": _community_prediction(q),
            "reasoning": _truncate(
                getattr(report, "explanation", None) or getattr(report, "reasoning", None)
            ),
            "num_minor_errors": len(getattr(report, "errors", []) or []),
        }
    except Exception as e:  # never let bookkeeping kill a run
        logger.warning(f"forecast_log: failed to extract a report: {e}")
        return None


def log_forecasts(reports: Sequence[Any]) -> int:
    """
    Append one JSONL line per valid ForecastReport. Returns the count written.
    Exceptions (the framework returns these too when return_exceptions=True) are
    skipped — only real forecasts are logged.
    """
    if not reports:
        return 0
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning(f"forecast_log: could not create {LOG_PATH.parent}: {e}")
        return 0

    written = 0
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            for report in reports:
                if isinstance(report, BaseException):
                    continue
                rec = _record(report)
                if rec is None:
                    continue
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                written += 1
    except Exception as e:
        logger.warning(f"forecast_log: write failed: {e}")
        return written

    if written:
        logger.info(f"forecast_log: recorded {written} forecast(s) to {LOG_PATH}")
    return written
