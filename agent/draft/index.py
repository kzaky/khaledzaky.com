"""
Draft Lambda — Uses Amazon Bedrock (Claude) to write a blog post in Markdown
based on the author's content and research notes. The author's draft/bullets/ideas
are the skeleton; the AI polishes, structures, and enriches — never replaces.

LLM passes (in order):
  Pass 1 — Sonnet + extended thinking (_thinking_plan): produces a drafting or revision plan.
  Pass 2 — Opus 4.7 (_invoke_model, DRAFT_MODEL_ID): full draft generation, plan injected.
  Pass 3 — Sonnet (_invoke_model): chart placeholder insertion — editorial judgment on what's worth visualising.
  Pass 4 — Sonnet (_invoke_model): diagram placeholder insertion — chooses type and placement.
  Pass 5 — Sonnet 8192 tokens (_audit_citations): verifies every link maps to a research source.
             Rewrites the full draft with corrections. Never truncates (8192 token budget).
  Pass 6 — Sonnet 8192 tokens (_audit_voice_profile): enforces voice/style rules from voice-profile.md.
             Always rewrites the draft with fixes applied, regardless of post length.
             No annotation-only mode. Never skips.
  Pass 7 — Sonnet (_audit_structure): checks TL;DR, headings, Next Steps, closing italic.
             Auto-inserts missing structural elements. Needs Sonnet quality for generated content.
  Pass 8 — Sonnet (_audit_named_entities): flags unverifiable regulation/version references
             with ENTITY CHECK annotations for human review. Skipped in revision mode.
  Pass 9 — Sonnet 8192 tokens (_audit_insight): flags generic paragraphs with <!-- ⚡ INSIGHT: --> annotations.
             Runs on all posts regardless of length. Skipped in revision mode.

Haiku reserved for: _infer_categories only (64-token structured label pick — genuinely mechanical).

All annotation comments (CITATION FAIL, CITATION NOTE, INSIGHT, ENTITY CHECK, STRUCTURE)
are stripped by Publish Lambda before committing to GitHub.

The voice profile is loaded from S3 at runtime and injected into every Draft prompt.
"""

import json
import logging
import os
import re
from datetime import UTC, datetime

import boto3
from botocore.config import Config

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_BEDROCK_CONFIG = Config(read_timeout=240, connect_timeout=10, retries={"max_attempts": 3})
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"), config=_BEDROCK_CONFIG)
s3 = boto3.client("s3")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
DRAFT_MODEL_ID = os.environ.get("DRAFT_MODEL_ID", "us.anthropic.claude-opus-4-7")
HAIKU_MODEL_ID = os.environ.get("HAIKU_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
THINKING_BUDGET = int(os.environ.get("THINKING_BUDGET_TOKENS", "2000"))  # default 2000 for local dev; CFN sets 8000 via ThinkingBudgetTokens parameter
DRAFTS_BUCKET = os.environ.get("DRAFTS_BUCKET", "")

SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://khaledzaky.com")
KNOWN_SLUGS_PARAM = os.environ.get("KNOWN_SLUGS_PARAM", "/blog-agent/known-post-slugs")

# Canonical category taxonomy. "tech" is intentionally absent — it's too broad to be useful.
_CATEGORY_TAXONOMY = {
    "ai": "Artificial intelligence, LLMs, machine learning, AI agents, models, Bedrock, Claude, inference",
    "cloud": "AWS, cloud infrastructure, serverless, distributed systems, CDN, S3, Lambda, architecture",
    "security": "Security hardening, pen testing, threat modelling, access control, vulnerabilities",
    "identity": "Authentication, authorization, identity delegation, OIDC, OAuth, IETF, trust chains",
    "devops": "CI/CD, deployment automation, SRE, build systems, pipelines, observability tooling",
    "platform-engineering": "Platform teams, developer experience, internal platforms, agent platforms, governance as code",
    "leadership": "Engineering strategy, org design, team building, decision-making, governance frameworks",
}

# Known post slugs — injected into prompts to prevent the model from fabricating internal links.
# At cold start we try SSM first (kept current by Publish Lambda); fall back to hardcoded list.
_HARDCODED_SLUGS = [
    "why-agentic-ai-needs-a-platform-mindset",
    "agents-are-not-software",
    "the-conversation-after-agentic-ai-needs-a-platform-mindset",
    "governing-autonomous-agents-is-a-platform-problem",
    "the-ietf-is-now-working-on-agent-authentication-here-is-what-that-means",
    "i-built-an-ai-agent-that-writes-for-my-blog",
    "upgrading-the-blog-agent-sonnet-4-6-and-real-citations",
    "weekend-engineering-smarter-ai-pipeline-alarms-and-upgrading-to-claude-sonnet-46-with-extended-thinking",
    "teaching-the-blog-agent-to-see-conceptual-diagrams-and-visual-thinking",
    "why-platform-engineers-should-care-about-identity-systems",
    "agentic-ai-in-financial-services",
    "pen-testing-my-own-infrastructure",
    "a-sunday-well-spent-hardening-my-cloud-infrastructure",
    "operational-excellence-ten-dives-into-a-production-personal-site",
    "migrating-from-jekyll-to-astro",
    "my-website-is-now-serverless",
    "multiple-mfa-devices-in-aws-iam",
    "challenges-with-mfa-adoption",
    "4-months-with-amazon-web-services",
    "digital-signage-solution-with-raspberry-pi",
    "learn-from-a-real-product-manager-at-brainstation",
    "understanding-blockchain",
    "what-is-bitcoin",
    "what-is-ethereum",
    "how-can-i-get-bitcoin",
    "buying-bitcoin-in-canada",
    "coinbase-shutting-down-bitcoin-trading",
    "top-10-cryptos",
    "what-is-cloud",
    "from-governance-is-a-platform-problem-to-governance-is-infrastructure",
]


def _load_known_slugs():
    """Load known post slugs from SSM, falling back to hardcoded list."""
    try:
        ssm_client = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        resp = ssm_client.get_parameter(Name=KNOWN_SLUGS_PARAM)
        slugs = [s.strip() for s in resp["Parameter"]["Value"].split(",") if s.strip()]
        if slugs:
            logger.info("Loaded %d known slugs from SSM", len(slugs))
            return slugs
    except Exception:
        pass
    logger.info("Using hardcoded slug list (%d slugs)", len(_HARDCODED_SLUGS))
    return list(_HARDCODED_SLUGS)


# Load at cold start — refreshed each Lambda container lifetime
KNOWN_POST_SLUGS = _load_known_slugs()


def _build_site_context():
    """Build a site context block injected into every draft prompt.
    Tells the model the real base URL and every existing post slug so it
    never fabricates internal links."""
    slugs_formatted = "\n".join(f"  - {SITE_BASE_URL}/blog/{s}/" for s in KNOWN_POST_SLUGS if s)
    return f"""=== SITE CONTEXT ===
This post will be published at: {SITE_BASE_URL}/blog/[slug]/
The author's site is khaledzaky.com — NOT kzaky.com, NOT kzaky.tech, NOT any other domain.

Existing posts you MAY link to (these URLs are real and verified):
{slugs_formatted}

INTERNAL LINK RULES (CRITICAL):
- If you reference a previous post, you MUST use one of the exact URLs listed above.
- NEVER construct a khaledzaky.com URL that is not in the list above — if unsure, link to {SITE_BASE_URL}/blog/ instead.
- NEVER invent slug variations like /governance-is-a-platform-problem if it is not in the list.
=== END SITE CONTEXT ==="""


# Voice profile loaded from S3 with TTL (re-read every 50 invocations)
_voice_profile_cache = None
_voice_profile_invocations = 0
_voice_profile_error_until = 0
_VOICE_PROFILE_TTL = 50
_VOICE_PROFILE_ERROR_BACKOFF = 10


def _thinking_plan(topic, author_content, is_revision=False, feedback="", research="", voice_profile="", goal="", avoid="", analogies=""):
    """Pass 1: short converse+thinking call to produce a drafting plan.
    Fits within the 4096 maxTokens cross-region profile cap.
    Returns a concise plan string to inject into the main generation prompt."""
    voice_rules = ""
    if voice_profile:
        # Extract just the key constraints from the voice profile to keep tokens low
        lines = [ln.strip() for ln in voice_profile.splitlines() if ln.strip()]
        voice_rules = "\n".join(lines[:40])  # include core rules + vocabulary preferences

    if is_revision:
        think_prompt = f"""You are planning a revision of a technical blog post by Khaled Zaky.

Topic: {topic[:300]}
Reviewer feedback: {feedback[:600]}

Key voice rules (abide by these in your plan):
{voice_rules}

Think carefully, then output a concise revision plan (max 300 words):
1. The most important changes to make — be specific about which sections
2. What to preserve verbatim (author's opinions, anecdotes, concrete details)
3. Any structural changes needed (reorder, split, merge sections)
4. Which citations need fixing vs. which are fine
5. Tone adjustments — flag any generic filler that crept into the original"""
        if goal:
            think_prompt += f"\n\nPost goal (reader takeaway): {goal[:300]}"
        if avoid:
            think_prompt += f"\nAvoid in this revision: {avoid[:200]}"
    else:
        research_excerpt = research[:800] if research else "None provided"
        think_prompt = f"""You are planning a technical blog post by Khaled Zaky.

Topic: {topic[:300]}
Author notes (excerpt): {author_content[:600] if author_content else 'None provided'}
Research summary (excerpt): {research_excerpt}

Key voice rules (abide by these in your plan):
{voice_rules}

Think carefully, then output a concise writing plan (max 300 words):
1. Best post structure — specific section titles and their purpose
2. Which author points are strongest and must lead each section
3. Where the research genuinely supports the author's argument (cite these) vs. where it conflicts (flag these — do NOT use conflicting research)
4. Claims in the author notes that have NO research backing — mark these as author opinion, not fact
5. The strongest concrete opening (avoid generic framing) and a quiet, confident closing
6. Any voice/tone traps to avoid given this specific topic"""
        if goal:
            think_prompt += f"\n\nPost goal (reader takeaway): {goal[:300]}"
        if avoid:
            think_prompt += f"\nAvoid in this post: {avoid[:200]}"
        if analogies:
            think_prompt += f"\nOptional analogies to consider: {analogies[:200]}"

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2500,
        "temperature": 1,
        "thinking": {"type": "enabled", "budget_tokens": THINKING_BUDGET},
        "messages": [{"role": "user", "content": think_prompt}],
    })
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(response["body"].read())
    text_parts = [
        block["text"]
        for block in result["content"]
        if block.get("type") == "text"
    ]
    return "\n".join(text_parts).strip()


def _invoke_model(prompt, temperature=0.8, max_tokens=8192, model_id=None):
    """Full generation via invoke_model. model_id defaults to MODEL_ID (Sonnet); pass DRAFT_MODEL_ID for the creative generation pass.
    Pass temperature=None to omit the parameter (required for Opus 4.7 which deprecated temperature)."""
    model_id = model_id or MODEL_ID
    body_dict = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if temperature is not None:
        body_dict["temperature"] = temperature
    body = json.dumps(body_dict)
    response = bedrock.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def _invoke_haiku(prompt, max_tokens=2048, temperature=0.0):
    """Deterministic structured passes via Haiku (fast, cheap, no quality loss)."""
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    })
    response = bedrock.invoke_model(
        modelId=HAIKU_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def _infer_categories(title, post_body, explicit_categories):
    """Infer 1-4 categories from post title and opening using Haiku.

    If the caller already supplied explicit categories (from the email directive or
    pipeline input), those are returned as-is — user intent takes precedence.
    Otherwise Haiku picks from _CATEGORY_TAXONOMY based on post content.
    Falls back to keyword heuristics if the model call fails.
    """
    if explicit_categories:
        return explicit_categories

    taxonomy_lines = "\n".join(f"  {k}: {v}" for k, v in _CATEGORY_TAXONOMY.items())
    snippet = post_body[:800].strip()

    prompt = f"""Tag this blog post for Khaled Zaky's technology blog.

Title: {title}
Opening:
{snippet}

Available categories (choose 1-4 that genuinely apply):
{taxonomy_lines}

Rules:
- Only use categories from the list above — no others
- "tech" is NOT a valid category
- Prefer specific over broad; most posts are about AI
- Only tag "cloud" if cloud infrastructure is a primary topic, not just mentioned
- Return ONLY a JSON array of strings, e.g. ["ai", "security"]

Categories:"""

    try:
        result = _invoke_haiku(prompt, max_tokens=64, temperature=0.0).strip()
        match = re.search(r'\[.*?\]', result, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            valid = [c for c in parsed if c in _CATEGORY_TAXONOMY]
            if valid:
                logger.info(json.dumps({"event": "categories_inferred", "categories": valid, "title": title[:80]}))
                return valid
    except Exception as exc:
        logger.warning(json.dumps({"event": "category_inference_failed", "error": str(exc)[:200]}))

    # Keyword fallback — better than defaulting to "tech"
    combined = (title + " " + post_body[:300]).lower()
    cats = []
    if any(w in combined for w in ["agent", "llm", "model", "bedrock", " ai ", "artificial", "claude", "inference"]):
        cats.append("ai")
    if any(w in combined for w in ["aws", "lambda", "s3", "cloud", "serverless", "infrastructure"]):
        cats.append("cloud")
    if any(w in combined for w in ["security", "hardening", "pen test", "vulnerab", "attack"]):
        cats.append("security")
    if any(w in combined for w in ["auth", "identity", "delegation", "oidc", "oauth", "trust chain"]):
        cats.append("identity")
    if any(w in combined for w in ["platform", "developer experience", "devex", "internal platform"]):
        cats.append("platform-engineering")
    if any(w in combined for w in ["leadership", "strategy", "governance", "org design", "team"]):
        cats.append("leadership")
    return cats if cats else ["ai"]


def _load_voice_profile():
    """Load voice profile from S3. Cached with TTL to pick up updates.
    On S3 error, backs off for 10 invocations before retrying."""
    global _voice_profile_cache, _voice_profile_invocations, _voice_profile_error_until
    _voice_profile_invocations += 1
    if _voice_profile_cache is not None and _voice_profile_invocations % _VOICE_PROFILE_TTL != 0:
        return _voice_profile_cache
    if _voice_profile_invocations < _voice_profile_error_until:
        return _voice_profile_cache or ""
    if not DRAFTS_BUCKET:
        return ""
    try:
        obj = s3.get_object(Bucket=DRAFTS_BUCKET, Key="config/voice-profile.md")
        _voice_profile_cache = obj["Body"].read().decode("utf-8")
        logger.info("Voice profile loaded from S3 (invocation #%d)", _voice_profile_invocations)
        return _voice_profile_cache
    except Exception as e:
        logger.warning("Could not load voice profile from S3: %s — backing off %d invocations", e, _VOICE_PROFILE_ERROR_BACKOFF)
        _voice_profile_error_until = _voice_profile_invocations + _VOICE_PROFILE_ERROR_BACKOFF
        return _voice_profile_cache or ""


def _strip_haiku_wrapper(text):
    """
    Strip leading HTML comment wrapper that Haiku occasionally injects around its output.
    Pattern: '<!--\n# BLOG POST DRAFT...' at the start, optionally closing with '\n-->'
    This would cause the entire post body to render as an HTML comment (empty page).
    """
    stripped = re.sub(r'^<!--\n#[^\n]*\n', '', text)
    if stripped != text:
        logger.warning("Stripped Haiku comment wrapper from output")
        stripped = re.sub(r'\n-->\s*$', '', stripped)
        return stripped.strip()
    return text


def _insert_chart_placeholders(post_body, research):
    """
    Second LLM pass: scan the draft for quantitative claims that have matching
    data in the research, and insert <!-- CHART: description --> placeholders.
    Only inserts placeholders if the research contains structured data points.
    """
    if "- Data point:" not in research:
        logger.info("No structured data points in research — skipping chart placeholder insertion")
        return post_body

    insertion_prompt = f"""You are an editorial assistant. Your ONLY job is to insert chart placeholders
into a blog post draft where quantitative data from the research supports a visual.

BLOG POST DRAFT:
{post_body}

RESEARCH DATA POINTS (look for "Data point:" entries):
{research}

Instructions:
1. Find places in the draft where a chart would strengthen the argument — ONLY for hard numeric data (percentages, dollar amounts, time comparisons, adoption rates, survey results)
2. For each match, insert a placeholder comment on its own line AFTER the relevant paragraph: <!-- CHART: [short description matching the data point] -->
3. Only insert a placeholder if there is a matching "Data point:" entry in the research with actual NUMERIC values in "Label: number" format
4. Do NOT insert placeholders for conceptual comparisons, qualitative differences, or feature tables — those are not charts
5. Insert at most 3 chart placeholders per post (less is better — only where it truly adds value)
6. Do NOT change any of the draft text. Do NOT add, remove, or rewrite any prose.
7. Output the COMPLETE draft with the placeholders inserted. Nothing else.

If the research data points do not contain clear numeric values, or the post is primarily conceptual/opinion-based, output the draft UNCHANGED — not every post needs a chart."""

    try:
        updated = _invoke_model(insertion_prompt, temperature=0.0, max_tokens=4096)
        updated = updated.strip()
        updated = _strip_haiku_wrapper(updated)

        # Sanity check: the updated draft should contain <!-- CHART and be roughly the same length
        chart_count = len(re.findall(r"<!--\s*CHART:", updated))
        if chart_count > 0:
            logger.info("Inserted %d chart placeholder(s) into draft", chart_count)
            return updated
        else:
            logger.info("No chart placeholders inserted — draft unchanged")
            return post_body

    except Exception as e:
        logger.warning("Chart placeholder insertion failed: %s", e)
        return post_body


def _insert_diagram_placeholders(post_body):
    """
    Third LLM pass: scan the draft for conceptual ideas that would benefit from
    a visual diagram (comparisons, progressions, layered stacks, Venn overlaps,
    convergence patterns). Outputs <!-- DIAGRAM: ... --> placeholders with
    structured specs that the Chart Lambda can render as SVG.

    This is separate from chart placeholders — diagrams are for conceptual
    visuals, charts are for numeric data.
    """
    insertion_prompt = f"""You are a visual editor for a technical blog. Your job is to identify
sections of a blog post where a CONCEPTUAL DIAGRAM would significantly strengthen the reader's
understanding, then insert structured diagram placeholders.

BLOG POST DRAFT:
{post_body}

DIAGRAM TYPES you can specify:
1. **architecture** — Conceptual system flow: inputs -> processing steps -> outputs (best for pipeline, platform, or system overviews)
   Format: <!-- DIAGRAM: architecture | Title | inputs: A;B | steps: S1;S2;S3;S4 | outputs: O1;O2;O3 | footer: optional infra note -->
   Example: <!-- DIAGRAM: architecture | Agent Platform Pipeline | inputs: User Request;Knowledge Base | steps: Planner;Tool Selector;Executor;Validator | outputs: Response;Audit Log;Trace | footer: All steps observed via OpenTelemetry -->

2. **comparison** — Two-column comparison (e.g., "Traditional vs Modern", "Before vs After")
   Format: <!-- DIAGRAM: comparison | Left Header | Right Header | Left1:Right1 | Left2:Right2 | ... -->
   Example: <!-- DIAGRAM: comparison | Traditional Software | AI Agents | Deterministic:Probabilistic | Request/Response:Autonomous Action | Static Permissions:Dynamic Authority -->

3. **progression** — Ascending stages/steps (e.g., maturity model, adoption curve)
   Format: <!-- DIAGRAM: progression | Title | Stage1 Name;Detail1;Detail2 | Stage2 Name;Detail1;Detail2 | ... -->
   Example: <!-- DIAGRAM: progression | Platform Maturity | Sandbox;Small experiments;Fast iteration | Guarded Pilots;Defined use cases;Basic logging | Reusable Platform;Shared controls;Self-service -->

4. **stack** — Layered horizontal bars (e.g., platform layers, architecture tiers)
   Format: <!-- DIAGRAM: stack | Title | Layer1 Name;Detail | Layer2 Name;Detail | ... -->
   Example: <!-- DIAGRAM: stack | Platform Primitives | Identity & Access;Scoped permissions | Tool Controls;Allowlists and policy | Observability;Input/output logging -->

5. **convergence** — Multiple items flowing into a central concept
   Format: <!-- DIAGRAM: convergence | Center Label | Item1;Detail | Item2;Detail | ... -->
   Example: <!-- DIAGRAM: convergence | Agent Platform | SPIFFE;Workload Identity | Cedar;Authorization | OpenTelemetry;Observability -->

6. **timeline** — Left-to-right sequence of milestones or stages (best for build journeys, feature rollouts, chronological narratives)
   Format: <!-- DIAGRAM: timeline | Title | Label;detail | Label;detail | ... -->
   Example: <!-- DIAGRAM: timeline | How We Built It | Design;Defined the spec | Prototype;First working version | Gaps found;SDK missing | Pivot;Rebuilt on mock layer | Production;Full pipeline live -->

7. **venn** — 2-3 overlapping circles showing relationships
   Format: <!-- DIAGRAM: venn | Title | Circle1 Label;trait1;trait2 | Circle2 Label;trait1;trait2 | Circle3 Label;trait1;trait2 -->
   Example: <!-- DIAGRAM: venn | Agent Identity | Human;Decisions;Accountability | Agent;Reasons like humans;Executes like machines | Machine;Deterministic;Static credentials -->

Instructions:
1. Read the draft and identify 1-3 places where a conceptual diagram would help readers grasp an idea faster
2. Choose the BEST diagram type for each concept — use **architecture** whenever the post describes a pipeline, platform, system flow, or multi-component technical build
3. Insert the placeholder on its own line AFTER the relevant paragraph
4. The placeholder MUST follow the exact format above with pipe-delimited fields
5. Only insert diagrams where they genuinely add value — NOT for simple lists or linear arguments
6. Good candidates for architecture: any post that walks through how a system is built, how data flows, or how components connect
7. Good candidates for other types: comparisons between two approaches, multi-stage models, layered architectures, converging trends, overlapping categories
8. Bad candidates: simple bullet lists, chronological narratives, single-concept explanations
9. Insert at most 3 diagram placeholders per post
10. Do NOT change any of the draft text. Do NOT add, remove, or rewrite any prose.
11. Output the COMPLETE draft with the placeholders inserted. Nothing else.

If the post does not contain concepts that benefit from a diagram, output the draft UNCHANGED."""

    try:
        updated = _invoke_model(insertion_prompt, temperature=0.0, max_tokens=4096)
        updated = updated.strip()
        updated = _strip_haiku_wrapper(updated)

        diagram_count = len(re.findall(r"<!--\s*DIAGRAM:", updated))
        if diagram_count > 0:
            logger.info("Inserted %d diagram placeholder(s) into draft", diagram_count)
            return updated
        else:
            logger.info("No diagram placeholders inserted — draft unchanged")
            return post_body

    except Exception as e:
        logger.warning("Diagram placeholder insertion failed: %s", e)
        return post_body


def _strip_md_formatting(text):
    """Strip markdown syntax from plain-text fields (e.g. frontmatter description).
    Unwraps bold/italic/code markers while preserving the inner text.
    Descriptions are used in meta/OG tags where raw markdown renders as literal characters."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)   # **bold** → bold
    text = re.sub(r'\*(.+?)\*', r'\1', text)         # *italic* → italic
    text = re.sub(r'__(.+?)__', r'\1', text)         # __bold__ → bold
    text = re.sub(r'_(.+?)_', r'\1', text)           # _italic_ → italic
    text = re.sub(r'`(.+?)`', r'\1', text)           # `code` → code
    text = re.sub(r'^#{1,6}\s*', '', text)           # leading headings
    text = re.sub(r'[*_`#]', '', text)               # any remaining stray markers
    return text.strip()


def _strip_footnotes(post_body):
    """
    Deterministic pre-pass: remove all markdown footnote syntax before the
    citation audit runs. Footnotes ([^N] references and [^N]: definitions)
    bypass the LLM citation audit entirely, and the model frequently invents
    plausible-but-fake URLs in footnote definitions.

    - [^1] inline references → stripped (the surrounding prose is kept)
    - [^1]: https://... definition lines → removed entirely
    """
    # Remove footnote definition lines ([^N]: ...) entirely
    cleaned = re.sub(r'\n\[\^[^\]]+\]:.*', '', post_body)
    # Remove inline footnote references ([^N]) — keep surrounding prose
    cleaned = re.sub(r'\[\^[^\]]+\]', '', cleaned)
    # Clean up any double blank lines left behind
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
    if cleaned != post_body:
        removed = len(re.findall(r'\[\^[^\]]+\]', post_body))
        logger.info("Stripped %d footnote reference(s)/definition(s) from draft", removed)
    return cleaned


def _audit_citations(post_body, research):
    """
    Fourth LLM pass: audit every inline citation in the draft.
    Checks that (1) the URL exists in the research sources, (2) the link text
    accurately describes what the source says, and (3) no claims from different
    sources are merged into a single link. Returns corrected draft.
    """
    audit_prompt = f"""You are a citation auditor for a technical blog post. Your ONLY job is to verify
that every inline markdown link in the draft correctly maps to a source from the research notes.

BLOG POST DRAFT:
{post_body}

RESEARCH SOURCES (look for "URL:" entries and "Verified:" confirmations):
{research}

FOOTNOTE CHECK (do this first):
- If the draft contains ANY footnote syntax ([^1], [^2], [^1]: url, etc.), REMOVE all of it:
  - Remove every [^N] inline reference from prose (keep the surrounding sentence)
  - Remove every [^N]: definition line entirely
  This is not negotiable — footnote citations are forbidden in this blog's format.

For EACH inline markdown link [text](url) in the draft, check:
1. Does the URL appear in the research sources? If not, REMOVE the link and keep the text as plain prose, or replace with a correct URL from the research if one supports the same claim.
2. Does the link text accurately describe what the source says? If the source says something different, fix the link text to match.
3. Is the claim in the surrounding sentence actually supported by this specific source? If the claim conflates two different sources, split into two separate links.
4. For regulatory citations (EU AI Act articles, NIST sections, RFC numbers), verify the article/section number matches the excerpt in the research. If you cannot confirm, add a comment: <!-- VERIFY: [url] - could not confirm article number -->
5. For arxiv papers, verify the paper ID appears in the research with a matching title/abstract. If not, REMOVE the link.
6. INTERNAL LINKS: For any link pointing to khaledzaky.com, verify the exact URL appears in this known-good list. If it does not, REMOVE the link entirely (keep the text as plain prose) — do NOT attempt to fix or guess the correct slug.
   Known valid khaledzaky.com URLs:
{chr(10).join(f'   - {SITE_BASE_URL}/blog/{s}/' for s in KNOWN_POST_SLUGS if s)}

Rules:
- Do NOT change any prose that is not directly related to fixing a citation
- Do NOT add new citations that are not in the research
- Do NOT remove citations that are correct
- If a URL is not in the research sources but the claim is the author's own opinion, remove the link and keep the text
- Output the COMPLETE draft with corrections. Nothing else.
- If all citations are correct, output the draft UNCHANGED.

After the draft, on a new line, output a summary line:
<!-- CITATION_AUDIT: X checked, Y fixed, Z removed -->"""

    try:
        updated = _invoke_model(audit_prompt, temperature=0.0, max_tokens=8192)
        updated = updated.strip()

        # Check if audit made changes
        audit_match = re.search(r"<!--\s*CITATION_AUDIT:.*?(\d+)\s*fixed.*?(\d+)\s*removed", updated)
        if audit_match:
            fixed = int(audit_match.group(1))
            removed = int(audit_match.group(2))
            if fixed > 0 or removed > 0:
                logger.info("Citation audit: %d fixed, %d removed", fixed, removed)
                # Strip the audit summary comment from the output
                updated = re.sub(r"\n*<!--\s*CITATION_AUDIT:.*?-->\s*$", "", updated).strip()
                return updated
            else:
                logger.info("Citation audit: all citations correct")
                return post_body
        else:
            # Accept output if it looks like a valid rewrite (may have corrected without summary)
            original_start = next((ln.strip() for ln in post_body.split("\n") if ln.strip()), "")
            if original_start and updated[:100].find(original_start[:30]) >= 0 and len(updated) >= len(post_body) * 0.8:
                logger.info("Citation audit: no summary found but output looks valid — accepting")
                updated = re.sub(r"\n*<!--\s*CITATION_AUDIT:.*?-->\s*$", "", updated).strip()
                return updated
            logger.info("Citation audit: no audit summary found — returning original")
            return post_body

    except Exception as e:
        logger.warning("Citation audit failed: %s", e)
        return post_body


def _audit_voice_profile(post_body, voice_profile):
    """
    Fifth LLM pass: audit the draft for voice profile compliance.
    Uses Sonnet at 8192 tokens so it can rewrite drafts of any length in one pass.
    Checks contractions, punctuation rules, paragraph length, opening/closing
    style, forbidden phrases, and formatting conventions.
    """
    if not voice_profile:
        return post_body

    word_count = len(post_body.split())
    logger.info("Voice audit: draft is %d words — rewriting with Sonnet", word_count)

    audit_prompt = f"""You are a voice profile auditor for a technical blog. Your ONLY job is to ensure
the draft strictly follows the voice and style guide below.

VOICE & STYLE GUIDE:
{voice_profile}

BLOG POST DRAFT:
{post_body}

Check and fix the following:
1. **Contractions:** The voice profile uses contractions naturally (don't, can't, it's, that's, I'm, I've, they're, we're, it's, doesn't, isn't, wasn't, weren't, haven't, hadn't, won't, wouldn't, couldn't, shouldn't). Fix any "do not", "cannot", "it is", "that is", "I am", "I have", "does not", "is not", "was not", "were not", "have not", "had not", "will not", "would not", "could not", "should not" to contractions where they appear in conversational prose. Do NOT change contractions inside formal definitions, quoted text, or inline code.
2. **Punctuation:** No em dashes or en dashes. Replace with commas, colons, or parentheses.
3. **Paragraph length:** No paragraph should exceed 4 lines. Split long paragraphs at natural sentence breaks.
4. **Forbidden phrases:** Remove or rephrase any instances of: "It is worth noting", "It goes without saying", "synergy", "leverage" (as verb), "paradigm shift", "perhaps", "maybe", "it could be argued", "In today's", "Stay tuned", "What do you think", "In this post I will", "delve into", "dive deep" (unless Amazon LP), "unpack", "game-changer", "revolutionary", "cutting-edge", "in conclusion", "to summarize", "without further ado", "let's explore", "let's take a look at".
5. **Closing style:** The last section should have actionable takeaways. The final sentence should be quiet and confident, optionally italicized.
6. **Opening style:** Must not start with a generic statement. Should start with TL;DR or personal context.
7. **Formatting:** Bold key terms on first mention. Inline code for technical terms, config values, CLI commands.
8. **Description frontmatter:** If the draft starts with frontmatter, ensure the description field is populated and is plain text (no markdown).

Rules:
- Make ONLY the minimum changes needed to comply with the voice profile
- Do NOT rewrite prose that already complies
- Do NOT change the author's arguments, opinions, or structure
- Do NOT add or remove sections
- Output the COMPLETE draft with corrections. Nothing else.
- If the draft already complies, output it UNCHANGED.

After the draft, on a new line, output a summary:
<!-- VOICE_AUDIT: X issues fixed -->"""

    try:
        updated = _invoke_model(audit_prompt, temperature=0.0, max_tokens=8192)
        updated = updated.strip()

        audit_match = re.search(r"<!--\s*VOICE_AUDIT:\s*(\d+)\s*issues?\s*fixed", updated)
        if audit_match:
            fixed = int(audit_match.group(1))
            if fixed > 0:
                logger.info("Voice audit: %d issues fixed", fixed)
                updated = re.sub(r"\n*<!--\s*VOICE_AUDIT:.*?-->\s*$", "", updated).strip()
                return updated
            else:
                logger.info("Voice audit: draft already compliant")
                return post_body
        else:
            # No summary line, but if the output looks like a valid post (starts similarly),
            # accept it — the model may have fixed issues without appending the summary
            original_start = next((ln.strip() for ln in post_body.split("\n") if ln.strip()), "")
            if original_start and updated[:100].find(original_start[:30]) >= 0 and len(updated) >= len(post_body) * 0.8:
                logger.info("Voice audit: no summary found but output looks valid — accepting")
                return updated
            logger.info("Voice audit: no summary found, output diverges — returning original")
            return post_body

    except Exception as e:
        logger.warning("Voice audit failed: %s", e)
        return post_body




def _audit_insight(post_body, research):
    """
    Seventh LLM pass: insight audit.
    Sonnet scans the draft for paragraphs that are generic, obvious, or lack editorial
    perspective. Annotates weak sections with specific, actionable improvement suggestions
    as HTML comments for human review. Strong drafts are returned unchanged.
    Uses 8192 token budget so no length limit — runs on all posts.
    Annotations are stripped by Publish Lambda before committing to GitHub.
    """
    word_count = len(post_body.split())
    if word_count < 300:
        return post_body

    research_snippet = research[:3000] if research else ""
    audit_prompt = f"""You are an editorial insight auditor for a technical blog. Your job is to identify
paragraphs that are generic, obvious, or lack a strong editorial perspective, and annotate them.

For each weak paragraph, insert an HTML comment IMMEDIATELY AFTER it (on a new line):
<!-- \u26a1 INSIGHT: [specific, actionable suggestion] -->

A paragraph is WEAK if it:
- States something any AI would write (e.g. "AI is transforming industries", "this is important")
- Makes a claim that research supports with specific data but the draft doesn't cite it
- Reads like a Wikipedia summary with no authorial POV
- Uses hedge phrases: "it's worth noting", "it's important to", "in today's world"

A paragraph is STRONG if it:
- Says something counter-intuitive or has a clear opinion
- Uses a specific data point, example, or comparison
- Would make an expert reader feel they learned something
- Has the author's voice -- agrees, disagrees, or adds nuance
- Draws from personal experience, real projects, or specific technical details

RULES:
- Only annotate paragraphs that are genuinely weak -- do not annotate strong paragraphs
- Your suggestion must be SPECIFIC: say what data point to add or what angle to take, not just "add more detail"
- Suggestions should preserve the author's voice — never suggest making prose more formal, academic, or generic
- Do NOT rewrite paragraphs -- only add the annotation comment after them
- If the draft is already strong throughout, output it UNCHANGED
- Frontmatter (the ---...--- block at the top) is exempt -- do not annotate it
- HTML comment placeholders `<!-- CHART: ... -->` and `<!-- DIAGRAM: ... -->` are exempt -- preserve them EXACTLY as-is, do not annotate or duplicate them
- Output the full draft with annotations inserted, nothing else

RESEARCH (for suggesting specific improvements):
{research_snippet}

DRAFT:
{post_body}"""

    try:
        updated = _invoke_model(audit_prompt, temperature=0.0, max_tokens=8192)
        updated = updated.strip()

        # Guard: Haiku sometimes prefixes its response with a task acknowledgment preamble
        # (e.g. "I'll audit this draft...") before the actual draft content.
        # Verify the response starts with the same content as the original by comparing
        # the first meaningful line. If they diverge, find and strip the preamble.
        original_first_line = next(
            (ln.strip() for ln in post_body.split("\n") if ln.strip()), ""
        )
        if original_first_line and not updated.startswith(original_first_line[:30]):
            idx = updated.find(original_first_line[:30])
            if 0 < idx < 600:
                logger.warning("Insight audit: stripping %d-char model preamble", idx)
                updated = updated[idx:]
            else:
                logger.warning("Insight audit: response diverges from original — returning original")
                return post_body

        annotation_count = updated.count("<!-- ⚡ INSIGHT:")
        if annotation_count > 0:
            logger.info("Insight audit: %d suggestions added", annotation_count)
        else:
            logger.info("Insight audit: draft already strong")
        return updated
    except Exception as e:
        logger.warning("Insight audit failed: %s", e)
        return post_body


def _audit_structure(post_body):
    """
    New Sonnet pass: structural completeness check.
    Verifies mandatory structural elements are present and auto-inserts any that are missing:
    TL;DR opening, ≥2 section headings, Next Steps closing section, closing italic line.
    Missing headings are flagged but not fabricated (content-specific — must be human-added).
    """
    prompt = f"""You are a structural editor for a technical blog. Check the blog post below for mandatory structural elements and add any that are missing.

MANDATORY STRUCTURAL ELEMENTS:
1. **TL;DR block** — The post MUST open with a bold `**TL;DR:**` line. If missing, insert one immediately before the first paragraph (after any `---` separator). It must be 1-2 sentences that accurately summarise the post's core argument — not generic.
2. **Section headings** — At least 2 `##` headings required. If fewer exist, insert: `<!-- ⚠️ STRUCTURE: Post needs section headings — add ## headings before publishing -->` at the top of the body but do NOT invent headings.
3. **Next Steps section** — The final section MUST be `## Next Steps` or `## Actionable Takeaways` with 3-5 actionable bullet points. If missing, add one at the end based on the post's actual advice.
4. **Closing italic line** — The post MUST end with at least one line in `*...*` italics. If missing, add a brief, confident closing sentence as an italic line at the very end.

RULES:
- Only ADD the missing elements. Do NOT change or rewrite any existing content.
- Preserve all HTML comments (`<!-- CHART: -->`, `<!-- DIAGRAM: -->`, `<!-- ⚡ INSIGHT: -->`) EXACTLY as-is.
- IMPORTANT: Output ONLY the complete post body followed by the STRUCTURE_AUDIT comment. Do NOT include any preamble, reasoning, audit summary, or explanation before the post body begins. Your output must start directly with the post content.
- End your output with: `<!-- STRUCTURE_AUDIT: [comma-separated list of what was added, or "all elements present"] -->`

POST BODY:
{post_body}"""

    try:
        result = _invoke_model(prompt, temperature=0.0, max_tokens=8192)
        result = result.strip()

        audit_match = re.search(r'<!--\s*STRUCTURE_AUDIT:\s*(.*?)\s*-->', result, re.DOTALL)
        if audit_match:
            summary = audit_match.group(1).strip()
            logger.info(json.dumps({"event": "structure_audit", "summary": summary[:200]}))
            result = re.sub(r'\n*<!--\s*STRUCTURE_AUDIT:.*?-->\s*$', '', result, flags=re.DOTALL).strip()

        # Strip any reasoning preamble the model may have prepended before the post body.
        # The post body must start with a known anchor: **TL;DR:, ## heading, or the first
        # substantive line of the original post_body. Anything before that is discarded.
        original_first = next((ln.strip() for ln in post_body.split("\n") if ln.strip()), "")
        anchors = [r'\*\*TL;DR:', r'^##\s', re.escape(original_first[:40]) if original_first else None]
        for anchor in anchors:
            if not anchor:
                continue
            m = re.search(anchor, result, re.MULTILINE)
            if m and m.start() > 10:  # preamble detected
                result = result[m.start():].strip()
                logger.warning(json.dumps({"event": "structure_audit", "summary": "stripped preamble before post body"}))
                break

        if audit_match:
            return result

        if original_first and result[:200].find(original_first[:30]) >= 0 and len(result) >= len(post_body) * 0.85:
            logger.info(json.dumps({"event": "structure_audit", "summary": "completed, no marker"}))
            return result
        logger.warning(json.dumps({"event": "structure_audit", "summary": "output diverges — returning original"}))
        return post_body
    except Exception as e:
        logger.warning("Structure audit failed: %s", e)
        return post_body


def _audit_named_entities(post_body, research):
    """
    New Sonnet pass: named entity verification.
    Extracts specific named entities that could be subtly wrong (regulation numbers,
    article sections, product versions, named studies) and flags any that can't be
    cross-referenced against the research notes with an ENTITY CHECK annotation
    for human review. Annotations are stripped by Publish Lambda before commit.
    Hyperlinked entities are treated as pre-verified and skipped.
    """
    if not research:
        return post_body

    research_snippet = research[:4000]
    prompt = f"""You are a fact-checking assistant for a technical blog.

TASK: Extract all specific named entities from the DRAFT that could be subtly wrong, then check each against the RESEARCH NOTES.

Entities to check:
- Regulation document identifiers (e.g. "SR 26-2", "E-23", "Article 14", "NIST SP 800-218")
- Product/model version numbers (e.g. "GPT-4o", "Kubernetes v1.30", "Sonnet 4.6")
- Named studies or reports (e.g. "Gartner 2025 AI survey", "Wang et al. survey on AgentOps")
- Specific percentages or statistics attributed to a named source

For each entity found:
- VERIFIED → it appears in the RESEARCH NOTES (even loosely matched): no annotation needed
- UNVERIFIED → it does NOT appear in the RESEARCH NOTES: insert this comment IMMEDIATELY after the sentence that contains it (on its own line):
  `<!-- 🔍 ENTITY CHECK: "[entity]" — not found in research, verify before publishing -->`

RULES:
- Skip entities that already have a markdown hyperlink `[text](url)` — they are pre-verified
- Skip entities that are clearly from the author's own direct experience ("I built", "we ran")
- Annotate each unverified entity at most once (first occurrence only)
- Do NOT rewrite any prose — only insert annotation comments
- If all entities are verified or hyperlinked, return the draft UNCHANGED
- Output the complete draft with any annotations inserted, nothing else

RESEARCH NOTES:
{research_snippet}

DRAFT:
{post_body}"""

    try:
        result = _invoke_model(prompt, temperature=0.0, max_tokens=8192)
        result = result.strip()

        original_start = next((ln.strip() for ln in post_body.split("\n") if ln.strip()), "")
        if original_start and not result.startswith(original_start[:30]):
            idx = result.find(original_start[:30])
            if 0 < idx < 600:
                logger.warning(json.dumps({"event": "entity_audit", "note": f"stripping {idx}-char preamble"}))
                result = result[idx:]
            else:
                logger.warning(json.dumps({"event": "entity_audit", "note": "output diverges — returning original"}))
                return post_body

        count = result.count("<!-- 🔍 ENTITY CHECK:")
        logger.info(json.dumps({"event": "entity_audit", "flagged": count}))
        return result
    except Exception as e:
        logger.warning("Entity audit failed: %s", e)
        return post_body


def handler(event, context):
    """
    Input event:
    {
        "topic": "...",
        "categories": ["cloud", "aws"],
        "research": "structured research notes markdown",
        "author_content": "the author's draft, bullets, ideas",
        "tone": "optional tone directive",
        "goal": "optional — what the reader should walk away understanding",
        "avoid": "optional — comma-separated things to avoid",
        "analogies": "optional — seed analogies to weave in",
        "suggested_title": "...",
        "suggested_description": "..."
    }

    Output:
    {
        "title": "...",
        "slug": "...",
        "categories": [...],
        "description": "...",
        "markdown": "complete markdown file content with frontmatter",
        "date": "YYYY-MM-DD"
    }
    """
    topic = event.get("topic", "")
    research = event.get("research", "")
    author_content = event.get("author_content", "")
    tone = event.get("tone", "")
    goal = event.get("goal", "")
    avoid = event.get("avoid", "")
    analogies = event.get("analogies", "")
    suggested_title = event.get("suggested_title", topic)
    suggested_description = event.get("suggested_description", "")
    categories = event.get("categories", [])
    previous_draft = event.get("previous_draft", "")
    feedback = event.get("feedback", "")

    if not research and not previous_draft and not author_content:
        raise ValueError("No research notes, author content, or previous draft provided")

    today = datetime.now(UTC).strftime("%Y-%m-%d")

    voice_profile = _load_voice_profile()
    voice_section = f"""
=== VOICE & STYLE GUIDE ===
{voice_profile}
=== END VOICE GUIDE ===
""" if voice_profile else ""

    has_author_content = bool(author_content and author_content.strip())

    request_id = getattr(context, 'aws_request_id', 'local')
    logger.info(json.dumps({"event": "draft_start", "topic": topic[:100], "has_author_content": has_author_content, "is_revision": bool(previous_draft and feedback), "request_id": request_id}))

    if previous_draft and feedback:
        # Revision mode — strip frontmatter before passing to the model (saves tokens, removes ambiguity)
        draft_body_for_revision = previous_draft
        if previous_draft.startswith("---"):
            end = previous_draft.find("---", 3)
            if end != -1:
                draft_body_for_revision = previous_draft[end + 3:].lstrip()

        # Revision mode — improve existing draft based on feedback
        prompt = f"""You are an editorial assistant for Khaled Zaky's personal technology blog.
Your job is to REVISE an existing draft based on the author's feedback while preserving
his voice, opinions, and personal insights.

{voice_section}

PREVIOUS DRAFT:
{draft_body_for_revision}

REVIEWER FEEDBACK:
{feedback}

RESEARCH NOTES (for additional context):
{research}

{f"TONE DIRECTIVE: {tone}" if tone else ""}
{f"POST GOAL (reader takeaway): {goal}" if goal else ""}
{f"AVOID IN THIS POST: {avoid}" if avoid else ""}

Revise the blog post based on the feedback. Keep what works, improve what was flagged.
Rules:
- Preserve the author's voice, opinions, and personal anecdotes — do NOT make them generic
- Keep concrete specifics (dollar amounts, service names, build times)
- Use the voice guide above for tone, sentence structure, and vocabulary
- Match the length of the previous draft — do NOT truncate. Output the COMPLETE revised post.
- If the feedback specifies exact text to insert or replace, copy it VERBATIM. Do not paraphrase, summarize, or reinterpret provided text.
- Use clear headings (## for main sections)
- Do NOT include the frontmatter — I will add that separately

CITATION RULES (CRITICAL):
- Every factual claim, statistic, or external reference MUST include an inline markdown link: [descriptive text](url)
- URLs come exclusively from the RESEARCH NOTES below. Each source entry looks like:
    Title: <title>
    URL: <url>          ← use this exact URL
    Verified: true/false
    Excerpt: ...
- If there is no URL in the research for a claim, write it as the author's own perspective with NO link
- NEVER fabricate a URL. NEVER invent a source name. NEVER write "according to a study" without a real link
- Named tools/frameworks/products should link to their official site on first mention — only if that URL appears in the research
- NEVER use footnote syntax ([^1], [^2], [^1]: url). ONLY inline links [text](url) are allowed.

{_build_site_context()}

Write the revised blog post body in Markdown. Do NOT include frontmatter (---) blocks.
Start directly with the content."""

    elif has_author_content:
        # Author-content mode — polish and structure the author's draft/bullets
        prompt = f"""You are a copy editor for Khaled Zaky's personal technology blog.
The author has written the content below. Your ONLY job is to edit it — not rewrite it.

{voice_section}

CITATION RULES (READ BEFORE ANYTHING ELSE — CRITICAL):
- Every factual claim, statistic, or external reference MUST have an inline markdown link: [descriptive text](url)
- URLs come exclusively from the RESEARCH & SUPPORTING DATA section below.
  Each source entry looks like:
    Title: <title>
    URL: <url>          ← use this exact URL
    Verified: true/false
    Excerpt: ...
- If there is no URL in the research for a claim, write it as the author's own perspective with NO link
- NEVER fabricate a URL. NEVER invent a source name. NEVER write "according to a study" without a real link
- Named tools/frameworks/products should link to their official site on first mention — but ONLY if that URL appears in the research
- NEVER use footnote syntax ([^1], [^2], [^1]: url). ONLY inline links [text](url) are allowed.

{_build_site_context()}

AUTHOR'S TOPIC: {topic}
{f"TONE DIRECTIVE: {tone}" if tone else ""}
{f"POST GOAL (reader takeaway): {goal}" if goal else ""}
{f"AVOID IN THIS POST: {avoid}" if avoid else ""}
{f"OPTIONAL ANALOGIES TO WEAVE IN: {analogies}" if analogies else ""}

AUTHOR'S CONTENT (this is the source of truth — every paragraph must originate here):
{author_content}

RESEARCH & SUPPORTING DATA (use only for citations and supporting evidence — do NOT use to replace author's framing):
{research}

Editing rules — follow in order:
1. **Preserve structure:** Keep the author's section order and paragraph intent. You may split an overly long paragraph but never merge or reorder.
2. **Edit prose, don't replace it:** Fix grammar, cut filler words, tighten sentences. If the author wrote it, keep his framing even if you'd phrase it differently. Preserve the author's distinctive phrases, metaphors, and sentence rhythms — these are what make the post authentic.
3. **Preserve the author's opinions and conclusions:** Never soften, hedge, or qualify the author's claims. If the author says "X is broken," don't change it to "X may need improvement." The author's directness is intentional.
4. **Add supporting evidence inline:** Where research directly supports an author claim, weave in a cited fact as one sentence. If research conflicts with the author's point, skip it — do NOT correct the author with external data.
5. **No filler additions:** Do NOT add transitional paragraphs, conclusions, or context the author didn't write. Every sentence must trace back to the author's content or a research citation.
6. **Length:** 800-2500 words. If the author's content is under 800 words, expand by adding cited evidence — not invented commentary.
7. **Formatting:** Bold key terms on first mention. Inline code for technical terms, config values, CLI commands.

Do NOT include frontmatter. Start directly with the content."""

    else:
        # Fallback: topic-only mode (no author content provided)
        prompt = f"""You are an editorial assistant for Khaled Zaky's personal technology blog.
Khaled is a Senior Director of Agentic AI Platform Engineering at RBC Borealis who writes
about platform engineering, cloud, identity/security, AI, and leadership.

{voice_section}

Write a complete blog post based on the following research notes. The post should sound like
Khaled wrote it himself — grounded in personal experience, technically specific, and practical.

Research Notes:
{research}

Suggested Title: {suggested_title}
Suggested Description: {suggested_description}
{f"Tone directive: {tone}" if tone else ""}
{f"Post goal (reader takeaway): {goal}" if goal else ""}
{f"Avoid in this post: {avoid}" if avoid else ""}
{f"Optional analogies to weave in: {analogies}" if analogies else ""}

Rules:
- Use the voice guide above for tone, sentence structure, and vocabulary
- Ground the post in first-person experience where possible
- Be 800-2500 words depending on the topic's depth
- Use clear headings (## for main sections)
- If the research includes quantitative data points suitable for charts, add a markdown
  comment where a chart would go: <!-- CHART: [description] -->
- Never start with "In today's..." or any generic opener
- Do NOT include the frontmatter — I will add that separately

CITATION RULES (CRITICAL):
- Every factual claim, statistic, or external reference MUST include an inline markdown link: [descriptive text](url)
- URLs come exclusively from the Research Notes below. Each source entry looks like:
    Title: <title>
    URL: <url>          ← use this exact URL
    Verified: true/false
    Excerpt: ...
- If there is no URL in the research for a claim, write it as the author's own perspective with NO link
- NEVER fabricate a URL. NEVER invent a source name. NEVER write "according to a study" without a real link
- Named tools/frameworks/products should link to their official site on first mention — only if that URL appears in the research
- NEVER use footnote syntax ([^1], [^2], [^1]: url). ONLY inline links [text](url) are allowed.

{_build_site_context()}

Write the blog post body in Markdown. Do NOT include frontmatter (---) blocks.
Start directly with the content."""

    is_revision = bool(previous_draft and feedback)
    try:
        plan = _thinking_plan(topic, author_content, is_revision=is_revision, feedback=feedback, research=research, voice_profile=voice_profile, goal=goal, avoid=avoid, analogies=analogies)
        logger.info(json.dumps({"event": "thinking_plan_generated", "chars": len(plan), "request_id": request_id}))
        prompt += f"\n\n=== WRITING PLAN (from extended thinking) ===\n{plan}\n=== END PLAN ==="
    except Exception as e:
        logger.warning(json.dumps({"event": "thinking_plan_failed", "error": str(e)[:200], "request_id": request_id}))

    try:
        post_body = _invoke_model(prompt, temperature=None, model_id=DRAFT_MODEL_ID)
        logger.info(json.dumps({"event": "draft_generated", "chars": len(post_body), "model": DRAFT_MODEL_ID, "request_id": request_id}))
    except Exception as e:
        logger.error(json.dumps({"event": "draft_failed", "error": str(e)[:200]}))
        raise RuntimeError(f"Draft generation failed: {e}") from e

    # --- Structural validation: ensure the draft has section headings ---
    heading_count = len(re.findall(r'^#{1,3}\s+', post_body, re.MULTILINE))
    word_count = len(post_body.split())
    if heading_count < 2 and word_count > 500:
        logger.warning(json.dumps({"event": "structural_warning", "headings": heading_count, "words": word_count, "request_id": request_id}))

    # --- Second pass: insert chart placeholders where data supports it ---
    post_body = _insert_chart_placeholders(post_body, research)

    # --- Third pass: insert conceptual diagram placeholders ---
    post_body = _insert_diagram_placeholders(post_body)

    # --- Fourth pass: strip footnotes (deterministic), then audit inline citations ---
    post_body = _strip_footnotes(post_body)
    post_body = _audit_citations(post_body, research)

    # --- Fifth pass: audit voice profile compliance ---
    post_body = _audit_voice_profile(post_body, voice_profile)

    # --- Sixth pass: structural completeness — TL;DR, headings, Next Steps, closing italic ---
    post_body = _audit_structure(post_body)

    # --- Seventh pass: named entity verification — flag unverifiable regulation/version references ---
    if not is_revision:
        post_body = _audit_named_entities(post_body, research)

    # --- Eighth pass: insight audit — annotate generic/weak paragraphs for human review ---
    # Skip in revision mode: the user is giving specific edits, not asking for new suggestions,
    # and re-running the audit would re-inject INSIGHT comments the user may have just asked to remove.
    if not is_revision:
        post_body = _audit_insight(post_body, research)

    # --- Frontmatter validation: ensure description is populated ---
    if not suggested_description or not suggested_description.strip():
        # Generate a description from the first meaningful sentence of the post
        for line in post_body.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("!") and not stripped.startswith("<!--") and len(stripped) > 30:
                # Use the full first sentence, not a char-truncated fragment
                first_sentence_end = None
                for i, ch in enumerate(stripped):
                    if ch in ".!?" and i > 30:
                        first_sentence_end = i + 1
                        break
                if first_sentence_end and first_sentence_end <= 200:
                    suggested_description = _strip_md_formatting(stripped[:first_sentence_end])
                else:
                    suggested_description = _strip_md_formatting(stripped[:160].rstrip(".")) + "."
                logger.info("Auto-generated description from post body: %s", suggested_description[:80])
                break

    # Generate slug from title
    slug = suggested_title.lower()
    for char in ['"', "'", "?", "!", ".", ",", ":", ";", "(", ")"]:
        slug = slug.replace(char, "")
    slug = slug.replace(" ", "-").strip("-")
    # Remove consecutive hyphens
    while "--" in slug:
        slug = slug.replace("--", "-")

    # Sanitize title for YAML frontmatter (strip outer quotes, escape inner ones)
    safe_title = suggested_title.strip('"').strip()
    safe_title = safe_title.replace('"', '\\"')

    # Sanitize description — strip markdown syntax (renders as literals in meta/OG tags)
    safe_desc = _strip_md_formatting(suggested_description or "")
    safe_desc = safe_desc.strip('"').strip()
    safe_desc = safe_desc.replace('"', '\\"')

    # Infer categories from content if not explicitly provided; never fall back to "tech"
    final_categories = _infer_categories(suggested_title, post_body, categories)

    # Normalize — handle double-serialized strings from upstream
    normalized_cats = []
    for c in final_categories:
        if isinstance(c, str) and c.startswith("["):
            try:
                parsed = json.loads(c)
                if isinstance(parsed, list):
                    normalized_cats.extend(parsed)
                    continue
            except (json.JSONDecodeError, TypeError):
                pass
        normalized_cats.append(c)
    cats_str = json.dumps(normalized_cats)

    # Build complete markdown with Astro frontmatter
    frontmatter = f"""---
title: "{safe_title}"
date: {today}
author: "Khaled Zaky"
categories: {cats_str}
description: "{safe_desc}"
draft: true
---"""

    markdown = f"{frontmatter}\n\n{post_body}\n"

    return {
        "title": suggested_title,
        "slug": slug,
        "categories": final_categories,
        "description": suggested_description,
        "markdown": markdown,
        "date": today,
    }
