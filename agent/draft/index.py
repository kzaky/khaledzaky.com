"""
Draft Lambda — Uses Amazon Bedrock (Claude) to write a blog post in Markdown
based on research notes. Outputs a complete Markdown file with Astro frontmatter.
"""

import json
import os
from datetime import datetime, timezone

import boto3

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")


def handler(event, context):
    """
    Input event:
    {
        "topic": "...",
        "categories": ["cloud", "aws"],
        "research": "structured research notes markdown",
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
    suggested_title = event.get("suggested_title", topic)
    suggested_description = event.get("suggested_description", "")
    categories = event.get("categories", [])

    if not research:
        return {"error": "No research notes provided"}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = f"""You are a blog writer for Khaled Zaky's personal technology blog. 
Khaled is a Sr. Product Manager at AWS who writes about cloud, product management, 
identity/security, and tech trends.

Write a complete blog post based on the following research notes. The post should:
- Be written in Khaled's voice: professional but approachable, technically informed, 
  with occasional personal insights
- Be 800-1500 words
- Use clear headings (## for main sections)
- Include relevant links where appropriate
- Be engaging and provide practical value to the reader
- NOT include the frontmatter — I will add that separately

Research Notes:
{research}

Suggested Title: {suggested_title}
Suggested Description: {suggested_description}

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

    # Generate slug from title
    slug = suggested_title.lower()
    for char in ['"', "'", "?", "!", ".", ",", ":", ";", "(", ")"]:
        slug = slug.replace(char, "")
    slug = slug.replace(" ", "-").strip("-")
    # Remove consecutive hyphens
    while "--" in slug:
        slug = slug.replace("--", "-")

    # Build categories array string
    cats_str = json.dumps(categories if categories else ["tech"])

    # Build complete markdown with Astro frontmatter
    frontmatter = f"""---
title: "{suggested_title}"
date: {today}
author: "Khaled Zaky"
categories: {cats_str}
description: "{suggested_description}"
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
