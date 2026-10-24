"""Unit tests for the release-gate rules added after the October posts, and a parity
check that keeps the Markdown gate (agent/common/gate.py) and the built-HTML gate
(scripts/check-render-shape.mjs) on the same phrase lists.

The corpus tests in test_evals.py prove each rule catches the real shipped defect;
these pin the edges: what must fire, what must stay quiet, and at which level in the
pipeline versus published mode.
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "common"))

import gate  # noqa: E402


def _doc(body, fm_extra=""):
    return f"---\ntitle: \"A post\"\ndate: 2026-10-24\n{fm_extra}---\n\n{body}\n"


def _checks(markdown, published=False, level=None):
    found = gate.structure_findings(markdown, published=published)
    return {f["check"] for f in found if level is None or f["level"] == level}


# --- parity with the HTML gate ----------------------------------------------------

def _js_array(name):
    src = (ROOT / "scripts" / "check-render-shape.mjs").read_text()
    m = re.search(rf"const {name} = (\[.*?\]);", src, re.DOTALL)
    assert m, f"{name} not found in check-render-shape.mjs"
    return json.loads(m.group(1))


@pytest.mark.parametrize("name", ["APPENDIX_HEADINGS", "HEDGE_PHRASES"])
def test_html_gate_uses_the_same_lists(name):
    assert _js_array(name) == list(getattr(gate, name))


# --- review_appendix ----------------------------------------------------------------

@pytest.mark.parametrize("heading", [
    "## Change Log", "## Changelog", "### Citation Audit", "## Remaining Blockers",
    "## 2. Revision Notes", "#### Review notes",
])
def test_appendix_heading_is_an_error_in_both_modes(heading):
    md = _doc(f"Some prose.\n\n{heading}\n\n1. stuff")
    assert "review_appendix" in _checks(md, published=False, level="error")
    assert "review_appendix" in _checks(md, published=True, level="error")


@pytest.mark.parametrize("text", [
    "The change log for the draft spec is public.",           # prose, not a heading
    "## Changes to the Market",                                # heading, different words
    "## What Changed Since March",
])
def test_appendix_rule_ignores_prose_and_other_headings(text):
    assert "review_appendix" not in _checks(_doc(f"Intro.\n\n{text}\n\nMore."))


def test_appendix_heading_inside_a_code_fence_is_ignored():
    md = _doc("Intro.\n\n```markdown\n## Change Log\n```\n\nMore.")
    assert "review_appendix" not in _checks(md)


# --- hedge_placeholder -------------------------------------------------------------

def test_hedge_placeholder_errors_when_published_and_warns_in_the_pipeline():
    md = _doc("Scores remain unconfirmed pending verification of the source URL.")
    assert "hedge_placeholder" in _checks(md, published=True, level="error")
    assert "hedge_placeholder" in _checks(md, published=False, level="warn")
    assert "hedge_placeholder" not in _checks(md, published=False, level="error")


@pytest.mark.parametrize("text", [
    "I haven't reproduced them yet.",
    "I have not independently verified the full scope.",
    "The verification step is pending a reviewer.",
])
def test_hedge_rule_leaves_the_authors_own_caveats_alone(text):
    assert "hedge_placeholder" not in _checks(_doc(text), published=True)


# --- body_h1 -------------------------------------------------------------------------

def test_body_h1_errors_when_published_and_warns_in_the_pipeline():
    md = _doc("# A different title\n\nIntro.")
    assert "body_h1" in _checks(md, published=True, level="error")
    assert "body_h1" in _checks(md, published=False, level="warn")


def test_h2_and_code_comments_are_not_h1():
    md = _doc("## Section\n\n```bash\n# a shell comment\n```\n")
    assert "body_h1" not in _checks(md, published=True)


# --- meta_dash and tldr_late (advisory) ---------------------------------------------

def test_dash_in_description_is_a_warning_only():
    md = _doc("Body.", fm_extra="description: \"Accuracy moved—a lot.\"\n")
    assert "meta_dash" in _checks(md, published=True, level="warn")
    assert "meta_dash" not in _checks(md, published=True, level="error")


def test_tldr_position():
    late = _doc("Paragraph one is long. " * 40 + "\n\n**TL;DR:** the point.")
    early = _doc("> **TL;DR:** the point.\n\n" + "Paragraph. " * 40)
    assert "tldr_late" in _checks(late, level="warn")
    assert "tldr_late" not in _checks(early)


# --- the gate still parses under the Lambda runtime's grammar ------------------------

def test_gate_has_no_nested_quote_fstrings():
    """Lambdas run python3.12, but keep gate.py importable by older local tooling:
    an f-string that reuses its own quote type inside a replacement field is a
    SyntaxError before 3.12."""
    src = (ROOT / "agent" / "common" / "gate.py").read_text()
    assert not re.search(r'f"[^"\n]*\{[^}\n]*"[^}\n]*\}', src)
