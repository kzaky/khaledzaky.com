"""
Notify Lambda — Sends an SNS email notification with the draft blog post
for human-in-the-loop review. Stores the draft in S3 for retrieval.
"""

import json
import logging
import os
import re
import urllib.parse

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sns = boto3.client("sns")
s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
cloudwatch = boto3.client("cloudwatch", region_name=os.environ.get("AWS_REGION", "us-east-1"))

SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
DRAFTS_BUCKET = os.environ.get("DRAFTS_BUCKET", "")
APPROVE_URL = os.environ.get("APPROVE_URL", "")
HAIKU_MODEL_ID = os.environ.get("HAIKU_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")


def _count_words(markdown):
    """Count words in markdown body, excluding YAML frontmatter."""
    body = markdown
    if markdown.startswith("---"):
        end = markdown.find("---", 3)
        if end != -1:
            body = markdown[end + 3:]
    return len(body.split())


def _check_author_intent(author_content, markdown):
    """Use Haiku to check whether the final draft preserved the author's original intent.

    Returns dict: {"score": 0-10, "preserved": [...], "drifted": [...]}
    or None if skipped (author_content < 100 chars — e.g. topic-only CLI runs)
    or failed (non-fatal — Bedrock errors are caught and logged).
    """
    if not author_content or len(author_content.strip()) < 100:
        return None

    body = markdown
    if markdown.startswith("---"):
        end = markdown.find("---", 3)
        if end != -1:
            body = markdown[end + 3:]

    prompt = (
        "You are reviewing whether an AI-polished blog post preserved the author's original "
        "intent and key claims.\n\n"
        "AUTHOR'S ORIGINAL CONTENT (their draft/bullets/ideas):\n"
        f"{author_content[:2000]}\n\n"
        "FINAL POLISHED DRAFT (first 3000 chars):\n"
        f"{body[:3000]}\n\n"
        "Check whether the final draft preserves the author's key claims, opinions, and "
        "framing — or whether the agent drifted into generic commentary.\n\n"
        'Output ONLY valid JSON: {"score": <int 0-10>, "preserved": ["...", ...], "drifted": ["...", ...]}\n\n'
        "Score: 10 = all key claims and framing preserved, 0 = completely generic/unrecognizable.\n"
        "Cap each list at 3 concise items. Output ONLY the JSON object, nothing else."
    )

    try:
        response = bedrock.invoke_model(
            modelId=HAIKU_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 512,
                "temperature": 0.0,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        raw = json.loads(response["body"].read())["content"][0]["text"].strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        result = json.loads(raw)
        score = max(0, min(10, int(result.get("score", 0))))
        preserved = [str(p) for p in result.get("preserved", [])][:3]
        drifted = [str(d) for d in result.get("drifted", [])][:3]
        logger.info(json.dumps({
            "event": "intent_check_complete",
            "score": score,
            "preserved_count": len(preserved),
            "drifted_count": len(drifted),
        }))
        return {"score": score, "preserved": preserved, "drifted": drifted}
    except Exception as e:
        logger.warning(json.dumps({"event": "intent_check_failed", "error": str(e)[:200]}))
        return None


def _emit_pipeline_metrics(quality_pct, word_count):
    """Emit CitationQualityScore and PostWordCount to CloudWatch. Non-fatal on failure."""
    try:
        cloudwatch.put_metric_data(
            Namespace="BlogAgent/Pipeline",
            MetricData=[
                {"MetricName": "CitationQualityScore", "Value": quality_pct, "Unit": "Percent"},
                {"MetricName": "PostWordCount", "Value": word_count, "Unit": "Count"},
            ],
        )
        logger.info(json.dumps({
            "event": "pipeline_metrics_emitted",
            "citation_quality_pct": quality_pct,
            "word_count": word_count,
        }))
    except Exception as e:
        logger.warning(json.dumps({"event": "pipeline_metrics_failed", "error": str(e)[:200]}))


def handler(event, context):
    """
    Input event:
    {
        "title": "...",
        "slug": "...",
        "categories": [...],
        "description": "...",
        "markdown": "complete markdown content",
        "date": "YYYY-MM-DD",
        "author_content": "author's original draft/bullets (may be empty string)",
        "taskToken": "Step Functions task token for callback"
    }

    Stores draft in S3 and sends SNS notification with citation quality summary,
    author intent check, and one-click approval/revision/rejection links.
    """
    title = event.get("title", "Untitled")
    slug = event.get("slug", "untitled")
    markdown = event.get("markdown", "")
    date = event.get("date", "")
    task_token = event.get("taskToken", "")
    verification = event.get("verification", {})
    author_content = event.get("author_content", "")

    if not DRAFTS_BUCKET:
        raise RuntimeError("DRAFTS_BUCKET not configured — cannot store draft")
    if not SNS_TOPIC_ARN:
        raise RuntimeError("SNS_TOPIC_ARN not configured — cannot send review notification")

    # Store draft in S3
    draft_key = f"drafts/{date}-{slug}.md"
    s3.put_object(
        Bucket=DRAFTS_BUCKET,
        Key=draft_key,
        Body=markdown.encode("utf-8"),
        ContentType="text/markdown",
    )

    # Build one-click approval/rejection URLs
    encoded_token = urllib.parse.quote(task_token, safe="")
    approve_link = f"{APPROVE_URL}?action=approve&token={encoded_token}"
    reject_link = f"{APPROVE_URL}?action=reject&token={encoded_token}"

    # Generate presigned download URL (valid 7 days, matching HITL timeout)
    download_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": DRAFTS_BUCKET, "Key": draft_key},
        ExpiresIn=604800,  # 7 days
    )

    # Build verification quality summary if available
    verification_block = ""
    quality_pct = 0
    if verification:
        total = verification.get("total_links", 0)
        passed = verification.get("passed", 0)
        repaired = verification.get("repaired", 0)
        warnings = verification.get("warnings", 0)
        failures = verification.get("failures", 0)
        unreachable = verification.get("unreachable", 0)
        if total > 0:
            reachable = total - unreachable
            quality_pct = round(100 * (passed + repaired) / reachable) if reachable else 0
            status_icon = "✅" if failures == 0 else "⚠️"
            verification_block = (
                f"\n--- CITATION QUALITY ({status_icon}) ---\n"
                f"Links checked: {total}  |  "
                f"Passed: {passed}  |  "
                f"Auto-repaired: {repaired}  |  "
                f"Warnings: {warnings}  |  "
                f"Failures: {failures}  |  "
                f"Unreachable: {unreachable}\n"
                f"Quality score: {quality_pct}%"
                + (f"\n⚠️  {failures} citation(s) flagged as FAIL — search for '<!-- ⚠️ CITATION FAIL' in the draft below." if failures > 0 else "")
                + (f"\n⚡  {repaired} citation(s) were auto-repaired (URLs swapped silently)." if repaired > 0 else "")
                + "\n---\n"
            )

    # Author intent preservation check (Haiku — skipped when no author content provided)
    intent_check = _check_author_intent(author_content, markdown)
    intent_block = ""
    if intent_check is not None:
        score = intent_check["score"]
        preserved = intent_check["preserved"]
        drifted = intent_check["drifted"]
        score_icon = "✅" if score >= 8 else ("⚠️" if score >= 5 else "🚨")
        preserved_lines = "\n".join(f"  ✓ {p}" for p in preserved) if preserved else "  (none noted)"
        drifted_lines = "\n".join(f"  ✗ {d}" for d in drifted) if drifted else "  (none noted)"
        intent_block = (
            f"\n--- INTENT CHECK ({score_icon} {score}/10) ---\n"
            f"Preserved:\n{preserved_lines}\n"
            f"Drifted:\n{drifted_lines}\n"
            "---\n"
        )

    # Emit CloudWatch quality metrics (always — word count regardless of citation data)
    _emit_pipeline_metrics(quality_pct, _count_words(markdown))

    # Send SNS notification with full post if small enough, summary + download link otherwise.
    # SNS email limit is 256KB. Overhead for action links is ~2KB; guard at 200KB for markdown.
    _SNS_MARKDOWN_LIMIT = 200 * 1024
    subject = f"[Blog Draft] {title}"
    markdown_bytes = markdown.encode("utf-8")

    if len(markdown_bytes) > _SNS_MARKDOWN_LIMIT:
        logger.warning(json.dumps({"event": "notify_draft_truncated", "size_bytes": len(markdown_bytes), "limit_bytes": _SNS_MARKDOWN_LIMIT, "slug": slug}))
        draft_body = f"Draft is too large to include inline ({len(markdown_bytes) // 1024}KB). Download the full draft using the link below."
    else:
        draft_body = f"--- FULL DRAFT ---\n\n{markdown}\n\n--- END DRAFT ---"

    message = f"""A new blog post draft is ready for your review!

Title: {title}
Date: {date}
{verification_block}{intent_block}
{draft_body}

Download as .md file:
{download_url}

--- ACTIONS ---

APPROVE and publish:
{approve_link}

REQUEST REVISIONS (provide feedback):
{APPROVE_URL}?action=revise&token={encoded_token}

REJECT this draft:
{reject_link}

---
This is an automated message from your blog agent.
"""

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=subject[:100],  # SNS subject limit
        Message=message,
    )

    return {
        "notified": True,
        "draft_key": draft_key,
        "title": title,
        "slug": slug,
    }
