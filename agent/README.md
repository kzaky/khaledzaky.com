# Blog Agent — AI-Powered Blog Writing Pipeline

An AWS-native blog writing agent that researches topics, drafts posts, and publishes them to your site with human-in-the-loop (HITL) approval.

## Architecture

```
You (trigger) → Step Functions → Research (Bedrock) → Draft (Bedrock) → SNS Email → You (approve) → GitHub Commit → CodeBuild → S3/CloudFront
```

### Components
- **Research Lambda** — Uses Bedrock Claude to research a topic and produce structured notes
- **Draft Lambda** — Uses Bedrock Claude to write a complete Markdown blog post with Astro frontmatter
- **Notify Lambda** — Stores draft in S3, sends SNS email for review
- **Publish Lambda** — On approval, commits the post to GitHub (triggers CodeBuild deploy)
- **Step Functions** — Orchestrates the pipeline with a HITL wait step
- **SNS** — Email notifications for draft review
- **S3** — Draft storage
- **SSM Parameter Store** — Secure GitHub token storage

## Cost Estimate (~4 posts/month)
- **Bedrock (Claude Haiku):** ~$0.10/month
- **Lambda:** Free tier
- **Step Functions:** Free tier
- **SNS:** Free tier (email)
- **S3:** ~$0.01/month
- **Total: < $1/month**

## Prerequisites

1. **AWS CLI** configured with credentials
2. **Amazon Bedrock** model access enabled for Claude in your region (us-east-1)
3. **GitHub Personal Access Token** with `repo` scope

## Setup

### 1. Store GitHub token in SSM
```bash
aws ssm put-parameter \
  --name "/blog-agent/github-token" \
  --type SecureString \
  --value "ghp_YOUR_TOKEN_HERE" \
  --region us-east-1
```

### 2. Enable Bedrock model access
- Go to AWS Console → Amazon Bedrock → Model access
- Request access to `Anthropic Claude 3 Haiku`

### 3. Deploy the stack
```bash
cd agent
chmod +x deploy.sh
./deploy.sh your-email@example.com
```

### 4. Confirm SNS subscription
Check your email and click the confirmation link.

## Usage

### Trigger the agent
```bash
aws stepfunctions start-execution \
  --state-machine-arn <STATE_MACHINE_ARN> \
  --input '{"topic": "Zero Trust Architecture in AWS", "categories": ["cloud", "aws", "security"]}'
```

### Review the draft
You'll receive an email with:
- A preview of the draft
- The S3 location of the full draft
- CLI commands to approve or reject

### Approve
```bash
aws stepfunctions send-task-success \
  --task-token '<TOKEN_FROM_EMAIL>' \
  --task-output '{"approved": true}'
```

### Reject
```bash
aws stepfunctions send-task-failure \
  --task-token '<TOKEN_FROM_EMAIL>' \
  --error 'Rejected' \
  --cause 'Draft needs revision'
```

## Customization

### Use a better model
Change the `BedrockModelId` parameter to use Sonnet for higher quality:
```
anthropic.claude-3-sonnet-20240229-v1:0
```

### Schedule automatic runs
Uncomment the `ScheduledTrigger` section in `template.yaml` and set your preferred schedule and default topic.

### Edit the prompts
The research and drafting prompts are in `research/index.py` and `draft/index.py`. Customize them to match your writing style and preferences.
