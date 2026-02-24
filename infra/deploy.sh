#!/bin/bash
# Deploy the static site infrastructure to AWS
# Usage: ./deploy.sh <notification-email> <acm-cert-arn> <hosted-zone-id> [stack-name]
#
# Example:
#   ./deploy.sh you@example.com arn:aws:acm:us-east-1:123456789012:certificate/abc-123 Z1234567890
#
# Prerequisites:
#   1. AWS CLI configured with appropriate credentials
#   2. ACM certificate already provisioned in us-east-1
#   3. Route 53 hosted zone already exists
#
# IMPORTANT: This template manages existing resources.
#   - S3 bucket 'khaledzaky.com' has DeletionPolicy: Retain
#   - First deploy will FAIL if resources already exist with different names.
#   - For initial import, use `aws cloudformation create-stack` with --import-resources.

set -euo pipefail

if [ $# -lt 3 ]; then
  echo "Usage: $0 <notification-email> <acm-cert-arn> <hosted-zone-id> [stack-name]"
  echo ""
  echo "  notification-email  Email for budget alerts and uptime alarms"
  echo "  acm-cert-arn        ACM certificate ARN (must be in us-east-1)"
  echo "  hosted-zone-id      Route 53 hosted zone ID"
  echo "  stack-name          Optional, defaults to 'khaledzaky-infra'"
  exit 1
fi

NOTIFICATION_EMAIL="$1"
ACM_CERT_ARN="$2"
HOSTED_ZONE_ID="$3"
STACK_NAME="${4:-khaledzaky-infra}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

echo "=== Deploying Site Infrastructure ==="
echo "Stack:  $STACK_NAME"
echo "Region: $REGION"
echo ""

echo ">> Validating template..."
aws cloudformation validate-template \
  --template-body file://template.yaml \
  --region "$REGION" > /dev/null

echo ">> Deploying CloudFormation stack..."
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name "$STACK_NAME" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    NotificationEmail="$NOTIFICATION_EMAIL" \
    AcmCertificateArn="$ACM_CERT_ARN" \
    HostedZoneId="$HOSTED_ZONE_ID"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Outputs:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[].{Key:OutputKey,Value:OutputValue}' \
  --output table \
  --region "$REGION"
