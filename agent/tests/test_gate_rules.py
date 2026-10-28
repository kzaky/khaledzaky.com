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


@pytest.mark.parametrize("name", ["APPENDIX_HEADINGS", "HEDGE_PHRASES", "RAW_HTML_TAGS"])
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

def test_hedge_placeholder_is_an_error_in_both_modes():
    """Publish does not run the gate, so Notify must stop what check:render would."""
    md = _doc("Scores remain unconfirmed pending verification of the source URL.")
    assert "hedge_placeholder" in _checks(md, published=True, level="error")
    assert "hedge_placeholder" in _checks(md, published=False, level="error")


@pytest.mark.parametrize("text", [
    "I haven't reproduced them yet.",
    "I have not independently verified the full scope.",
    "The verification step is pending a reviewer.",
])
def test_hedge_rule_leaves_the_authors_own_caveats_alone(text):
    assert "hedge_placeholder" not in _checks(_doc(text), published=True)


# --- body_h1 -------------------------------------------------------------------------

def test_body_h1_is_an_error_in_both_modes():
    md = _doc("# A different title\n\nIntro.")
    assert "body_h1" in _checks(md, published=True, level="error")
    assert "body_h1" in _checks(md, published=False, level="error")


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


# --- guard_rewrite: whole-post rewrites may not add hedging or review notes ----------

_BODY = "A paragraph about agents and authority. " * 40


def test_guard_rejects_a_rewrite_that_adds_placeholder_hedging():
    kept, reason = gate.guard_rewrite(_BODY, _BODY + " The scores remain unconfirmed pending verification.")
    assert kept == _BODY and "placeholder hedging" in reason


def test_guard_rejects_a_rewrite_that_appends_review_notes():
    kept, reason = gate.guard_rewrite(_BODY, _BODY + "\n\n## Change Log\n\n1. Rewrote the intro.")
    assert kept == _BODY and "review-notes heading" in reason


def test_guard_keeps_hedging_the_author_already_wrote():
    before = _BODY + " Their numbers remain unconfirmed pending verification by a second lab."
    after = before.replace("A paragraph", "One paragraph", 1)
    kept, reason = gate.guard_rewrite(before, after)
    assert reason is None and kept == after


# --- voice rules added for the model-decision post (1b54389) -------------------------

def _slop(body):
    return gate.slop_findings(body)


def test_rule_of_three_sees_through_grouped_numbers():
    assert any("rule-of-three" in f for f in _slop("Same model. Same 1,000 requests. Same 150 possible answers."))
    assert any("rule-of-three" in f for f in _slop("I win. You lose. We tie."))


def test_did_beat_fires_on_the_second_repeat_only():
    one = "Neither model changed. The question did, and that matters."
    two = one + "\n\nNo model changed. A repair step in the path did, every time."
    assert not any("didn't change" in f for f in _slop(one))
    assert any("didn't change" in f for f in _slop(two))


def test_this_is_the_part_fires_on_the_second_use():
    one = "This is the part I had to think through twice."
    assert not any("This is the part" in f for f in _slop(one))
    assert any("This is the part" in f for f in _slop(one + "\n\nThis is the part closest to my day job."))


def _pre_agent_posts():
    out = []
    for f in sorted((ROOT / "src" / "content" / "blog").glob("*.md")):
        text = f.read_text()
        m = re.search(r"^date:\s*(\S+)", text, re.MULTILINE)
        if m and m.group(1) < "2026-02-21":
            out.append((f.name, text))
    return out


@pytest.mark.skipif(not (ROOT / "src" / "content" / "blog").is_dir(), reason="site content not checked out")
def test_new_voice_rules_never_fire_on_the_authors_pre_agent_posts():
    """Calibration: the author's 18 pre-agent posts (before 2026-02-21) are the voice
    baseline. A rule that fires on them is flagging the author, not the agent."""
    posts = _pre_agent_posts()
    assert len(posts) == 18
    for name, text in posts:
        _, body = gate.split_frontmatter(text)
        hits = [f for f in gate.slop_findings(body)
                if f.startswith(("rule-of-three", '"This is the part', '"X didn'))]
        hits += [f["check"] for f in gate.structure_findings(text, published=True)
                 if f["check"] in ("ascii_figure", "no_figures", "employer_reference")]
        assert hits == [], (name, hits)


# --- figure and employer rules (b702217, b7b1918, 4f84b26, 6cb5563) ---------------------

def test_ascii_flow_and_hash_bars_are_flagged():
    flow = "```\nApplication state\n       |\n       v\nA bounded question\n       |\n       v\nDecision\n```"
    bars = "```text\nCost per 1,000 emails\n\nJev    ##        $0.0384\nHaiku  ######### $0.4622\nOther  ######    $0.2000\n```"
    arrows = "```\nAgent\n   \u2193\nGuardrails\n   \u2193\nEvidence\n```"
    for block in (flow, bars, arrows):
        assert "ascii_figure" in _checks(_doc("Intro.\n\n" + block), level="warn"), block


def test_code_and_directory_trees_are_not_figures():
    tree = "```\nsrc/\n\u251c\u2500\u2500 layouts/BlogPost.astro\n\u251c\u2500\u2500 styles/global.css\n\u2514\u2500\u2500 plugins/rehype-stack-tables.mjs\n```"
    code = "```python\nx = a -> b\n# ---> not a figure\nprint(x)\n```"
    for block in (tree, code):
        assert "ascii_figure" not in _checks(_doc("Intro.\n\n" + block)), block


def test_long_post_needs_a_figure_and_placeholders_count():
    long_body = ("A sentence about agents and authority. " * 360).strip()  # 2,160 words
    assert "no_figures" in _checks(_doc(long_body), level="warn")
    for fig in ("![A diagram](/postimages/charts/x.svg)", "<!-- CHART: bar | A | 1 -->", "```mermaid\nflowchart TD\nA-->B\n```"):
        assert "no_figures" not in _checks(_doc(long_body + "\n\n" + fig)), fig
    assert "no_figures" not in _checks(_doc("Short post. " * 100))


@pytest.mark.parametrize("text", ["On the platform I'm building, we tier checks.", "A colleague on my team asked me.",
                                  "Someone on my team made me look."])
def test_employer_as_authority_is_flagged(text):
    assert "employer_reference" in _checks(_doc(text), level="warn")


def test_named_past_employer_is_not_employer_as_authority():
    assert "employer_reference" not in _checks(_doc("I worked in identity at AWS, where Zelkova earned its keep."))
