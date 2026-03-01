#!/bin/bash
# Deploy the Blog Agent infrastructure to AWS
# Usage: ./deploy.sh <your-email@example.com> [stack-name]
#
# Prerequisites:
#   1. AWS CLI configured with appropriate credentials
#   2. A GitHub Personal Access Token stored in SSM Parameter Store:
#      aws ssm put-parameter --name "/blog-agent/github-token" \
#        --type SecureString --value "ghp_YOUR_TOKEN_HERE"
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

# Package Lambda functions
echo ">> Packaging Lambda functions..."
for fn in research draft notify publish approve ingest chart; do
  if [ -d "$fn" ]; then
    pushd "$fn" > /dev/null
    zip -qr "../${fn}.zip" index.py $(find . -name '*.py' -path '*/renderers/*' 2>/dev/null | tr '\n' ' ')
    popd > /dev/null
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
for fn in research draft notify publish approve ingest chart; do
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

# Cleanup zips
rm -f research.zip draft.zip notify.zip publish.zip approve.zip ingest.zip chart.zip

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
echo "Or send an email to blog@khaledzaky.com with:"
echo "  Subject: Your blog topic"
echo "  Body: Your draft, bullets, or ideas (the agent polishes YOUR content)"
echo ""
echo "Prerequisites reminder:"
echo "  1. Store GitHub token: aws ssm put-parameter --name '/blog-agent/github-token' --type SecureString --value 'ghp_...'"
echo "  2. Enable Bedrock model access for Claude in the AWS console"
