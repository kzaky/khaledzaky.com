# Blog Agent — AI-Powered Blog Writing Pipeline

An AWS-native blog writing agent that researches topics, drafts posts, and publishes them to your site with human-in-the-loop (HITL) approval.

## Architecture

```
You (email or CLI) → Step Functions → Research (Bedrock) → Draft (Bedrock) → SNS Email → You (one-click approve/revise/reject) → GitHub Commit → CodeBuild → S3/CloudFront
```

### Components
- **Ingest Lambda** — Receives inbound email via SES, parses topic and notes, starts the pipeline
- **Research Lambda** — Uses Bedrock Claude 3.5 Sonnet v2 to research a topic and produce structured notes
- **Draft Lambda** — Uses Bedrock Claude 3.5 Sonnet v2 to write a complete Markdown blog post with Astro frontmatter
- **Notify Lambda** — Stores draft in S3, sends SNS email with one-click approve/revise/reject links
- **Approve Lambda** — API Gateway handler that processes approval, revision feedback, or rejection
- **Publish Lambda** — On approval, commits the post to GitHub (triggers CodeBuild deploy)
- **Step Functions** — Orchestrates the pipeline with a HITL wait step (up to 7 days)
- **API Gateway** — HTTP API for one-click approval actions from email
- **SNS** — Email notifications for draft review
- **SES** — Inbound email processing (receives emails to `blog@khaledzaky.com`)
- **S3** — Draft storage (auto-expires after 90 days)
- **SSM Parameter Store** — Secure GitHub token storage

## Cost Estimate (~4 posts/month)
- **Bedrock (Claude 3.5 Sonnet v2):** ~$0.12/month
- **Lambda (6 functions):** ~$0.00 (free tier)
- **Step Functions:** ~$0.00 (free tier)
- **SNS:** ~$0.00 (free tier, email)
- **API Gateway:** ~$0.00
- **SES (inbound):** ~$0.00
- **S3:** ~$0.01/month
- **Total: ~$0.13/month**

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
- Request access to `Anthropic Claude 3.5 Sonnet v2`

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

### Trigger via email (preferred)
Send an email to `blog@khaledzaky.com`:
- **Subject** = the blog topic
- **Body** = optional notes, context, or guidance for research
- Optionally include `Categories: tech, cloud, leadership` in the body

### Review the draft
You'll receive an email with:
- A preview of the draft
- Three one-click action links:
  - **Approve** — publishes the post immediately
  - **Request Revisions** — opens a feedback form; the agent revises and re-sends for review
  - **Reject** — discards the draft

All actions are handled via API Gateway — no CLI needed.

## Customization

### Schedule automatic runs
Uncomment the `ScheduledTrigger` section in `template.yaml` and set your preferred schedule and default topic.

### Edit the prompts
The research and drafting prompts are in `research/index.py` and `draft/index.py`. Customize them to match your writing style and preferences.

### Change the model
The agent uses Claude 3.5 Sonnet v2 via inference profile (`us.anthropic.claude-3-5-sonnet-20241022-v2:0`). To change the model, update the `BedrockModelId` parameter in `template.yaml`.
