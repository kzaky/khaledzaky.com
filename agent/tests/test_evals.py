"""Eval harness assertions — run in CI alongside the handler tests.

The corpus (agent/evals/cases) is fourteen hand fixes the author made after the
pipeline published a post. For every case the shipped text must trip the gate check
the fix addressed, and the fixed text must not; every currently published post must
pass the gate in published mode with zero errors (a false positive here would have
blocked a real post). No model calls — this is the deterministic layer only.
"""

import sys
from pathlib import Path

import pytest

EVALS = Path(__file__).resolve().parent.parent / "evals"
sys.path.insert(0, str(EVALS))
sys.path.insert(0, str(EVALS.parent / "common"))

import run_gate  # noqa: E402

CASES = run_gate.load_cases()
DETECTABLE = [c for c in CASES if c["gate_detectable"]]
BLOG_DIR = run_gate.ROOT / "src" / "content" / "blog"


def test_corpus_and_manifest_agree():
    assert len(CASES) == 14
    assert all(c["before"] != c["after"] for c in CASES), "a case with identical before/after carries no signal"


@pytest.mark.parametrize("case", DETECTABLE, ids=[c["commit"] for c in DETECTABLE])
def test_gate_catches_what_the_author_fixed(case):
    passed, checks = run_gate.score_case(case)
    failed = [(n, d) for n, ok, d in checks if not ok]
    assert passed, f"{case['commit']} {case['subject']}: {failed}"


def test_detectability_partition_is_documented():
    """Nine of fourteen cases carry a deterministic signal today. If a gate change moves
    this number, update manifest.json deliberately rather than letting it drift."""
    assert len(DETECTABLE) == 9, [c["commit"] for c in DETECTABLE]


@pytest.mark.skipif(not BLOG_DIR.is_dir(), reason="site content not checked out")
def test_no_false_positives_on_published_posts():
    rows = run_gate.run_oracle(BLOG_DIR)
    assert len(rows) >= 50
    false_positives = [(name, errs) for name, errs, _ in rows if errs]
    assert false_positives == [], false_positives
