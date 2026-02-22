"""
Approve Lambda — Handles one-click approval/rejection of blog drafts
via a Lambda Function URL. Called from links in the SNS email.
"""

import json
import os
import urllib.parse

import boto3

sfn = boto3.client("stepfunctions")


def handler(event, context):
    """
    Handles GET requests from the email approval links.
    Query params: action=approve|reject, token=<task_token>
    """
    # Parse query string from Function URL event
    params = event.get("queryStringParameters", {}) or {}
    action = params.get("action", "")
    token = params.get("token", "")

    if not token or not action:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/html"},
            "body": "<html><body><h2>Missing parameters.</h2><p>This link may have expired or is invalid.</p></body></html>",
        }

    try:
        if action == "approve":
            sfn.send_task_success(
                taskToken=token,
                output=json.dumps({"approved": True}),
            )
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "text/html"},
                "body": "<html><body><h2>Draft approved!</h2><p>The post is being published to your blog. It will be live in a few minutes.</p></body></html>",
            }
        elif action == "reject":
            sfn.send_task_failure(
                taskToken=token,
                error="Rejected",
                cause="Draft rejected by reviewer via email link",
            )
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "text/html"},
                "body": "<html><body><h2>Draft rejected.</h2><p>The draft has been discarded. You can trigger a new one anytime.</p></body></html>",
            }
        else:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "text/html"},
                "body": f"<html><body><h2>Unknown action: {action}</h2></body></html>",
            }
    except sfn.exceptions.TaskTimedOut:
        return {
            "statusCode": 410,
            "headers": {"Content-Type": "text/html"},
            "body": "<html><body><h2>This review has expired.</h2><p>The task timed out. Please trigger a new draft.</p></body></html>",
        }
    except sfn.exceptions.InvalidToken:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/html"},
            "body": "<html><body><h2>Invalid or already used token.</h2><p>This draft may have already been approved or rejected.</p></body></html>",
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html"},
            "body": f"<html><body><h2>Error</h2><p>{str(e)}</p></body></html>",
        }
