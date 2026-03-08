"""
Upload Lambda — Presigned URL file drop for personal use.
Validates a passphrase from SSM, then generates presigned S3 URLs
for upload/download, lists files, or deletes files.
"""

import json
import logging
import os

import boto3
from botocore.config import Config

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
s3 = boto3.client(
    "s3",
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
    config=Config(signature_version="s3v4"),
)

BUCKET = os.environ.get("DRAFTS_BUCKET", "blog-agent-drafts")
UPLOAD_PREFIX = "uploads/"
PASSPHRASE_PARAM = os.environ.get("PASSPHRASE_PARAM", "/blog-agent/upload-passphrase")
PRESIGN_EXPIRY = 3600  # 1 hour for upload URLs
DOWNLOAD_EXPIRY = 86400  # 24 hours for download URLs
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

# Cache passphrase across warm invocations with TTL to pick up rotations
_passphrase_cache = None
_passphrase_invocations = 0
_PASSPHRASE_TTL = 50


def _get_passphrase():
    """Retrieve upload passphrase from SSM Parameter Store. Cached with TTL so
    a rotated passphrase takes effect within _PASSPHRASE_TTL invocations."""
    global _passphrase_cache, _passphrase_invocations
    _passphrase_invocations += 1
    if _passphrase_cache is not None and _passphrase_invocations % _PASSPHRASE_TTL != 0:
        return _passphrase_cache
    try:
        resp = ssm.get_parameter(Name=PASSPHRASE_PARAM, WithDecryption=True)
        _passphrase_cache = resp["Parameter"]["Value"]
        logger.info(json.dumps({"event": "passphrase_refreshed", "invocation": _passphrase_invocations}))
        return _passphrase_cache
    except Exception as e:
        logger.error(json.dumps({"event": "passphrase_fetch_failed", "error": str(e)[:200]}))
        return _passphrase_cache


def _cors_headers():
    """Return CORS headers for the response."""
    return {
        "Access-Control-Allow-Origin": "https://khaledzaky.com",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _response(status, body):
    """Build API Gateway response."""
    return {
        "statusCode": status,
        "headers": {**_cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _validate_passphrase(payload):
    """Check passphrase from request payload. Returns True if valid."""
    provided = payload.get("passphrase", "")
    expected = _get_passphrase()
    if not expected:
        return False
    # Constant-time comparison
    import hmac
    return hmac.compare_digest(provided, expected)


def _get_upload_url(payload):
    """Generate a presigned PUT URL for S3 upload."""
    filename = payload.get("filename", "").strip()
    content_type = payload.get("content_type", "application/octet-stream")

    if not filename:
        return _response(400, {"error": "filename is required"})

    # Sanitize filename — alphanumeric, hyphens, underscores, dots only
    safe_name = "".join(c for c in filename if c.isalnum() or c in ".-_").strip()
    if not safe_name:
        return _response(400, {"error": "Invalid filename"})

    key = f"{UPLOAD_PREFIX}{safe_name}"

    try:
        url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": BUCKET,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=PRESIGN_EXPIRY,
        )
        logger.info(json.dumps({"event": "upload_url_generated", "key": key}))
        return _response(200, {"upload_url": url, "key": key})
    except Exception as e:
        logger.error(json.dumps({"event": "presign_failed", "error": str(e)[:200]}))
        return _response(500, {"error": "Failed to generate upload URL"})


def _list_files(payload):
    """List all files in the uploads prefix with presigned download URLs."""
    try:
        response = s3.list_objects_v2(Bucket=BUCKET, Prefix=UPLOAD_PREFIX)
        files = []
        for obj in response.get("Contents", []):
            key = obj["Key"]
            # Skip the prefix itself
            if key == UPLOAD_PREFIX:
                continue
            filename = key[len(UPLOAD_PREFIX):]
            download_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": BUCKET, "Key": key},
                ExpiresIn=DOWNLOAD_EXPIRY,
            )
            files.append({
                "filename": filename,
                "key": key,
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
                "download_url": download_url,
            })

        # Sort by last_modified descending (newest first)
        files.sort(key=lambda f: f["last_modified"], reverse=True)
        logger.info(json.dumps({"event": "files_listed", "count": len(files)}))
        return _response(200, {"files": files})
    except Exception as e:
        logger.error(json.dumps({"event": "list_failed", "error": str(e)[:200]}))
        return _response(500, {"error": "Failed to list files"})


def _delete_file(payload):
    """Delete a file from the uploads prefix."""
    key = payload.get("key", "").strip()
    if not key or not key.startswith(UPLOAD_PREFIX):
        return _response(400, {"error": "Invalid key"})

    try:
        s3.delete_object(Bucket=BUCKET, Key=key)
        logger.info(json.dumps({"event": "file_deleted", "key": key}))
        return _response(200, {"deleted": key})
    except Exception as e:
        logger.error(json.dumps({"event": "delete_failed", "error": str(e)[:200]}))
        return _response(500, {"error": "Failed to delete file"})


def handler(event, context):
    """API Gateway proxy handler."""
    request_id = getattr(context, "aws_request_id", "local")

    # Handle CORS preflight
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if method == "OPTIONS":
        return {
            "statusCode": 204,
            "headers": _cors_headers(),
            "body": "",
        }

    # Parse body
    body = event.get("body", "")
    if event.get("isBase64Encoded"):
        import base64
        body = base64.b64decode(body).decode("utf-8")

    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON"})

    action = payload.get("action", "")
    logger.info(json.dumps({"event": "upload_request", "action": action, "request_id": request_id}))

    # Validate passphrase for all actions
    if not _validate_passphrase(payload):
        logger.warning(json.dumps({"event": "auth_failed", "request_id": request_id}))
        return _response(403, {"error": "Invalid passphrase"})

    if action == "get-upload-url":
        return _get_upload_url(payload)
    elif action == "list":
        return _list_files(payload)
    elif action == "delete":
        return _delete_file(payload)
    else:
        return _response(400, {"error": f"Unknown action: {action}"})
