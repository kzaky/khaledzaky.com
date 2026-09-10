#!/usr/bin/env python3
"""Offline runner for the deterministic release gate (agent/common/gate.py).

Two jobs, both cheap (no model calls):

  1. ORACLE  — every published post under src/content/blog must pass the gate in
               published mode with zero errors. A false positive here means the gate
               would have blocked a real post; fix the gate, not the post.
  2. CORPUS  — every case in evals/cases (a hand fix the author made after the
               pipeline published) is scored against manifest.json's expectations:
               the shipped text must trip the check, the fixed text must not.

    python3 agent/evals/run_gate.py            # human-readable report, exit 1 on failure
    python3 agent/evals/run_gate.py --json     # machine-readable

The same assertions run in CI via agent/tests/test_evals.py.
"""

import argparse
import glob
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "common"))

import gate  # noqa: E402


def _links(md):
    _, body = gate.split_frontmatter(md)
    return len(set(re.findall(r"\]\((https?://[^)\s]+)\)", body)))


def _words(md):
    _, body = gate.split_frontmatter(md)
    return len(re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).split())


def load_cases():
    manifest = json.loads((HERE / "manifest.json").read_text())
    by_commit = {c["commit"]: c for c in manifest["cases"]}
    cases = []
    for f in sorted(glob.glob(str(HERE / "cases" / "*.json"))):
        rec = json.loads(Path(f).read_text())
        entry = by_commit.get(rec["commit"])
        if entry is None:
            raise SystemExit(f"{f}: commit {rec['commit']} is not in manifest.json — rebuild with build_cases.py")
        rec["expect"] = entry.get("expect")
        rec["gate_detectable"] = entry.get("gate_detectable", False)
        cases.append(rec)
    missing = set(by_commit) - {c["commit"] for c in cases}
    if missing:
        raise SystemExit(f"manifest cases without a case file: {sorted(missing)} — run build_cases.py")
    return cases


def score_case(case):
    """Return (passed: bool, checks: list[(name, ok, detail)]) for one case."""
    exp = case["expect"] or {}
    before, after = case["before"], case["after"]
    b_find, a_find = gate.analyze(before), gate.analyze(after)
    b_err = {f["check"] for f in gate.errors(b_find)}
    a_err = {f["check"] for f in gate.errors(a_find)}
    b_warn = [f["detail"] for f in gate.warnings(b_find)]
    a_warn = [f["detail"] for f in gate.warnings(a_find)]
    checks = []

    for check in exp.get("before_errors", []):
        checks.append((f"before raises {check}", check in b_err, sorted(b_err)))
    if exp.get("after_errors_empty"):
        checks.append(("after raises nothing", not a_err, sorted(a_err)))
    for check in exp.get("before_published_errors", []):
        pub_err = {f["check"] for f in gate.errors(gate.analyze(before, published=True))}
        checks.append((f"before (published mode) raises {check}", check in pub_err, sorted(pub_err)))
    for sub in exp.get("before_finding_substr", []):
        checks.append((f"before flags {sub}", any(sub in w for w in b_warn), b_warn[:4]))
    for sub in exp.get("after_finding_absent_substr", []):
        checks.append((f"after no longer flags {sub}", not any(sub in w for w in a_warn), a_warn[:4]))
    if exp.get("findings_decrease"):
        checks.append(("fewer advisory findings after the fix", len(a_warn) < len(b_warn), f"{len(b_warn)} -> {len(a_warn)}"))
    if exp.get("links_increase"):
        lb, la = _links(before), _links(after)
        checks.append(("fix added source links", la > lb, f"{lb} -> {la}"))
    if exp.get("words_increase_pct"):
        wb, wa = _words(before), _words(after)
        pct = exp["words_increase_pct"]
        checks.append((f"fix restored >= {pct}% words", wa >= wb * (1 + pct / 100), f"{wb} -> {wa}"))
    return all(ok for _, ok, _ in checks), checks


def run_oracle(blog_dir):
    rows = []
    for f in sorted(glob.glob(str(blog_dir / "*.md"))):
        findings = gate.analyze(Path(f).read_text(), published=True)
        rows.append((Path(f).name, [x["check"] + ": " + x["detail"] for x in gate.errors(findings)], len(gate.warnings(findings))))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--blog-dir", default=str(ROOT / "src" / "content" / "blog"))
    args = ap.parse_args(argv)

    blog_dir = Path(args.blog_dir)
    oracle = run_oracle(blog_dir) if blog_dir.is_dir() else []
    oracle_fail = [(n, e) for n, e, _ in oracle if e]

    cases = load_cases()
    results = []
    for c in cases:
        if not c["gate_detectable"]:
            results.append({"commit": c["commit"], "classes": c["classes"], "detectable": False, "passed": None, "checks": []})
            continue
        passed, checks = score_case(c)
        results.append({"commit": c["commit"], "classes": c["classes"], "detectable": True, "passed": passed,
                        "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks]})
    corpus_fail = [r for r in results if r["detectable"] and not r["passed"]]

    if args.json:
        print(json.dumps({"oracle": {"posts": len(oracle), "false_positives": oracle_fail}, "corpus": results}, indent=1, default=str))
    else:
        print(f"ORACLE  {len(oracle)} published posts, {len(oracle_fail)} with gate errors")
        for name, errs in oracle_fail:
            print(f"   FAIL {name}: {errs}")
        det = [r for r in results if r["detectable"]]
        print(f"\nCORPUS  {len(det)}/{len(results)} cases carry a deterministic signal; "
              f"{sum(1 for r in det if r['passed'])}/{len(det)} pass")
        for r in results:
            tag = "  --  " if not r["detectable"] else ("  ok  " if r["passed"] else " FAIL ")
            print(f" {tag}{r['commit']}  {','.join(r['classes'])}")
            for ch in r["checks"]:
                if not ch["ok"] or "--verbose" in sys.argv:
                    print(f"          {'ok ' if ch['ok'] else 'BAD'} {ch['name']}  ({ch['detail']})")
        undet = [r for r in results if not r["detectable"]]
        print(f"\n{len(undet)} cases need an LLM seat (L1 claim verification / L2 rubric panel): "
              + ", ".join(f"{r['commit']}({'/'.join(r['classes'])})" for r in undet))
    return 1 if (oracle_fail or corpus_fail) else 0


if __name__ == "__main__":
    sys.exit(main())
