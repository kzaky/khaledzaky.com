"""
Ingest Lambda — Receives inbound emails via SES, parses the topic and notes,
and triggers the blog agent Step Functions pipeline.

Expected email format:
  Subject: The blog topic or title idea
  Body: Your draft, bullets, ideas, or stream of consciousness.
         The agent will use this as the skeleton and polish it in your voice.

Optional directives in the body (parsed and removed from content):
  Categories: tech, cloud, leadership
  Tone: more technical | conversational | opinionated
  Hero: yes  (triggers hero image generation)

Only emails from the allowed sender are processed.
"""

import json
import logging
import os
import email
from email import policy

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
sfn = boto3.client("stepfunctions")

STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")
ALLOWED_SENDER = os.environ.get("ALLOWED_SENDER", "")
SES_BUCKET = os.environ.get("SES_BUCKET", "")


def handler(event, context):
    """
    Triggered by SES inbound email rule.
    SES stores the raw email in S3, then invokes this Lambda.
    """
    for record in event.get("Records", []):
        ses_event = record.get("ses", {})
        mail = ses_event.get("mail", {})
        message_id = mail.get("messageId", "")

        # Verify sender — fail closed if ALLOWED_SENDER is not configured
        sender = mail.get("source", "")
        if not ALLOWED_SENDER:
            logger.error("ALLOWED_SENDER not configured — rejecting all inbound email")
            raise RuntimeError("ALLOWED_SENDER not configured — rejecting all inbound email")
        if sender.lower() != ALLOWED_SENDER.lower():
            logger.warning("Ignoring email from unauthorized sender: %s", sender)
            raise PermissionError(f"Unauthorized sender: {sender}")

        # Fetch raw email from S3
        if not SES_BUCKET or not message_id:
            raise RuntimeError(f"Missing SES_BUCKET ({SES_BUCKET!r}) or messageId ({message_id!r})")

        obj = s3.get_object(Bucket=SES_BUCKET, Key=f"inbound/{message_id}")
        raw_email = obj["Body"].read().decode("utf-8", errors="replace")

        # Parse email
        msg = email.message_from_string(raw_email, policy=policy.default)
        subject = msg.get("subject", "").strip()
        body = _get_text_body(msg).strip()

        if not subject:
            raise ValueError("Empty subject line — cannot determine blog topic")

        # Parse directives from body
        categories = ["tech"]
        tone = ""
        hero = False
        author_content = body

        directive_lines = []
        for line in body.split("\n"):
            line_lower = line.lower().strip()
            if line_lower.startswith("categories:"):
                cats = line.split(":", 1)[1].strip()
                categories = [c.strip().lower() for c in cats.split(",") if c.strip()]
                directive_lines.append(line)
            elif line_lower.startswith("tone:"):
                tone = line.split(":", 1)[1].strip()
                directive_lines.append(line)
            elif line_lower.startswith("hero:"):
                hero = line.split(":", 1)[1].strip().lower() in ("yes", "true", "1")
                directive_lines.append(line)

        # Remove directive lines from author content
        for dl in directive_lines:
            author_content = author_content.replace(dl, "")
        author_content = author_content.strip()

        # Trigger Step Functions
        sfn_input = {
            "topic": subject,
            "categories": categories,
            "author_content": author_content,
        }
        if tone:
            sfn_input["tone"] = tone
        if hero:
            sfn_input["generate_hero"] = True

        execution = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps(sfn_input),
        )

        logger.info(json.dumps({"event": "ingest_success", "topic": subject[:100], "executionArn": execution['executionArn']}))
        return {
            "processed": True,
            "topic": subject,
            "executionArn": execution["executionArn"],
        }

    raise RuntimeError("No records in event")


def _get_text_body(msg):
    """Extract plain text body from email message."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
        return ""
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode("utf-8", errors="replace")
        return ""
