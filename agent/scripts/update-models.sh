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
    # claude-{family}-{major}, no minor at all — the naming Bedrock uses for the newest
    # generation (us.anthropic.claude-sonnet-5, us.anthropic.claude-opus-5 — listed as
    # ACTIVE in the target account, though NOT currently entitled there: every model
    # newer than the 4-6 line returns AccessDeniedException on invoke, which is why the
    # accessibility probe below exists and why this script still selects 4-6 today.
    # Listed is not entitled; only the probe decides). Without this pattern the two
    # above never match a bare "-5" and the script silently caps upgrades at 4.x
    # forever, even once 5-generation models exist and are enabled.
    pat_bare = re.compile(r'^us\.anthropic\.claude-' + family + r'-(\d+)$')
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
            continue
        mb = pat_bare.match(p)
        if mb:
            key = (int(mb.group(1)), 0)
            if key > best_key:
                best_key, best_id = key, p
    return best_id or ''

print(best('sonnet'), best('opus'), best('haiku'))
PYEOF

# First pass: find highest-versioned IDs by parsing the profile list
read CANDIDATE_SONNET CANDIDATE_OPUS CANDIDATE_HAIKU < <(python3 /tmp/find_latest_models.py)

# Second pass: confirm each candidate is actually accessible in this account.
# A model can be listed as an inference profile but still require separate model-access
# approval in the Bedrock console. Test by running a minimal invocation; if it returns
# AccessDeniedException, walk down to the next-highest version.
echo '{"anthropic_version":"bedrock-2023-05-31","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}' \
  > /tmp/probe_body.json

_probe_accessible() {
  local model="$1"
  [ -z "$model" ] && return 1
  aws bedrock-runtime invoke-model \
    --model-id "$model" --region "$REGION" \
    --body fileb:///tmp/probe_body.json \
    --content-type application/json --accept application/json \
    /tmp/probe_out.json > /dev/null 2>&1
}

# For each family, walk the profile list from highest to lowest version until one is accessible
_best_accessible() {
  local family="$1"
  python3 - "$family" <<'PYEOF'
import re, sys
family = sys.argv[1]
with open('/tmp/bedrock_profiles.txt') as f:
    profiles = [l.strip() for l in f if l.strip()]
pat  = re.compile(r'^us\.anthropic\.claude-' + family + r'-(\d+)-(\d{1,3})(?:[-:]|$)')
pat0 = re.compile(r'^us\.anthropic\.claude-' + family + r'-(\d+)-(\d{8})')
pat_bare = re.compile(r'^us\.anthropic\.claude-' + family + r'-(\d+)$')
scored = []
for p in profiles:
    m = pat.match(p)
    if m:
        scored.append(((int(m.group(1)), int(m.group(2))), p)); continue
    m0 = pat0.match(p)
    if m0:
        scored.append(((int(m0.group(1)), 0), p)); continue
    mb = pat_bare.match(p)
    if mb:
        scored.append(((int(mb.group(1)), 0), p))
for _, p in sorted(scored, reverse=True):
    print(p)
PYEOF
}

_find_accessible() {
  local family="$1"
  while IFS= read -r candidate; do
    if _probe_accessible "$candidate"; then
      echo "$candidate"
      return
    fi
  done < <(_best_accessible "$family")
  echo ""
}

echo ">> Probing model accessibility..."
LATEST_SONNET=$(_find_accessible sonnet)
LATEST_OPUS=$(_find_accessible opus)
LATEST_HAIKU=$(_find_accessible haiku)

echo "Latest available (accessible):"
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
# NOTE: `for path val in ...; do` is not valid bash (a for-loop takes one variable) —
# the pair-iterating loop this used to be written as had never been syntactically
# valid since the day it was committed, so this step had never actually run. Three
# explicit calls, one per model, instead of a loop construct that has to get pairing
# exactly right.
_put_model_param() {
  aws ssm put-parameter \
    --name "$1" --value "$2" \
    --type String --overwrite \
    --region "$REGION" --no-cli-pager > /dev/null
  echo "   $1 = $2"
}

_write_ssm_params() {
  echo ">> Writing SSM parameters (source of truth for deploy.sh)..."
  _put_model_param "/blog-agent/models/sonnet" "$LATEST_SONNET"
  _put_model_param "/blog-agent/models/opus"   "$LATEST_OPUS"
  _put_model_param "/blog-agent/models/haiku"  "$LATEST_HAIKU"
  echo ""
}

SONNET_CHANGED=false; OPUS_CHANGED=false; HAIKU_CHANGED=false
[[ "$LATEST_SONNET" != "$CURRENT_SONNET" ]] && SONNET_CHANGED=true
[[ "$LATEST_OPUS"   != "$CURRENT_OPUS"   ]] && OPUS_CHANGED=true
[[ "$LATEST_HAIKU"  != "$CURRENT_HAIKU"  ]] && HAIKU_CHANGED=true

# SSM is written BEFORE the up-to-date early-exit below, not after. deploy.sh reads
# these parameters as the source of truth for its --parameter-overrides; if they only
# ever got written on a change, the common case (models already current) left SSM empty
# and deploy.sh silently fell through to its hardcoded defaults every time — making the
# whole SSM-first mechanism inert and untested. Writing unconditionally is idempotent
# and costs one put-parameter per model.
if ! $DRY_RUN; then
  _write_ssm_params
fi

if ! $SONNET_CHANGED && ! $OPUS_CHANGED && ! $HAIKU_CHANGED; then
  echo "✓ All models are already up to date (SSM parameters refreshed). Nothing else to do."
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
# 5. Update Lambda env vars directly on affected functions (no stack deploy)
# ---------------------------------------------------------------------------
echo ""
echo ">> Updating Lambda environment variables..."

# draft uses:    BEDROCK_MODEL_ID (sonnet fallback), DRAFT_MODEL_ID (opus), HAIKU_MODEL_ID
# research uses: BEDROCK_MODEL_ID (sonnet), SYNTHESIS_MODEL_ID (opus), HAIKU_MODEL_ID
# chart uses:    BEDROCK_MODEL_ID (sonnet)
# verify uses:   HAIKU_MODEL_ID (per-link citation verification)
# evaluate uses: BEDROCK_MODEL_ID (sonnet — fact_checker/author_intent seats + repair)
# notify uses:   HAIKU_MODEL_ID (author-intent second opinion)
#
# evaluate and notify were added after this script; every Lambda that reads a Claude
# model env var must be listed here, or a model bump silently misses it and that
# function keeps running the old model indefinitely.

python3 - <<PYEOF
import json, subprocess, sys


def _fn_exists(name, region):
    try:
        subprocess.check_output(
            ["aws", "lambda", "get-function", "--function-name", name, "--region", region],
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


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
    f"{stack}-evaluate": {"BEDROCK_MODEL_ID": sonnet},
    f"{stack}-notify":   {"HAIKU_MODEL_ID": haiku},
}
# Only touch a function if it's actually deployed (evaluate/notify may not exist yet
# on an account that hasn't redeployed the current template).
updates = {fn: v for fn, v in updates.items() if _fn_exists(fn, region)}

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
