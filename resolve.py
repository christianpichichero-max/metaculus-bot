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
import sys
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


def _fetch_post(post_id):
    """Return (fetched_ok, post_json). fetched_ok=False means the request FAILED
    after retries (rate limit/error) — the caller must NOT miscount that as
    'unresolved' and silently miss a real score. Retries with backoff on 429/5xx."""
    for attempt in range(4):
        try:
            r = requests.get(
                f"{API}/posts/{post_id}/",
                headers={"Authorization": f"Token {TOKEN}"},
                timeout=20,
            )
            if r.status_code == 200:
                return True, (r.json() or {})
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            return True, {}  # definitive non-200 (e.g. 404) → no data
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return False, {}


def _question_node(post_json: dict, sub_id):
    """The question dict for this record — handles GROUP posts, where subquestions
    live under group_of_questions.questions and share one post id."""
    q = post_json.get("question")
    if q and (sub_id is None or q.get("id") == sub_id):
        return q
    for sq in ((post_json.get("group_of_questions") or {}).get("questions") or []):
        if sq.get("id") == sub_id:
            return sq
    return q


def _percentile_of_resolution(structured: dict, res_value: float):
    """Where the resolution landed on our declared-percentile curve (linear interp).
    0.0/1.0 = at-or-beyond our extreme declared tails."""
    try:
        dps = [
            (float(p) if float(p) <= 1.0 else float(p) / 100.0, float(v))
            for p, v in (structured.get("declared_percentiles") or [])
        ]
        dps.sort(key=lambda t: t[0])
        if len(dps) < 2:
            return None
        if res_value <= dps[0][1]:
            return 0.0 if res_value < dps[0][1] else dps[0][0]
        if res_value >= dps[-1][1]:
            return 1.0 if res_value > dps[-1][1] else dps[-1][0]
        for (p1, v1), (p2, v2) in zip(dps, dps[1:]):
            if v1 <= res_value <= v2:
                if v2 == v1:
                    return (p1 + p2) / 2.0
                return p1 + (p2 - p1) * (res_value - v1) / (v2 - v1)
    except Exception:
        pass
    return None


def _parse_numeric_resolution(res, structured: dict):
    """Numeric/discrete/date resolution → (kind, value_or_percentile).
    kind: 'value' (float), 'oob_high', 'oob_low', or None (annulled/ambiguous/unparseable)."""
    if res is None or res in ("annulled", "ambiguous"):
        return None, None
    if res == "above_upper_bound":
        return "oob_high", None
    if res == "below_lower_bound":
        return "oob_low", None
    try:
        return "value", float(res)
    except (TypeError, ValueError):
        pass
    if structured.get("is_date"):
        try:
            from datetime import datetime as _dt
            return "value", _dt.fromisoformat(str(res).replace("Z", "+00:00")).timestamp()
        except Exception:
            pass
    return None, None


def _extract_scores(my_forecasts) -> dict:
    """Defensively pull official score fields if present. Schema probe: when a
    resolved question carries my_forecasts but no recognizable scores, we print its
    keys once so the next daily report reveals the true schema at zero extra cost."""
    out: dict = {}
    try:
        mf = my_forecasts or {}
        sd = mf.get("score_data") or {}
        for k in ("spot_peer_score", "spot_baseline_score", "peer_score", "baseline_score", "coverage"):
            if sd.get(k) is not None:
                out[k] = sd[k]
        latest = mf.get("latest") or {}
        if latest.get("forecast_values") is not None:
            out["submitted_values"] = latest["forecast_values"]
    except Exception:
        pass
    return out


def _structured_of(rec: dict, backfill: dict):
    s = rec.get("prediction_structured")
    if s is not None:
        return s
    return backfill.get((rec.get("question_id"), rec.get("question_sub_id")))


def main() -> None:
    recs = _records()
    if not recs:
        return
    by_key: dict = {}
    text_by_post: dict = {}
    for rec in recs:
        qid = rec.get("question_id")
        if qid is None:
            continue
        key = (qid, rec.get("question_sub_id"))
        by_key[key] = rec  # last wins
        prev = text_by_post.get(qid)
        if (prev and rec.get("question_text") and prev != rec.get("question_text")
                and rec.get("question_sub_id") is None):
            print(f"TRIPWIRE: post {qid} carries two different question_texts without sub_ids "
                  "— possible group-question collision in old log lines.")
        text_by_post.setdefault(qid, rec.get("question_text"))
    print(f"{len(recs)} log lines | {len(by_key)} unique questions")

    # One-time backfill of structured predictions for pre-upgrade log lines.
    backfill: dict = {}
    bf = Path("data/forecasts_structured.jsonl")
    if bf.exists():
        for line in bf.read_text().splitlines():
            try:
                b = json.loads(line)
                backfill[(b.get("question_id"), b.get("question_sub_id"))] = b.get("structured")
            except Exception:
                pass

    # Fetch each POST once (group subquestions share a post).
    post_ids = sorted({qid for qid, _ in by_key})
    print(f"fetching {len(post_ids)} posts...")
    posts: dict = {}
    failures = 0
    for pid in post_ids:
        ok, pj = _fetch_post(pid)
        if not ok:
            failures += 1
        else:
            posts[pid] = pj
        time.sleep(0.35)  # be gentle on the API to avoid rate-limit gaps

    bin_scored = []   # (p, outcome, rec)
    mc_scored = []    # (logscore, brier, rec)
    num_scored = []   # (pctile, rec)  pctile of resolution on our declared curve
    official = []
    probe_printed = False

    for (qid, sub), rec in by_key.items():
        pj = posts.get(qid)
        if pj is None:
            continue
        node = _question_node(pj, sub) or {}
        res = node.get("resolution")
        if res is None:
            continue
        mf = node.get("my_forecasts")
        fields = _extract_scores(mf)
        if fields:
            rec["official"] = fields
            if any(k.endswith("_score") for k in fields):
                official.append((qid, fields))
        if not fields and mf is not None and not probe_printed:
            print(f"score_data ABSENT on resolved {qid} — my_forecasts keys: {sorted((mf or {}).keys())}")
            probe_printed = True

        qtype = rec.get("question_type")
        structured = _structured_of(rec, backfill)
        if qtype == "BinaryQuestion":
            p = rec.get("prediction") if isinstance(rec.get("prediction"), (int, float)) else structured
            if res in ("yes", "no") and isinstance(p, (int, float)):
                p = max(0.001, min(0.999, float(p)))
                bin_scored.append((p, 1.0 if res == "yes" else 0.0, rec))
        elif qtype == "MultipleChoiceQuestion" and isinstance(structured, dict) \
                and "declared_percentiles" not in structured:
            if res in structured:  # resolution == winning option name
                total = sum(structured.values()) or 1.0
                probs = {k: max(1e-4, v / total) for k, v in structured.items()}
                pwin = probs[res]
                logscore = math.log(pwin)
                brier = sum((probs[k] - (1.0 if k == res else 0.0)) ** 2 for k in probs)
                mc_scored.append((logscore, brier, rec))
            elif res not in ("annulled", "ambiguous"):
                print(f"MC resolution '{res}' not in logged options for {qid} — skipped")
        elif qtype in ("NumericQuestion", "DiscreteQuestion", "DateQuestion") \
                and isinstance(structured, dict) and structured.get("declared_percentiles"):
            kind, val = _parse_numeric_resolution(res, structured)
            if kind == "value":
                pct = _percentile_of_resolution(structured, val)
                if pct is not None:
                    num_scored.append((pct, rec))
            elif kind == "oob_high":
                num_scored.append((1.0, rec))
            elif kind == "oob_low":
                num_scored.append((0.0, rec))

    if failures:
        print(f"WARNING: {failures} of {len(post_ids)} posts could not be fetched "
              "(rate limit/error). Report is INCOMPLETE — resolved.jsonl NOT overwritten; re-run.")

    total_resolved = len(bin_scored) + len(mc_scored) + len(num_scored)
    if not total_resolved:
        print("No resolved binary questions yet — the flywheel is still accruing. Re-run as questions resolve.")
        if failures:
            sys.exit(2)
        return

    # NOTE: the daily workflow's news trigger greps "RESOLVED binary: N" — keep that
    # exact phrase, now with the all-types count alongside.
    if bin_scored:
        brier = sum((p - o) ** 2 for p, o, _ in bin_scored) / len(bin_scored)
        logloss = -sum(o * math.log(p) + (1 - o) * math.log(1 - p) for p, o, _ in bin_scored) / len(bin_scored)
        print(f"\nRESOLVED binary: {len(bin_scored)} | Brier {brier:.4f} "
              f"(lower=better, 0.25=coinflip) | LogLoss {logloss:.4f}")
        print("\nReliability (predicted bucket vs actual yes-rate):")
        bins = defaultdict(list)
        for p, o, _ in bin_scored:
            bins[min(9, int(p * 10))].append(o)
        for b in range(10):
            ys = bins.get(b, [])
            if ys:
                print(f"  {b*10:>2}-{b*10+10:>3}% | n={len(ys):>3} | actual {sum(ys)/len(ys):.0%}")
    else:
        print(f"\nRESOLVED binary: 0 (but {total_resolved} total resolved below)")

    if mc_scored:
        avg_log = sum(ls for ls, _, _ in mc_scored) / len(mc_scored)
        avg_brier = sum(b for _, b, _ in mc_scored) / len(mc_scored)
        print(f"\nRESOLVED multiple-choice: {len(mc_scored)} | avg ln p(winner) {avg_log:.3f} "
              f"| multiclass Brier {avg_brier:.4f}")

    if num_scored:
        in80 = sum(1 for pct, _ in num_scored if 0.10 <= pct <= 0.90) / len(num_scored)
        in95 = sum(1 for pct, _ in num_scored if 0.025 <= pct <= 0.975) / len(num_scored)
        tails = sum(1 for pct, _ in num_scored if pct in (0.0, 1.0))
        print(f"\nRESOLVED numeric/discrete/date: {len(num_scored)} | "
              f"P10-P90 coverage {in80:.0%} (target ~80%) | "
              f"P2.5-P97.5 coverage {in95:.0%} (target ~95%) | beyond-declared-tails: {tails}")

    if official:
        spot_total = sum(f.get("spot_peer_score", 0.0) for _, f in official)
        print(f"\nOFFICIAL scores captured on {len(official)} question(s): "
              f"SPOT PEER total = {spot_total:.2f} (prize share ∝ max(0, total)²)")

    if not failures:
        out = Path("data/resolved.jsonl")
        with out.open("w") as f:
            for p, o, rec in bin_scored:
                f.write(json.dumps({
                    "kind": "binary", "question_id": rec.get("question_id"),
                    "question_sub_id": rec.get("question_sub_id"),
                    "p": p, "outcome": o, "brier": (p - o) ** 2,
                    "url": rec.get("url"), "official": rec.get("official"),
                }) + "\n")
            for ls, b, rec in mc_scored:
                f.write(json.dumps({
                    "kind": "mc", "question_id": rec.get("question_id"),
                    "question_sub_id": rec.get("question_sub_id"),
                    "log_p_winner": ls, "brier_multiclass": b,
                    "url": rec.get("url"), "official": rec.get("official"),
                }) + "\n")
            for pct, rec in num_scored:
                f.write(json.dumps({
                    "kind": "numeric", "question_id": rec.get("question_id"),
                    "question_sub_id": rec.get("question_sub_id"),
                    "resolution_percentile": pct,
                    "url": rec.get("url"), "official": rec.get("official"),
                }) + "\n")
        print(f"\nWrote {out} ({total_resolved} resolved) — the ground-truth that gates every change.")

    outcomes = {}
    for p, o, rec in bin_scored:
        outcomes[rec.get("question_id")] = o
        if rec.get("question_sub_id") is not None:
            outcomes[("sub", rec.get("question_sub_id"))] = o
    _score_supervisor_shadow(outcomes)

    if failures:
        sys.exit(2)


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
            if outcome is None and rec.get("id_of_question") is not None:
                outcome = outcomes.get(("sub", rec.get("id_of_question")))
            if outcome is not None:
                fired.append((float(rec["p0"]), float(rec["revised"]), outcome, rec.get("confidence")))
    if not fired:
        print("\nSupervisor shadow A/B: no resolved fired-questions yet — still accruing.")
        return
    # POLICY-FAITHFUL headline: live mode only submits the revision at confidence
    # 'high' (else it submits p0) — so score exactly that policy, not the
    # counterfactual 'always trust the supervisor'.
    b0 = sum((p0 - o) ** 2 for p0, _, o, _ in fired) / len(fired)
    b_policy = sum(
        ((pr if c == "high" else p0) - o) ** 2 for p0, pr, o, c in fired
    ) / len(fired)
    b_counterfactual = sum((pr - o) ** 2 for _, pr, o, _ in fired) / len(fired)
    hi = [(p0, pr, o) for p0, pr, o, c in fired if c == "high"]
    print(f"\nSUPERVISOR SHADOW A/B ({len(fired)} resolved fired-questions):")
    print(f"  geo-odds (submitted)        Brier: {b0:.4f}")
    print(f"  ship-policy (high-conf only) Brier: {b_policy:.4f}  "
          f"{'← supervisor policy BETTER' if b_policy < b0 else '← geo-odds better/tied'}")
    print(f"  diagnostic (always-trust)    Brier: {b_counterfactual:.4f}")
    if hi:
        h0 = sum((p0 - o) ** 2 for p0, _, o in hi) / len(hi)
        h1 = sum((pr - o) ** 2 for _, pr, o in hi) / len(hi)
        print(f"  high-confidence overrides ({len(hi)}): geo-odds {h0:.4f} vs supervisor {h1:.4f}")
    print("  Gate: flip use_supervisor=True only if ship-policy wins on ≥30 fired resolutions.")


if __name__ == "__main__":
    main()
