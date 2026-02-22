"""
Research Lambda — Uses Amazon Bedrock (Claude) to research a given topic
and produce structured research notes for blog post drafting.
"""

import json
import os
import boto3

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-sonnet-20241022-v2:0")


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

Format your response as structured markdown."""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0.7,
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
    research_text = result["content"][0]["text"]

    # Extract suggested title and description from the research
    suggested_title = topic  # fallback
    suggested_description = ""
    for line in research_text.split("\n"):
        if "suggested title" in line.lower() and ":" in line:
            suggested_title = line.split(":", 1)[1].strip().strip("*").strip('"')
        if "suggested description" in line.lower() and ":" in line:
            suggested_description = line.split(":", 1)[1].strip().strip("*").strip('"')

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
