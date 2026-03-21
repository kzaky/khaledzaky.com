"""
Alarm Formatter Lambda — Intercepts CloudWatch alarm SNS messages,
enriches them with Step Functions execution context, and sends
a clean, actionable email via a dedicated alerts SNS topic.
"""

import contextlib
import json
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-east-1")
ALERTS_TOPIC_ARN = os.environ["ALERTS_TOPIC_ARN"]
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")

sns = boto3.client("sns", region_name=REGION)
sfn = boto3.client("stepfunctions", region_name=REGION)
cw = boto3.client("cloudwatch", region_name=REGION)


def _get_recent_failed_execution():
    """Get the most recent failed Step Functions execution for context."""
    if not STATE_MACHINE_ARN:
        return None
    try:
        resp = sfn.list_executions(
            stateMachineArn=STATE_MACHINE_ARN,
            statusFilter="FAILED",
            maxResults=1,
        )
        execs = resp.get("executions", [])
        if not execs:
            return None

        exec_arn = execs[0]["executionArn"]
        detail = sfn.describe_execution(executionArn=exec_arn)

        # Get the last few events to find the error
        history = sfn.get_execution_history(
            executionArn=exec_arn,
            reverseOrder=True,
            maxResults=5,
        )

        error = "Unknown"
        cause = ""
        failed_state = ""
        for event in history.get("events", []):
            etype = event.get("type", "")
            if etype == "ExecutionFailed":
                ed = event.get("executionFailedEventDetails", {})
                error = ed.get("error", error)
                cause = ed.get("cause", "")
            elif etype == "TaskFailed":
                td = event.get("taskFailedEventDetails", {})
                error = td.get("error", error)
                cause = td.get("cause", cause)
            elif etype == "LambdaFunctionFailed":
                ld = event.get("lambdaFunctionFailedEventDetails", {})
                error = ld.get("error", error)
                cause = ld.get("cause", cause)
            # Find which state failed
            if "stateEnteredEventDetails" in event:
                failed_state = event["stateEnteredEventDetails"].get("name", "")

        # Parse input for topic/slug
        input_data = {}
        with contextlib.suppress(Exception):
            input_data = json.loads(detail.get("input", "{}"))

        exec_name = execs[0]["name"]
        console_url = (
            f"https://{REGION}.console.aws.amazon.com/states/home"
            f"?region={REGION}#/v2/executions/details/{exec_arn}"
        )

        return {
            "exec_name": exec_name,
            "exec_arn": exec_arn,
            "error": error,
            "cause": cause[:500] if cause else "",
            "failed_state": failed_state,
            "topic": input_data.get("topic", ""),
            "started": execs[0]["startDate"].strftime("%Y-%m-%d %H:%M UTC"),
            "stopped": execs[0]["stopDate"].strftime("%Y-%m-%d %H:%M UTC"),
            "console_url": console_url,
        }
    except Exception as e:
        logger.warning(json.dumps({"event": "sfn_query_failed", "error": str(e)[:200]}))
        return None


def _sep(title=""):
    """Section separator line."""
    if title:
        return f"\n{'─' * 4} {title} {'─' * (40 - len(title))}\n"
    return "\n" + "─" * 48 + "\n"


def _format_pipeline_alarm(alarm_data):
    """Format a pipeline failure alarm into a readable email."""
    alarm_name = alarm_data.get("AlarmName", "Unknown Alarm")
    new_state = alarm_data.get("NewStateValue", "")
    timestamp = alarm_data.get("StateChangeTime", "")

    if new_state == "OK":
        subject = f"✅ RECOVERED: {alarm_name}"
        body = f"Pipeline alarm cleared. No action needed.\n\nTime: {timestamp}"
        return subject, body

    exec_info = _get_recent_failed_execution()
    err = exec_info["error"] if exec_info else "Unknown"
    is_timeout = err == "States.Timeout"

    if is_timeout:
        topic = exec_info.get("topic", "unknown topic")
        subject = f"⏰ EXPIRED: Draft awaiting approval — {topic[:60]}"
    else:
        subject = f"🚨 PIPELINE FAILED: {alarm_name}"

    lines = []

    # WHAT
    lines.append(_sep("WHAT"))
    if is_timeout:
        lines.append("The blog pipeline stalled at the human-approval step.")
        lines.append("A draft was generated but never approved, revised, or rejected.")
        lines.append("After 7 days the execution timed out automatically.")
    else:
        lines.append("The blog agent pipeline failed during execution.")
        if exec_info and exec_info.get("failed_state"):
            lines.append(f"Failed at step: {exec_info['failed_state']}")
        if exec_info and exec_info.get("error"):
            lines.append(f"Error type:     {exec_info['error']}")

    # WHY
    lines.append(_sep("WHY"))
    if is_timeout:
        lines.append("No action was taken on the draft within the 7-day approval window.")
        lines.append("This is expected behaviour when you miss a review email.")
    elif exec_info and exec_info.get("cause"):
        lines.append(exec_info["cause"][:400])
    else:
        lines.append("Check execution history in Step Functions console for root cause.")

    # CONTEXT
    if exec_info:
        lines.append(_sep("CONTEXT"))
        if exec_info.get("topic"):
            lines.append(f"Topic:   {exec_info['topic'][:100]}")
        lines.append(f"Started: {exec_info['started']}")
        lines.append(f"Stopped: {exec_info['stopped']}")

    # ACTION
    lines.append(_sep("ACTION"))
    if is_timeout:
        lines.append("Priority: LOW — safe to ignore.")
        lines.append("")
        lines.append("If you want to publish this post, start a new pipeline run")
        lines.append("with the same topic. The draft is not recoverable from this execution.")
    else:
        lines.append("Priority: HIGH — pipeline did not complete.")
        lines.append("")
        lines.append("1. Open the execution in Step Functions to see the full error.")
        lines.append("2. Check CloudWatch logs for the failed Lambda.")
        lines.append("3. Fix the root cause and re-trigger the pipeline if needed.")

    # LINKS
    lines.append(_sep("LINKS"))
    if exec_info:
        lines.append(f"Execution:  {exec_info['console_url']}")
    lines.append(f"Alarm:      https://{REGION}.console.aws.amazon.com/cloudwatch/home?region={REGION}#alarmsV2:alarm/{alarm_name}")
    lines.append(f"Logs:       https://{REGION}.console.aws.amazon.com/cloudwatch/home?region={REGION}#logsV2:log-groups$3FlogGroupNameFilter$3D/aws/lambda/blog-agent")

    return subject, "\n".join(lines)


def _format_lambda_alarm(alarm_data):
    """Format a Lambda error alarm."""
    alarm_name = alarm_data.get("AlarmName", "Unknown")
    new_state = alarm_data.get("NewStateValue", "")
    timestamp = alarm_data.get("StateChangeTime", "")
    reason = alarm_data.get("NewStateReason", "")

    if new_state == "OK":
        return f"✅ RECOVERED: {alarm_name}", f"Lambda errors cleared. No action needed.\n\nTime: {timestamp}"

    subject = f"🚨 LAMBDA ERROR: {alarm_name}"
    lines = []

    # WHAT
    lines.append(_sep("WHAT"))
    lines.append("One or more blog agent Lambda functions threw an unhandled exception.")
    lines.append(f"Detected: {timestamp}")
    lines.append(f"Trigger:  {reason}")

    # WHY
    lines.append(_sep("WHY"))
    lines.append("Common causes:")
    lines.append("  • Bedrock API error (model throttling, token limit, config change)")
    lines.append("  • Tavily or Perplexity search failure (API key expired, quota exceeded)")
    lines.append("  • S3 permission or missing object (voice profile, draft bucket)")
    lines.append("  • Step Functions input missing expected fields")
    lines.append("  • Unhandled exception in new code deployment")

    # ACTION
    lines.append(_sep("ACTION"))
    lines.append("Priority: HIGH if pipeline is actively running. LOW if no pipeline was triggered.")
    lines.append("")
    lines.append("1. Check which Lambda threw the error (logs link below).")
    lines.append("2. Look for ERROR-level structured log lines with 'error' and 'event' fields.")
    lines.append("3. If the pipeline run failed, re-trigger after fixing the root cause.")
    lines.append("4. If this fired during a pipeline run you care about, check Step Functions.")

    # IGNORE IF
    lines.append(_sep("IGNORE IF"))
    lines.append("• Error count = 1 and correlates with a known bad input you already rejected.")
    lines.append("• Error fired during a pipeline run you intentionally stopped.")
    lines.append("• The alarm self-cleared to OK within minutes (transient Bedrock throttle).")

    # LINKS
    lines.append(_sep("LINKS"))
    lines.append(f"Lambda logs:  https://{REGION}.console.aws.amazon.com/cloudwatch/home?region={REGION}#logsV2:log-groups$3FlogGroupNameFilter$3D/aws/lambda/blog-agent")
    lines.append(f"Step Fns:     https://{REGION}.console.aws.amazon.com/states/home?region={REGION}#/statemachines")
    lines.append(f"Alarm:        https://{REGION}.console.aws.amazon.com/cloudwatch/home?region={REGION}#alarmsV2:alarm/{alarm_name}")

    return subject, "\n".join(lines)


def _format_api_alarm(alarm_data):
    """Format an API Gateway 5xx alarm."""
    alarm_name = alarm_data.get("AlarmName", "Unknown")
    new_state = alarm_data.get("NewStateValue", "")
    timestamp = alarm_data.get("StateChangeTime", "")
    reason = alarm_data.get("NewStateReason", "")

    if new_state == "OK":
        return f"✅ RECOVERED: {alarm_name}", f"API 5xx errors cleared. No action needed.\n\nTime: {timestamp}"

    subject = f"🚨 API ERROR: {alarm_name}"
    lines = []

    # WHAT
    lines.append(_sep("WHAT"))
    lines.append("The blog agent API Gateway returned one or more HTTP 5xx responses.")
    lines.append(f"Detected: {timestamp}")
    lines.append(f"Trigger:  {reason}")

    # WHY
    lines.append(_sep("WHY"))
    lines.append("Common causes:")
    lines.append("  • Approve/revise Lambda crashed during a HITL approval action")
    lines.append("  • Task token expired before the Lambda sent SendTaskSuccess/Failure")
    lines.append("  • Lambda cold-start timeout on the approve endpoint")
    lines.append("  • Step Functions execution was already in a terminal state")

    # ACTION
    lines.append(_sep("ACTION"))
    lines.append("Priority: MEDIUM — the pipeline may have stalled at the approval step.")
    lines.append("")
    lines.append("1. Check if a pipeline execution is stuck in RUNNING state.")
    lines.append("2. Check approve Lambda logs for the error.")
    lines.append("3. If the task token expired, re-trigger the pipeline with the same input.")

    # IGNORE IF
    lines.append(_sep("IGNORE IF"))
    lines.append("• Single 5xx that immediately resolved (transient Lambda cold start).")
    lines.append("• You were testing the approve endpoint manually with a bad/stale token.")
    lines.append("• The alarm self-cleared to OK within a few minutes.")

    # LINKS
    lines.append(_sep("LINKS"))
    lines.append(f"API logs:    https://{REGION}.console.aws.amazon.com/apigateway/main/apis?region={REGION}")
    lines.append(f"Lambda logs: https://{REGION}.console.aws.amazon.com/cloudwatch/home?region={REGION}#logsV2:log-groups$3FlogGroupNameFilter$3D/aws/lambda/blog-agent")
    lines.append(f"Alarm:       https://{REGION}.console.aws.amazon.com/cloudwatch/home?region={REGION}#alarmsV2:alarm/{alarm_name}")

    return subject, "\n".join(lines)


def handler(event, context):
    """SNS trigger handler — format and forward alarm notifications."""
    request_id = getattr(context, "aws_request_id", "local")

    for record in event.get("Records", []):
        message_raw = record.get("Sns", {}).get("Message", "")

        try:
            alarm_data = json.loads(message_raw)
        except json.JSONDecodeError:
            # Not a JSON message (e.g. subscription confirmation) — skip
            logger.info(json.dumps({"event": "skipped_non_json", "request_id": request_id}))
            continue

        # Only process CloudWatch alarm notifications
        if "AlarmName" not in alarm_data:
            logger.info(json.dumps({"event": "skipped_non_alarm", "request_id": request_id}))
            continue

        alarm_name = alarm_data.get("AlarmName", "")
        logger.info(json.dumps({"event": "formatting_alarm", "alarm": alarm_name, "request_id": request_id}))

        # Route to appropriate formatter
        if "pipeline" in alarm_name.lower():
            subject, body = _format_pipeline_alarm(alarm_data)
        elif "lambda" in alarm_name.lower():
            subject, body = _format_lambda_alarm(alarm_data)
        elif "api" in alarm_name.lower() or "5xx" in alarm_name.lower():
            subject, body = _format_api_alarm(alarm_data)
        else:
            subject = f"🔔 Alert: {alarm_name}"
            body = json.dumps(alarm_data, indent=2, default=str)

        # Publish formatted email
        sns.publish(
            TopicArn=ALERTS_TOPIC_ARN,
            Subject=subject[:100],  # SNS subject max 100 chars
            Message=body,
        )
        logger.info(json.dumps({"event": "alert_sent", "alarm": alarm_name, "request_id": request_id}))

    return {"status": "ok"}
