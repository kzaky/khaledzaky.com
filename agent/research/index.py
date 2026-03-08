"""
Research Lambda — Uses Amazon Bedrock (Claude) to research a given topic
and produce structured research notes for blog post drafting.

Architecture:
- Query generation: Sonnet (LLM builds 5-8 targeted queries)
- Web search: Tavily (8 results per query, full article fetch for top 3)
- Thinking plan: Sonnet converse+thinking (research angles + structure)
- Research synthesis: Sonnet invoke_model (full generation)
- Cross-reference fact-check: Haiku (claim verification across sources)
- Chart data extraction: Haiku (deterministic structured extraction)
"""

import html
import json
import logging
import os
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
HAIKU_MODEL_ID = os.environ.get("HAIKU_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
THINKING_BUDGET = int(os.environ.get("THINKING_BUDGET_TOKENS", "2000"))  # budget_tokens must be < maxTokens; maxTokens must be <= 4096 on cross-region profiles
TAVILY_API_KEY_PARAM = os.environ.get("TAVILY_API_KEY_PARAM", "/blog-agent/tavily-api-key")


def get_tavily_api_key():
    """Retrieve Tavily API key from SSM Parameter Store."""
    try:
        response = ssm.get_parameter(Name=TAVILY_API_KEY_PARAM, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        logger.warning("Could not retrieve Tavily API key: %s", e)
        return None


def tavily_search(query, max_results=8):
    """Search Tavily for real sources. Returns list of {title, url, content, score}."""
    api_key = get_tavily_api_key()
    if not api_key:
        logger.info("Tavily API key not available — skipping web search")
        return []

    try:
        payload = json.dumps({
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": False,
            "include_raw_content": True,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            logger.info("Tavily returned %d results for: %s", len(results), query[:80])
            return results
    except Exception as e:
        logger.warning("Tavily search failed: %s", e)
        return []


def _thinking_plan(topic, author_content):
    """Pass 1: short converse+thinking call to produce a research plan.
    Fits within the 4096 maxTokens cross-region profile cap.
    Returns a concise plan string to inject into the main generation prompt."""
    think_prompt = f"""You are planning a research task for a blog post.

Topic: {topic[:500]}
Author notes (excerpt): {author_content[:800] if author_content else 'None'}

Think carefully, then output a concise research plan (max 400 words):
1. The 3-5 most important angles to research
2. What supporting data or examples would strengthen each angle
3. Specific claims the author made that need verification or enrichment
4. Suggested post structure"""

    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": think_prompt}]}],
        inferenceConfig={"maxTokens": 1500, "temperature": 1},
        additionalModelRequestFields={
            "thinking": {"type": "enabled", "budget_tokens": THINKING_BUDGET}
        },
    )
    text_parts = [
        block["text"]
        for block in response["output"]["message"]["content"]
        if block.get("type") == "text"
    ]
    return "\n".join(text_parts).strip()


def _invoke_model(prompt):
    """Pass 2: full generation via invoke_model (no token cap issues)."""
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0.7,
        "messages": [{"role": "user", "content": prompt}],
    })
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def build_search_queries(topic, author_content):
    """Use Haiku to generate 5-8 targeted search queries from topic and author content."""
    prompt = f"""Generate 5 to 8 targeted web search queries to research a blog post.

Topic: {topic[:400]}
Author notes excerpt: {author_content[:600] if author_content else 'None'}

Rules:
- Each query should target a different angle: background, data/stats, expert opinion, recent news, comparisons, tools/implementations
- Make queries specific and likely to return authoritative sources (docs, reports, news articles)
- Output ONLY the queries, one per line, no numbering, no extra text"""

    try:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
            "temperature": 0.3,
            "messages": [{"role": "user", "content": prompt}],
        })
        response = bedrock.invoke_model(
            modelId=HAIKU_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        queries = [q.strip() for q in result["content"][0]["text"].strip().splitlines() if q.strip()]
        queries = queries[:8]
        logger.info(json.dumps({"event": "queries_generated", "count": len(queries)}))
        return queries
    except Exception as e:
        logger.warning("Query generation failed, falling back to topic: %s", e)
        return [topic]


def verify_url(url, timeout=10):
    """Verify a URL resolves with HTTP HEAD (falls back to GET). Returns (ok, status, title)."""
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(
                url,
                method=method,
                headers={"User-Agent": "BlogAgent/1.0 (link-checker)"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.getcode()
                title = ""
                if method == "GET":
                    # Try to extract <title> from first 4KB for content matching
                    try:
                        chunk = resp.read(4096).decode("utf-8", errors="ignore")
                        m = re.search(r"<title[^>]*>([^<]+)</title>", chunk, re.IGNORECASE)
                        if m:
                            title = m.group(1).strip()
                    except Exception:
                        pass
                if 200 <= status < 400:
                    return True, status, title
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405):
                continue
            logger.warning("URL verify %s failed (%s): HTTP %d", url[:80], method, e.code)
            return False, e.code, ""
        except Exception as e:
            if method == "HEAD":
                continue
            logger.warning("URL verify %s failed: %s", url[:80], e)
            return False, 0, ""
    return False, 0, ""


def fetch_full_article(url, max_bytes=8192):
    """Fetch up to max_bytes of a page and extract visible text (strip HTML tags)."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "BlogAgent/1.0 (research-fetcher)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read(max_bytes).decode("utf-8", errors="ignore")
            # Strip scripts/styles first
            raw = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
            # Strip all remaining tags
            text = re.sub(r"<[^>]+>", " ", raw)
            text = html.unescape(text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:4000]  # cap at 4000 chars for prompt budget
    except Exception as e:
        logger.warning("Full article fetch failed for %s: %s", url[:80], e)
        return ""


def format_sources_for_prompt(search_results):
    """Format Tavily search results into a sources block for the prompt.
    Verifies each URL, fetches full article text for top 3 results."""
    if not search_results:
        return ""

    sources = []
    seen_urls = set()
    dropped = 0
    full_fetch_count = 0

    for _, r in enumerate(search_results):
        url = r.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)

        ok, status, page_title = verify_url(url)
        if not ok:
            logger.warning("Dropping unverified source: %s (status=%d)", url[:80], status)
            dropped += 1
            continue

        title = r.get("title", "Untitled")
        # Use raw_content from Tavily if available, else snippet, else fetch
        raw_content = r.get("raw_content", "") or ""
        snippet = r.get("content", "")[:500]

        if raw_content:
            body_text = raw_content[:4000]
            content_label = "Full content (via Tavily)"
        elif full_fetch_count < 3:
            body_text = fetch_full_article(url)
            full_fetch_count += 1
            content_label = "Full content (fetched)"
        else:
            body_text = snippet
            content_label = "Excerpt"

        verified_note = f"  Page title: {page_title}" if page_title else ""
        sources.append(
            f"- **{title}**\n  URL: {url}\n  {content_label}: {body_text}\n  Verified: YES (HTTP {status}){verified_note}"
        )

    if dropped:
        logger.info("Dropped %d unverified source(s) from results", dropped)

    if not sources:
        return ""

    return (
        "\n\n--- REAL SOURCES FROM WEB SEARCH ---\n"
        "The following are REAL, verified sources found via web search. "
        "Use these as your PRIMARY source material for citations. "
        "Always include the URL when citing these sources. "
        "Do NOT fabricate or hallucinate any sources — only cite what is provided here "
        "or clearly label any additional context as coming from your training data.\n\n"
        + "\n\n".join(sources)
        + "\n--- END SOURCES ---\n"
    )


def _extract_chart_data(research_text):
    """
    Second LLM pass: extract structured data points from research output.
    Uses a focused prompt to guarantee the exact format the Chart Lambda expects.
    Returns the structured text block, or empty string if no chartable data found.
    """
    extraction_prompt = f"""You are a data extraction assistant. Read the research notes below and extract
ALL quantitative data points that could be visualized as charts (bar charts, pie/donut charts, or comparisons).

RESEARCH NOTES:
{research_text}

For EACH data point you find, output it in this EXACT format (one block per data point):

- Data point: [short description of what is being measured]
- Values: [Label1: number, Label2: number, Label3: number]
- Source: [where this data came from]
- Chart type: [bar|pie|comparison]

Rules:
- Values MUST follow the format Label: number — NEVER bare numbers. Bad: "60, 40". Good: "Failure rate: 60, Success rate: 40"
- Values MUST be numeric only (strip %, $, hrs, etc. but keep the number). Example: "45%" becomes "45", "$2.3B" becomes "2.3"
- Each data point needs at least 2 labeled values to be chartable
- Use "bar" for ranked/ordered comparisons, "pie" for parts-of-a-whole, "comparison" for before/after
- If the research contains NO quantitative data suitable for charts, respond with exactly: NO_CHART_DATA
- Do NOT invent data. Only extract what is explicitly stated in the research notes.
- CRITICAL: Only extract data points whose Source is a real URL or a named organization/report (e.g. "Gartner 2024", "arxiv.org/..."). SKIP any data point where the source is "general knowledge", "training data", "model knowledge", or any variation of that — those are hallucinated and must not become charts.
- Output ONLY the structured data blocks, no other text.

Example of correct output:
- Data point: Enterprise agent deployment outcomes
- Values: Face significant failure: 60, Succeed with platform design: 40
- Source: arxiv.org/html/2510.25423v2
- Chart type: pie"""

    try:
        # Chart extraction is deterministic/structured — use Haiku (fast, cheap, no quality loss)
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "temperature": 0.0,
            "messages": [{"role": "user", "content": extraction_prompt}],
        })
        response = bedrock.invoke_model(
            modelId=HAIKU_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        extracted = result["content"][0]["text"].strip()

        if "NO_CHART_DATA" in extracted:
            logger.info("No chartable data found in research")
            return ""

        logger.info("Extracted chart data: %d chars", len(extracted))
        return "### Quantitative Data Points (for chart generation)\n\n" + extracted

    except Exception as e:
        logger.warning("Chart data extraction failed: %s", e)
        return ""


def _cross_reference_check(research_text, all_results):
    """Haiku pass: extract key factual claims from research and verify each is
    supported by at least one source. Appends a fact-check summary section."""
    if not all_results:
        return research_text

    source_urls = [r.get("url", "") for r in all_results if r.get("url")]
    source_titles = [r.get("title", "") for r in all_results if r.get("title")]
    source_list = "\n".join(f"- {t} ({u})" for t, u in zip(source_titles, source_urls, strict=False))[:2000]

    prompt = f"""You are a fact-checking assistant. Review the research notes below and identify
the 5-8 most specific factual claims (statistics, percentages, dates, named studies, product
capabilities). For each claim, state whether it is:
- SUPPORTED: directly backed by one of the provided sources
- UNVERIFIED: plausible but not in the provided sources (from training data)
- UNSUPPORTED: contradicted or not found anywhere

RESEARCH NOTES (excerpt):
{research_text[:3000]}

AVAILABLE SOURCES:
{source_list}

Output format (one per claim):
CLAIM: [the specific claim]
STATUS: [SUPPORTED|UNVERIFIED|UNSUPPORTED]
SOURCE: [source title or 'training data' or 'none']

Be concise. Output only the structured claim blocks."""

    try:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "temperature": 0.0,
            "messages": [{"role": "user", "content": prompt}],
        })
        response = bedrock.invoke_model(
            modelId=HAIKU_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        fact_check = result["content"][0]["text"].strip()
        logger.info(json.dumps({"event": "fact_check_complete", "chars": len(fact_check)}))
        return research_text + "\n\n### Fact-Check Summary\n\n" + fact_check
    except Exception as e:
        logger.warning("Cross-reference fact-check failed: %s", e)
        return research_text


def handler(event, context):
    """
    Input event:
    {
        "topic": "string — the blog topic",
        "categories": ["cloud", "aws"],
        "author_content": "the author's draft, bullets, ideas, or notes",
        "tone": "optional tone directive"
    }

    Output:
    {
        "topic": "...",
        "categories": [...],
        "author_content": "...",
        "tone": "...",
        "research": "structured research notes (markdown)",
        "suggested_title": "...",
        "suggested_description": "...",
        "data_points": "structured data suitable for chart generation"
    }
    """
    topic = event.get("topic", "")
    categories = event.get("categories", [])
    author_content = event.get("author_content", "")
    tone = event.get("tone", "")
    generate_hero = event.get("generate_hero", False)

    request_id = getattr(context, 'aws_request_id', 'local')
    logger.info(json.dumps({"event": "research_start", "topic": topic[:100], "request_id": request_id}))

    if not topic:
        raise ValueError("No topic provided")

    has_author_content = bool(author_content and author_content.strip())

    # --- Web search for real sources (parallel) ---
    search_queries = build_search_queries(topic, author_content)
    all_results = []
    with ThreadPoolExecutor(max_workers=min(len(search_queries), 5)) as executor:
        futures = {executor.submit(tavily_search, q): q for q in search_queries}
        for future in as_completed(futures):
            try:
                all_results.extend(future.result())
            except Exception as e:
                logger.warning("Tavily query failed in thread: %s", e)

    # Deduplicate by URL before synthesis to avoid confusing the fact-checker
    seen = set()
    deduped_results = []
    for r in all_results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            deduped_results.append(r)
    all_results = deduped_results
    sources_block = format_sources_for_prompt(all_results)

    if has_author_content:
        prompt = f"""You are a research assistant for a technology blog written by Khaled Zaky,
a Senior Director of Agentic AI Platform Engineering at RBC Borealis. Previously a Sr. Product
Manager at AWS Identity, FIDO Alliance and W3C WebAuthn member. He writes about platform
engineering, cloud, identity/security, AI, and leadership.

The author has written the following draft, bullets, or ideas for a blog post. Your job is NOT
to research the topic from scratch. Instead, your job is to ENRICH the author's existing points
with supporting evidence, data, references, and context.

AUTHOR'S TOPIC: {topic}

AUTHOR'S CONTENT (draft/bullets/ideas):
{author_content}

{f"Suggested categories: {', '.join(categories)}" if categories else ""}
{f"Tone directive: {tone}" if tone else ""}

Your task:
1. **Author's Key Arguments** — Identify the 3-6 main points the author is making
2. **Supporting Evidence** — For each key argument, find data, statistics, industry reports,
   or expert perspectives that support, contextualize, or add nuance to the author's point.
   ALWAYS cite sources (organization name, report title, year).
3. **Gaps & Enrichment** — Identify any areas where the author's content could be strengthened
   with additional context, a counterpoint, or a real-world example
4. **Quantitative Data Points** — Extract or find specific numbers, percentages, comparisons,
   or trends that could be visualized as charts. Format each as:
   - Data point: [description]
   - Values: [label: value, label: value, ...]
   - Source: [citation]
   - Chart type: [bar|line|pie|comparison]
5. **Suggested Title** — A compelling blog post title that reflects the AUTHOR'S perspective
6. **Suggested Description** — A 1-2 sentence meta description for SEO
7. **Suggested Categories** — 2-4 category tags from: cloud, aws, tech, product, career,
   leadership, identity, security, mfa, ai, code, devops

IMPORTANT: Do not replace the author's perspective. Your job is to find evidence that makes
the author's arguments stronger and more credible. The author's voice and opinions are the
foundation — you are adding supporting material.
{sources_block}
IMPORTANT CITATION RULES:
- Prefer the real web sources provided above over your training data
- Always include URLs when citing the web sources
- If you reference something NOT from the web sources, clearly note it is from general knowledge
- Never fabricate URLs or source names

Format your response as structured markdown."""
    else:
        prompt = f"""You are a research assistant for a technology blog written by Khaled Zaky,
a Senior Director of Agentic AI Platform Engineering at RBC Borealis. Previously a Sr. Product
Manager at AWS Identity, FIDO Alliance and W3C WebAuthn member. He writes about platform
engineering, cloud, identity/security, AI, and leadership.

Research the following topic and produce structured notes. Focus on finding concrete data,
statistics, and expert perspectives that Khaled can weave into a post grounded in his own
experience.

Topic: {topic}
{f"Suggested categories: {', '.join(categories)}" if categories else ""}
{f"Tone directive: {tone}" if tone else ""}

Please provide:
1. **Key Points** — The 5-8 most important things to cover
2. **Background Context** — Brief history or context the reader needs
3. **Current State** — What's happening now with this topic
4. **Expert Opinions / Data** — Notable quotes, statistics, or findings (cite sources)
5. **Quantitative Data Points** — Specific numbers, percentages, comparisons, or trends
   that could be visualized as charts. Format each as:
   - Data point: [description]
   - Values: [label: value, label: value, ...]
   - Source: [citation]
   - Chart type: [bar|line|pie|comparison]
6. **Practical Takeaways** — What the reader should do or think about
7. **Suggested Title** — A compelling blog post title
8. **Suggested Description** — A 1-2 sentence meta description for SEO
9. **Suggested Categories** — 2-4 category tags from: cloud, aws, tech, product, career,
   leadership, identity, security, mfa, ai, code, devops

Format your response as structured markdown.
{sources_block}
IMPORTANT CITATION RULES:
- Prefer the real web sources provided above over your training data
- Always include URLs when citing the web sources
- If you reference something NOT from the web sources, clearly note it is from general knowledge
- Never fabricate URLs or source names"""

    try:
        plan = _thinking_plan(topic, author_content)
        logger.info(json.dumps({"event": "thinking_plan_generated", "chars": len(plan), "request_id": request_id}))
        prompt += f"\n\n=== RESEARCH PLAN (from extended thinking) ===\n{plan}\n=== END PLAN ==="
    except Exception as e:
        logger.warning(json.dumps({"event": "thinking_plan_failed", "error": str(e)[:200], "request_id": request_id}))

    try:
        research_text = _invoke_model(prompt)
        logger.info(json.dumps({"event": "research_generated", "chars": len(research_text), "request_id": request_id}))
    except Exception as e:
        logger.error(json.dumps({"event": "research_failed", "error": str(e)[:200], "request_id": request_id}))
        raise RuntimeError(f"Research generation failed: {e}") from e

    # Extract suggested title and description from the research
    suggested_title = topic  # fallback
    suggested_description = ""
    for line in research_text.split("\n"):
        if "suggested title" in line.lower() and ":" in line:
            suggested_title = line.split(":", 1)[1].strip().strip("*").strip('"')
        if "suggested description" in line.lower() and ":" in line:
            suggested_description = line.split(":", 1)[1].strip().strip("*").strip('"')

    # --- Third pass: cross-reference fact-check (Haiku) ---
    research_text = _cross_reference_check(research_text, all_results)

    # --- Fourth pass: extract structured data points for chart generation (Haiku) ---
    data_points_text = _extract_chart_data(research_text)
    if data_points_text:
        research_text += "\n\n" + data_points_text

    # Always include all fields so Step Functions $.path references don't fail
    return {
        "topic": topic,
        "categories": categories,
        "research": research_text,
        "suggested_title": suggested_title,
        "suggested_description": suggested_description,
        "author_content": author_content or "",
        "tone": tone or "",
        "generate_hero": generate_hero,
    }
