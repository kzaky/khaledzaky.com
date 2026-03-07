"""
Notify Lambda — Sends an SNS email notification with the draft blog post
for human-in-the-loop review. Stores the draft in S3 for retrieval.
"""

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

    # Send SNS notification with full post
    # SNS email limit is 256KB — markdown posts are typically 5-15KB
    subject = f"[Blog Draft] {title}"
    message = f"""A new blog post draft is ready for your review!

Title: {title}
Date: {date}

--- ACTIONS ---

APPROVE and publish:
{approve_link}

REQUEST REVISIONS (provide feedback):
{APPROVE_URL}?action=revise&token={encoded_token}

REJECT this draft:
{reject_link}

--- FULL DRAFT ---

{markdown}

--- END DRAFT ---

Download as .md file:
{download_url}

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
