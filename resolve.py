"""resolve.py — the measurement half of the calibration flywheel.

Reads the accumulated forecast log (data/forecasts.jsonl), fetches each question's
REAL resolution from Metaculus, and reports calibration (Brier + a reliability table)
on the resolved subset. This private ground-truth record is the one durable edge: it
tells us which bot changes actually improved accuracy, and it can't be copied from the repo.

The log lives on the 'data' branch (the Action appends to it every run). To analyze locally:
  git fetch origin data && git show origin/data:forecasts.jsonl > data/forecasts.jsonl
  .venv/bin/python resolve.py

Needs METACULUS_TOKEN in .env. Read-only against Metaculus.
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from pathlib import Path

import dotenv
import requests

dotenv.load_dotenv()
TOKEN = os.getenv("METACULUS_TOKEN")
LOG = Path(os.getenv("FORECAST_LOG_PATH", "data/forecasts.jsonl"))
API = "https://www.metaculus.com/api"


def _records() -> list[dict]:
    if not LOG.exists():
        print(f"No log at {LOG}. In CI the log lives on the 'data' branch — pull it with:")
        print("  git fetch origin data && git show origin/data:forecasts.jsonl > data/forecasts.jsonl")
        return []
    out = []
    for line in LOG.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def _fetch_resolution(post_id) -> str | None:
    """Return the binary resolution ('yes'/'no'), or None if open/unknown."""
    try:
        r = requests.get(
            f"{API}/posts/{post_id}/",
            headers={"Authorization": f"Token {TOKEN}"},
            timeout=20,
        )
        if r.status_code != 200:
            return None
        q = (r.json() or {}).get("question") or {}
        return q.get("resolution")
    except Exception:
        return None


def main() -> None:
    recs = _records()
    if not recs:
        return
    by_q = {rec.get("question_id"): rec for rec in recs if rec.get("question_id") is not None}  # last wins
    print(f"{len(recs)} log lines | {len(by_q)} unique questions")

    binary = [
        (qid, rec)
        for qid, rec in by_q.items()
        if rec.get("question_type") == "BinaryQuestion" and isinstance(rec.get("prediction"), (int, float))
    ]
    print(f"{len(binary)} binary forecasts; fetching resolutions...")

    scored = []  # (p, outcome, rec)
    for qid, rec in binary:
        res = _fetch_resolution(qid)
        if res in ("yes", "no"):
            p = max(0.001, min(0.999, float(rec["prediction"])))
            scored.append((p, 1.0 if res == "yes" else 0.0, rec))

    if not scored:
        print("No resolved binary questions yet — the flywheel is still accruing. Re-run as questions resolve.")
        return

    brier = sum((p - o) ** 2 for p, o, _ in scored) / len(scored)
    logloss = -sum(o * math.log(p) + (1 - o) * math.log(1 - p) for p, o, _ in scored) / len(scored)
    print(f"\nRESOLVED binary: {len(scored)} | Brier {brier:.4f} (lower=better, 0.25=coinflip) | LogLoss {logloss:.4f}")

    print("\nReliability (predicted bucket vs actual yes-rate):")
    bins = defaultdict(list)
    for p, o, _ in scored:
        bins[min(9, int(p * 10))].append(o)
    for b in range(10):
        ys = bins.get(b, [])
        if ys:
            print(f"  {b*10:>2}-{b*10+10:>3}% | n={len(ys):>3} | actual {sum(ys)/len(ys):.0%}")

    out = Path("data/resolved.jsonl")
    with out.open("w") as f:
        for p, o, rec in scored:
            f.write(json.dumps({
                "question_id": rec.get("question_id"), "p": p, "outcome": o,
                "brier": (p - o) ** 2, "url": rec.get("url"),
            }) + "\n")
    print(f"\nWrote {out} ({len(scored)} resolved) — the ground-truth that gates every change.")


if __name__ == "__main__":
    main()
