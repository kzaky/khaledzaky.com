# Site Infrastructure — CloudFormation

Infrastructure as Code for the [khaledzaky.com](https://khaledzaky.com) static site hosting stack.

## Stacks

| Stack | Region | Template | Description |
|-------|--------|----------|-------------|
| **`khaledzaky-infra`** | us-east-1 | `template.yaml` | CloudFront, OAC, security headers, index rewrite function, IAM role, Route 53 health check, CloudWatch alarm + dashboard, CloudTrail |
| **`khaledzaky-storage`** | us-east-2 | `storage.yaml` | S3 site bucket (versioning, AES-256 + BucketKey, 90-day non-current version lifecycle) |

The S3 bucket is in us-east-2 (where it was originally created), so it lives in a separate stack from the us-east-1 resources.

## Deploying

```bash
cd infra
./deploy.sh <notification-email> <acm-cert-arn> <hosted-zone-id> [stack-name]
```

Example:
```bash
./deploy.sh you@example.com \
  arn:aws:acm:us-east-1:123456789012:certificate/abc-123 \
  Z1234567890
```

The storage stack must be deployed separately:
```bash
aws cloudformation deploy \
  --template-file storage.yaml \
  --stack-name khaledzaky-storage \
  --region us-east-2
```

## Resources Not in CloudFormation

These resources don't support CFN import and are managed outside the stacks:

| Resource | Reason |
|----------|--------|
| **CodeBuild project** (`khaledzaky_com`) | `AWS::CodeBuild::Project` doesn't support import |
| **AWS Budget** (`Monthly-25-USD`) | `AWS::Budgets::Budget` doesn't support import |
| **S3 bucket policy** | Cross-region — bucket in us-east-2, CloudFront in us-east-1 |

Templates for these resources are preserved as comments in `template.yaml` for documentation.

## Security

- No AWS account IDs, emails, or secrets in template defaults
- Sensitive parameters (ACM cert ARN, hosted zone ID, email) passed at deploy time via CLI
- All resources have `DeletionPolicy: Retain` to prevent accidental deletion
