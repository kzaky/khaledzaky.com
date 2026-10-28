"""Shared Bedrock invocation helpers for the Blog Agent Lambdas.

Every model call in the pipeline goes through this module, so the request shape,
per-model capability handling (temperature, thinking, effort), stop_reason checks,
retries/fallback and usage logging live in exactly one place:

  * ``invoke`` builds and sends one Anthropic Messages request through
    ``bedrock-runtime`` InvokeModel and returns an ``LLMText``;
  * ``invoke_model`` / ``invoke_with_thinking`` are the two call shapes the handlers
    use (plain generation, and a planning pass with thinking on);
  * ``invoke_with_opus_fallback`` is the Opus -> Sonnet wrapper for the two heavy
    creative passes, and reports which model actually served the call;
  * ``converse`` / ``invoke_judge`` are the cross-family judge path (Converse API);
  * ``emit_opus_fallback_metric`` feeds the OpusModelFallback alarm.

This module is VENDORED into each Lambda deployment package at build time by
``scripts/package-lambda.sh`` (driven by the function's ``.common-deps`` file),
so at runtime it lands next to ``index.py`` at the zip root and imports as a
top-level module:

    from llm import invoke_model, invoke_with_opus_fallback

Keeping it self-contained (no imports from sibling Lambda code) is what lets the
``test_handler_imports_in_lambda_isolation`` check keep reproducing the real
Lambda import root.

Model capabilities (the 5.5 generation changed the request surface)
-------------------------------------------------------------------
* Opus 5.5 / Sonnet 5.5 / Haiku 5.5 reject ``temperature`` (400), think adaptively
  even when ``thinking`` is omitted, and reject ``{"type": "disabled"}`` and
  ``budget_tokens``. ``output_config.effort`` is the control; Opus 5.5 defaults to
  ``medium``, Sonnet 5.5 to ``high``, so every call here sets it explicitly.
* Thinking tokens count toward ``max_tokens``, so on models that think by default
  ``invoke`` adds headroom on top of the caller's reply budget (unused headroom is
  not billed).
* A response can start with ``thinking`` blocks: text is read by block type, never
  as ``content[0]``.
* 4.x models keep the request shape they had before (temperature where accepted, no
  effort), so rolling the SSM model parameters back to 4.6 restores 4.6 behaviour.
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

# read_timeout covers the longest single non-streaming Bedrock generation; the 3
# internal boto retries absorb sub-second transient throttles before our own backoff
# runs. BEDROCK_READ_TIMEOUT raises it without a code change if thinking at a higher
# effort pushes the Opus draft past it.
_READ_TIMEOUT = int(os.environ.get("BEDROCK_READ_TIMEOUT", "240"))
_BEDROCK_CONFIG = Config(read_timeout=_READ_TIMEOUT, connect_timeout=10, retries={"max_attempts": 3})
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION, config=_BEDROCK_CONFIG)

ANTHROPIC_VERSION = "bedrock-2023-05-31"
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

# Lazy CloudWatch client — created on first fallback so healthy runs pay no
# cold-start cost for a client they never use.
_cw = None


class LLMError(Exception):
    """A model call returned, but its output can't be used as-is."""

    def __init__(self, message, *, model_id=None, stop_reason=None, text=""):
        super().__init__(message)
        self.model_id = model_id
        self.stop_reason = stop_reason
        self.text = text


class LLMTruncatedError(LLMError):
    """stop_reason == "max_tokens": the reply was cut off mid-output."""


class LLMRefusalError(LLMError):
    """stop_reason == "refusal": a safety classifier declined the request."""


class LLMText(str):
    """The reply text, carrying which model produced it and why it stopped.

    A ``str`` subclass so every caller that treats the reply as text keeps working;
    callers that need the metadata (draft/research log the model that actually ran)
    read ``.model_id`` / ``.stop_reason`` / ``.usage`` / ``.fell_back``."""

    model_id = None
    stop_reason = None
    usage = None
    fell_back = False

    @classmethod
    def build(cls, text, *, model_id, stop_reason=None, usage=None, fell_back=False):
        out = cls(text)
        out.model_id = model_id
        out.stop_reason = stop_reason
        out.usage = usage or {}
        out.fell_back = fell_back
        return out


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


# ---------------------------------------------------------------------------
# Per-model capabilities
# ---------------------------------------------------------------------------

# claude-<family>-<major>[-<minor>] — minor is 1-2 digits, so a date (claude-sonnet-4-
# 20250514) is never read as a minor version. Works for bare (claude-opus-5-5), us./
# global. profile (us.anthropic.claude-haiku-4-5-20251001-v1:0) and anthropic. ids.
_CLAUDE_ID_RE = re.compile(r"claude-(opus|sonnet|haiku|fable|mythos)-(\d+)(?:-(\d{1,2}))?(?=[-:.]|$)", re.IGNORECASE)


def model_capabilities(model_id):
    """What request shape this model accepts. Unknown / non-Anthropic ids get the
    permissive defaults (temperature yes, no effort, thinking negotiated)."""
    m = _CLAUDE_ID_RE.search(model_id or "")
    if not m:
        return {"anthropic": False, "family": None, "version": None, "temperature": True,
                "effort": False, "thinking": "negotiate", "thinks_by_default": False}
    family = m.group(1).lower()
    version = (int(m.group(2)), int(m.group(3) or 0))
    gen5 = version[0] >= 5
    top_tier = family in ("opus", "fable", "mythos")
    return {
        "anthropic": True,
        "family": family,
        "version": version,
        # Opus-class models have rejected temperature since 4.x; every 5-generation
        # model (Sonnet 5.5 and Haiku 5.5 included) rejects it.
        "temperature": not (top_tier or gen5),
        # Effort is sent to the 5-generation only, so a rollback to 4.6 restores the
        # exact 4.6 request (no effort). Haiku 4.5 rejects it outright.
        "effort": gen5,
        # Adaptive is the only thinking shape from 4.6 on (budget_tokens is a 400 on
        # 5.x); Haiku 4.5 and older still need enabled + budget_tokens.
        "thinking": "adaptive" if (gen5 or (family != "haiku" and version >= (4, 6))) else "enabled",
        # 5-generation models think adaptively even with ``thinking`` omitted, and
        # Opus 5.5 / Sonnet 5.5 can't disable it, so max_tokens needs headroom.
        "thinks_by_default": gen5,
    }


def supports_temperature(model_id):
    """Opus-class and 5-generation Claude models reject an explicit ``temperature``
    (400 ValidationException). Sonnet/Haiku 4.x accept it."""
    return model_capabilities(model_id)["temperature"]


# Thinking budget the model may spend before the reply, by effort. Added to the
# caller's reply budget on models that think by default; only generated tokens bill.
_THINKING_HEADROOM = {"low": 2048, "medium": 8192, "high": 16000, "xhigh": 32000, "max": 32000, None: 8192}

# Request features a model rejected with a ValidationException naming them, learned
# per container: {model_id: {"effort", "temperature", "cache_control"}}.
_UNSUPPORTED = {}
# Which thinking request shape a model accepts, learned on first call per container.
_THINKING_MODE = {}
_temperature_warned = set()

_PROMPT_CACHE = os.environ.get("PROMPT_CACHE", "1") != "0"
# Below ~1024 tokens' worth of text a prefix can't reach any model's cache minimum
# (512 tokens on the 5.5 generation, 1024-4096 on 4.x); skip the marker.
_MIN_CACHE_CHARS = 2000


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

_THROTTLE_MARKERS = ("ThrottlingException", "TooManyRequestsException", "Too many tokens", "Too many requests")
_UNAVAILABLE_MARKERS = ("AccessDeniedException", "ResourceNotFoundException", "ServiceUnavailableException",
                        "ModelNotReadyException")
_TIMEOUT_MARKERS = ("ModelTimeoutException", "ReadTimeoutError", "ReadTimeout", "ConnectTimeoutError")


def _error_text(exc):
    code = ""
    resp = getattr(exc, "response", None)
    if isinstance(resp, dict):
        code = str((resp.get("Error") or {}).get("Code", ""))
    return f"{code} {type(exc).__name__} {exc}"


def error_kind(exc):
    """'throttle' | 'unavailable' | 'timeout' | None. A ValidationException is never
    a fallback reason: it means the request itself is wrong (a temperature the model
    rejects, a bad thinking shape, an unknown model id), and retrying the same body on
    another model only hides that."""
    text = _error_text(exc)
    if "ValidationException" in text:
        return None
    if any(k in text for k in _THROTTLE_MARKERS):
        return "throttle"
    if any(k in text for k in _UNAVAILABLE_MARKERS):
        return "unavailable"
    if any(k in text for k in _TIMEOUT_MARKERS):
        return "timeout"
    return None


def _rejected_feature(exc, body):
    """If a ValidationException names a request field we sent, which one. Used to drop
    that field for this model and retry the SAME model once; never a model fallback."""
    text = _error_text(exc)
    if "ValidationException" not in text:
        return None
    low = text.lower()
    if "output_config" in body and ("effort" in low or "output_config" in low):
        return "effort"
    if "thinking" in body and ("thinking" in low or "adaptive" in low or "budget" in low):
        return "thinking"
    if "temperature" in body and "temperature" in low:
        return "temperature"
    if "cache_control" in json.dumps(body.get("messages", [])) and ("cache" in low):
        return "cache_control"
    return None


# ---------------------------------------------------------------------------
# Core call
# ---------------------------------------------------------------------------

def _text_of(result):
    return "\n".join(b.get("text", "") for b in result.get("content", []) if b.get("type", "text") == "text").strip()


def _user_content(prompt, cache_through, use_cache):
    """Plain string, or two text blocks with a cache breakpoint after the static
    prefix (everything up to and including the first ``cache_through``)."""
    if not (use_cache and cache_through):
        return prompt
    idx = prompt.find(cache_through)
    if idx < 0:
        return prompt
    cut = idx + len(cache_through)
    head, tail = prompt[:cut], prompt[cut:]
    if len(head) < _MIN_CACHE_CHARS or not tail.strip():
        return prompt
    return [
        {"type": "text", "text": head, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": tail},
    ]


def _build_body(prompt, *, model_id, max_tokens, temperature, effort, thinking, budget_tokens,
                system, cache_through):
    caps = model_capabilities(model_id)
    unsupported = _UNSUPPORTED.get(model_id, set())
    body = {"anthropic_version": ANTHROPIC_VERSION, "max_tokens": max_tokens}
    if system:
        body["system"] = system

    thinking_mode = None
    if thinking:
        thinking_mode = _THINKING_MODE.get(model_id) or (
            "adaptive" if caps["thinking"] in ("adaptive", "negotiate") else "enabled")
        forced = os.environ.get("THINKING_MODE", "").strip().lower()
        if forced in ("adaptive", "enabled"):
            thinking_mode = forced
        if thinking_mode == "adaptive":
            body["thinking"] = {"type": "adaptive"}
        else:
            body["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
            body["max_tokens"] = max(max_tokens, budget_tokens + 500)

    send_effort = effort if (effort and caps["effort"] and "effort" not in unsupported) else None
    if send_effort:
        body["output_config"] = {"effort": send_effort}
    if caps["thinks_by_default"]:
        body["max_tokens"] = max_tokens + _THINKING_HEADROOM.get(send_effort, _THINKING_HEADROOM[None])

    if thinking and caps["temperature"] and "temperature" not in unsupported:
        body["temperature"] = 1  # thinking requires temperature 1 where it is accepted
    elif temperature is not None and not thinking:
        if caps["temperature"] and "temperature" not in unsupported:
            body["temperature"] = temperature
        elif model_id not in _temperature_warned:
            _temperature_warned.add(model_id)
            logger.info(json.dumps({"event": "temperature_omitted", "model": model_id}))

    use_cache = _PROMPT_CACHE and caps["anthropic"] and "cache_control" not in unsupported
    body["messages"] = [{"role": "user", "content": _user_content(prompt, cache_through, use_cache)}]
    return body, thinking_mode


def _log_call(label, model_id, result, started, *, fell_back_from=None):
    usage = result.get("usage") or {}
    entry = {
        "event": "llm_call",
        "label": label,
        "model": model_id,
        "stop_reason": result.get("stop_reason"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
        "latency_ms": int((time.monotonic() - started) * 1000),
    }
    if fell_back_from:
        entry["fell_back_from"] = fell_back_from
    logger.info(json.dumps(entry))
    return usage


def invoke(prompt, *, model_id, max_tokens=8192, label="invoke", temperature=None, effort=None,
           thinking=False, budget_tokens=2000, system=None, cache_through=None,
           allow_truncation=False, _fell_back_from=None):
    """One Anthropic Messages call through Bedrock InvokeModel. Returns ``LLMText``.

    ``max_tokens`` is the REPLY budget; on models that think by default, thinking
    headroom is added on top. ``effort`` (low..max) is sent only to models that take
    it. ``temperature`` is dropped where the model rejects it. ``cache_through`` marks
    a static prompt prefix (ending at that substring) for prompt caching.

    Raises ``LLMTruncatedError`` on stop_reason ``max_tokens`` unless
    ``allow_truncation`` (then the partial text is returned with ``.stop_reason``
    set), and ``LLMRefusalError`` on ``refusal``. Bedrock errors propagate unchanged
    except a ValidationException that names a field we sent (effort, thinking shape,
    temperature, cache_control): that field is dropped for this model and the same
    model is retried once per field."""
    if effort is not None and effort not in EFFORT_LEVELS:
        raise ValueError(f"unknown effort {effort!r}")
    for _attempt in range(5):
        body, thinking_mode = _build_body(
            prompt, model_id=model_id, max_tokens=max_tokens, temperature=temperature, effort=effort,
            thinking=thinking, budget_tokens=budget_tokens, system=system, cache_through=cache_through)
        started = time.monotonic()
        try:
            response = bedrock.invoke_model(
                modelId=model_id, contentType="application/json", accept="application/json",
                body=json.dumps(body),
            )
        except Exception as e:
            feature = _rejected_feature(e, body)
            if feature is None:
                raise
            if feature == "thinking":
                if thinking_mode == "enabled" or os.environ.get("THINKING_MODE", "").strip():
                    raise
                _THINKING_MODE[model_id] = "enabled"
            else:
                _UNSUPPORTED.setdefault(model_id, set()).add(feature)
            logger.warning(json.dumps({"event": "llm_capability_downgraded", "label": label, "model": model_id,
                                       "feature": feature, "error": str(e)[:160]}))
            continue
        result = json.loads(response["body"].read())
        if thinking:
            _THINKING_MODE[model_id] = thinking_mode
        usage = _log_call(label, model_id, result, started, fell_back_from=_fell_back_from)
        text = _text_of(result)
        stop_reason = result.get("stop_reason")
        if stop_reason == "max_tokens" and not allow_truncation:
            raise LLMTruncatedError(
                f"{label}: {model_id} hit max_tokens ({body['max_tokens']}); output truncated",
                model_id=model_id, stop_reason=stop_reason, text=text)
        if stop_reason == "refusal":
            details = result.get("stop_details") or {}
            raise LLMRefusalError(f"{label}: {model_id} declined (category={details.get('category')})",
                                  model_id=model_id, stop_reason=stop_reason, text=text)
        return LLMText.build(text, model_id=model_id, stop_reason=stop_reason, usage=usage,
                             fell_back=_fell_back_from is not None)
    raise LLMError(f"{label}: {model_id} kept rejecting the request shape", model_id=model_id)


def invoke_model(prompt, *, model_id, temperature=0.8, max_tokens=8192, effort=None, label="invoke",
                 system=None, cache_through=None, allow_truncation=False):
    """Single-shot text generation. ``temperature`` is dropped for models that reject
    it (every 5-generation model); ``effort`` is sent to models that take it."""
    return invoke(prompt, model_id=model_id, max_tokens=max_tokens, label=label, temperature=temperature,
                  effort=effort, system=system, cache_through=cache_through, allow_truncation=allow_truncation)


def invoke_with_thinking(prompt, *, model_id, max_tokens, budget_tokens=2000, label="thinking", effort="medium"):
    """Planning call with thinking on, surviving model bumps.

    Sends ``{"type": "adaptive"}`` to models that take it (4.6+ and the whole 5
    generation, which reject ``budget_tokens``) and ``enabled`` + ``budget_tokens``
    to older ones; an id this module can't classify tries adaptive first and falls
    back to the legacy shape on a ValidationException that names thinking, remembering
    the working shape for the rest of the container. ``THINKING_MODE`` env forces one.
    Returns the text blocks only (thinking blocks are discarded)."""
    return invoke(prompt, model_id=model_id, max_tokens=max_tokens, label=label, thinking=True,
                  budget_tokens=budget_tokens, effort=effort)


# ---------------------------------------------------------------------------
# Cross-family judge (Bedrock Converse)
# ---------------------------------------------------------------------------
# The rubric panel's taste seats should not be graded by the family that wrote the
# draft ("Your Judge Is Not an Independent Reviewer"). Converse is model-agnostic, so
# a seat can run on a non-Anthropic Bedrock model and fall back to Sonnet only once
# every configured candidate is unavailable.
#
# There is no API signal for "which Bedrock model is currently the most capable" —
# list-foundation-models returns modalities and lifecycle status, not a quality tier.
# So JUDGE_MODEL_ID (or JUDGE_MODEL_ID_<SEAT>) is a comma-separated PRIORITY LIST,
# tried in order per invocation: prepend a newer frontier model as one lands on
# Bedrock and the pipeline picks it up immediately, with every model behind it (down
# to the Anthropic fallback) still available if it turns out not to be accessible.
# scripts/update-judge-model.sh discovers and maintains this list against the live
# account/region; the default below is the one third-party Bedrock model this code
# has verified access to — it is a starting point, not a claim about what's "best".
# Ordered fallback chain, every entry verified invokable via Converse in the target
# account on 2026-09-10. gpt-oss is ON_DEMAND so it takes the bare, unprefixed id; the
# "us."-prefixed form of it does not exist and was removed after probing returned
# ValidationException for it. Ordering is a starting hypothesis to be settled by the
# judge-calibration pass over agent/evals, not a claim that bigger is a better judge.
# scripts/update-judge-model.sh re-probes and rewrites this via SSM/env at any time.
_DEFAULT_JUDGE_CANDIDATES = (
    "mistral.mistral-large-3-675b-instruct",
    "us.meta.llama4-maverick-17b-instruct-v1:0",
    "openai.gpt-oss-120b-1:0",
)

_judge_fallback_notified = set()


def judge_candidates_for(seat):
    """Ordered list of non-Anthropic model ids to try for this seat, most-preferred
    first. A seat-specific env (JUDGE_MODEL_ID_<SEAT>) wins outright over the shared
    JUDGE_MODEL_ID; either may be a single id or a comma-separated list."""
    seat_key = f"JUDGE_MODEL_ID_{re.sub(r'[^A-Z0-9]', '_', seat.upper())}"
    raw = os.environ.get(seat_key) or os.environ.get("JUDGE_MODEL_ID") or ""
    candidates = [c.strip() for c in raw.split(",") if c.strip()]
    return candidates or list(_DEFAULT_JUDGE_CANDIDATES)


def converse(prompt, *, model_id, max_tokens=4000, system=None, label="converse"):
    """Model-agnostic text generation through the Bedrock Converse API. Returns the
    concatenated text blocks; reasoning blocks (gpt-oss) are skipped. Raises
    ``LLMTruncatedError`` when the model stops on max_tokens."""
    kwargs = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens},
    }
    if system:
        kwargs["system"] = [{"text": system}]
    if supports_temperature(model_id):
        kwargs["inferenceConfig"]["temperature"] = 0.0
    started = time.monotonic()
    response = bedrock.converse(**kwargs)
    usage = response.get("usage") or {}
    stop_reason = response.get("stopReason")
    logger.info(json.dumps({
        "event": "llm_call", "label": label, "model": model_id, "api": "converse",
        "stop_reason": stop_reason, "input_tokens": usage.get("inputTokens"),
        "output_tokens": usage.get("outputTokens"),
        "cache_read_input_tokens": usage.get("cacheReadInputTokens", 0),
        "cache_creation_input_tokens": usage.get("cacheWriteInputTokens", 0),
        "latency_ms": int((time.monotonic() - started) * 1000),
    }))
    blocks = response.get("output", {}).get("message", {}).get("content", [])
    text = "\n".join(b["text"] for b in blocks if isinstance(b, dict) and "text" in b).strip()
    if stop_reason == "max_tokens":
        raise LLMTruncatedError(f"{label}: {model_id} hit max_tokens ({max_tokens})",
                                model_id=model_id, stop_reason=stop_reason, text=text)
    return text


def _judge_candidate_unusable(exc):
    """A judge candidate is skipped when it is unavailable/throttled/timing out, or
    when Bedrock rejects the model ID itself (not entitled here, wrong id form,
    on-demand not supported). Any other ValidationException is a request bug and
    propagates."""
    if error_kind(exc):
        return True
    text = _error_text(exc).lower()
    return "validationexception" in text and any(
        k in text for k in ("model identifier", "model id", "on-demand throughput", "not supported for this model"))


def invoke_judge(prompt, *, seat, fallback_model_id, max_tokens=4000, system=None, effort="medium"):
    """Try each configured non-Anthropic candidate for this seat, in priority order,
    falling back to the Anthropic fallback_model_id only once every candidate is
    unavailable (not enabled, wrong region, throttled, or simply doesn't exist).
    Returns (text, model_id_used)."""
    last_exc = None
    for primary in judge_candidates_for(seat):
        try:
            return converse(prompt, model_id=primary, max_tokens=max_tokens, system=system,
                            label=f"judge_{seat}"), primary
        except Exception as e:
            if isinstance(e, LLMError) or not _judge_candidate_unusable(e):
                raise
            last_exc = e
            if primary not in _judge_fallback_notified:
                _judge_fallback_notified.add(primary)
                logger.warning(json.dumps({"event": "judge_candidate_unavailable", "seat": seat, "model": primary, "error": str(e)[:160]}))
    logger.warning(json.dumps({"event": "judge_fallback_to_anthropic", "seat": seat, "fallback": fallback_model_id, "last_error": str(last_exc)[:160] if last_exc else None}))
    full = f"{system}\n\n{prompt}" if system else prompt
    return invoke_model(full, model_id=fallback_model_id, temperature=0.0, max_tokens=max_tokens,
                        effort=effort, label=f"judge_{seat}"), fallback_model_id


# ---------------------------------------------------------------------------
# Opus -> Sonnet fallback for the heavy creative passes
# ---------------------------------------------------------------------------

def invoke_with_opus_fallback(prompt, *, primary_model_id, fallback_model_id, label,
                              max_tokens=8192, temperature=None, effort="medium", cache_through=None):
    """Invoke the primary (Opus) model, falling back to ``fallback_model_id``
    (Sonnet) only when Opus is throttled, unavailable (access denied, not found,
    service unavailable, not ready) or timing out.

    A ValidationException never falls back: it means the request is wrong for the
    model (temperature, thinking shape, an invalid model id from a bad bump), and
    the same body would be just as wrong on Sonnet. Truncation and refusals raise.

    boto3 already does 3 internal retries with exponential backoff for the
    sub-second transient throttles. If those still fail, fall back immediately
    rather than burning Lambda timeout on long outer waits — when Opus is
    quota-saturated the wait never helps, and the post-generation passes need
    every second of the Lambda budget. Set ``OPUS_OUTER_RETRY_DELAYS`` (e.g.
    "45,90") to restore the longer-wait behaviour once Opus quota is healthy.

    Returns ``LLMText``; ``.model_id`` is the model that actually produced the text
    and ``.fell_back`` says whether that was the fallback."""
    delays_env = os.environ.get("OPUS_OUTER_RETRY_DELAYS", "")
    delays = [int(x) for x in delays_env.split(",") if x.strip().isdigit()] if delays_env else []
    for attempt in range(len(delays) + 1):
        try:
            return invoke(prompt, model_id=primary_model_id, max_tokens=max_tokens, label=label,
                          temperature=temperature, effort=effort, cache_through=cache_through)
        except LLMError:
            raise
        except Exception as e:
            kind = error_kind(e)
            if kind is None:
                raise
            if kind == "throttle" and attempt < len(delays):
                wait = delays[attempt]
                logger.warning(json.dumps({"event": f"{label}_throttled", "attempt": attempt + 1, "wait_seconds": wait}))
                time.sleep(wait)
                continue
            reason = {"throttle": "opus_throttled", "unavailable": "opus_unavailable", "timeout": "opus_timeout"}[kind]
            logger.warning(json.dumps({"event": f"{label}_fallback_sonnet", "reason": reason,
                                       "primary_model": primary_model_id, "fallback_model": fallback_model_id,
                                       "error": str(e)[:160]}))
            if kind == "unavailable":
                emit_opus_fallback_metric(primary_model_id)
            return invoke(prompt, model_id=fallback_model_id, max_tokens=max_tokens, label=label,
                          temperature=temperature, effort=effort, cache_through=cache_through,
                          _fell_back_from=primary_model_id)
    raise RuntimeError("unreachable")  # pragma: no cover
