#!/bin/bash
# Deploy the Blog Agent infrastructure to AWS
# Usage: ./deploy.sh <your-email@example.com> [stack-name]
#
# Prerequisites:
#   1. AWS CLI configured with appropriate credentials
#   2. Secrets stored in SSM Parameter Store:
#      aws ssm put-parameter --name "/blog-agent/github-token" \
#        --type SecureString --value "ghp_YOUR_TOKEN_HERE"
#      aws ssm put-parameter --name "/blog-agent/tavily-api-key" \
#        --type SecureString --value "tvly-YOUR_KEY_HERE"
#      aws ssm put-parameter --name "/blog-agent/perplexity-api-key" \
#        --type SecureString --value "pplx-YOUR_KEY_HERE"  # optional — degrades gracefully
#   3. Amazon Bedrock model access enabled for Claude in your region

set -euo pipefail

EMAIL="${1:?Usage: ./deploy.sh <notification-email> [stack-name]}"
STACK_NAME="${2:-blog-agent}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

echo "=== Deploying Blog Agent ==="
echo "Stack:  $STACK_NAME"
echo "Region: $REGION"
echo "Email:  $EMAIL"
echo ""

# Voice profile will be uploaded to S3 after stack deployment
VOICE_PROFILE_FILE="voice-profile.md"
if [ ! -f "$VOICE_PROFILE_FILE" ]; then
  echo "!! WARNING: voice-profile.md not found — Draft Lambda will run without voice guidance"
fi

# Pre-deploy: syntax-check all Lambda Python files before packaging
# Catches SyntaxError and obvious import-time issues early.
echo ">> Syntax-checking Lambda Python files..."
for fn in research draft verify notify publish approve ingest chart upload alarm-formatter; do
  if [ -f "${fn}/index.py" ]; then
    if ! python3 -m py_compile "${fn}/index.py" 2>/tmp/py_compile_err; then
      echo "!! SYNTAX ERROR in ${fn}/index.py — aborting deploy"
      cat /tmp/py_compile_err
      exit 1
    fi
  fi
done
echo "   All syntax checks passed."

# Package Lambda functions
echo ">> Packaging Lambda functions..."
for fn in research draft verify notify publish approve ingest chart upload alarm-formatter; do
  if [ -d "$fn" ]; then
    pushd "$fn" > /dev/null
    # chart has a renderers/ subpackage — zip -r preserves directory structure
    zip -qr "../${fn}.zip" .
    popd > /dev/null

    # Post-zip structure validation: index.py must be at the zip root, not nested.
    # A common mistake is zipping the directory itself (zip draft.zip draft/) which
    # puts files at draft/index.py and causes Runtime.ImportModuleError in Lambda.
    if [ -f "${fn}.zip" ]; then
      if ! unzip -l "${fn}.zip" | awk '{print $4}' | grep -q '^index\.py$'; then
        echo "!! BAD ZIP STRUCTURE in ${fn}.zip — index.py not at root (got nested path)."
        echo "   Fix: ensure you run 'zip' from inside the Lambda directory."
        exit 1
      fi
    fi
  fi
done

# Deploy CloudFormation stack
echo ">> Deploying CloudFormation stack..."
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name "$STACK_NAME" \
  --parameter-overrides \
    NotificationEmail="$EMAIL" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION"

# Update Lambda function code from zips
echo ">> Updating Lambda function code..."
for fn in research draft verify notify publish approve ingest chart upload alarm-formatter; do
  if [ -f "${fn}.zip" ]; then
    echo "   Updating ${STACK_NAME}-${fn}..."
    aws lambda update-function-code \
      --function-name "${STACK_NAME}-${fn}" \
      --zip-file "fileb://${fn}.zip" \
      --region "$REGION" \
      --no-cli-pager
  fi
done

# Upload voice profile to S3 for Draft Lambda to load at runtime
DRAFTS_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`DraftsBucketName`].OutputValue' \
  --output text \
  --region "$REGION")

if [ -f "$VOICE_PROFILE_FILE" ] && [ -n "$DRAFTS_BUCKET" ]; then
  echo ">> Uploading voice profile to s3://${DRAFTS_BUCKET}/config/voice-profile.md..."
  aws s3 cp "$VOICE_PROFILE_FILE" "s3://${DRAFTS_BUCKET}/config/voice-profile.md" \
    --region "$REGION" --quiet
  echo "   Voice profile uploaded."
fi

# Seed known-post-slugs SSM parameter if it doesn't already exist
# Draft Lambda reads this to avoid fabricating internal links; Publish Lambda keeps it current.
echo ">> Checking known-post-slugs SSM parameter..."
if ! aws ssm get-parameter --name "/blog-agent/known-post-slugs" --region "$REGION" --no-cli-pager > /dev/null 2>&1; then
  echo "   Parameter not found — seeding from hardcoded slug list in draft/index.py..."
  SEED_SLUGS=$(grep -oP "(?<=['\"])[a-z0-9-]+(?=['\"],?)" draft/index.py | grep -E '^[a-z0-9-]{10,}$' | paste -sd ',')
  if [ -n "$SEED_SLUGS" ]; then
    aws ssm put-parameter \
      --name "/blog-agent/known-post-slugs" \
      --value "$SEED_SLUGS" \
      --type String \
      --region "$REGION" \
      --no-cli-pager
    echo "   Seeded $(echo "$SEED_SLUGS" | tr ',' '\n' | wc -l | tr -d ' ') slugs."
  else
    echo "   WARNING: Could not extract slugs from draft/index.py — skipping seed."
  fi
else
  echo "   Parameter already exists — skipping seed (Publish Lambda keeps it current)."
fi

# Cleanup zips
rm -f research.zip draft.zip verify.zip notify.zip publish.zip approve.zip ingest.zip chart.zip upload.zip alarm-formatter.zip

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "IMPORTANT: Check your email ($EMAIL) and confirm the SNS subscription!"
echo ""
echo "To trigger the agent:"
echo "  aws stepfunctions start-execution \\"
echo "    --state-machine-arn \$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`StateMachineArn\`].OutputValue' --output text) \\"
echo "    --input '{\"topic\": \"Your blog topic here\", \"categories\": [\"cloud\", \"aws\"]}'"
echo ""
echo "Or send an email to $EMAIL with:"
echo "  Subject: Your blog topic"
echo "  Body: Your draft, bullets, or ideas (the agent polishes YOUR content)"
echo ""
echo "Prerequisites reminder:"
echo "  1. Store GitHub token:    aws ssm put-parameter --name '/blog-agent/github-token' --type SecureString --value 'ghp_...'"
echo "  2. Store Tavily key:      aws ssm put-parameter --name '/blog-agent/tavily-api-key' --type SecureString --value 'tvly-...'"
echo "  3. Store Perplexity key:  aws ssm put-parameter --name '/blog-agent/perplexity-api-key' --type SecureString --value 'pplx-...' (optional)"
echo "  4. Enable Bedrock model access for Claude in the AWS console"
