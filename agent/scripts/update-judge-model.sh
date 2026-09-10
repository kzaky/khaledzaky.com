#!/usr/bin/env bash
# Discover and apply the best available NON-Anthropic Bedrock model for the rubric
# panel's independent judge seats (JUDGE_MODEL_ID on the "evaluate" Lambda).
#
# Usage: ./scripts/update-judge-model.sh [--dry-run]
#
# Why this is a separate script from update-models.sh: that script parses Anthropic's
# own inference-profile version numbering (claude-{family}-{major}-{minor}) to compare
# versions. There is no equivalent numbering scheme across providers, and Bedrock's
# list-foundation-models API returns modalities and lifecycle status, not a capability
# tier — there is no API-derivable answer to "which model is currently the most
# capable." So this script does NOT try to rank models. Instead:
#
#   1. Lists every ACTIVE, TEXT-capable, non-Amazon, non-Anthropic model actually
#      present in this account, across BOTH Bedrock catalogs — on-demand foundation
#      models AND cross-region inference profiles. A live audit of this exact
#      pipeline's account found OpenAI's models registered only in the latter; a
#      foundation-models-only scan would report zero OpenAI availability even with
#      several OpenAI profiles active and invokable. This is the live, authoritative
#      answer to "what's actually available," including anything from OpenAI newer
#      than what this codebase currently knows about (the pipeline currently
#      defaults to openai.gpt-oss-120b-1:0; if a newer OpenAI model — whatever it's
#      actually called, "GPT-6" or otherwise — is present and accessible, this
#      script will find it and print it for you to add to the priority list below).
#   2. Probes each PREFERENCE_LIST candidate (edit this list as new frontier models
#      land on Bedrock) for actual invoke access, keeping only ones that work.
#   3. Prints every other available non-Anthropic model it found that ISN'T on the
#      preference list, so you can see if something worth adding showed up.
#   4. Writes the resulting comma-separated priority list to SSM
#      (/blog-agent/models/judge) and live-patches the "evaluate" Lambda's
#      JUDGE_MODEL_ID env var. The runtime code (common/llm.py::invoke_judge) already
#      knows how to walk a comma-separated priority list, trying each until one
#      works, before falling back to the Anthropic model — so listing multiple
#      accessible candidates here is not "picking one," it's ordering the fallback
#      chain from most to least preferred.
#
# Safe to run at any time; makes no CloudFormation changes (env var patch only, same
# pattern as update-models.sh). The next `./deploy.sh` run will pick up whatever this
# script wrote to SSM automatically.

set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
STACK="${STACK_NAME:-blog-agent}"
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

# Edit this list as new frontier models land on Bedrock. Most-preferred first — the
# runtime tries them in this order and only reaches the next one if a candidate is
# not accessible. openai.gpt-oss-120b-1:0 is the one model here this codebase has
# actually verified access to; everything else is a plausible frontier candidate that
# may or may not exist in a given account/region — the probe step (below) is what
# decides, not this list's ordering alone.
PREFERENCE_LIST=(
  "openai.gpt-oss-120b-1:0"
  "us.openai.gpt-oss-120b-1:0"
  "openai.gpt-oss-20b-1:0"
  "us.openai.gpt-oss-20b-1:0"
)

echo "=== Blog Agent Judge Model Discovery ==="
echo "Region: $REGION  Stack: $STACK  Dry-run: $DRY_RUN"
echo ""

# ---------------------------------------------------------------------------
# 1. List every non-Amazon, non-Anthropic, TEXT-capable, active model actually
#    present in this account — TWO separate Bedrock catalogs, both needed. A live
#    audit of this exact pipeline's account found third-party models split across
#    both: OpenAI's models on this account are registered ONLY as cross-region
#    inference profiles (list-inference-profiles), not as on-demand foundation
#    models — a foundation-models-only scan reports zero OpenAI availability even
#    when several OpenAI profiles are active and invokable. Both are written to
#    temp files rather than captured into shell variables and re-interpolated into
#    an inline script, since JSON containing quotes/newlines does not survive that
#    round-trip safely.
# ---------------------------------------------------------------------------
echo ">> Listing non-Anthropic on-demand foundation models available in this account..."
aws bedrock list-foundation-models --region "$REGION" \
  --query "modelSummaries[?modelLifecycle.status=='ACTIVE' && !starts_with(providerName, 'Amazon') && !starts_with(providerName, 'Anthropic') && contains(inputModalities, 'TEXT') && contains(outputModalities, 'TEXT')].{id:modelId,provider:providerName,name:modelName}" \
  --output json > /tmp/judge_on_demand.json

echo ">> Listing non-Anthropic cross-region inference profiles available in this account..."
aws bedrock list-inference-profiles --region "$REGION" \
  --query "inferenceProfileSummaries[?status=='ACTIVE' && !starts_with(inferenceProfileId, 'us.amazon.') && !starts_with(inferenceProfileId, 'us.anthropic.') && !starts_with(inferenceProfileId, 'global.amazon.') && !starts_with(inferenceProfileId, 'global.anthropic.')].{id:inferenceProfileId,name:inferenceProfileName}" \
  --output json > /tmp/judge_inference_profiles.json

python3 - <<'MERGEPY'
import json

with open('/tmp/judge_on_demand.json') as f:
    on_demand = json.load(f)
with open('/tmp/judge_inference_profiles.json') as f:
    profiles = json.load(f)

merged = [{"id": m["id"], "provider": m.get("provider", ""), "name": m.get("name", "")} for m in on_demand]
merged += [{"id": p["id"], "provider": p["id"].split(".")[1] if "." in p["id"] else "", "name": p.get("name", "")} for p in profiles]

with open('/tmp/judge_all_third_party.json', 'w') as f:
    json.dump(merged, f)

if not merged:
    print("   (none found in either catalog — this account/region may not have third-party Bedrock models enabled)")
for m in merged:
    print(f"   {m['id']:50s} {m['provider']:12s} {m['name']}")
MERGEPY
ALL_THIRD_PARTY=$(cat /tmp/judge_all_third_party.json)
echo ""

# ---------------------------------------------------------------------------
# 2. Probe each preference-list candidate for actual invoke access via Converse
#    (the same API path the runtime code uses), keeping only the ones that work.
# ---------------------------------------------------------------------------
_probe_converse() {
  aws bedrock-runtime converse \
    --region "$REGION" \
    --model-id "$1" \
    --messages '[{"role":"user","content":[{"text":"hi"}]}]' \
    --inference-config '{"maxTokens":5}' \
    /tmp/judge_probe_out.json > /dev/null 2>&1
}

echo ">> Probing preference-list candidates for actual access..."
ACCESSIBLE=()
for candidate in "${PREFERENCE_LIST[@]}"; do
  if _probe_converse "$candidate"; then
    echo "   OK    $candidate"
    ACCESSIBLE+=("$candidate")
  else
    echo "   --    $candidate (not accessible — not enabled, wrong region, or doesn't exist here)"
  fi
done
echo ""

# ---------------------------------------------------------------------------
# 3. Flag anything discovered in step 1 that ISN'T on the preference list — this is
#    where a newer OpenAI (or other provider) model would surface if this account has
#    one this codebase doesn't know about yet.
# ---------------------------------------------------------------------------
echo ">> Models available in this account but NOT on the preference list above:"
python3 - "$ALL_THIRD_PARTY" "${PREFERENCE_LIST[@]}" <<'PYEOF'
import json, sys
all_models = json.loads(sys.argv[1])
preference = set(sys.argv[2:])
extra = [m for m in all_models if m["id"] not in preference]
if not extra:
    print("   (none — every text-capable third-party model here is already on the list)")
for m in extra:
    print(f"   {m['id']:45s} {m['provider']:12s} {m['name']}")
    if "gpt" in m["id"].lower() or "openai" in m["provider"].lower():
        print("        ^ this looks like an OpenAI model not yet in PREFERENCE_LIST —")
        print("          consider adding it to scripts/update-judge-model.sh and re-running")
PYEOF
echo ""

if [ "${#ACCESSIBLE[@]}" -eq 0 ]; then
  echo "No preference-list candidate is currently accessible in this account/region."
  echo "The pipeline still works — invoke_judge falls back to the Anthropic model for"
  echo "every taste seat — but cross-family judging is effectively disabled until you"
  echo "either enable one of the candidates above in Bedrock model access, or add a"
  echo "model found in step 1/3 to PREFERENCE_LIST and re-run this script."
  exit 0
fi

NEW_VALUE=$(IFS=,; echo "${ACCESSIBLE[*]}")
echo "Accessible priority list: $NEW_VALUE"

CURRENT_VALUE=$(aws lambda get-function-configuration \
  --function-name "${STACK}-evaluate" --region "$REGION" \
  --query 'Environment.Variables.JUDGE_MODEL_ID' --output text 2>/dev/null || echo "unknown")
echo "Currently deployed:       $CURRENT_VALUE"
echo ""

if [ "$NEW_VALUE" == "$CURRENT_VALUE" ]; then
  echo "Already up to date. Nothing to do."
  exit 0
fi

if $DRY_RUN; then
  echo "(dry-run) Would update /blog-agent/models/judge and ${STACK}-evaluate's JUDGE_MODEL_ID."
  exit 0
fi

echo ">> Updating SSM parameter /blog-agent/models/judge..."
aws ssm put-parameter --name "/blog-agent/models/judge" --value "$NEW_VALUE" \
  --type String --overwrite --region "$REGION" --no-cli-pager > /dev/null

echo ">> Updating ${STACK}-evaluate JUDGE_MODEL_ID..."
python3 - "$STACK" "$REGION" "$NEW_VALUE" <<'PYEOF'
import json, subprocess, sys
stack, region, new_value = sys.argv[1:4]
fn = f"{stack}-evaluate"
env = json.loads(subprocess.check_output([
    "aws", "lambda", "get-function-configuration",
    "--function-name", fn, "--region", region,
    "--query", "Environment.Variables", "--output", "json",
]))
env["JUDGE_MODEL_ID"] = new_value
with open("/tmp/judge-env.json", "w") as f:
    json.dump({"Variables": env}, f)
subprocess.check_call([
    "aws", "lambda", "update-function-configuration",
    "--function-name", fn,
    "--environment", "file:///tmp/judge-env.json",
    "--region", region, "--no-cli-pager",
    "--query", "LastUpdateStatus", "--output", "text",
])
print(f"   {fn}: updated")
PYEOF

echo ""
echo "=== Done. Judge model priority list updated. ==="
echo "Tip: re-run with --dry-run to check without applying changes."
