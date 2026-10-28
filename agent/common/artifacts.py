"""Stage artifacts: keep large stage outputs out of Step Functions state.

Step Functions caps an execution's state at 256 KB, and an oversized result fails the
execution with States.DataLimitExceeded, which skips Catch (runs ab924859 and 4e0f28a4).
So each stage writes its large fields (research notes, author content, the post body,
verification details, the evaluation) to

    s3://<DRAFTS_BUCKET>/runs/<execution name>/<stage>-<sha256[:16]>.json

and returns only the small fields the state machine reads, plus
{"key", "sha256", "summary"}. The next stage is handed a ref ({"key", "sha256"}) and
loads the fields it needs, checking the hash.

The key is content-addressed, so an artifact is never overwritten: a retry, a revise
loop or a redrive can never make an older ref point at newer bytes.

Backward compatibility: offloading only happens when the event carries `run_id`, which
only the new state machine definition sends. An execution started on the previous
definition keeps running on that definition (Step Functions pins it), so new Lambda code
invoked by it sees the old inline shape, hydrates nothing and returns the old shape.
"""

import functools
import hashlib
import json
import logging
import os
import re

import boto3

logger = logging.getLogger()

DRAFTS_BUCKET = os.environ.get("DRAFTS_BUCKET", "")
RUNS_PREFIX = "runs/"
_RUN_ID_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")

s3 = boto3.client("s3")


class ArtifactIntegrityError(Exception):
    """An artifact's bytes do not match the sha256 its ref recorded."""


def sha256_hex(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def run_id(event):
    """The execution name the state machine passed in, made safe for an S3 key; None
    when the event came from the previous definition (or a direct invoke)."""
    raw = (event or {}).get("run_id")
    if not raw:
        return None
    return _RUN_ID_UNSAFE.sub("_", str(raw))[:80]


def run_prefix(rid):
    return f"{RUNS_PREFIX}{rid}/"


def review_key(rid, markdown_sha256):
    """Where Notify stores the draft the reviewer sees, and Publish reads it back."""
    return f"{run_prefix(rid)}review-{markdown_sha256}.md"


def _bucket():
    bucket = DRAFTS_BUCKET or os.environ.get("DRAFTS_BUCKET", "")
    if not bucket:
        raise RuntimeError("DRAFTS_BUCKET not configured: cannot read or write stage artifacts")
    return bucket


def put(rid, stage, payload):
    """Write payload as a content-addressed JSON artifact; return its ref."""
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = sha256_hex(body)
    key = f"{run_prefix(rid)}{stage}-{digest[:16]}.json"
    s3.put_object(Bucket=_bucket(), Key=key, Body=body, ContentType="application/json",
                  Metadata={"sha256": digest})
    logger.info(json.dumps({"event": "artifact_written", "key": key, "bytes": len(body)}))
    return {"key": key, "sha256": digest, "bytes": len(body)}


def get(ref):
    """Load and hash-check the artifact a ref points at."""
    key = (ref or {}).get("key")
    if not key or not str(key).startswith(RUNS_PREFIX):
        raise ArtifactIntegrityError(f"artifact ref has no runs/ key: {ref!r}")
    body = s3.get_object(Bucket=_bucket(), Key=key)["Body"].read()
    expected = ref.get("sha256")
    if expected and sha256_hex(body) != expected:
        raise ArtifactIntegrityError(f"{key}: sha256 {sha256_hex(body)[:12]} does not match ref {expected[:12]}")
    return json.loads(body.decode("utf-8"))


def hydrate(event, spec):
    """Fill event fields from artifacts.

    spec maps a ref field in the event to {event_field: artifact_field}. A field already
    present inline (the old shape) wins, so a legacy event is returned unchanged. Each
    distinct artifact is loaded once.
    """
    if not spec:
        return event
    out = dict(event)
    cache = {}
    for ref_field, fields in spec.items():
        ref = event.get(ref_field)
        if not isinstance(ref, dict) or not ref.get("key"):
            continue
        needed = {dst: src for dst, src in fields.items() if dst not in event}
        if not needed:
            continue
        if ref["key"] not in cache:
            cache[ref["key"]] = get(ref)
        payload = cache[ref["key"]]
        for dst, src in needed.items():
            if src in payload:
                out[dst] = payload[src]
    return out


def _unwrap_input(event):
    """Research is the first stage, so its Parameters wrap the whole execution input as
    {"input": <input>, "run_id": <name>} (listing the fields would fail on any one a CLI
    start leaves out)."""
    if isinstance(event, dict) and isinstance(event.get("input"), dict) and "run_id" in event:
        return {**event["input"], "run_id": event["run_id"]}
    return event


def offload(event, stage, result, large, extra=None):
    """Move result's large fields into an artifact when the run uses artifacts.

    Returns the old inline result unchanged when the event has no run_id."""
    rid = run_id(event)
    if not rid or not large or not isinstance(result, dict):
        return result
    payload = {f: result[f] for f in large if f in result}
    ref = put(rid, stage, payload)
    out = {k: v for k, v in result.items() if k not in large}
    summary = {f"{f}_bytes": len(json.dumps(v, ensure_ascii=False)) for f, v in payload.items()}
    out.update(key=ref["key"], sha256=ref["sha256"], summary=summary)
    if extra:
        out.update(extra(rid, result))
    return out


def stage(name, *, inputs=None, large=(), extra=None, callback=None):
    """Decorator for a stage handler: hydrate the event, run the stage, offload its
    large fields. `callback(token, output)` sends the output for waitForTaskToken stages.

    The wrapped function is looked up at call time as `handler.core`, so tests can
    swap the stage body while keeping the real I/O wrapper."""
    def decorate(fn):
        @functools.wraps(fn)
        def wrapper(event, context):
            event = hydrate(_unwrap_input(event), inputs)
            out = offload(event, name, wrapper.core(event, context), large, extra)
            if callback and event.get("taskToken"):
                callback(event["taskToken"], out)
            return out
        wrapper.core = fn
        return wrapper
    return decorate
