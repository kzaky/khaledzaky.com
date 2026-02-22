"""
Ingest Lambda — Receives inbound emails via SES, parses the topic and notes,
and triggers the blog agent Step Functions pipeline.

Expected email format:
  Subject: The blog topic
  Body: Optional notes, context, or TL;DR for the research phase

Only emails from the allowed sender are processed.
"""

import json
import os
import email
from email import policy

import boto3

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

        # Verify sender
        sender = mail.get("source", "")
        if ALLOWED_SENDER and sender.lower() != ALLOWED_SENDER.lower():
            print(f"Ignoring email from unauthorized sender: {sender}")
            return {"processed": False, "reason": f"Unauthorized sender: {sender}"}

        # Fetch raw email from S3
        if not SES_BUCKET or not message_id:
            return {"processed": False, "reason": "Missing SES_BUCKET or messageId"}

        obj = s3.get_object(Bucket=SES_BUCKET, Key=f"inbound/{message_id}")
        raw_email = obj["Body"].read().decode("utf-8", errors="replace")

        # Parse email
        msg = email.message_from_string(raw_email, policy=policy.default)
        subject = msg.get("subject", "").strip()
        body = _get_text_body(msg).strip()

        if not subject:
            return {"processed": False, "reason": "Empty subject line"}

        # Parse categories from body if present (e.g., "Categories: tech, cloud")
        categories = ["tech"]
        notes = body
        for line in body.split("\n"):
            if line.lower().startswith("categories:"):
                cats = line.split(":", 1)[1].strip()
                categories = [c.strip().lower() for c in cats.split(",") if c.strip()]
                notes = body.replace(line, "").strip()
                break

        # Trigger Step Functions
        sfn_input = {
            "topic": subject,
            "categories": categories,
        }
        if notes:
            sfn_input["notes"] = notes

        execution = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps(sfn_input),
        )

        print(f"Started execution: {execution['executionArn']}")
        return {
            "processed": True,
            "topic": subject,
            "executionArn": execution["executionArn"],
        }

    return {"processed": False, "reason": "No records in event"}


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
