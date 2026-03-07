"""
Alarm Formatter Lambda — Intercepts CloudWatch alarm SNS messages,
enriches them with Step Functions execution context, and sends
a clean, actionable email via a dedicated alerts SNS topic.
"""

import json
import logging
import os
from datetime import datetime, timezone

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
        try:
            input_data = json.loads(detail.get("input", "{}"))
        except Exception:
            pass

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


def _format_pipeline_alarm(alarm_data):
    """Format a pipeline failure alarm into a readable email."""
    alarm_name = alarm_data.get("AlarmName", "Unknown Alarm")
    alarm_desc = alarm_data.get("AlarmDescription", "")
    new_state = alarm_data.get("NewStateValue", "")
    reason = alarm_data.get("NewStateReason", "")
    timestamp = alarm_data.get("StateChangeTime", "")

    # If going to OK state, send a short recovery notice
    if new_state == "OK":
        subject = f"✅ RECOVERED: {alarm_name}"
        body = f"Alarm '{alarm_name}' has returned to OK state.\n\nTime: {timestamp}"
        return subject, body

    # ALARM state — enrich with context
    subject = f"🚨 ALARM: {alarm_name}"

    lines = [
        f"Alarm:   {alarm_name}",
        f"Status:  {new_state}",
        f"Time:    {timestamp}",
        f"Detail:  {alarm_desc}",
        "",
        f"Reason:  {reason}",
    ]

    # If it's a pipeline failure, get execution context
    if "pipeline" in alarm_name.lower():
        exec_info = _get_recent_failed_execution()
        if exec_info:
            lines.append("")
            lines.append("─── Execution Details ───")
            lines.append("")

            # Classify the error
            err = exec_info["error"]
            if err == "States.Timeout":
                lines.append("⏰  HITL TIMEOUT — Draft expired without approval")
                lines.append("")
                lines.append("Action: No action needed. The draft sat in the")
                lines.append("        approval queue for 7 days with no response.")
                subject = f"⏰ TIMEOUT: Draft expired — {exec_info.get('topic', 'unknown topic')}"
            else:
                lines.append(f"Error:   {err}")
                if exec_info["cause"]:
                    lines.append(f"Cause:   {exec_info['cause']}")

            if exec_info["failed_state"]:
                lines.append(f"State:   {exec_info['failed_state']}")
            if exec_info["topic"]:
                lines.append(f"Topic:   {exec_info['topic']}")
            lines.append(f"Started: {exec_info['started']}")
            lines.append(f"Stopped: {exec_info['stopped']}")
            lines.append("")
            lines.append(f"Console: {exec_info['console_url']}")

    lines.append("")
    lines.append("─── Quick Actions ───")
    lines.append("")
    lines.append(f"• View alarm:  https://{REGION}.console.aws.amazon.com/cloudwatch/home?region={REGION}#alarmsV2:alarm/{alarm_name}")
    lines.append(f"• View logs:   https://{REGION}.console.aws.amazon.com/cloudwatch/home?region={REGION}#logsV2:log-groups")

    body = "\n".join(lines)
    return subject, body


def _format_lambda_alarm(alarm_data):
    """Format a Lambda error alarm."""
    alarm_name = alarm_data.get("AlarmName", "Unknown")
    new_state = alarm_data.get("NewStateValue", "")
    timestamp = alarm_data.get("StateChangeTime", "")
    reason = alarm_data.get("NewStateReason", "")

    if new_state == "OK":
        return f"✅ RECOVERED: {alarm_name}", f"Lambda errors cleared.\n\nTime: {timestamp}"

    subject = f"🚨 ALARM: {alarm_name}"
    lines = [
        f"Alarm:   {alarm_name}",
        f"Status:  {new_state}",
        f"Time:    {timestamp}",
        "",
        f"Reason:  {reason}",
        "",
        "─── Quick Actions ───",
        "",
        "Check recent Lambda errors:",
        f"• https://{REGION}.console.aws.amazon.com/cloudwatch/home?region={REGION}#logsV2:log-groups",
    ]
    return subject, "\n".join(lines)


def _format_api_alarm(alarm_data):
    """Format an API Gateway 5xx alarm."""
    alarm_name = alarm_data.get("AlarmName", "Unknown")
    new_state = alarm_data.get("NewStateValue", "")
    timestamp = alarm_data.get("StateChangeTime", "")
    reason = alarm_data.get("NewStateReason", "")

    if new_state == "OK":
        return f"✅ RECOVERED: {alarm_name}", f"API 5xx errors cleared.\n\nTime: {timestamp}"

    subject = f"🚨 ALARM: {alarm_name}"
    lines = [
        f"Alarm:   {alarm_name}",
        f"Status:  {new_state}",
        f"Time:    {timestamp}",
        "",
        f"Reason:  {reason}",
        "",
        "─── Quick Actions ───",
        "",
        f"• View API logs: https://{REGION}.console.aws.amazon.com/apigateway/main/apis?region={REGION}",
    ]
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
