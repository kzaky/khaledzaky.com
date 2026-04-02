"""
Notify Lambda — Sends an SNS email notification with the draft blog post
for human-in-the-loop review. Stores the draft in S3 for retrieval.
"""

import json
import logging
import os
import urllib.parse

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sns = boto3.client("sns")
s3 = boto3.client("s3")

SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
DRAFTS_BUCKET = os.environ.get("DRAFTS_BUCKET", "")
APPROVE_URL = os.environ.get("APPROVE_URL", "")


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
        "taskToken": "Step Functions task token for callback"
    }

    Stores draft in S3 and sends SNS notification.
    """
    title = event.get("title", "Untitled")
    slug = event.get("slug", "untitled")
    markdown = event.get("markdown", "")
    date = event.get("date", "")
    task_token = event.get("taskToken", "")
    verification = event.get("verification", {})

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
{verification_block}
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
