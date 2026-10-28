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

# The model id a deployed Lambda actually uses, or the code default if it can't be read.
_env() {
    local v
    v=$(aws lambda get-function-configuration --region "$REGION" --function-name "$1" \
        --query "Environment.Variables.$2" --output text 2>/dev/null || true)
    if [ -z "$v" ] || [ "$v" = "None" ]; then v="$3"; fi
    echo "$v"
}

echo ""
echo "Checking Bedrock model access (region: $REGION)"
echo "------------------------------------------------"

# Models used by blog-agent-research
echo "blog-agent-research:"
check_model "BEDROCK_MODEL_ID (Sonnet)"  "$(_env blog-agent-research BEDROCK_MODEL_ID us.anthropic.claude-sonnet-5-5)"
check_model "SYNTHESIS_MODEL_ID (Opus)"  "$(_env blog-agent-research SYNTHESIS_MODEL_ID us.anthropic.claude-opus-5-5)"
check_model "HAIKU_MODEL_ID"             "$(_env blog-agent-research HAIKU_MODEL_ID us.anthropic.claude-haiku-5-5)"

echo ""
echo "blog-agent-draft:"
check_model "BEDROCK_MODEL_ID (Sonnet)"  "$(_env blog-agent-draft BEDROCK_MODEL_ID us.anthropic.claude-sonnet-5-5)"
check_model "DRAFT_MODEL_ID (Opus)"      "$(_env blog-agent-draft DRAFT_MODEL_ID us.anthropic.claude-opus-5-5)"
check_model "HAIKU_MODEL_ID"             "$(_env blog-agent-draft HAIKU_MODEL_ID us.anthropic.claude-haiku-5-5)"

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
