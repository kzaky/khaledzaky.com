"""
Research Lambda — Uses Amazon Bedrock (Claude) to research a given topic
and produce structured research notes for blog post drafting.
"""

import json
import os
import boto3

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")


def handler(event, context):
    """
    Input event:
    {
        "topic": "string — the blog topic to research",
        "categories": ["cloud", "aws"],  # optional suggested categories
        "notes": "optional additional context or angle"
    }

    Output:
    {
        "topic": "...",
        "categories": [...],
        "research": "structured research notes (markdown)",
        "suggested_title": "...",
        "suggested_description": "..."
    }
    """
    topic = event.get("topic", "")
    categories = event.get("categories", [])
    notes = event.get("notes", "")

    if not topic:
        return {"error": "No topic provided"}

    prompt = f"""You are a research assistant for a technology blog written by Khaled Zaky, 
a Sr. Product Manager at AWS. The blog covers cloud computing, product management, 
identity/security, and general tech trends.

Research the following topic thoroughly and produce structured notes that a writer 
can use to draft a compelling blog post.

Topic: {topic}
{f"Additional context: {notes}" if notes else ""}
{f"Suggested categories: {', '.join(categories)}" if categories else ""}

Please provide:
1. **Key Points** — The 5-8 most important things to cover
2. **Background Context** — Brief history or context the reader needs
3. **Current State** — What's happening now with this topic
4. **Expert Opinions / Data** — Notable quotes, statistics, or findings (cite sources where possible)
5. **Practical Takeaways** — What the reader should do or think about
6. **Suggested Title** — A compelling blog post title
7. **Suggested Description** — A 1-2 sentence meta description for SEO
8. **Suggested Categories** — 2-4 category tags from: cloud, aws, tech, product, career, 
   leadership, identity, security, mfa, blockchain, bitcoin, ethereum, code, devops

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

    return {
        "topic": topic,
        "categories": categories,
        "research": research_text,
        "suggested_title": suggested_title,
        "suggested_description": suggested_description,
    }
