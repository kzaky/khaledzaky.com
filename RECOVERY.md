# Disaster Recovery — khaledzaky.com

How to rebuild everything from scratch if the AWS account is compromised or resources are deleted.

## Prerequisites

- AWS CLI configured with credentials
- GitHub repo: `kzaky/khaledzaky.com` (the source of truth for all code and content)
- Access to email for SNS subscription confirmation

## 1. Recreate SSM Secrets

These are not in git or CloudFormation — they must be recreated manually.

```bash
# GitHub Personal Access Token (repo scope)
aws ssm put-parameter \
  --name "/blog-agent/github-token" \
  --type SecureString \
  --value "ghp_YOUR_TOKEN_HERE" \
  --region us-east-1

# Tavily API key (from app.tavily.com)
aws ssm put-parameter \
  --name "/blog-agent/tavily-api-key" \
  --type SecureString \
  --value "tvly-YOUR_KEY_HERE" \
  --region us-east-1

# CloudFront distribution ID (set after infra stack deploys)
aws ssm put-parameter \
  --name "cloudfront_distid" \
  --type String \
  --value "<DISTRIBUTION_ID>" \
  --region us-east-1
```

## 2. Deploy Infrastructure Stacks

```bash
# Storage stack (us-east-2) — S3 site bucket
aws cloudformation deploy \
  --template-file infra/storage.yaml \
  --stack-name khaledzaky-storage \
  --region us-east-2

# Infra stack (us-east-1) — CloudFront, IAM, monitoring
cd infra
./deploy.sh <notification-email> <acm-cert-arn> <hosted-zone-id>

# Agent stack (us-east-1) — Lambdas, Step Functions, SNS, API Gateway
cd ../agent
./deploy.sh <notification-email>
```

## 3. Resources Not Managed by CloudFormation

These must be recreated manually:

### CodeBuild Project (`khaledzaky_com`)

```bash
aws codebuild create-project \
  --name khaledzaky_com \
  --source type=GITHUB,location=https://github.com/kzaky/khaledzaky.com.git,buildspec=buildspec.yml \
  --artifacts type=NO_ARTIFACTS \
  --environment type=LINUX_CONTAINER,computeType=BUILD_GENERAL1_SMALL,image=aws/codebuild/amazonlinux-x86_64-standard:5.0,imagePullCredentialsType=CODEBUILD \
  --service-role codebuild_khaledzaky.com \
  --badge-enabled \
  --region us-east-1

# Set timeout to 10 minutes
aws codebuild update-project --name khaledzaky_com --timeout-in-minutes 10 --region us-east-1

# Enable GitHub webhook
aws codebuild create-webhook \
  --project-name khaledzaky_com \
  --filter-groups '[[{"type":"EVENT","pattern":"PUSH"},{"type":"HEAD_REF","pattern":"^refs/heads/master$"}]]' \
  --region us-east-1
```

### AWS Budget (`Monthly-25-USD`)

```bash
aws budgets create-budget \
  --account-id <ACCOUNT_ID> \
  --budget '{"BudgetName":"Monthly-25-USD","BudgetType":"COST","TimeUnit":"MONTHLY","BudgetLimit":{"Amount":"25.0","Unit":"USD"}}' \
  --notifications-with-subscribers '[
    {"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"zakykhaled@gmail.com"}]},
    {"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":100},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"zakykhaled@gmail.com"}]}
  ]'
```

### S3 Bucket Policy (khaledzaky.com)

The site bucket is in us-east-2 but CloudFront OAC is in us-east-1 — the bucket policy must be applied manually:

```bash
aws s3api put-bucket-policy --bucket khaledzaky.com --region us-east-2 --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "cloudfront.amazonaws.com"},
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::khaledzaky.com/*",
    "Condition": {
      "StringEquals": {
        "AWS:SourceArn": "arn:aws:cloudfront::<ACCOUNT_ID>:distribution/<DISTRIBUTION_ID>"
      }
    }
  }]
}'
```

### Log Retention (Lambda + CodeBuild)

Lambda and CodeBuild log groups are auto-created — set retention after first invocation:

```bash
for lg in /aws/lambda/blog-agent-research /aws/lambda/blog-agent-draft \
  /aws/lambda/blog-agent-chart /aws/lambda/blog-agent-notify \
  /aws/lambda/blog-agent-approve /aws/lambda/blog-agent-ingest \
  /aws/lambda/blog-agent-publish /aws/codebuild/khaledzaky_com; do
  aws logs put-retention-policy --log-group-name "$lg" --retention-in-days 30 --region us-east-1
done
```

## 4. Deploy Lambda Code + Voice Profile

```bash
cd agent
./deploy.sh <notification-email>
# deploy.sh handles: zip + upload Lambda code, upload voice profile to S3
```

## 5. Confirm SNS Subscription

Check your email and click the confirmation link for the `blog-agent-review` SNS topic.

## 6. Update CloudFront Distribution ID in SSM

After the infra stack deploys, get the distribution ID and update SSM:

```bash
DIST_ID=$(aws cloudformation describe-stacks --stack-name khaledzaky-infra \
  --query 'Stacks[0].Outputs[?OutputKey==`DistributionId`].OutputValue' --output text --region us-east-1)
aws ssm put-parameter --name "cloudfront_distid" --type String --value "$DIST_ID" --overwrite --region us-east-1
```

## 7. Trigger a Build

Push any commit to `master` or start a build manually:

```bash
aws codebuild start-build --project-name khaledzaky_com --region us-east-1
```

## Recovery Time Estimates

| Scenario | RTO |
|----------|-----|
| Site content deleted from S3 | ~5 min (push to master triggers rebuild) |
| Lambda code corrupted | ~5 min (re-run `deploy.sh`) |
| Full account rebuild | ~30 min (all steps above) |
| SSM secrets lost | Manual — requires new GitHub token and Tavily key |

## What's NOT Recoverable from Git

- SSM secrets (GitHub token, Tavily API key) — must be recreated
- CloudTrail historical logs — stored in S3, not in git
- Step Functions execution history — ephemeral
- CloudWatch metrics/logs — ephemeral (30-day retention)
