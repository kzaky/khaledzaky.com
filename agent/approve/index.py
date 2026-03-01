"""
Approve Lambda — Handles approval, rejection, and revision requests for blog drafts
via API Gateway. Called from links in the SNS review email.

Actions:
  - approve: Publishes the draft
  - reject: Discards the draft
  - revise: Shows a feedback form
  - submit_revision: Sends feedback back to the pipeline for a revised draft
"""

import html
import json
import urllib.parse

import boto3

sfn = boto3.client("stepfunctions")

MAX_FEEDBACK_LENGTH = 5000

STYLE = """
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; }
  h2 { margin-bottom: 8px; }
  p { color: #555; line-height: 1.6; }
  textarea { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; font-family: inherit; resize: vertical; }
  button { background: #2563eb; color: white; border: none; padding: 10px 24px; border-radius: 8px; font-size: 14px; cursor: pointer; margin-top: 12px; }
  button:hover { background: #1d4ed8; }
</style>
"""


def handler(event, context):
    """
    Handles GET/POST requests from the email approval links.
    GET with action=approve|reject|revise → shows confirmation page (no side effects)
    POST with action=approve|reject|submit_revision → executes the action
    """
    http_method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

    if http_method == "POST":
        body = event.get("body", "") or ""
        if event.get("isBase64Encoded"):
            import base64
            body = base64.b64decode(body).decode("utf-8")
        params = dict(urllib.parse.parse_qsl(body))
    else:
        params = event.get("queryStringParameters", {}) or {}

    action = params.get("action", "")
    token = params.get("token", "")

    if not token or not action:
        return _html(400, "<h2>Missing parameters.</h2><p>This link may have expired or is invalid.</p>")

    # Escape token for safe embedding in hidden form fields
    safe_token = html.escape(token, quote=True)

    try:
        # --- GET requests show confirmation pages (safe, no side effects) ---
        if http_method == "GET":
            if action == "approve":
                return _html(200, f"""
                    <h2>Approve this draft?</h2>
                    <p>The post will be published to your blog and go live in a few minutes.</p>
                    <form method="POST" action="">
                      <input type="hidden" name="action" value="approve" />
                      <input type="hidden" name="token" value="{safe_token}" />
                      <button type="submit">Confirm &amp; Publish</button>
                    </form>""")

            elif action == "reject":
                return _html(200, f"""
                    <h2>Reject this draft?</h2>
                    <p>The draft will be discarded. You can trigger a new one anytime.</p>
                    <form method="POST" action="">
                      <input type="hidden" name="action" value="reject" />
                      <input type="hidden" name="token" value="{safe_token}" />
                      <button type="submit" style="background:#dc2626;">Confirm Rejection</button>
                    </form>""")

            elif action == "revise":
                return _html(200, f"""
                    <h2>Request Revisions</h2>
                    <p>Describe what you'd like changed. The agent will research further and produce a revised draft.</p>
                    <form method="POST" action="">
                      <input type="hidden" name="action" value="submit_revision" />
                      <input type="hidden" name="token" value="{safe_token}" />
                      <textarea name="feedback" rows="6" maxlength="5000" placeholder="e.g., Make the intro stronger, add a section on cost implications, tone down the technical jargon..."></textarea>
                      <br/>
                      <button type="submit">Send Feedback &amp; Revise</button>
                    </form>""")

            else:
                return _html(400, f"<h2>Unknown action: {html.escape(action)}</h2>")

        # --- POST requests execute the action ---
        if action == "approve":
            sfn.send_task_success(
                taskToken=token,
                output=json.dumps({"approved": True}),
            )
            return _html(200, "<h2>Draft approved!</h2><p>The post is being published to your blog. It will be live in a few minutes.</p>")

        elif action == "reject":
            sfn.send_task_failure(
                taskToken=token,
                error="Rejected",
                cause="Draft rejected by reviewer via email link",
            )
            return _html(200, "<h2>Draft rejected.</h2><p>The draft has been discarded. You can trigger a new one anytime.</p>")

        elif action == "submit_revision":
            feedback = params.get("feedback", "").strip()
            if not feedback:
                return _html(400, "<h2>Please provide feedback.</h2><p>Go back and describe what you'd like changed.</p>")
            if len(feedback) > MAX_FEEDBACK_LENGTH:
                feedback = feedback[:MAX_FEEDBACK_LENGTH]

            sfn.send_task_success(
                taskToken=token,
                output=json.dumps({"approved": False, "revise": True, "feedback": feedback}),
            )
            return _html(200, "<h2>Feedback sent!</h2><p>The agent is revising the draft based on your feedback. You'll receive a new email with the updated version shortly.</p>")

        else:
            return _html(400, f"<h2>Unknown action: {html.escape(action)}</h2>")

    except sfn.exceptions.TaskTimedOut:
        return _html(410, "<h2>This review has expired.</h2><p>The task timed out. Please trigger a new draft.</p>")
    except sfn.exceptions.InvalidToken:
        return _html(400, "<h2>Invalid or already used token.</h2><p>This draft may have already been approved or rejected.</p>")
    except Exception as e:
        return _html(500, f"<h2>Error</h2><p>{html.escape(str(e))}</p>")


def _html(status_code, body_content):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "text/html",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'",
        },
        "body": f"<html><head>{STYLE}</head><body>{body_content}</body></html>",
    }
