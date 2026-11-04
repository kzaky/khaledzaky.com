#!/usr/bin/env bash
# Prove a deployed Lambda loads its module. A package that can't import fails here with
# Runtime.ImportModuleError before the handler runs, so a broken deploy is caught at
# deploy time instead of mid-pipeline.
#
# Usage: smoke-lambda.sh <function-name> [region]
#
# Sends {"smoke": true}, which every handler answers without doing any work
# (common/artifacts.py is_smoke, an early return, or nothing to do for an event it doesn't
# recognize), so a deploy doesn't trip blog-agent-lambda-errors-any. Any function error is
# a real one and fails.

set -euo pipefail

FUNCTION_NAME="${1:?Usage: smoke-lambda.sh <function-name> [region]}"
REGION="${2:-${AWS_DEFAULT_REGION:-us-east-1}}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
RESP="${TMP_DIR}/response.json"

echo ">> Smoke-invoking ${FUNCTION_NAME} to verify the module loads..."
if ! INVOKE_META="$(aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload '{"smoke": true}' \
  --cli-binary-format raw-in-base64-out \
  --region "$REGION" \
  --output json \
  --no-cli-pager \
  "$RESP" 2>&1)"; then
  echo "!! SMOKE FAILED — could not invoke ${FUNCTION_NAME}, so the module load is unproven:" >&2
  echo "$INVOKE_META" >&2
  exit 1
fi

if grep -q 'Runtime.ImportModuleError\|Unable to import module' "$RESP" 2>/dev/null; then
  echo "!! SMOKE FAILED — ${FUNCTION_NAME} cannot import its module:" >&2
  cat "$RESP" >&2
  echo "" >&2
  echo "   The deployed package is incomplete. Fix and redeploy before re-running the pipeline." >&2
  exit 1
fi

if printf '%s' "$INVOKE_META" | grep -q '"FunctionError"'; then
  echo "!! SMOKE FAILED — ${FUNCTION_NAME} raised on the smoke event:" >&2
  cat "$RESP" >&2
  echo "" >&2
  exit 1
fi

echo "   Smoke response: $(cat "$RESP")"
