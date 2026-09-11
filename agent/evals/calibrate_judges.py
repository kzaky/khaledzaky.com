#!/usr/bin/env python3
"""Measure which judge model belongs first in the rubric panel's preference list.

The panel's independent seats (target_reader, skeptical_expert, voice_fidelity) run on
whichever non-Anthropic model is first in JUDGE_MODEL_ID and accessible. That ordering
has so far been a hypothesis — "bigger and newer is probably a better judge" — which is
exactly the kind of unmeasured claim the pipeline's own gates exist to catch. This
script replaces it with a number.

GROUND TRUTH
------------
The corpus in evals/cases is fourteen posts the author fixed BY HAND after the pipeline
published them. The `before` text is what shipped; the `after` text is what the author
wanted. The lines the author changed are, by construction, the defects a good judge
should have caught — no labelling effort required, and no model's opinion involved.

SCORING
-------
For each case, the before->after diff yields the set of REMOVED lines: prose the author
deleted or rewrote. A seat finding counts as a `hit` when its quoted sentence is
substantially contained in one of those removed lines.

  hit_rate   hits / findings          — of what this seat flagged, how much the author
                                        actually went on to change
  case_recall cases with >=1 hit      — how often the seat found anything real at all
  volume     findings per case        — flag-everything inflates hit_rate's denominator
                                        without being useful, so it is reported alongside

hit_rate is a LOWER BOUND on correctness, deliberately. A finding on text the author
left alone is not necessarily wrong — the author fixed what they noticed, on a deadline,
not everything that was wrong. So do not read hit_rate as accuracy. Read it as a
*relative* signal: the same cases, the same seats, the same scoring, different models.
That comparison is fair even though the absolute number is pessimistic.

Seats are only scored on cases whose defect class they are responsible for (a voice seat
has no business being graded on a citation fix), per SEAT_CLASSES below.

COST
----
One model call per (case, seat, model). With the default corpus and three seats that is
about 30 calls per model. Run --estimate first; it prints the call count and does not
touch Bedrock.

USAGE
-----
    python3 agent/evals/calibrate_judges.py --estimate
    python3 agent/evals/calibrate_judges.py --models mistral.mistral-large-3-675b-instruct,openai.gpt-oss-120b-1:0
    python3 agent/evals/calibrate_judges.py --models ... --json results.json

Requires AWS credentials with bedrock:Converse. Nothing is written to SSM or Lambda —
this only measures. Acting on the result means reordering JUDGE_MODEL_ID yourself.
"""

import argparse
import difflib
import json
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "common"))
sys.path.insert(0, str(HERE.parent / "evaluate"))

import run_gate  # noqa: E402

# Which corpus defect classes each seat is actually responsible for. Scoring a seat on a
# class it was never meant to catch measures nothing.
SEAT_CLASSES = {
    "fact_checker": {"citation", "overclaim"},
    "skeptical_expert": {"overclaim", "citation"},
    "voice_fidelity": {"ai_pattern", "voice", "spelling"},
    "target_reader": {"ai_pattern", "voice", "overclaim"},
    "author_intent": {"content_loss"},
}

# Seats that run on the independent (non-Anthropic) model. Only these are worth
# comparing across candidate judge models; the others always run on Sonnet.
INDEPENDENT_SEATS = ("target_reader", "skeptical_expert", "voice_fidelity")

_MIN_QUOTE_CHARS = 25


def _normalize(text):
    return re.sub(r"\s+", " ", text or "").strip().lower()


def removed_lines(before, after):
    """Prose lines the author deleted or rewrote, i.e. the defects they went on to fix.

    Only substantial prose is kept: blank lines, headings, and markup-only lines carry
    no claim worth a judge flagging, and would otherwise make near-empty strings match
    everything."""
    out = []
    for line in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0):
        if not line.startswith("-") or line.startswith("---"):
            continue
        body = line[1:].strip()
        if len(body) < _MIN_QUOTE_CHARS or body.startswith(("#", "|", "!", "<", "```")):
            continue
        out.append(_normalize(body))
    return out


def is_hit(quote, removed):
    """True when a seat's quoted sentence is substantially inside a line the author
    changed. Containment both ways, because a seat may quote a fragment of a long
    paragraph or a whole short line the author edited."""
    q = _normalize(quote)
    if len(q) < _MIN_QUOTE_CHARS:
        return False
    for line in removed:
        if q in line or line in q:
            return True
        # near-match tolerance: a seat may normalize punctuation or clip mid-word
        if difflib.SequenceMatcher(None, q[:300], line[:300]).ratio() >= 0.82:
            return True
    return False


def score_seat_run(findings, before, after):
    """Score one seat's findings for one case. Returns (hits, total)."""
    removed = removed_lines(before, after)
    quotes = [f.get("quote", "") for f in findings]
    hits = sum(1 for q in quotes if is_hit(q, removed))
    return hits, len(quotes)


def relevant_cases(cases, seat):
    classes = SEAT_CLASSES.get(seat, set())
    return [c for c in cases if classes & set(c["classes"])]


def aggregate(rows):
    """rows: list of dicts with model, seat, case, hits, findings, hit_case."""
    by = defaultdict(lambda: {"hits": 0, "findings": 0, "cases": 0, "cases_with_hit": 0, "failed": 0})
    for r in rows:
        key = (r["model"], r["seat"])
        agg = by[key]
        if r.get("error"):
            agg["failed"] += 1
            continue
        agg["hits"] += r["hits"]
        agg["findings"] += r["findings"]
        agg["cases"] += 1
        agg["cases_with_hit"] += 1 if r["hits"] else 0
    out = []
    for (model, seat), a in sorted(by.items()):
        out.append({
            "model": model,
            "seat": seat,
            "cases": a["cases"],
            "failed": a["failed"],
            "findings": a["findings"],
            "hits": a["hits"],
            "hit_rate": round(a["hits"] / a["findings"], 3) if a["findings"] else None,
            "case_recall": round(a["cases_with_hit"] / a["cases"], 3) if a["cases"] else None,
            "findings_per_case": round(a["findings"] / a["cases"], 2) if a["cases"] else None,
        })
    return out


def _run_one(evaluate, case, seat, model, references):
    """One seat, one case, one model. Returns a row dict."""
    import llm

    body = evaluate._body(case["before"])
    row = {"model": model, "seat": seat, "case": case["commit"], "classes": case["classes"]}
    try:
        # Pin this call to the model under test, bypassing the priority list.
        original = llm.judge_candidates_for
        llm.judge_candidates_for = lambda _seat, _m=model: [_m]
        try:
            result = evaluate.run_seat(seat, body, research="", verdicts="(not supplied)",
                                       author_content="", references=references)
        finally:
            llm.judge_candidates_for = original
        if result.get("unavailable"):
            row["error"] = result["unavailable"]
            return row
        served = result.get("model", "")
        if served and served != model:
            # a silent fallback would score the wrong model's output as this model's
            row["error"] = f"served by {served}, not {model}"
            return row
        hits, total = score_seat_run(result.get("findings", []), case["before"], case["after"])
        row.update({"hits": hits, "findings": total, "score": result.get("score")})
    except Exception as e:  # noqa: BLE001 - a failed seat is data, not a crash
        row["error"] = str(e)[:200]
    return row


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="", help="comma-separated Bedrock model ids to compare")
    ap.add_argument("--seats", default=",".join(INDEPENDENT_SEATS))
    ap.add_argument("--estimate", action="store_true", help="print the call count and exit; no Bedrock calls")
    ap.add_argument("--json", dest="json_out", default="", help="write full per-run rows here")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args(argv)

    cases = run_gate.load_cases()
    seats = [s.strip() for s in args.seats.split(",") if s.strip()]
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    plan = [(c, s) for s in seats for c in relevant_cases(cases, s)]
    if args.estimate or not models:
        print(f"corpus: {len(cases)} cases")
        for s in seats:
            print(f"  {s:18s} {len(relevant_cases(cases, s)):2d} relevant case(s)  (classes: {', '.join(sorted(SEAT_CLASSES.get(s, [])))})")
        print(f"\n{len(plan)} call(s) per model.")
        if models:
            print(f"{len(models)} model(s) -> {len(plan) * len(models)} total Bedrock calls.")
        else:
            print("Pass --models to run. Nothing was called.")
        return 0

    import evaluate  # noqa: PLC0415 - imported late so --estimate needs no boto3/AWS

    references = evaluate._load_voice_references()
    if not references:
        print("warning: no voice references loaded; voice_fidelity will judge without them", file=sys.stderr)

    rows = []
    for model in models:
        print(f">> {model} ({len(plan)} calls)", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futures = [ex.submit(_run_one, evaluate, c, s, model, references) for c, s in plan]
            for f in futures:
                rows.append(f.result())

    summary = aggregate(rows)
    print(f"\n{'model':45s} {'seat':18s} {'cases':>5s} {'find':>5s} {'hits':>5s} {'hit_rate':>9s} {'recall':>7s} {'f/case':>7s} {'fail':>5s}")
    for r in summary:
        print(f"{r['model'][:45]:45s} {r['seat']:18s} {r['cases']:5d} {r['findings']:5d} {r['hits']:5d} "
              f"{str(r['hit_rate']):>9s} {str(r['case_recall']):>7s} {str(r['findings_per_case']):>7s} {r['failed']:5d}")

    print("\nhit_rate = of what the seat flagged, the share the author actually changed.")
    print("It is a lower bound (the author did not fix everything), so read it as a")
    print("relative comparison between models on identical cases, not as accuracy.")
    print("A high hit_rate with a high findings_per_case is the combination worth having.")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps({"rows": rows, "summary": summary}, indent=1))
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
