#!/bin/bash
# Deploy the static site infrastructure to AWS
# Usage: ./deploy.sh [stack-name]
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

STACK_NAME="${1:-khaledzaky-infra}"
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
  --no-fail-on-empty-changeset

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Outputs:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[].{Key:OutputKey,Value:OutputValue}' \
  --output table \
  --region "$REGION"
