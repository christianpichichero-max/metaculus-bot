# Synthesis: Metaculus bot audit → build list

**Judge verdict.** The audit's central irony: the project's declared edge is the calibration flywheel, and the four worst confirmed defects all destroy flywheel data — silently. Nothing found threatens submissions themselves (the SDK's publish path is sound and retries); everything critical is about *losing the record* of what was submitted, *never noticing* the bot died, or *never scoring* 42% of what it does. After those, the two genuine placement levers are a two-line numeric-tail fix that is pure free log-score, and the multi-family ensemble whose concurrency design is now proven safe. All 13 build items below were re-anchored against the live code in this session (`/Users/christian/metaculus-bot/main.py`, `resolve.py`, `forecast_log.py`, both workflow YAMLs, `requirements.txt`) — every cited line was verified present.

## The ranked list (see buildNow for exact how-tos + test plans)

| # | Item | Class | Effort |
|---|------|-------|--------|
| 1 | Log forecasts BEFORE the summary raise; per-file data-branch persist | data-loss bug | low |
| 2 | Dead-man switch (green-failure aware) + failed.jsonl | silent-death gap | low |
| 3 | Pin `forecasting-tools==0.2.92` + direct deps | outage/stealth-regression risk | low |
| 4 | Data-branch push retry; issue-after-push (NOT a shared concurrency group) | data-loss bug | low |
| 5 | P2.5/P97.5 in numeric+date prompts (~+0.08 nats, 31% of forecasts) | live scoring bug | low |
| 6 | Read `my_forecasts`/`score_data` in resolve.py — official spot-peer capture | flywheel upgrade | low |
| 7 | Structured prediction logging + backfill + MC/numeric scorers + loud incomplete-report failure | flywheel coverage | medium |
| 8 | Policy-faithful supervisor A/B headline + stale-notes purge + version tag | gate correctness | low |
| 9 | Group-question hardening (id_of_question everywhere) | latent corruption | medium |
| 10 | MC aggregation: key on `question.options`, water-fill floor after renormalize | latent crash/correctness | low |
| 11 | Kill the Metaculus Cup cron | budget protection | low |
| 12 | Multi-family ensemble (ContextVar rotation + draws.jsonl ledger + slug gates) | roadmap #1 | high |
| 13 | Quant data researcher for series numerics | roadmap #2 | medium |

**Why this order.** Items 1–4 are the mandated data-loss/reliability tier — they protect the only asset that compounds. Item 5 jumps the flywheel tier because it is a *confirmed live scoring defect* (verified in both the SDK and the production CDFs), not an optimization: every open-bound numeric currently donates ~10% of its probability mass to out-of-bounds regions as a template artifact. Items 6–8 make the flywheel measure the actual tournament objective (spot-peer) and fix a mis-specified go-live gate. Items 9–10 are latent corruptions cheapest to fix before they fire. Item 11 lands immediately before item 12 because the ensemble raises per-question burn on a $290 pool with no reliable in-repo meter. Items 12–13 are the validated roadmap builds, each behind explicit deploy gates.

## Judge overrides and cross-lens reconciliation

- **Shared concurrency group REJECTED (item 4).** The reliability lens (and its verifier) proposed one `data-branch-writer` group for both workflows. GitHub keeps at most one *pending* run per group and cancels the older pending run when a new one queues — with the tournament cron firing every 20 minutes and runs that outlast the cadence, the once-daily report would be starved out of its pending slot. The push-retry loop (re-clone, re-append, re-push ×3) closes the seconds-wide race without that hazard, and the daily's `|| echo "nothing to commit"` swallow + issue-before-push ordering get fixed in the same step.
- **Official scores (item 6) vs hand-written scorers (item 7): build both.** If `score_data` exists (one live probe confirms; the extraction is defensive either way), it supersedes hand-rolled *tournament* scoring — but item 7 is still required: structured prediction logging feeds everything downstream (ensemble ledger, variance work), the P10–P90 coverage rate is the diagnostic that validates item 5, and `my_forecasts.latest.forecast_values` gives an authoritative cross-check of what was actually submitted.
- **Duplicates merged.** Group-question findings (reliability-F5 + flywheel-F5) → item 9. MC findings (reliability-F9 + numeric-MC-1) → item 10. Repr-logging findings (reliability-F13 + flywheel-F3 + numeric-FLY-1) → item 7. Supervisor contamination (reliability-F11) + wrong-policy gate (flywheel-F4) → item 8. Supervisor persistence (reliability-F7) and per-block try/except (F8) → folded into items 1–2. ENS-4's version tag is pulled forward into item 8 (one line now prevents pooling incomparable populations later).
- **Verified-in-session confirmations.** I independently re-read the load-bearing anchors: `main.py:1072/1075` ordering (and that `forecast_log.log_forecasts` already skips exceptions at line 101 — the reorder is even safer than the lens assumed); the supervisor's live gate really is confidence=='high'-only (`main.py:342-348`), so the flywheel-F4 headline defect is real; `resolve.py:98-102` really prints a warning while its comment promises a non-zero exit that doesn't exist; the daily grep really keys on `RESOLVED binary:` only.
- **One knowingly-unproven input.** The `score_data` schema (item 6) cannot be verified offline. The build is shaped so the wrong guess costs nothing: defensive extraction plus a keys-dump probe line that self-confirms in the next daily report.

## Deploy sequencing and test discipline

- **Batching:** PR-A = items 1–4 (main.py tail + both workflows — items 1 and 4 edit the same persist step, do them together). PR-B = item 5. PR-C = items 6–8 (resolve.py + forecast_log.py). PR-D = items 9–10. PR-E = item 11. PR-F = item 12 (after its slug smoke gates pass). PR-G = item 13.
- **Nothing in CI or tests may submit forecasts.** All test plans above are mocked (fixtures, monkeypatched HTTP/LLMs, local bare-repo git harness for the workflow scripts). `--mode test_questions` posts to the Metaculus playground (bot-testing-area, not the tournament) — acceptable only as a final manual smoke with Christian's say-so, never automated.
- **Post-deploy watch (no code needed):** after PR-A, confirm the next scheduled run appends to `origin/data`; after PR-B, confirm new numeric log lines show CDF edge mass ~0.013 instead of 0.0504; after PR-C, the next daily report either prints spot-peer numbers or the `score_data ABSENT` schema dump.
- **Known first-run artifacts:** item 7's counter switch (binary-count → all-count) legitimately fires one "new resolutions" issue; item 6's probe adds a few lines to report.txt. Both expected.

## Skipped (with reasons) — see skip list
Variance-shrinkage and per-model weights (gated on post-ensemble ledger data, N≥30/member — fitting on mono-model history would over-shrink); MC 0.02-floor/linear-blend (shadow field ships free in item 10, decide on resolutions); get_config override (bundle with next benchmark touch); summarizer stays ON (verified deliberate); leaderboard endpoint (probe after item 6); standalone prompt passes (dead lever — only structural lines ship inside items 5/13); formal N-of-M framework (practical version lands in items 1–2); all previously-decided dead levers stay dead.

## Key numbers for context
83 forecasts logged (48 binary / 20 numeric / 9 MC / 6 discrete); first resolution Brier 0.327 (N=1), 8 more resolving now; supervisor shadow: 17 records, 8 fired, 2 high-confidence (gate needs ≥30 fired resolutions — every lost supervisor line delays it); budget ~$290 remaining, ensemble path ≈ $0.20–0.28/question ≈ $220–280 through Nov 30 — fits, thin margin, meter lives on the OpenRouter dashboard until item 12's `litellm.register_model` makes in-repo cost stats real.