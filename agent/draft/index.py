"""
Draft Lambda — Uses Amazon Bedrock (Claude) to write a blog post in Markdown
based on the author's content and research notes. The author's draft/bullets/ideas
are the skeleton; the AI polishes, structures, and enriches — never replaces.

The voice profile (agent/voice-profile.md) is loaded at build time and injected
into every prompt to ensure consistent voice.
"""

import json
import os
import re
from datetime import datetime, timezone

import boto3

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
s3 = boto3.client("s3")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
DRAFTS_BUCKET = os.environ.get("DRAFTS_BUCKET", "")

# Voice profile loaded from S3 with TTL (re-read every 50 invocations)
_voice_profile_cache = None
_voice_profile_invocations = 0
_VOICE_PROFILE_TTL = 50


def _load_voice_profile():
    """Load voice profile from S3. Cached with TTL to pick up updates."""
    global _voice_profile_cache, _voice_profile_invocations
    _voice_profile_invocations += 1
    if _voice_profile_cache is not None and _voice_profile_invocations % _VOICE_PROFILE_TTL != 0:
        return _voice_profile_cache
    if not DRAFTS_BUCKET:
        return ""
    try:
        obj = s3.get_object(Bucket=DRAFTS_BUCKET, Key="config/voice-profile.md")
        _voice_profile_cache = obj["Body"].read().decode("utf-8")
        print(f"Voice profile loaded from S3 (invocation #{_voice_profile_invocations})")
        return _voice_profile_cache
    except Exception as e:
        print(f"Warning: Could not load voice profile from S3: {e}")
        return _voice_profile_cache or ""


def _insert_chart_placeholders(post_body, research):
    """
    Second LLM pass: scan the draft for quantitative claims that have matching
    data in the research, and insert <!-- CHART: description --> placeholders.
    Only inserts placeholders if the research contains structured data points.
    """
    if "- Data point:" not in research:
        print("No structured data points in research — skipping chart placeholder insertion")
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

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0.0,
        "messages": [
            {"role": "user", "content": insertion_prompt}
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
        updated = result["content"][0]["text"].strip()

        # Sanity check: the updated draft should contain <!-- CHART and be roughly the same length
        chart_count = len(re.findall(r"<!--\s*CHART:", updated))
        if chart_count > 0:
            print(f"Inserted {chart_count} chart placeholder(s) into draft")
            return updated
        else:
            print("No chart placeholders inserted — draft unchanged")
            return post_body

    except Exception as e:
        print(f"Warning: Chart placeholder insertion failed: {e}")
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
1. **comparison** — Two-column comparison (e.g., "Traditional vs Modern", "Before vs After")
   Format: <!-- DIAGRAM: comparison | Left Header | Right Header | Left1:Right1 | Left2:Right2 | ... -->
   Example: <!-- DIAGRAM: comparison | Traditional Software | AI Agents | Deterministic:Probabilistic | Request/Response:Autonomous Action | Static Permissions:Dynamic Authority -->

2. **progression** — Ascending stages/steps (e.g., maturity model, adoption curve)
   Format: <!-- DIAGRAM: progression | Title | Stage1 Name;Detail1;Detail2 | Stage2 Name;Detail1;Detail2 | ... -->
   Example: <!-- DIAGRAM: progression | Platform Maturity | Sandbox;Small experiments;Fast iteration | Guarded Pilots;Defined use cases;Basic logging | Reusable Platform;Shared controls;Self-service -->

3. **stack** — Layered horizontal bars (e.g., platform layers, architecture tiers)
   Format: <!-- DIAGRAM: stack | Title | Layer1 Name;Detail | Layer2 Name;Detail | ... -->
   Example: <!-- DIAGRAM: stack | Platform Primitives | Identity & Access;Scoped permissions | Tool Controls;Allowlists and policy | Observability;Input/output logging -->

4. **convergence** — Multiple items flowing into a central concept
   Format: <!-- DIAGRAM: convergence | Center Label | Item1;Detail | Item2;Detail | ... -->
   Example: <!-- DIAGRAM: convergence | Agent Platform | SPIFFE;Workload Identity | Cedar;Authorization | OpenTelemetry;Observability -->

5. **venn** — 2-3 overlapping circles showing relationships
   Format: <!-- DIAGRAM: venn | Title | Circle1 Label;trait1;trait2 | Circle2 Label;trait1;trait2 | Circle3 Label;trait1;trait2 -->
   Example: <!-- DIAGRAM: venn | Agent Identity | Human;Decisions;Accountability | Agent;Reasons like humans;Executes like machines | Machine;Deterministic;Static credentials -->

Instructions:
1. Read the draft and identify 1-3 places where a conceptual diagram would help readers grasp an idea faster
2. Choose the BEST diagram type for each concept
3. Insert the placeholder on its own line AFTER the relevant paragraph
4. The placeholder MUST follow the exact format above with pipe-delimited fields
5. Only insert diagrams where they genuinely add value — NOT for simple lists or linear arguments
6. Good candidates: comparisons between two approaches, multi-stage models, layered architectures, converging trends, overlapping categories
7. Bad candidates: simple bullet lists, chronological narratives, single-concept explanations
8. Insert at most 3 diagram placeholders per post
9. Do NOT change any of the draft text. Do NOT add, remove, or rewrite any prose.
10. Output the COMPLETE draft with the placeholders inserted. Nothing else.

If the post does not contain concepts that benefit from a diagram, output the draft UNCHANGED."""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0.0,
        "messages": [
            {"role": "user", "content": insertion_prompt}
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
        updated = result["content"][0]["text"].strip()

        diagram_count = len(re.findall(r"<!--\s*DIAGRAM:", updated))
        if diagram_count > 0:
            print(f"Inserted {diagram_count} diagram placeholder(s) into draft")
            return updated
        else:
            print("No diagram placeholders inserted — draft unchanged")
            return post_body

    except Exception as e:
        print(f"Warning: Diagram placeholder insertion failed: {e}")
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
    suggested_title = event.get("suggested_title", topic)
    suggested_description = event.get("suggested_description", "")
    categories = event.get("categories", [])
    previous_draft = event.get("previous_draft", "")
    feedback = event.get("feedback", "")

    if not research and not previous_draft and not author_content:
        return {"error": "No research notes, author content, or previous draft provided"}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    voice_profile = _load_voice_profile()
    voice_section = f"""
=== VOICE & STYLE GUIDE ===
{voice_profile}
=== END VOICE GUIDE ===
""" if voice_profile else ""

    has_author_content = bool(author_content and author_content.strip())

    if previous_draft and feedback:
        # Revision mode — improve existing draft based on feedback
        prompt = f"""You are an editorial assistant for Khaled Zaky's personal technology blog.
Your job is to REVISE an existing draft based on the author's feedback while preserving
his voice, opinions, and personal insights.

{voice_section}

PREVIOUS DRAFT:
{previous_draft}

REVIEWER FEEDBACK:
{feedback}

RESEARCH NOTES (for additional context):
{research}

{f"TONE DIRECTIVE: {tone}" if tone else ""}

Revise the blog post based on the feedback. Keep what works, improve what was flagged.
Rules:
- Preserve the author's voice, opinions, and personal anecdotes — do NOT make them generic
- Keep concrete specifics (dollar amounts, service names, build times)
- Use the voice guide above for tone, sentence structure, and vocabulary
- Be 800-2500 words depending on the topic's depth
- Use clear headings (## for main sections)
- Do NOT include the frontmatter — I will add that separately

CITATION RULES (CRITICAL):
- Every factual claim, statistic, or external reference MUST include an inline markdown link: [descriptive text](url)
- Extract URLs from the RESEARCH NOTES below — look for lines containing "URL:" or "http"
- Format citations as natural prose with links, e.g. "Docker's [State of Agentic AI Report](https://...) found that..."
- If the research does not provide a URL for a claim, either drop the claim or clearly attribute it as the author's own perspective
- NEVER fabricate URLs. NEVER invent source names. NEVER write vague attributions like "according to a study" or "research shows" without a link
- Named tools/frameworks/products (e.g. SPIFFE, Cedar) should link to their official site on first mention

Write the revised blog post body in Markdown. Do NOT include frontmatter (---) blocks.
Start directly with the content."""

    elif has_author_content:
        # Author-content mode — polish and structure the author's draft/bullets
        prompt = f"""You are an editorial assistant for Khaled Zaky's personal technology blog.
The author has provided his own draft, bullets, or ideas below. Your job is to POLISH and
STRUCTURE his content into a complete blog post — NOT to replace it with your own writing.

{voice_section}

AUTHOR'S TOPIC: {topic}

AUTHOR'S CONTENT (draft/bullets/ideas):
{author_content}

RESEARCH & SUPPORTING DATA:
{research}

{f"TONE DIRECTIVE: {tone}" if tone else ""}

Your task:
1. Use the author's content as the SKELETON — his ideas, opinions, and framing come first
2. Structure it into a well-organized blog post with clear headings
3. Polish the prose: fix grammar, improve flow, tighten sentences
4. Weave in supporting data and references from the research where they strengthen the
   author's points — every external claim MUST include an inline markdown link (see CITATION RULES)
5. If the research includes quantitative data points suitable for charts, add a markdown
   comment where a chart would go: <!-- CHART: [description] -->
6. Preserve the author's personal anecdotes, opinions, and first-person perspective
7. Do NOT add generic filler, corporate buzzwords, or conclusions that could apply to any topic

Rules:
- The author's voice is the foundation. You are his editor, not his ghostwriter.
- Use the voice guide above for tone, sentence structure, and vocabulary
- Be 800-2500 words depending on the topic's depth
- Never start with "In today's..." or any generic opener
- Never end with "Stay tuned!" or "What do you think?"
- Do NOT include the frontmatter — I will add that separately

CITATION RULES (CRITICAL):
- Every factual claim, statistic, or external reference MUST include an inline markdown link: [descriptive text](url)
- Extract URLs from the RESEARCH & SUPPORTING DATA section — look for lines containing "URL:" or "http"
- Format citations as natural prose with links, e.g. "Docker's [State of Agentic AI Report](https://...) found that..."
- If the research does not provide a URL for a claim, either drop the claim or clearly attribute it as the author's own perspective
- NEVER fabricate URLs. NEVER invent source names. NEVER write vague attributions like "according to a study" or "research shows" without a link
- Named tools/frameworks/products (e.g. SPIFFE, Cedar) should link to their official site on first mention

Write the blog post body in Markdown. Do NOT include frontmatter (---) blocks.
Start directly with the content."""

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
- Extract URLs from the Research Notes — look for lines containing "URL:" or "http"
- Format citations as natural prose with links, e.g. "Docker's [State of Agentic AI Report](https://...) found that..."
- If the research does not provide a URL for a claim, either drop the claim or clearly attribute it as the author's own perspective
- NEVER fabricate URLs. NEVER invent source names. NEVER write vague attributions like "according to a study" or "research shows" without a link
- Named tools/frameworks/products (e.g. SPIFFE, Cedar) should link to their official site on first mention

Write the blog post body in Markdown. Do NOT include frontmatter (---) blocks.
Start directly with the content."""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0.8,
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
        post_body = result["content"][0]["text"]
    except Exception as e:
        print(f"ERROR: Draft generation failed: {e}")
        return {"error": f"Draft generation failed: {e}"}

    # --- Second pass: insert chart placeholders where data supports it ---
    post_body = _insert_chart_placeholders(post_body, research)

    # --- Third pass: insert conceptual diagram placeholders ---
    post_body = _insert_diagram_placeholders(post_body)

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

    # Sanitize description
    safe_desc = (suggested_description or "").strip('"').strip()
    safe_desc = safe_desc.replace('"', '\\"')

    # Normalize categories — handle double-serialized strings from upstream
    cats = categories if categories else ["tech"]
    normalized_cats = []
    for c in cats:
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
        "categories": categories if categories else ["tech"],
        "description": suggested_description,
        "markdown": markdown,
        "date": today,
    }
