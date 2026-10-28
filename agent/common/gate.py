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
  * spelling convention  - British -ise where the author writes -ize (00f126c)

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

# Three consecutive very short sentences on ONE line: "Start small. Ship fast. Iterate."
# Same-line only ([ \t] not \s): spanning paragraphs matched unrelated sentences. None of
# the author's 18 pre-agent posts contains one; 41% of agent-era posts do — it is an
# agent tell, reported from the first occurrence.
# Tokens may be grouped numbers ("1,000"): the model-decision post opened "Same model.
# Same 1,000 requests. Same 150 possible answers." and the comma hid it (1b54389).
_R3_TOKEN = r"[\w'’-]+(?:,\d{3})*"
_R3_FIRST = r"[A-Z][\w'’-]*(?:,\d{3})*"  # a sentence may open on one letter ("I", "A")
RULE_OF_THREE_RE = re.compile(rf"(?:\b{_R3_FIRST}(?:[ \t]+{_R3_TOKEN}){{0,3}}[.!][ \t]+){{2}}{_R3_FIRST}(?:[ \t]+{_R3_TOKEN}){{0,3}}[.!]")

# "Neither model changed. The question did." used as a repeated beat (1b54389 had two
# besides the title). Zero hits in the author's 18 pre-agent posts and in every other
# published post.
DID_BEAT_RE = re.compile(
    r"(?:\b(?:no|neither|nothing)\b[^.!?\n]{0,40}\bchanged|\b(?:didn['’]t|did not|doesn['’]t|does not) change)\.\s+[^.!?\n]{1,60}?\bdid\b",
    re.IGNORECASE,
)

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
# No -or/-our rule: "behavior" appears 48 times across the author's own posts, so it is
# their convention, not a slip. Only the -ise -> -ize correction is evidenced (00f126c).


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
    if not_but >= 2:  # 43 of 52 posts have none; the author scrubbed a post at 2 (f313e2f)
        findings.append(f'"not X, but Y" contrast x{not_but} (stacked contrasts read as generated)')

    triplets = RULE_OF_THREE_RE.findall(prose_text)
    if triplets:
        findings.append(f"rule-of-three fragments x{len(triplets)}: {triplets[0].strip()[:60]}")

    part_that = len(re.findall(r"\bthe part that\b", lower))
    if part_that >= 2:  # 49 of 52 posts have none
        findings.append(f'"the part that..." formula x{part_that}')
    this_part = len(re.findall(r"\b(?:this|that) is the part\b", lower))
    if this_part >= 2:  # none of the 55 published posts after 1b54389's fix
        findings.append(f'"This is the part..." opener x{this_part}')
    did_beats = len(DID_BEAT_RE.findall(prose_text))
    if did_beats >= 2:
        findings.append(f'"X didn\'t change. Y did." beat x{did_beats}')
    heres = len(re.findall(r"(?:^|[.!?]\s+)here['’]s the\b", lower))
    if heres >= 2:
        findings.append(f'"Here\'s the ..." sentence opener x{heres}')

    # Italic closing line. 17 of the author's 18 pre-agent posts end in plain prose (the
    # one exception is a single beat); 26 of 34 agent-era posts end on an italic line,
    # 13 of them three-beat slogans. The structure audit used to mandate it. Any italic
    # closer is reported; the slogan shape is named so the reviewer sees the worse case.
    last = next((ln.strip() for ln in reversed(body.splitlines()) if ln.strip()), "")
    m = _ITALIC_LINE_RE.match(last)
    if m:
        inner = m.group(2)
        beats = len(re.findall(r"[.!?](?:\s|$)", inner))
        if beats >= 2:
            findings.append(f"aphoristic italic closer with {beats} beats: {inner[:80]}")
        else:
            findings.append(f"italic one-line closer (author's pre-agent posts end in plain prose): {inner[:80]}")

    ise = sorted({w.lower() for w in _ISE_RE.findall(body)})
    if ise:
        findings.append(f"British -ise spelling (author uses Canadian -ize): {', '.join(ise[:6])}")

    return findings


# ---------------------------------------------------------------------------
# Document-level structural checks
# ---------------------------------------------------------------------------

_PREAMBLE_RE = re.compile(
    r"^(?:here(?:'s| is| are)\b|below is\b|sure[,!]|certainly[,!]|i(?:'ve| have) (?:annotated|polished|revised|updated)\b|the (?:revised|polished|updated) (?:draft|post)\b)",
    re.IGNORECASE,
)
REVIEW_ANNOTATION_RE = re.compile(
    r"<!--\s*(?:[^\w\s<>-]+\s*)?(?:CITATION\s+(?:FAIL|WARN|NOTE|REPLACED)|INSIGHT|ENTITY\s+CHECK|STRUCTURE|VOICE)\b",
    re.IGNORECASE,
)
# Anchored to the line start: prose that mentions the syntax in backticks must not match.
PLACEHOLDER_RE = re.compile(r"^\s*<!--\s*(?:CHART|DIAGRAM):", re.MULTILINE)

# Review notes a revision pass appended after the closing paragraph as ordinary
# headings (df7a2c6: "## Change Log", "## Citation Audit", "## Remaining Blockers"
# went live). They are Markdown, not comments, so REVIEW_ANNOTATION_RE never saw them.
# scripts/check-render-shape.mjs carries the same list; agent/tests/test_gate_rules.py
# keeps the two identical.
APPENDIX_HEADINGS = (
    "change log", "changelog", "citation audit", "remaining blockers", "revision notes",
    "revision summary", "changes made", "review notes", "reviewer notes",
)
APPENDIX_RE = re.compile(
    r"^#{1,4}\s*(?:\d+[.)]\s*)?(?:" + "|".join(re.escape(h).replace(r"\ ", r"\s+") for h in APPENDIX_HEADINGS) + r")\b",
    re.IGNORECASE | re.MULTILINE,
)

# Prose a fact-check or repair pass writes in place of a claim it could not source
# (a94987b: "remain unconfirmed pending verification of the source URL"). None of the
# 55 published posts contains any of these; a reader should never see one.
HEDGE_PHRASES = (
    "pending verification", "unverified pending", "unconfirmed pending", "remain unconfirmed",
    "remains unconfirmed", "could not be verified against", "cannot be independently verified",
    "not been independently verified",
)
HEDGE_RE = re.compile("|".join(re.escape(h) for h in HEDGE_PHRASES), re.IGNORECASE)

# Raw HTML that executes or embeds in the reader's browser. Astro renders raw HTML in
# Markdown as-is, so a <script> a model (or a spoofed email in preserve mode) wrote into
# the body would ship to the live site. None of the 55 published posts uses any of these
# outside code. scripts/check-render-shape.mjs runs the same tag list over the built
# post body; agent/tests/test_gate_rules.py keeps the two identical.
RAW_HTML_TAGS = ("script", "iframe", "form", "object", "embed")
RAW_HTML_TAG_RE = re.compile(r"<\s*(" + "|".join(RAW_HTML_TAGS) + r")\b", re.IGNORECASE)
# An on*= attribute inside a tag (onclick, onerror, onload, ...), not prose like "on = ".
EVENT_HANDLER_RE = re.compile(r"<[a-zA-Z][^>]*?\s(on[a-z]+)\s*=", re.IGNORECASE)
# javascript: as a link target: Markdown link/autolink/reference definition or an attribute.
JS_URL_RE = re.compile(r"""(?:\]\(\s*<?|\]:\s*<?|<|=\s*["']?)\s*javascript\s*:""", re.IGNORECASE)

# The private voice profile and the Draft prompt's own section markers. A post that
# contains these echoed its prompt (draft/index.py frames the guide as
# "VOICE & STYLE GUIDE" and the thinking pass as "WRITING PLAN"). Upper case only for
# the two markers, and the S3 key only outside inline code: published posts describe
# the "writing plan" and cite `config/voice-profile.md` by name.
PROMPT_LEAK_MARKERS = ("VOICE & STYLE GUIDE", "WRITING PLAN")
PROMPT_LEAK_RE = re.compile("|".join(re.escape(m) for m in PROMPT_LEAK_MARKERS))
VOICE_PROFILE_KEY_RE = re.compile(r"config/voice-profile\.md")
VOICE_PROFILE_HEADING_RE = re.compile(r"^#{1,6}\s.*\bvoice\s+(?:(?:&|and)\s+style\s+)?(?:profile|guide)\b", re.IGNORECASE | re.MULTILINE)

_INLINE_CODE_RE = re.compile(r"(`+)(?!`).*?(?<!`)\1")


def _strip_inline_code(text):
    """Prose with HTML comments and `inline code` removed: code spans render escaped."""
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    return "\n".join(_INLINE_CODE_RE.sub(" ", ln) for ln in text.splitlines())


def raw_html_findings(body_prose):
    """Names of the raw-HTML hazards in prose (outside fenced and inline code)."""
    text = _strip_inline_code(body_prose)
    hits = {f"<{m.lower()}>" for m in RAW_HTML_TAG_RE.findall(text)}
    hits |= {f"{m.lower()}=" for m in EVENT_HANDLER_RE.findall(text)}
    if JS_URL_RE.search(text):
        hits.add("javascript: URL")
    return sorted(hits)


def prompt_leak_findings(body_prose):
    text = _strip_inline_code(body_prose)
    hits = set(PROMPT_LEAK_RE.findall(text))
    if VOICE_PROFILE_KEY_RE.search(text):
        hits.add("config/voice-profile.md")
    hits |= {"voice profile heading" for _ in VOICE_PROFILE_HEADING_RE.findall(text)}
    return sorted(hits)


def structure_findings(markdown, *, min_headings=2, min_words=600, max_words=4500, published=False):
    """Rendering/structure integrity. Returns list of {"level", "check", "detail"}.

    ``published=True`` is the edge-check mode (CI over src/content/blog): review
    annotations and unrendered chart placeholders are errors there, because nothing
    downstream will strip or render them. In the pipeline they are expected."""
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

    # An LLM meta line published as the opening of the article ("Here is the blog post
    # draft with the weak paragraphs annotated:") — the agent-identity post shipped this.
    first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
    if first and not first.startswith(("#", "!", "<", "|", "-", "*", "`", "[")) and _PREAMBLE_RE.match(first):
        err("llm_preamble", f"body opens with an LLM meta line: {first[:80]}")

    review = len(REVIEW_ANNOTATION_RE.findall(body))
    if review:
        (err if published else warn)("review_annotations", f"{review} review annotation(s) present")
    placeholders = len(PLACEHOLDER_RE.findall(body_prose))
    if placeholders and published:
        err("unrendered_placeholders", f"{placeholders} CHART/DIAGRAM placeholder(s) never rendered")

    ratio = _fence_wrap_ratio(body)
    if ratio >= 0.5:
        err("body_fenced", f"a code fence opened at the top of the body encloses {int(ratio * 100)}% of it; the article will render as one code block")

    words = len(re.sub(r"<!--.*?-->", "", body_prose, flags=re.DOTALL).split())
    headings = len(re.findall(r"^#{2,3}\s+\S", body_prose, re.MULTILINE))
    if headings < min_headings:
        # Short personal posts legitimately have no sections (3 of 52 real posts);
        # an article-length draft with none is a stub or a fenced body.
        (err if words >= 800 else warn)("headings_low", f"{headings} section headings (minimum {min_headings})")

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

    appendix = APPENDIX_RE.findall(body_prose)
    if appendix:
        names = sorted({a.strip("# ").lower() for a in appendix})
        err("review_appendix", "review notes published as sections: " + ", ".join(names))

    hedges = sorted({h.lower() for h in HEDGE_RE.findall(body_prose)})
    if hedges:
        # Error in both modes: Publish does not run the gate, so a draft that passed
        # Notify with this would fail check:render in CodeBuild and hold every deploy.
        err("hedge_placeholder", f"placeholder hedging in prose: {', '.join(hedges)}")

    # Errors in both modes: nothing downstream strips raw HTML, and check:render fails
    # the deploy on the same tags in the built post body.
    raw_html = raw_html_findings(body_prose)
    if raw_html:
        err("raw_html", "executable or embedded HTML in the body: " + ", ".join(raw_html))

    leaks = prompt_leak_findings(body_prose)
    if leaks:
        err("prompt_leak", "the private voice profile or writing plan leaked into the body: " + ", ".join(leaks))

    # The layout renders the frontmatter title as the page <h1>; Draft drops a body H1
    # that repeats the title, but any other body H1 still yields two (2992112). An error
    # in both modes for the same reason as hedge_placeholder.
    body_h1 = len(re.findall(r"^#\s+\S", body_prose, re.MULTILINE))
    if body_h1:
        err("body_h1", f"{body_h1} '# ' heading(s) in the body; the layout already renders the title as <h1>")

    # Meta and OG tags. Warn, not error: four posts published before this check carry
    # an em dash in their description.
    for key in ("title", "description"):
        m = re.search(rf"^{key}:\s*(.*)$", fm, re.MULTILINE)
        if m and re.search(r"[—–]", m.group(1)):
            warn("meta_dash", f"em/en dash in frontmatter {key}")

    # 24 of the 25 posts with a TL;DR open with it; the model-decision post shipped one
    # 28% of the way down (281c2a0).
    tldr = re.search(r"tl;\s?dr", body_prose, re.IGNORECASE)
    if tldr and len(body_prose) > 0 and tldr.start() / len(body_prose) > 0.10:
        warn("tldr_late", f"TL;DR starts {round(100 * tldr.start() / len(body_prose))}% into the post; move it to the top")

    # Figures drawn as text in a code block: arrows and box-drawing flows, or #### bar
    # charts. b702217 replaced seven of these with SVGs. A block tagged with a real
    # language, or made of file paths (a directory tree), is code, not a figure.
    ascii_blocks = [lang for lang, block in _CODE_BLOCK_RE.findall(body) if _is_ascii_figure(lang, block)]
    if ascii_blocks:
        warn("ascii_figure", f"{len(ascii_blocks)} code block(s) draw a figure in text; render a diagram instead")

    # A long post with no figure at all. b7b1918 added two diagrams to a 2,400-word post
    # that shipped with none. Placeholders count: the Chart step renders them later.
    prose_words = len(re.findall(r"\b\w+\b", body_prose))
    figures = len(re.findall(r"!\[|<!--\s*(?:CHART|DIAGRAM):|^```mermaid|<svg\b", body, re.MULTILINE))
    if prose_words >= 2000 and not figures:
        warn("no_figures", f"{prose_words}-word post with no figure; add a diagram for the core argument")

    # The employer as an unnamed authority ("the platform I'm building", "a colleague on
    # my team"). 4f84b26 and 6cb5563 softened both; the author's own posts never use them.
    employer = _EMPLOYER_RE.findall(body_prose)
    if employer:
        warn("employer_reference", f"employer-as-authority phrasing ({', '.join(sorted({e.lower() for e in employer}))})")

    return findings


_CODE_BLOCK_RE = re.compile(r"^```([^\n]*)\n(.*?)^```", re.MULTILINE | re.DOTALL)
_DRAWING_RE = re.compile(r"[\u2500-\u259f\u25b2-\u25c4\u2190-\u21ff]|\+-{2,}|-{3,}>|#{3,}\s+[$\d]")
_PATH_RE = re.compile(r"[\w-]+\.(?:md|mdx|py|js|mjs|ts|astro|json|ya?ml|html|css|svg|sh)\b|/\s*$")
_EMPLOYER_RE = re.compile(r"\b(?:on my team|my team|the platform I'?m building)\b", re.IGNORECASE)


def _is_ascii_figure(lang, block):
    if lang.strip().lower() not in ("", "text", "txt", "plain", "plaintext", "ascii"):
        return False
    lines = [ln for ln in block.splitlines() if ln.strip()]
    if len(lines) < 3:
        return False
    drawn = sum(1 for ln in lines if _DRAWING_RE.search(ln) or re.fullmatch(r"\s*[|v^]\s*", ln))
    paths = sum(1 for ln in lines if _PATH_RE.search(ln))
    return drawn / len(lines) >= 0.3 and paths / len(lines) < 0.3


_HEADING_RE = re.compile(r"^#{2,3}\s+\S", re.MULTILINE)
_URL_RE = re.compile(r"\]\((https?://[^)\s]+)\)")


def guard_rewrite(before, after, *, min_ratio=0.85, max_ratio=1.15, heading_delta=(0, 0), max_url_loss_frac=0.0,
                  allow_added_urls=False):
    """Shape invariants for any pass that regenerates a whole post (the audit chain in
    Draft, the repair pass in Evaluate). Returns (text_to_keep, reason): ``after`` with
    reason None when it preserves ``before``'s shape, else ``before`` with the reason.

    Invariants: chart/diagram placeholders preserved; word count within
    [min_ratio, max_ratio] of the original; ## / ### heading count changes only within
    ``heading_delta`` (lo, hi); at most ``max_url_loss_frac`` of the original citation
    URLs may disappear and no new URL may appear (Verify does not run again); no placeholder hedging (HEDGE_PHRASES) or review-notes
    heading (APPENDIX_HEADINGS) that ``before`` did not already contain. Those two are
    how a repair pass wrote "unconfirmed pending verification" into a post (a94987b)
    and how a revision appended its change log (df7a2c6)."""
    reasons = []
    for label, rx in (("placeholder hedging", HEDGE_RE), ("review-notes heading", APPENDIX_RE)):
        b, a = len(rx.findall(before)), len(rx.findall(after))
        if a > b:
            reasons.append(f"{label} added {b} -> {a}")
    for label, rx in (("chart", r"<!--\s*CHART:"), ("diagram", r"<!--\s*DIAGRAM:")):
        b, a = len(re.findall(rx, before)), len(re.findall(rx, after))
        if b and a < b:
            reasons.append(f"{label} placeholders {b} -> {a}")
    wb, wa = len(before.split()), len(after.split())
    if wb and not (min_ratio <= wa / wb <= max_ratio):
        reasons.append(f"words {wb} -> {wa}")
    hb, ha = len(_HEADING_RE.findall(before)), len(_HEADING_RE.findall(after))
    if not (heading_delta[0] <= ha - hb <= heading_delta[1]):
        reasons.append(f"headings {hb} -> {ha}")
    ub, ua = set(_URL_RE.findall(before)), set(_URL_RE.findall(after))
    lost = ub - ua
    if ub and len(lost) > max_url_loss_frac * len(ub):
        reasons.append(f"citations lost {len(lost)}/{len(ub)}")
    # Verify has already run when Evaluate repairs, so a link the rewrite adds would
    # reach the reviewer unchecked. Any new URL rejects the rewrite.
    added = ua - ub
    if added and not allow_added_urls:
        reasons.append(f"citations added {len(added)} (unverified: {sorted(added)[0][:80]})")
    if reasons:
        return before, "; ".join(reasons)
    return after, None


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
