#!/usr/bin/env bash
# Safely (re)deploy a SINGLE Lambda function's code.
#
# Usage: deploy-lambda.sh <function-dir> [stack-name] [region]
#   deploy-lambda.sh chart                  # -> blog-agent-chart, us-east-1
#   deploy-lambda.sh chart my-stack us-west-2
#
# Reach for this instead of a hand-rolled `zip + aws lambda update-function-code`
# when you only need to push one function. It:
#   1. packages through package-lambda.sh, so the artifact is always complete;
#   2. updates the function and waits for the update to settle;
#   3. smoke-invokes it — a package that can't import its modules fails here with
#      Runtime.ImportModuleError BEFORE the handler runs, so a broken deploy is
#      caught at deploy time instead of mid-pipeline.
#
# The smoke invoke sends an empty event and only asserts the MODULE LOADED; any
# business-logic error from the empty event is expected and ignored.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"

FN="${1:?Usage: deploy-lambda.sh <function-dir> [stack-name] [region]}"
FN="${FN%/}"
STACK_NAME="${2:-blog-agent}"
REGION="${3:-${AWS_DEFAULT_REGION:-us-east-1}}"
FUNCTION_NAME="${STACK_NAME}-${FN}"

cd "$AGENT_DIR"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
ZIP="${TMP_DIR}/${FN}.zip"

echo ">> Packaging ${FN}..."
"$SCRIPT_DIR/package-lambda.sh" "$FN" "$ZIP"

echo ">> Updating ${FUNCTION_NAME} (region ${REGION})..."
aws lambda update-function-code \
  --function-name "$FUNCTION_NAME" \
  --zip-file "fileb://${ZIP}" \
  --region "$REGION" \
  --no-cli-pager > /dev/null

echo ">> Waiting for the update to finish..."
aws lambda wait function-updated \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION"

echo ">> Smoke-invoking ${FUNCTION_NAME} to verify the module loads..."
RESP="${TMP_DIR}/response.json"
aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  --region "$REGION" \
  --no-cli-pager \
  "$RESP" > /dev/null 2>&1 || true

if grep -q 'Runtime.ImportModuleError\|Unable to import module' "$RESP" 2>/dev/null; then
  echo "!! SMOKE FAILED — ${FUNCTION_NAME} cannot import its module:" >&2
  cat "$RESP" >&2
  echo "" >&2
  echo "   The deployed package is incomplete. Fix and redeploy before re-running the pipeline." >&2
  exit 1
fi

echo "=== ${FUNCTION_NAME} redeployed and verified — module loads cleanly. ==="
