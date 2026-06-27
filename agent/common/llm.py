"""Shared Bedrock invocation helpers for the Blog Agent Lambdas.

Single source of truth for the bits that were previously copy-pasted (and had
already drifted) between the Research and Draft handlers:

  * the configured ``bedrock-runtime`` client,
  * the plain ``invoke_model`` text-generation call,
  * the Opus -> Sonnet fallback wrapper used by the two heavy creative passes,
  * the CloudWatch ``OpusModelFallback`` metric emitter.

This module is VENDORED into each Lambda deployment package at build time by
``scripts/package-lambda.sh`` (driven by the function's ``.common-deps`` file),
so at runtime it lands next to ``index.py`` at the zip root and imports as a
top-level module:

    from llm import bedrock, invoke_with_opus_fallback

Keeping it self-contained (no imports from sibling Lambda code) is what lets the
``test_handler_imports_in_lambda_isolation`` check keep reproducing the real
Lambda import root.
"""

import json
import logging
import os
import time

import boto3
from botocore.config import Config

logger = logging.getLogger()

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# read_timeout 240s covers the longest single Bedrock generation; the 3 internal
# boto retries absorb sub-second transient throttles before our own backoff runs.
_BEDROCK_CONFIG = Config(read_timeout=240, connect_timeout=10, retries={"max_attempts": 3})
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION, config=_BEDROCK_CONFIG)

# Lazy CloudWatch client — created on first fallback so healthy runs pay no
# cold-start cost for a client they never use.
_cw = None


def emit_opus_fallback_metric(model_id):
    """Emit BlogAgent/OpusModelFallback so the CloudWatch alarm fires the moment
    Opus is inaccessible and a run silently degrades to Sonnet."""
    global _cw
    try:
        if _cw is None:
            _cw = boto3.client("cloudwatch", region_name=AWS_REGION)
        _cw.put_metric_data(
            Namespace="BlogAgent",
            MetricData=[{"MetricName": "OpusModelFallback", "Value": 1.0, "Unit": "Count",
                         "Dimensions": [{"Name": "ModelId", "Value": model_id}]}],
        )
    except Exception as metric_err:
        logger.warning(json.dumps({"event": "metric_emit_failed", "error": str(metric_err)[:100]}))


def invoke_model(prompt, *, model_id, temperature=0.8, max_tokens=8192):
    """Single-shot text generation via Bedrock ``invoke_model``.

    Pass ``temperature=None`` to omit the parameter entirely (required for the
    Opus model, which rejects an explicit temperature)."""
    body_dict = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if temperature is not None:
        body_dict["temperature"] = temperature
    response = bedrock.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body_dict),
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def invoke_with_opus_fallback(prompt, *, primary_model_id, fallback_model_id, label,
                              max_tokens=8192, temperature=None):
    """Invoke the primary (Opus) model, falling back to ``fallback_model_id``
    (Sonnet) on throttle or access errors.

    boto3 already does 3 internal retries with exponential backoff for the
    sub-second transient throttles. If those still fail, fall back immediately
    rather than burning Lambda timeout on long outer waits — when Opus is
    quota-saturated the wait never helps, and the post-generation passes need
    every second of the Lambda budget. Set ``OPUS_OUTER_RETRY_DELAYS`` (e.g.
    "45,90") to restore the longer-wait behaviour once Opus quota is healthy.

    ``label`` namespaces the structured log events (e.g. "draft", "synthesis")."""
    delays_env = os.environ.get("OPUS_OUTER_RETRY_DELAYS", "")
    delays = [int(x) for x in delays_env.split(",") if x.strip().isdigit()] if delays_env else []
    last_exc = None
    for attempt in range(len(delays) + 1):
        try:
            return invoke_model(prompt, model_id=primary_model_id, temperature=temperature, max_tokens=max_tokens)
        except Exception as e:
            err_str = str(e)
            is_throttle = "ThrottlingException" in err_str or "Too many tokens" in err_str
            is_unavailable = "AccessDeniedException" in err_str
            if is_throttle and attempt < len(delays):
                wait = delays[attempt]
                last_exc = e
                logger.warning(json.dumps({"event": f"{label}_throttled", "attempt": attempt + 1, "wait_seconds": wait}))
                time.sleep(wait)
            elif is_throttle or is_unavailable:
                reason = "opus_unavailable" if is_unavailable else "opus_throttled"
                logger.warning(json.dumps({"event": f"{label}_fallback_sonnet", "reason": reason, "fallback_model": fallback_model_id}))
                if is_unavailable:
                    emit_opus_fallback_metric(primary_model_id)
                return invoke_model(prompt, model_id=fallback_model_id, temperature=temperature, max_tokens=max_tokens)
            else:
                raise
    raise last_exc
