"""Deterministic release gate (L0) shared by the Draft, Notify and Evaluate Lambdas
and by the offline eval harness (agent/evals).

Every check here is a regex or a parse, never a model call. That is deliberate: these
are the properties a probabilistic judge keeps missing (a regex never forgets a
phrase, never anchors on its examples, and costs nothing), and they are the exact
defect classes that escaped to production in the last five agent-published posts:

  * rendering integrity  - a second frontmatter block nested inside a ```markdown
                           fence that wrapped the whole article (5a98dce)
  * content loss         - sections dropped by a full-rewrite audit pass (9115b2d)
  * AI-writing patterns  - antithesis closers, three-beat aphorisms, the
                           "the part that..." formula (f313e2f, 8ba7eae, 8d2afc3)
  * spelling convention  - British -ise where the author writes Canadian -ize (00f126c)

Findings carry a level:
  "error" - the draft must not reach the reviewer's inbox (Notify raises)
  "warn"  - surfaced on the review email / scorecard, never blocks

This module is VENDORED into each Lambda package at build time (see
scripts/package-lambda.sh and the function's .common-deps manifest), so it must stay
self-contained: standard library only, no imports from sibling Lambda code.
"""

import re

# ---------------------------------------------------------------------------
# Frontmatter / body helpers
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def split_frontmatter(markdown):
    """Return (frontmatter_text, body). frontmatter_text is "" when the document has
    no leading ``---`` block. The body excludes the delimiters."""
    if not markdown.startswith("---"):
        return "", markdown
    end = markdown.find("\n---", 3)
    if end == -1:
        return markdown, ""
    fm = markdown[3:end].strip("\n")
    body = markdown[end + 4:]
    return fm, body


def _prose_lines(body):
    """Yield (line_no, line) for lines that are outside fenced code blocks."""
    in_fence = False
    for i, line in enumerate(body.splitlines(), 1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield i, line


def _fence_wrap_ratio(body):
    """If the first non-empty body line opens a code fence, return the fraction of
    the body enclosed by that fence (0.0 otherwise). A whole article wrapped in
    ```markdown renders as one <pre><code> block instead of headings and tables."""
    lines = body.splitlines()
    first = next((i for i, ln in enumerate(lines) if ln.strip()), None)
    if first is None or not _FENCE_RE.match(lines[first]):
        return 0.0
    close = next((i for i in range(first + 1, len(lines)) if _FENCE_RE.match(lines[i])), None)
    if close is None:
        return 1.0
    enclosed = sum(len(ln) + 1 for ln in lines[first + 1:close])
    total = max(1, sum(len(ln) + 1 for ln in lines))
    return enclosed / total


# ---------------------------------------------------------------------------
# Prose-shape patterns (detect only; regex must never rewrite a sentence)
# ---------------------------------------------------------------------------

FORBIDDEN_PHRASES = (
    "it is worth noting", "it goes without saying", "paradigm shift", "in today's",
    "stay tuned", "delve into", "dive deep", "game-changer", "cutting-edge",
    "in conclusion", "to summarize", "without further ado", "let's explore",
    "let's take a look at", "the reality is", "the truth is", "make no mistake",
    "let me be clear", "here's the thing", "here's what that means in practice",
    "here's where it gets interesting", "is where it gets interesting", "this is not magic",
    "here is the part that connects", "as i mentioned", "as mentioned above", "as we discussed",
)

# Two short sentences where the second negates then renames the first:
# "That's not cutting corners. That's allocation."
ANTITHESIS_RE = re.compile(
    r"\b(?:that|it|this)(?:['’]s| is| was)\s+not\b[^.!?]*[.!?]\s+"
    r"(?:that|it|this)(?:['’]s| is| was)\b[^.!?]*[.!?]",
    re.IGNORECASE,
)

# "not X, but Y" / "not X but Y" contrast used as a sentence spine.
NOT_BUT_RE = re.compile(r"\bnot\s+(?:a|an|the|about|just|only)?\s*[^,.;]{2,40},?\s+but\s+(?:a|an|the|about)?\b", re.IGNORECASE)

# Three consecutive very short sentences on one prose line: "Start small. Ship fast. Iterate."
RULE_OF_THREE_RE = re.compile(r"(?:\b[A-Z][\w'’-]*(?:\s+[\w'’-]+){0,3}[.!]\s+){2}[A-Z][\w'’-]*(?:\s+[\w'’-]+){0,3}[.!]")

_ITALIC_LINE_RE = re.compile(r"^(\*|_)(?!\1)(.+?)\1$")

# British -ise verbs the author corrects to Canadian -ize (00f126c). Allow-listed
# stems only, so "promise", "enterprise", "precise", "otherwise" never trip it.
_ISE_STEMS = (
    "organis", "recognis", "realis", "penalis", "optimis", "prioritis", "summaris",
    "categoris", "standardis", "authoris", "minimis", "maximis", "utilis", "emphasis",
    "centralis", "formalis", "normalis", "serialis", "initialis", "tokenis", "visualis",
    "characteris", "specialis", "generalis", "capitalis", "industrialis", "criticis",
    "apologis", "customis", "modernis", "monetis", "operationalis", "parameteris",
    "sanitis", "synchronis", "materialis", "finalis", "legitimis", "scrutinis",
)
_ISE_RE = re.compile(r"\b(?:" + "|".join(_ISE_STEMS) + r")(?:e|es|ed|ing)\b", re.IGNORECASE)
# American -or forms the author writes with Canadian -our.
_US_OUR_RE = re.compile(r"\b(?:behavior|color|favor|honor|labor|flavor|neighbor|rumor|humor)(?:s|ed|ing|al|ally|able)?\b", re.IGNORECASE)


def slop_findings(body):
    """Detect AI-writing shapes, forbidden phrases and spelling-convention slips in a
    post body. Returns a list of human-readable finding strings (no levels — every
    item here is advisory). Used by Draft (_lint_slop) and by Notify via analyze()."""
    findings = []
    lower = body.lower().replace("’", "'")

    for phrase in FORBIDDEN_PHRASES:
        n = lower.count(phrase)
        if n:
            findings.append(f'forbidden phrase "{phrase}" x{n}')

    for hit in ANTITHESIS_RE.findall(body)[:5]:
        findings.append(f"antithesis mic-drop: {hit.strip()[:80]}")

    prose = [ln for _, ln in _prose_lines(body) if ln.strip() and not ln.lstrip().startswith(("#", "-", "*", "|", "!", "<", ">", "1", "2", "3", "4", "5", "6", "7", "8", "9"))]
    prose_text = "\n".join(prose)

    not_but = len(NOT_BUT_RE.findall(prose_text))
    if not_but >= 3:
        findings.append(f'"not X, but Y" contrast x{not_but} (stacked contrasts read as generated)')

    for hit in RULE_OF_THREE_RE.findall(prose_text)[:3]:
        findings.append(f"rule-of-three fragments: {hit.strip()[:80]}")

    part_that = len(re.findall(r"\bthe part that\b", lower))
    if part_that >= 3:
        findings.append(f'"the part that..." formula x{part_that}')
    heres = len(re.findall(r"(?:^|[.!?]\s+)here['’]s the\b", lower))
    if heres >= 2:
        findings.append(f'"Here\'s the ..." sentence opener x{heres}')

    # Aphoristic closer: the final non-empty line is an italic-only sentence or a
    # three-beat slogan. The author deleted these by hand on two of the last five
    # posts (8d2afc3, f313e2f); the structure audit used to *mandate* them.
    last = next((ln.strip() for ln in reversed(body.splitlines()) if ln.strip()), "")
    m = _ITALIC_LINE_RE.match(last)
    if m:
        inner = m.group(2)
        beats = len(re.findall(r"[.!?](?:\s|$)", inner))
        if beats >= 2:
            findings.append(f"aphoristic italic closer with {beats} beats: {inner[:80]}")
        else:
            findings.append(f"italic one-line closer: {inner[:80]}")

    ise = sorted({w.lower() for w in _ISE_RE.findall(body)})
    if ise:
        findings.append(f"British -ise spelling (author uses Canadian -ize): {', '.join(ise[:6])}")
    usour = sorted({w.lower() for w in _US_OUR_RE.findall(body)})
    if usour:
        findings.append(f"US -or spelling (author uses Canadian -our): {', '.join(usour[:6])}")

    return findings


# ---------------------------------------------------------------------------
# Document-level structural checks
# ---------------------------------------------------------------------------

def structure_findings(markdown, *, min_headings=2, min_words=600, max_words=4500):
    """Rendering/structure integrity. Returns list of {"level", "check", "detail"}."""
    findings = []

    def err(check, detail):
        findings.append({"level": "error", "check": check, "detail": detail})

    def warn(check, detail):
        findings.append({"level": "warn", "check": check, "detail": detail})

    if not markdown.startswith("---"):
        err("frontmatter_missing", "document does not start with a --- frontmatter block")
        fm, body = "", markdown
    else:
        fm, body = split_frontmatter(markdown)
        if not body and "\n---" not in markdown[3:]:
            err("frontmatter_unclosed", "opening --- has no closing ---")

    for key in ("title", "date"):
        n = len(re.findall(rf"^{key}:", fm, re.MULTILINE))
        if fm and n != 1:
            err("frontmatter_key_count", f"frontmatter has {n} '{key}:' lines (expected 1)")
    drafts = len(re.findall(r"^draft:", fm, re.MULTILINE))
    if drafts > 1:
        err("draft_flag_duplicate", f"frontmatter has {drafts} 'draft:' lines")

    # A second frontmatter block inside the body (outside code fences) — the nested
    # duplicate that the coverage post shipped with.
    body_prose = "\n".join(ln for _, ln in _prose_lines(body))
    if re.search(r"^---\s*\n(?:[^\n]*\n){0,8}?title:", body_prose, re.MULTILINE):
        err("frontmatter_nested", "a second frontmatter block appears inside the body")

    ratio = _fence_wrap_ratio(body)
    if ratio >= 0.5:
        err("body_fenced", f"a code fence opened at the top of the body encloses {int(ratio * 100)}% of it; the article will render as one code block")

    headings = len(re.findall(r"^##\s+\S", body_prose, re.MULTILINE))
    if headings < min_headings:
        err("headings_low", f"{headings} '##' headings (minimum {min_headings})")

    words = len(re.sub(r"<!--.*?-->", "", body_prose, flags=re.DOTALL).split())
    if words < min_words:
        warn("words_low", f"{words} words (expected at least {min_words})")
    elif words > max_words:
        warn("words_high", f"{words} words (expected at most {max_words})")

    links = len(re.findall(r"\]\(https?://", body_prose))
    if links == 0:
        warn("no_external_links", "no external links; every claim rests on model knowledge")

    dashes = len(re.findall(r"[—–]", body_prose))
    if dashes:
        warn("dash", f"em/en dash x{dashes}")

    return findings


def analyze(markdown, **kwargs):
    """Run every deterministic check. Returns list of {"level", "check", "detail"}
    with structural errors first, then advisory prose findings."""
    findings = structure_findings(markdown, **kwargs)
    _, body = split_frontmatter(markdown)
    for f in slop_findings(body):
        findings.append({"level": "warn", "check": "slop", "detail": f})
    return findings


def errors(findings):
    return [f for f in findings if f["level"] == "error"]


def warnings(findings):
    return [f for f in findings if f["level"] == "warn"]
