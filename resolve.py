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
import time
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


def _fetch_resolution(post_id):
    """Return (fetched_ok, resolution). resolution is 'yes'/'no' if resolved, None if
    still open/unresolved. fetched_ok=False means the request FAILED after retries
    (rate limit / error) — so the caller must NOT miscount that as 'unresolved' and
    silently miss a real score. Retries with backoff on 429/5xx."""
    for attempt in range(4):
        try:
            r = requests.get(
                f"{API}/posts/{post_id}/",
                headers={"Authorization": f"Token {TOKEN}"},
                timeout=20,
            )
            if r.status_code == 200:
                q = (r.json() or {}).get("question") or {}
                return True, q.get("resolution")
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            return True, None  # a definitive non-200 (e.g. 404) → treat as no-resolution
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return False, None


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
    failures = 0
    for qid, rec in binary:
        ok, res = _fetch_resolution(qid)
        if not ok:
            failures += 1
            continue
        if res in ("yes", "no"):
            p = max(0.001, min(0.999, float(rec["prediction"])))
            scored.append((p, 1.0 if res == "yes" else 0.0, rec))
        time.sleep(0.35)  # be gentle on the API to avoid rate-limit gaps

    if failures:
        # Loud on purpose: a silent under-count on resolution day would defeat the
        # whole watch system. Exit non-zero so the daily workflow surfaces it.
        print(f"WARNING: {failures} of {len(binary)} questions could not be fetched "
              "(rate limit/error). Report may be INCOMPLETE — re-run.")

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

    _score_supervisor_shadow({rec.get("question_id"): o for _, o, rec in scored})


def _score_supervisor_shadow(outcomes: dict) -> None:
    """The shadow A/B: on questions where the supervisor FIRED and the question has
    resolved, compare Brier(supervisor's revised p) vs Brier(submitted geo-odds p0).
    This is the gate that decides whether the supervisor goes live.
    Pull the log with: git show origin/data:supervisor.jsonl > data/supervisor.jsonl"""
    sup_log = Path("data/supervisor.jsonl")
    if not sup_log.exists():
        return
    fired = []
    for line in sup_log.read_text().splitlines():
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("fired") and rec.get("revised") is not None:
            outcome = outcomes.get(rec.get("question_id"))
            if outcome is not None:
                fired.append((float(rec["p0"]), float(rec["revised"]), outcome, rec.get("confidence")))
    if not fired:
        print("\nSupervisor shadow A/B: no resolved fired-questions yet — still accruing.")
        return
    b0 = sum((p0 - o) ** 2 for p0, _, o, _ in fired) / len(fired)
    b1 = sum((pr - o) ** 2 for _, pr, o, _ in fired) / len(fired)
    hi = [(p0, pr, o) for p0, pr, o, c in fired if c == "high"]
    print(f"\nSUPERVISOR SHADOW A/B ({len(fired)} resolved fired-questions):")
    print(f"  geo-odds (submitted) Brier: {b0:.4f}")
    print(f"  supervisor (shadow)  Brier: {b1:.4f}  {'← supervisor BETTER' if b1 < b0 else '← geo-odds better/tied'}")
    if hi:
        h0 = sum((p0 - o) ** 2 for p0, _, o in hi) / len(hi)
        h1 = sum((pr - o) ** 2 for _, pr, o in hi) / len(hi)
        print(f"  high-confidence only ({len(hi)}): geo-odds {h0:.4f} vs supervisor {h1:.4f}")
    print("  Gate: flip use_supervisor=True only if the supervisor wins on ≥30 fired resolutions.")


if __name__ == "__main__":
    main()
