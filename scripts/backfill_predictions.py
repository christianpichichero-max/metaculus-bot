"""One-time backfill: parse the human-readable prediction reprs in pre-upgrade
forecast-log lines into machine-scoreable structures, so the flywheel can score the
numeric/MC/discrete forecasts made before prediction_structured logging existed.

Writes data/forecasts_structured.jsonl BESIDE the append-only history (never mutates it).
Run:  git fetch origin data && git show origin/data:forecasts.jsonl > data/forecasts.jsonl
      .venv/bin/python scripts/backfill_predictions.py
Then commit data/forecasts_structured.jsonl to the data branch.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

LOG = Path("data/forecasts.jsonl")
OUT = Path("data/forecasts_structured.jsonl")

PCT_RE = re.compile(r"Percentile\(percentile=([\d.eE+-]+),\s*value=([-\d.eE+-]+)")
OPT_RE = re.compile(r"option_name=(['\"])(.+?)\1,\s*probability=([\d.eE+-]+)")
FIELD_RES = {
    "lower_bound": re.compile(r"(?<!open_)lower_bound=([-\d.eE+None]+)"),
    "upper_bound": re.compile(r"(?<!open_)upper_bound=([-\d.eE+None]+)"),
    "open_lower_bound": re.compile(r"open_lower_bound=(True|False)"),
    "open_upper_bound": re.compile(r"open_upper_bound=(True|False)"),
    "cdf_size": re.compile(r"cdf_size=(\d+)"),
    "is_date": re.compile(r"is_date=(True|False)"),
}


def _parse_field(rx, s):
    m = rx.search(s)
    if not m:
        return None
    v = m.group(1)
    if v in ("True", "False"):
        return v == "True"
    if v == "None":
        return None
    try:
        return float(v) if "." in v or "e" in v.lower() else int(v)
    except ValueError:
        return None


def parse_repr(qtype: str, pred) -> dict | float | None:
    if isinstance(pred, (int, float)):
        return float(pred)
    if not isinstance(pred, str):
        return None
    if "PredictedOption" in pred:
        opts = {m.group(2): float(m.group(3)) for m in OPT_RE.finditer(pred)}
        return opts or None
    if "Percentile(" in pred:
        pairs = [[float(m.group(1)), float(m.group(2))] for m in PCT_RE.finditer(pred)]
        if not pairs:
            return None
        out = {"declared_percentiles": pairs}
        for k, rx in FIELD_RES.items():
            out[k] = _parse_field(rx, pred)
        # sanity: pair count should match this record's own cdf_size when the repr
        # carries the FULL cdf (discrete questions); declared-only lists are shorter.
        if out.get("cdf_size") and len(pairs) not in (out["cdf_size"], len(pairs)):
            print(f"  note: {len(pairs)} pairs vs cdf_size={out['cdf_size']}")
        return out
    return None


def main() -> None:
    if not LOG.exists():
        print("no data/forecasts.jsonl — pull the data branch first")
        return
    n_in = n_out = 0
    with OUT.open("w", encoding="utf-8") as fout:
        for line in LOG.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            n_in += 1
            if rec.get("prediction_structured") is not None:
                continue  # new-format line; no backfill needed
            structured = parse_repr(rec.get("question_type") or "", rec.get("prediction"))
            if structured is None:
                continue
            fout.write(json.dumps({
                "question_id": rec.get("question_id"),
                "question_sub_id": rec.get("question_sub_id"),
                "question_type": rec.get("question_type"),
                "structured": structured,
            }, ensure_ascii=False) + "\n")
            n_out += 1
    print(f"read {n_in} log lines → backfilled {n_out} structured predictions → {OUT}")


if __name__ == "__main__":
    main()
