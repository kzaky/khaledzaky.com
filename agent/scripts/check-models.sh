#!/usr/bin/env bash
# check-models.sh — validate all Bedrock model IDs used by the pipeline
# Run this before AND after any model ID change. Never change a model ID without running this.
#
# Usage: ./agent/scripts/check-models.sh
# Exit code: 0 if all pass, 1 if any fail

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
PAYLOAD='{"anthropic_version":"bedrock-2023-05-31","max_tokens":5,"messages":[{"role":"user","content":"hi"}]}'
PAYLOAD_FILE=$(mktemp)
echo "$PAYLOAD" > "$PAYLOAD_FILE"

PASS=0
FAIL=0

check_model() {
    local label="$1"
    local model_id="$2"
    local out
    out=$(mktemp)
    if aws bedrock-runtime invoke-model \
        --region "$REGION" \
        --model-id "$model_id" \
        --body "fileb://$PAYLOAD_FILE" \
        --content-type application/json \
        "$out" 2>&1 | grep -q "Exception\|Error\|error"; then
        echo "  FAIL  $label ($model_id)"
        FAIL=$((FAIL + 1))
    else
        echo "  OK    $label ($model_id)"
        PASS=$((PASS + 1))
    fi
    rm -f "$out"
}

echo ""
echo "Checking Bedrock model access (region: $REGION)"
echo "------------------------------------------------"

# Models used by blog-agent-research
echo "blog-agent-research:"
check_model "BEDROCK_MODEL_ID (Sonnet)"  "us.anthropic.claude-sonnet-4-6"
check_model "SYNTHESIS_MODEL_ID (Opus)"  "$(aws lambda get-function-configuration --function-name blog-agent-research --query 'Environment.Variables.SYNTHESIS_MODEL_ID' --output text 2>/dev/null || echo 'us.anthropic.claude-opus-4-6-v1')"
check_model "HAIKU_MODEL_ID"             "us.anthropic.claude-haiku-4-5-20251001-v1:0"

echo ""
echo "blog-agent-draft:"
check_model "BEDROCK_MODEL_ID (Sonnet)"  "us.anthropic.claude-sonnet-4-6"
check_model "DRAFT_MODEL_ID (Opus)"      "$(aws lambda get-function-configuration --function-name blog-agent-draft --query 'Environment.Variables.DRAFT_MODEL_ID' --output text 2>/dev/null || echo 'us.anthropic.claude-opus-4-6-v1')"
check_model "HAIKU_MODEL_ID"             "us.anthropic.claude-haiku-4-5-20251001-v1:0"

echo ""
echo "------------------------------------------------"
echo "  $PASS passed, $FAIL failed"
echo ""

rm -f "$PAYLOAD_FILE"

if [ "$FAIL" -gt 0 ]; then
    echo "ACTION REQUIRED: fix failing models before triggering the pipeline."
    exit 1
fi

echo "All models accessible. Safe to run the pipeline."
exit 0
