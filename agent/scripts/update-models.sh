#!/usr/bin/env bash
# Detect the latest Claude inference profiles available in Bedrock and update the
# blog-agent Lambda env vars + SSM model parameters if anything changed.
#
# Usage: ./scripts/update-models.sh [--dry-run]
#
# Run this whenever you want to check for newer model versions. No stack deploy
# required — updates Lambda env vars directly. Safe to run at any time.
#
# What it does:
#   1. Lists all active US cross-region inference profiles from Bedrock
#   2. Finds the highest sonnet and opus version numbers
#   3. Compares to what's currently deployed
#   4. Updates SSM params + Lambda env vars if newer models are available
#   5. Prints a summary of what changed (or what's already current)

set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
STACK="${STACK_NAME:-blog-agent}"
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

echo "=== Blog Agent Model Update Check ==="
echo "Region: $REGION  Stack: $STACK  Dry-run: $DRY_RUN"
echo ""

# ---------------------------------------------------------------------------
# 1. Discover latest available inference profiles for each model family
# ---------------------------------------------------------------------------
ALL_PROFILES=$(aws bedrock list-inference-profiles --region "$REGION" \
  --query 'inferenceProfileSummaries[?status==`ACTIVE`].inferenceProfileId' \
  --output text 2>&1)

# Anthropic model IDs have inconsistent naming:
#   claude-sonnet-4-20250514-v1:0   (v4.0 — date where minor version would be)
#   claude-sonnet-4-5-20250929-v1:0 (v4.5 — minor version then date)
#   claude-sonnet-4-6               (v4.6 — no date at all)
# Python parses major.minor from each ID and picks the highest.
printf '%s\n' $ALL_PROFILES > /tmp/bedrock_profiles.txt

cat > /tmp/find_latest_models.py << 'PYEOF'
import re, sys

with open('/tmp/bedrock_profiles.txt') as f:
    profiles = [l.strip() for l in f if l.strip()]

def best(family):
    # claude-{family}-{major}-{minor}[-...]  minor is 1-3 digits (not a YYYYMMDD date)
    # e.g. opus-4-8, sonnet-4-6, haiku-4-5-20251001-v1:0
    pat  = re.compile(r'^us\.anthropic\.claude-' + family + r'-(\d+)-(\d{1,3})(?:[-:]|$)')
    # claude-{family}-{major}-{YYYYMMDD}     minor=0 — the original base release
    # e.g. sonnet-4-20250514-v1:0
    pat0 = re.compile(r'^us\.anthropic\.claude-' + family + r'-(\d+)-(\d{8})')
    best_key, best_id = (-1, -1), None
    for p in profiles:
        m = pat.match(p)
        if m:
            key = (int(m.group(1)), int(m.group(2)))
            if key > best_key:
                best_key, best_id = key, p
            continue
        m0 = pat0.match(p)
        if m0:
            key = (int(m0.group(1)), 0)
            if key > best_key:
                best_key, best_id = key, p
    return best_id or ''

print(best('sonnet'), best('opus'), best('haiku'))
PYEOF

read LATEST_SONNET LATEST_OPUS LATEST_HAIKU < <(python3 /tmp/find_latest_models.py)

echo "Latest available:"
echo "  Sonnet : $LATEST_SONNET"
echo "  Opus   : $LATEST_OPUS"
echo "  Haiku  : $LATEST_HAIKU"
echo ""

# ---------------------------------------------------------------------------
# 2. Read what's currently deployed on the key Lambdas
# ---------------------------------------------------------------------------
CURRENT_SONNET=$(aws lambda get-function-configuration \
  --function-name "${STACK}-draft" --region "$REGION" \
  --query 'Environment.Variables.BEDROCK_MODEL_ID' --output text 2>/dev/null || echo "unknown")

CURRENT_OPUS=$(aws lambda get-function-configuration \
  --function-name "${STACK}-draft" --region "$REGION" \
  --query 'Environment.Variables.DRAFT_MODEL_ID' --output text 2>/dev/null || echo "unknown")

CURRENT_HAIKU=$(aws lambda get-function-configuration \
  --function-name "${STACK}-draft" --region "$REGION" \
  --query 'Environment.Variables.HAIKU_MODEL_ID' --output text 2>/dev/null || echo "unknown")

echo "Currently deployed:"
echo "  Sonnet : $CURRENT_SONNET"
echo "  Opus   : $CURRENT_OPUS"
echo "  Haiku  : $CURRENT_HAIKU"
echo ""

# ---------------------------------------------------------------------------
# 3. Determine what needs updating
# ---------------------------------------------------------------------------
SONNET_CHANGED=false; OPUS_CHANGED=false; HAIKU_CHANGED=false
[[ "$LATEST_SONNET" != "$CURRENT_SONNET" ]] && SONNET_CHANGED=true
[[ "$LATEST_OPUS"   != "$CURRENT_OPUS"   ]] && OPUS_CHANGED=true
[[ "$LATEST_HAIKU"  != "$CURRENT_HAIKU"  ]] && HAIKU_CHANGED=true

if ! $SONNET_CHANGED && ! $OPUS_CHANGED && ! $HAIKU_CHANGED; then
  echo "✓ All models are already up to date. Nothing to do."
  exit 0
fi

echo "Updates needed:"
$SONNET_CHANGED && echo "  Sonnet : $CURRENT_SONNET  ->  $LATEST_SONNET"
$OPUS_CHANGED   && echo "  Opus   : $CURRENT_OPUS    ->  $LATEST_OPUS"
$HAIKU_CHANGED  && echo "  Haiku  : $CURRENT_HAIKU   ->  $LATEST_HAIKU"
echo ""

if $DRY_RUN; then
  echo "(dry-run) No changes applied."
  exit 0
fi

# ---------------------------------------------------------------------------
# 4. Store updated model IDs in SSM (source of truth for future deploys)
# ---------------------------------------------------------------------------
echo ">> Updating SSM parameters..."
for param_path model_val in \
  "/blog-agent/models/sonnet" "$LATEST_SONNET" \
  "/blog-agent/models/opus"   "$LATEST_OPUS" \
  "/blog-agent/models/haiku"  "$LATEST_HAIKU"; do
  aws ssm put-parameter \
    --name "$param_path" --value "$model_val" \
    --type String --overwrite \
    --region "$REGION" --no-cli-pager > /dev/null
  echo "   $param_path = $model_val"
done

# ---------------------------------------------------------------------------
# 5. Update Lambda env vars directly on affected functions (no stack deploy)
# ---------------------------------------------------------------------------
echo ""
echo ">> Updating Lambda environment variables..."

# draft uses: BEDROCK_MODEL_ID (sonnet fallback), DRAFT_MODEL_ID (opus), HAIKU_MODEL_ID
# research uses: BEDROCK_MODEL_ID (sonnet), SYNTHESIS_MODEL_ID (opus), HAIKU_MODEL_ID
# chart uses: BEDROCK_MODEL_ID (sonnet)

python3 - <<PYEOF
import json, subprocess, sys

region = "$REGION"
stack  = "$STACK"
sonnet = "$LATEST_SONNET"
opus   = "$LATEST_OPUS"
haiku  = "$LATEST_HAIKU"

# model env var name -> new value, per function
updates = {
    f"{stack}-draft":    {"BEDROCK_MODEL_ID": sonnet, "DRAFT_MODEL_ID": opus, "HAIKU_MODEL_ID": haiku},
    f"{stack}-research": {"BEDROCK_MODEL_ID": sonnet, "SYNTHESIS_MODEL_ID": opus, "HAIKU_MODEL_ID": haiku},
    f"{stack}-chart":    {"BEDROCK_MODEL_ID": sonnet, "HAIKU_MODEL_ID": haiku},
    f"{stack}-verify":   {"HAIKU_MODEL_ID": haiku},
}

for fn, new_vars in updates.items():
    env = json.loads(subprocess.check_output([
        "aws","lambda","get-function-configuration",
        "--function-name", fn, "--region", region,
        "--query","Environment.Variables","--output","json"
    ]))
    env.update(new_vars)
    with open(f"/tmp/{fn}-env.json","w") as f:
        json.dump({"Variables": env}, f)
    subprocess.check_call([
        "aws","lambda","update-function-configuration",
        "--function-name", fn,
        "--environment", f"file:///tmp/{fn}-env.json",
        "--region", region, "--no-cli-pager",
        "--query","LastUpdateStatus","--output","text"
    ])
    print(f"   {fn}: updated")
PYEOF

echo ""
echo "=== Done. All models updated to latest. ==="
echo "Tip: re-run with --dry-run to check for newer versions without applying changes."
