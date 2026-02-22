"""
Notify Lambda — Sends an SNS email notification with the draft blog post
for human-in-the-loop review. Stores the draft in S3 for retrieval.
"""

import json
import os
import urllib.parse

import boto3

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

    # Store draft in S3
    draft_key = f"drafts/{date}-{slug}.md"
    if DRAFTS_BUCKET:
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

    # Send SNS notification
    subject = f"[Blog Draft] {title}"
    message = f"""A new blog post draft is ready for your review!

Title: {title}
Date: {date}
Draft Location: s3://{DRAFTS_BUCKET}/{draft_key}

--- DRAFT PREVIEW ---

{markdown[:3000]}

{"... (truncated, see full draft in S3)" if len(markdown) > 3000 else ""}

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

    if SNS_TOPIC_ARN:
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
