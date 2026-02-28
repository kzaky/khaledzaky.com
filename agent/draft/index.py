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

# Voice profile loaded from S3 on first invocation (cached across warm starts)
_voice_profile_cache = None


def _load_voice_profile():
    """Load voice profile from S3. Cached after first call."""
    global _voice_profile_cache
    if _voice_profile_cache is not None:
        return _voice_profile_cache
    if not DRAFTS_BUCKET:
        return ""
    try:
        obj = s3.get_object(Bucket=DRAFTS_BUCKET, Key="config/voice-profile.md")
        _voice_profile_cache = obj["Body"].read().decode("utf-8")
        return _voice_profile_cache
    except Exception as e:
        print(f"Warning: Could not load voice profile from S3: {e}")
        return ""


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
- Where research provides supporting data, weave it in naturally with source citations
- Do NOT include the frontmatter — I will add that separately

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
   author's points. Always cite sources inline (e.g., "according to [Source], ...")
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
- Include relevant links where appropriate
- If the research includes quantitative data points suitable for charts, add a markdown
  comment where a chart would go: <!-- CHART: [description] -->
- Never start with "In today's..." or any generic opener
- Do NOT include the frontmatter — I will add that separately

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

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )

    result = json.loads(response["body"].read())
    post_body = result["content"][0]["text"]

    # --- Second pass: insert chart placeholders where data supports it ---
    post_body = _insert_chart_placeholders(post_body, research)

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
