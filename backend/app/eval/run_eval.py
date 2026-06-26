"""Phase 6 eval harness — runs the agent graph on ~15 diverse queries and
scores groundedness, budget adherence, completeness/quality (LLM-as-judge),
and clarification behavior. Prints a scoreboard.

Cache integrity (BUILD_PLAN section 15): this harness measures REAL model
output only — it forces LLM_DEV_CACHE off regardless of the .env value used
for everyday dev iteration, so a case can never be silently scored against a
replayed or hand-seeded cache entry.

Quota strategy: a full run costs several real LLM calls per case (parser,
planner, possibly a critic-triggered revision, finalizer, the quality judge),
so this is designed to run in small batches across multiple invocations.
Results accumulate in results.json keyed by case id; re-running without
--rerun skips cases already recorded, so an interrupted batch just resumes.

Usage (run from backend/, with the venv active):
  python -m app.eval.run_eval                      # run all cases not yet recorded
  python -m app.eval.run_eval --cases full_trip_paris,vague_no_dates
  python -m app.eval.run_eval --rerun full_trip_paris,over_budget_paris
  python -m app.eval.run_eval --no-judge            # skip the extra LLM-judge call
  python -m app.eval.run_eval --report-only         # just print the scoreboard
"""

import argparse
import json
import logging
import os
import time
import uuid
from pathlib import Path

# Must happen before app.config.Settings() is constructed anywhere (the first
# `from app...` import below will trigger it) — env vars take precedence over
# .env in pydantic-settings, so this reliably forces real calls regardless of
# LLM_DEV_CACHE=true in .env (which stays on for everyday dev convenience).
os.environ["LLM_DEV_CACHE"] = "false"

from pydantic import BaseModel  # noqa: E402

from app import llm  # noqa: E402
from app.graph import nodes  # noqa: E402
from app.graph.graph import build_graph  # noqa: E402

logging.basicConfig(level=logging.WARNING)  # the per-node structured logs would drown out the scoreboard
logger = logging.getLogger("eval")

CASES_PATH = Path(__file__).resolve().parent / "cases.json"
RESULTS_PATH = Path(__file__).resolve().parent / "results.json"

GROUNDEDNESS_TARGET = 1.0  # hard requirement: every named fact must be real
# 1 of the ~6 budgeted cases (over_budget_paris) is a deliberate stress test —
# $200 for 5 days JFK<->Paris with fine dining and 5-star hotels is impossible
# by design, and the critic correctly flags it. 80% allows exactly that one
# designed-to-fail case without masking a real regression among the rest.
BUDGET_ADHERENCE_TARGET = 0.80
CLARIFY_ACCURACY_TARGET = 1.0

JUDGE_SYSTEM = """You are a discerning judge scoring a generated trip itinerary for
completeness and usefulness — NOT for factual grounding (assume every place/flight/
hotel named is real; that's checked separately). Score 1-5:
1 = barely usable: too sparse, ignores the traveler's stated interests/pace/constraints
2 = weak: thin variety, loosely matches the request
3 = serviceable but generic: covers the basics, doesn't feel tailored
4 = good: solid variety, sensibly paced, clearly shaped by the stated interests
5 = excellent: genuinely well-composed, every day has a coherent theme, strongly
    reflects what this specific traveler asked for
Be critical — most itineraries should land at 3-4; reserve 5 for itineraries that
clearly go beyond generic coverage."""


class QualityJudgment(BaseModel):
    score: int
    reasoning: str


def _load_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text())


def _load_results() -> dict:
    if RESULTS_PATH.exists():
        return json.loads(RESULTS_PATH.read_text())
    return {}


def _save_results(results: dict) -> None:
    RESULTS_PATH.write_text(json.dumps(results, indent=2, default=str))


def _judge_quality(case: dict, itinerary: list[dict], parsed: dict) -> tuple[int | None, dict, int]:
    """Returns (score_or_None, usage, extra_llm_calls)."""
    if not itinerary:
        return None, dict(llm.ZERO_USAGE), 0
    context = {"traveler_request": case["query"], "parsed_trip": parsed, "itinerary": itinerary}
    user_prompt = json.dumps(context, default=str, separators=(",", ":"))
    try:
        judgment, _provider, usage = llm.generate_structured(JUDGE_SYSTEM, user_prompt, QualityJudgment)
        return judgment.score, usage, 1
    except Exception as exc:
        logger.warning("quality judge call failed for %s: %s", case["id"], exc)
        return None, dict(llm.ZERO_USAGE), 0


class _UsageTracker:
    """Monkey-patches llm.generate_structured for the duration of one case so
    every real call is counted, regardless of whether LangGraph's checkpoint
    captured it. Necessary because a node that calls interrupt() never
    returns its partial-state update on the pausing pass — so for every
    expects_clarify case (which we deliberately never resume), the parser
    call's llm_calls/llm_usage would otherwise vanish from graph.get_state()."""

    def __init__(self):
        self.calls = 0
        self.usage = dict(llm.ZERO_USAGE)
        self._original = None

    def __enter__(self):
        self._original = llm.generate_structured

        def wrapped(system_prompt, user_prompt, schema):
            result, provider, usage = self._original(system_prompt, user_prompt, schema)
            self.calls += 1
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                self.usage[key] += usage[key]
            self.usage["cost_usd"] = round(self.usage["cost_usd"] + usage["cost_usd"], 6)
            return result, provider, usage

        llm.generate_structured = wrapped
        return self

    def __exit__(self, *exc_info):
        llm.generate_structured = self._original


def _score_case(
    case: dict, state: dict, interrupted: bool, error: str | None, duration_s: float, use_judge: bool, tracker: _UsageTracker
) -> dict:
    final = state.get("final") or {}
    itinerary = final.get("itinerary") or state.get("itinerary") or []
    parsed = final.get("parsed") or state.get("parsed") or {}
    budget_breakdown = final.get("budget_breakdown") or state.get("budget_breakdown") or {}

    result = {
        "id": case["id"],
        "category": case["category"],
        "query": case["query"],
        "error": error,
        "interrupted": interrupted,
        "duration_s": duration_s,
        "clarify_correct": None,
        "groundedness_ok": None,
        "groundedness_issues": [],
        "budget_ok": None,
        "quality_score": None,
        "hallucinated_despite_clarify": False,
    }

    try:
        if error is not None:
            return result

        expects_clarify = case["expects_clarify"]
        result["clarify_correct"] = interrupted == expects_clarify

        if interrupted:
            # Correctly stopped for clarification — the critical check is that
            # no hallucinated plan slipped out alongside the interrupt.
            result["hallucinated_despite_clarify"] = bool(itinerary)
            return result

        # Groundedness: re-run the critic's own deterministic check against the
        # ACTUAL final state, independent of whether the critic itself passed
        # it (it may have exhausted its revision budget and finalized anyway).
        verdict = nodes.critic_node(
            {
                "parsed": parsed,
                "flights": final.get("flights") or state.get("flights", []),
                "stays": final.get("stays") or state.get("stays", []),
                "activities": final.get("activities") or state.get("activities", []),
                "itinerary": itinerary,
                "budget_breakdown": budget_breakdown,
                "selected_flight_offer_id": final.get("selected_flight_offer_id")
                or state.get("selected_flight_offer_id"),
                "selected_hotel_id": final.get("selected_hotel_id") or state.get("selected_hotel_id"),
            }
        )["critic_verdict"]
        result["groundedness_ok"] = verdict["groundedness_ok"]
        result["groundedness_issues"] = verdict["issues"]

        budget = parsed.get("budget")
        if budget is not None and budget_breakdown:
            result["budget_ok"] = budget_breakdown.get("total", 0) <= budget
            result["budget_total"] = budget_breakdown.get("total")
            result["budget_stated"] = budget

        if use_judge:
            # Runs while the tracker is still active (caller keeps the `with`
            # block open across this call), so this call is counted too.
            result["quality_score"], _usage, _calls = _judge_quality(case, itinerary, parsed)

        return result
    finally:
        # Read last: reflects every real call made during this case, including
        # the judge call above.
        result["llm_calls"] = tracker.calls
        result["llm_usage"] = dict(tracker.usage)


def _run_case(case: dict, use_judge: bool) -> dict:
    graph = build_graph()
    thread_id = f"eval-{case['id']}-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    graph_input = {
        "raw_query": case["query"],
        "user_id": None,
        "trip_id": None,
        "llm_calls": 0,
        "revision_count": 0,
    }

    interrupted = False
    error = None
    start = time.monotonic()
    with _UsageTracker() as tracker:
        try:
            for update in graph.stream(graph_input, config, stream_mode="updates"):
                if "__interrupt__" in update:
                    interrupted = True
                    break
        except Exception as exc:
            error = str(exc)
            logger.warning("case %s failed: %s", case["id"], exc)
        duration_s = round(time.monotonic() - start, 1)

        state = graph.get_state(config).values
        return _score_case(case, state, interrupted, error, duration_s, use_judge, tracker)


def _fmt_bool(value: bool | None, true_label="PASS", false_label="FAIL") -> str:
    if value is None:
        return "  --"
    return true_label if value else false_label


def _print_scoreboard(results: dict, all_case_ids: list[str]) -> None:
    width = {"id": 24, "cat": 14, "clarify": 8, "ground": 8, "budget": 8, "quality": 8, "calls": 6, "tokens": 8, "cost": 9, "time": 7}
    header = (
        f"{'CASE':<{width['id']}} {'CATEGORY':<{width['cat']}} {'CLARIFY':<{width['clarify']}} "
        f"{'GROUND':<{width['ground']}} {'BUDGET':<{width['budget']}} {'QUALITY':<{width['quality']}} "
        f"{'CALLS':<{width['calls']}} {'TOKENS':<{width['tokens']}} {'COST $':<{width['cost']}} {'TIME':<{width['time']}}"
    )
    print("\n" + "=" * len(header))
    print("EVAL SCOREBOARD")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    n_run = 0
    clarify_correct, clarify_total = 0, 0
    grounded_pass, grounded_total = 0, 0
    budget_pass, budget_total = 0, 0
    quality_scores: list[int] = []
    total_calls = 0
    usage_total = dict(llm.ZERO_USAGE)
    errors = []
    hallucinations = []

    for case_id in all_case_ids:
        r = results.get(case_id)
        if r is None:
            print(f"{case_id:<{width['id']}} {'(not yet run)':<60}")
            continue
        n_run += 1

        if r["error"]:
            print(f"{r['id']:<{width['id']}} {r['category']:<{width['cat']}} ERROR: {r['error'][:60]}")
            errors.append(r["id"])
            continue

        if r["clarify_correct"] is not None:
            clarify_total += 1
            clarify_correct += int(r["clarify_correct"])
        if r["groundedness_ok"] is not None:
            grounded_total += 1
            grounded_pass += int(r["groundedness_ok"])
        if r["budget_ok"] is not None:
            budget_total += 1
            budget_pass += int(r["budget_ok"])
        if r["quality_score"] is not None:
            quality_scores.append(r["quality_score"])
        if r.get("hallucinated_despite_clarify"):
            hallucinations.append(r["id"])

        total_calls += r["llm_calls"]
        u = r["llm_usage"]
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage_total[k] += u.get(k, 0)
        usage_total["cost_usd"] = round(usage_total["cost_usd"] + u.get("cost_usd", 0.0), 6)

        clarify_str = _fmt_bool(r["clarify_correct"], "OK", "WRONG")
        ground_str = _fmt_bool(r["groundedness_ok"])
        budget_str = _fmt_bool(r["budget_ok"])
        quality_str = f"{r['quality_score']}/5" if r["quality_score"] is not None else "  --"
        print(
            f"{r['id']:<{width['id']}} {r['category']:<{width['cat']}} {clarify_str:<{width['clarify']}} "
            f"{ground_str:<{width['ground']}} {budget_str:<{width['budget']}} {quality_str:<{width['quality']}} "
            f"{r['llm_calls']:<{width['calls']}} {u.get('total_tokens', 0):<{width['tokens']}} "
            f"{u.get('cost_usd', 0.0):<{width['cost']}.4f} {r['duration_s']:<{width['time']}.1f}"
        )

    print("-" * len(header))
    n_total = len(all_case_ids)
    clarify_rate = clarify_correct / clarify_total if clarify_total else None
    ground_rate = grounded_pass / grounded_total if grounded_total else None
    budget_rate = budget_pass / budget_total if budget_total else None
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else None

    print(f"Cases run: {n_run}/{n_total}" + (f"  ({len(errors)} errored)" if errors else ""))
    print(
        f"Clarification accuracy: {clarify_correct}/{clarify_total}"
        + (f" ({clarify_rate:.0%})" if clarify_rate is not None else "")
        + f"  [target {CLARIFY_ACCURACY_TARGET:.0%}]"
    )
    print(
        f"Groundedness: {grounded_pass}/{grounded_total}"
        + (f" ({ground_rate:.0%})" if ground_rate is not None else "")
        + f"  [target {GROUNDEDNESS_TARGET:.0%}, HARD requirement]"
    )
    print(
        f"Budget adherence: {budget_pass}/{budget_total}"
        + (f" ({budget_rate:.0%})" if budget_rate is not None else "")
        + f"  [target {BUDGET_ADHERENCE_TARGET:.0%}]"
    )
    print(f"Avg quality (LLM-as-judge, 1-5): {avg_quality:.2f}" if avg_quality is not None else "Avg quality: --")
    print(f"Total LLM calls: {total_calls}  |  Total tokens: {usage_total['total_tokens']}  |  Notional cost: ${usage_total['cost_usd']:.4f}")
    if hallucinations:
        print(f"** HALLUCINATION ALERT: produced an itinerary despite clarifying on: {hallucinations} **")
    if errors:
        print(f"Errored cases (likely provider exhaustion — re-run with --cases {','.join(errors)}): {errors}")

    print("=" * len(header))
    if n_run < n_total:
        print(f"INCOMPLETE — {n_total - n_run} case(s) not yet run. Run again (resumes automatically) to continue the batch.")
        return

    passed = (
        not errors
        and (ground_rate is None or ground_rate >= GROUNDEDNESS_TARGET)
        and (budget_rate is None or budget_rate >= BUDGET_ADHERENCE_TARGET)
        and (clarify_rate is None or clarify_rate >= CLARIFY_ACCURACY_TARGET)
        and not hallucinations
    )
    print("RESULT: " + ("PASS — all thresholds met" if passed else "FAIL — see thresholds above"))
    print("=" * len(header))
    if not passed:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", default="all", help="Comma-separated case ids to run, or 'all' (default)")
    parser.add_argument("--rerun", default="", help="Comma-separated case ids to force re-run even if recorded")
    parser.add_argument("--judge", dest="judge", action="store_true", default=True)
    parser.add_argument("--no-judge", dest="judge", action="store_false", help="Skip the LLM-judge quality call")
    parser.add_argument("--report-only", action="store_true", help="Just print the scoreboard from results.json")
    args = parser.parse_args()

    all_cases = _load_cases()
    all_case_ids = [c["id"] for c in all_cases]
    results = _load_results()

    if not args.report_only:
        rerun_ids = {c.strip() for c in args.rerun.split(",") if c.strip()}
        requested_ids = all_case_ids if args.cases == "all" else [c.strip() for c in args.cases.split(",") if c.strip()]
        cases_by_id = {c["id"]: c for c in all_cases}

        to_run = [cid for cid in requested_ids if cid in rerun_ids or cid not in results]
        if not to_run:
            print("Nothing to run — all requested cases already recorded. Use --rerun to force, or --report-only.")
        for i, case_id in enumerate(to_run, 1):
            case = cases_by_id.get(case_id)
            if case is None:
                print(f"Unknown case id: {case_id}")
                continue
            print(f"[{i}/{len(to_run)}] Running {case_id} ({case['category']})...")
            results[case_id] = _run_case(case, use_judge=args.judge)
            _save_results(results)  # save after every case — a quota failure mid-batch loses nothing already done
            r = results[case_id]
            status = "ERROR" if r["error"] else ("INTERRUPTED" if r["interrupted"] else "done")
            print(f"  -> {status}  llm_calls={r['llm_calls']}  tokens={r['llm_usage'].get('total_tokens', 0)}")

    _print_scoreboard(results, all_case_ids)


if __name__ == "__main__":
    main()
