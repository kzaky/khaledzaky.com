"""
Research Lambda — Uses Amazon Bedrock (Claude) to research a given topic
and produce structured research notes for blog post drafting.
"""

import json
import os
import urllib.request
import urllib.parse
import boto3

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
TAVILY_API_KEY_PARAM = os.environ.get("TAVILY_API_KEY_PARAM", "/blog-agent/tavily-api-key")


def get_tavily_api_key():
    """Retrieve Tavily API key from SSM Parameter Store."""
    try:
        response = ssm.get_parameter(Name=TAVILY_API_KEY_PARAM, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Warning: Could not retrieve Tavily API key: {e}")
        return None


def tavily_search(query, max_results=5):
    """Search Tavily for real sources. Returns list of {title, url, content, score}."""
    api_key = get_tavily_api_key()
    if not api_key:
        print("Tavily API key not available — skipping web search")
        return []

    try:
        payload = json.dumps({
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": False,
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

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            print(f"Tavily returned {len(results)} results for: {query[:80]}")
            return results
    except Exception as e:
        print(f"Tavily search failed: {e}")
        return []


def build_search_queries(topic, author_content):
    """Build 1-3 targeted search queries from the topic and author content."""
    queries = [topic]
    if author_content and author_content.strip():
        # Extract key phrases from the first ~500 chars of author content
        snippet = author_content.strip()[:500]
        queries.append(f"{topic} {snippet[:100]}")
    return queries[:3]


def format_sources_for_prompt(search_results):
    """Format Tavily search results into a sources block for the prompt."""
    if not search_results:
        return ""

    sources = []
    seen_urls = set()
    for r in search_results:
        url = r.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        title = r.get("title", "Untitled")
        content = r.get("content", "")[:500]
        sources.append(f"- **{title}**\n  URL: {url}\n  Excerpt: {content}")

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
- Output ONLY the structured data blocks, no other text.

Example of correct output:
- Data point: Enterprise agent deployment outcomes
- Values: Face significant failure: 60, Succeed with platform design: 40
- Source: arxiv.org/html/2510.25423v2
- Chart type: pie"""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "temperature": 0.0,
        "messages": [
            {"role": "user", "content": extraction_prompt}
        ],
    })

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        extracted = result["content"][0]["text"].strip()

        if "NO_CHART_DATA" in extracted:
            print("No chartable data found in research")
            return ""

        print(f"Extracted chart data:\n{extracted}")
        return "### Quantitative Data Points (for chart generation)\n\n" + extracted

    except Exception as e:
        print(f"Warning: Chart data extraction failed: {e}")
        return ""


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

    if not topic:
        return {"error": "No topic provided"}

    has_author_content = bool(author_content and author_content.strip())

    # --- Web search for real sources ---
    search_queries = build_search_queries(topic, author_content)
    all_results = []
    for q in search_queries:
        all_results.extend(tavily_search(q))
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

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0.7,
        "messages": [
            {"role": "user", "content": prompt}
        ],
    })

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        research_text = result["content"][0]["text"]
    except Exception as e:
        print(f"ERROR: Research generation failed: {e}")
        return {"error": f"Research generation failed: {e}"}

    # Extract suggested title and description from the research
    suggested_title = topic  # fallback
    suggested_description = ""
    for line in research_text.split("\n"):
        if "suggested title" in line.lower() and ":" in line:
            suggested_title = line.split(":", 1)[1].strip().strip("*").strip('"')
        if "suggested description" in line.lower() and ":" in line:
            suggested_description = line.split(":", 1)[1].strip().strip("*").strip('"')

    # --- Second pass: extract structured data points for chart generation ---
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
