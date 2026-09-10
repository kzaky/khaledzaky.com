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
import re
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


_NO_TEMPERATURE_RE = re.compile(r"opus|fable|mythos|claude-(?:sonnet|haiku)-5(?!\d)", re.IGNORECASE)
_temperature_warned = set()


def supports_temperature(model_id):
    """Opus-class and 5-generation Claude models reject an explicit ``temperature``
    (400 ValidationException). Sonnet/Haiku 4.x accept it. Checked by model id so
    scripts/update-models.sh can bump a profile without breaking every call site."""
    return not _NO_TEMPERATURE_RE.search(model_id or "")


def _text_of(result):
    return "\n".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text").strip()


# Which thinking request shape a model accepts, learned on first call per container.
_THINKING_MODE = {}


def invoke_with_thinking(prompt, *, model_id, max_tokens, budget_tokens=2000, label="thinking"):
    """Extended-thinking call that survives model bumps.

    Tries ``{"type": "adaptive"}`` first (the only shape the 5-generation models
    accept; ``budget_tokens`` is deprecated on 4.6 and rejected with a 400 on
    Sonnet 5 / Opus 5). If the model rejects it with a ValidationException, falls
    back to the legacy ``enabled`` + ``budget_tokens`` shape and remembers the
    working mode for the rest of the container. ``THINKING_MODE`` env forces one.

    Returns the concatenated text blocks (thinking blocks are discarded)."""
    forced = os.environ.get("THINKING_MODE", "").strip().lower()
    modes = [forced] if forced in ("adaptive", "enabled") else ["adaptive", "enabled"]
    if model_id in _THINKING_MODE and not forced:
        modes = [_THINKING_MODE[model_id]]

    last_exc = None
    for mode in modes:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens if mode == "adaptive" else max(max_tokens, budget_tokens + 500),
            "messages": [{"role": "user", "content": prompt}],
        }
        if mode == "adaptive":
            body["thinking"] = {"type": "adaptive"}
        else:
            body["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
        if supports_temperature(model_id):
            body["temperature"] = 1
        try:
            response = bedrock.invoke_model(
                modelId=model_id, contentType="application/json", accept="application/json",
                body=json.dumps(body),
            )
            result = json.loads(response["body"].read())
            _THINKING_MODE[model_id] = mode
            return _text_of(result)
        except Exception as e:
            last_exc = e
            err = str(e)
            rejected_shape = "ValidationException" in err and ("thinking" in err.lower() or "adaptive" in err.lower() or "budget" in err.lower())
            if rejected_shape and mode != modes[-1]:
                logger.warning(json.dumps({"event": f"{label}_mode_rejected", "mode": mode, "model": model_id, "error": err[:160]}))
                continue
            raise
    raise last_exc


# ---------------------------------------------------------------------------
# Cross-family judge (Bedrock Converse)
# ---------------------------------------------------------------------------
# The rubric panel's taste seats should not be graded by the family that wrote the
# draft ("Your Judge Is Not an Independent Reviewer"). Converse is model-agnostic, so
# a seat can run on a non-Anthropic Bedrock model (JUDGE_MODEL_ID, e.g. an OpenAI
# gpt-oss profile) and fall back to Sonnet when that model is not enabled in the
# account. Per-seat override: JUDGE_MODEL_ID_<SEAT> (seat upper-cased).

_judge_fallback_notified = set()


def judge_model_for(seat, default_fallback):
    """Resolve the model id for a panel seat: per-seat env, then JUDGE_MODEL_ID, then
    the Anthropic fallback. Returns (primary, fallback)."""
    seat_key = f"JUDGE_MODEL_ID_{re.sub(r'[^A-Z0-9]', '_', seat.upper())}"
    primary = os.environ.get(seat_key) or os.environ.get("JUDGE_MODEL_ID") or ""
    fallback = os.environ.get("JUDGE_FALLBACK_MODEL_ID") or default_fallback
    return (primary or fallback), fallback


def converse(prompt, *, model_id, max_tokens=2048, system=None):
    """Model-agnostic text generation through the Bedrock Converse API. Returns the
    concatenated text blocks; reasoning blocks (gpt-oss) are skipped."""
    kwargs = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens},
    }
    if system:
        kwargs["system"] = [{"text": system}]
    if supports_temperature(model_id):
        kwargs["inferenceConfig"]["temperature"] = 0.0
    response = bedrock.converse(**kwargs)
    blocks = response.get("output", {}).get("message", {}).get("content", [])
    return "\n".join(b["text"] for b in blocks if isinstance(b, dict) and "text" in b).strip()


def invoke_judge(prompt, *, seat, fallback_model_id, max_tokens=2048, system=None):
    """Run one panel seat on its configured model, falling back to the Anthropic model
    when the cross-family model is unavailable (not enabled, wrong region, throttled).
    Returns (text, model_id_used)."""
    primary, fallback = judge_model_for(seat, fallback_model_id)
    try:
        return converse(prompt, model_id=primary, max_tokens=max_tokens, system=system), primary
    except Exception as e:
        err = str(e)
        recoverable = any(k in err for k in ("AccessDenied", "ResourceNotFound", "ValidationException", "Throttling", "ModelNotReady", "ServiceUnavailable"))
        if primary == fallback or not recoverable:
            raise
        if primary not in _judge_fallback_notified:
            _judge_fallback_notified.add(primary)
            logger.warning(json.dumps({"event": "judge_fallback", "seat": seat, "primary": primary, "fallback": fallback, "error": err[:160]}))
        full = f"{system}\n\n{prompt}" if system else prompt
        return invoke_model(full, model_id=fallback, temperature=0.0, max_tokens=max_tokens), fallback


def invoke_model(prompt, *, model_id, temperature=0.8, max_tokens=8192):
    """Single-shot text generation via Bedrock ``invoke_model``.

    Pass ``temperature=None`` to omit the parameter entirely (required for the
    Opus model, which rejects an explicit temperature)."""
    body_dict = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if temperature is not None and not supports_temperature(model_id):
        if model_id not in _temperature_warned:
            _temperature_warned.add(model_id)
            logger.info(json.dumps({"event": "temperature_omitted", "model": model_id}))
        temperature = None
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
