# Blog Agent — AI-Assisted Blog Writing Pipeline

An AWS-native blog writing agent that takes your draft, bullets, or ideas — enriches them with research and data — and produces a polished blog post in your voice. Human-in-the-loop (HITL) approval at every step.

## Philosophy

The agent is your **editor, not your ghostwriter**. You provide the ideas, opinions, and framing. The agent:
1. Enriches your points with supporting data, statistics, and citations
2. Polishes prose and structures the post using your voice profile
3. Generates data-driven SVG charts and conceptual diagrams (comparisons, staircase models, layered stacks, convergence patterns, Venn diagrams) from the draft content
4. Publishes to your site after your explicit approval

## Architecture

```mermaid
flowchart LR
    A[You — email or CLI] --> B[Ingest]
    B --> C[Research — Tavily + Bedrock]
    C --> D[Draft — Bedrock + Voice Profile]
    D --> E[Chart — SVG Generation]
    E --> F[Notify — SNS Email]
    F --> G{You — approve / revise / reject}
    G -->|approve| H[Publish — GitHub → CodeBuild → S3/CloudFront]
    G -->|revise| D
    G -->|reject| I[Discard]
    C -->|error after retries| J[PipelineFailed]
    D -->|error after retries| J
    E -->|error after retries| J
    H -->|error after retries| J
```

### Components (7 Lambda functions)
- **Ingest Lambda** — Receives inbound email via SES, parses author content and directives (Categories, Tone, Hero), starts the pipeline. SQS dead letter queue catches failed async invocations
- **Research Lambda** — Searches Tavily for real web sources, then uses Bedrock Claude Sonnet 4.6 to enrich the author's points with supporting evidence, data, and verified citations. A second focused LLM pass extracts structured data points for chart generation. Graceful fallback if Tavily is unavailable. Two modes: author-content enrichment (primary) and open research (fallback)
- **Draft Lambda** — Uses Bedrock Claude Sonnet 4.6 with an injected voice profile to polish and structure the author's content. A second LLM pass scans the draft for quantitative claims and inserts chart placeholders. A third LLM pass identifies conceptual ideas that would benefit from diagrams and inserts structured `<!-- DIAGRAM: type | ... -->` placeholders. Three modes: author-content polishing, revision from feedback, and topic-only fallback
- **Chart Lambda** — Handles two types of visuals: (1) matches structured data points from research to `<!-- CHART: -->` placeholders and renders SVG bar/donut charts, (2) parses `<!-- DIAGRAM: -->` placeholders and renders conceptual SVG diagrams (comparison, progression, stack, convergence, venn). All visuals use the site's color palette with light/dark mode support (CSS custom properties + `.dark` class). Saves to S3
- **Notify Lambda** — Stores draft in S3, sends full-text SNS email with presigned S3 download link (7-day expiry) and one-click approve/revise/reject links
- **Approve Lambda** — API Gateway handler that processes approval, revision feedback, or rejection
- **Publish Lambda** — On approval, commits the post and any chart images to GitHub (triggers CodeBuild deploy). Retries GitHub API calls with exponential backoff on transient errors (502/503/504)

### Supporting Services
- **Step Functions** — Orchestrates the pipeline: Research → Draft → Chart → HITL Review → Publish (with revision loop). All Task states have Retry (exponential backoff on Lambda transient errors) and Catch → PipelineFailed for unrecoverable errors
- **API Gateway** — HTTP API for one-click approval actions from email
- **SNS** — Email notifications for draft review
- **SES** — Inbound email processing (receives emails to `blog@khaledzaky.com`)
- **S3** — Draft and chart storage, voice profile config (auto-expires drafts after 90 days)
- **SSM Parameter Store** — Secure storage for GitHub token and Tavily API key
- **Tavily** — Web search API for real-time source discovery and citation verification (free tier: 1,000 searches/month)

### Voice Profile
The agent loads `voice-profile.md` from S3 at runtime and injects it into every Draft prompt. The profile was extracted from analysis of 20+ existing blog posts and captures:
- Tone, sentence structure, opening/closing patterns
- Vocabulary preferences and anti-patterns
- Technical depth expectations
- What Khaled always/never does in writing

See [`voice-profile.md`](voice-profile.md) for the full profile.

## Cost Estimate (~4 posts/month)
- **Bedrock (Claude Sonnet 4.6):** ~$0.30/month (~5 LLM calls/post: research, data extraction, draft, chart placement, diagram detection)
- **Tavily web search:** ~$0.00/month (free tier: 1,000 searches/month, ~2 per post)
- **Lambda (7 functions):** ~$0.00 (free tier)
- **Step Functions:** ~$0.00 (free tier)
- **SNS:** ~$0.00 (free tier, email)
- **API Gateway:** ~$0.00
- **SES (inbound):** ~$0.00
- **S3:** ~$0.01/month
- **Total: ~$0.31/month**

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

### 2. Store Tavily API key in SSM
```bash
aws ssm put-parameter \
  --name "/blog-agent/tavily-api-key" \
  --type SecureString \
  --value "tvly-YOUR_KEY_HERE" \
  --region us-east-1
```
Sign up at [app.tavily.com](https://app.tavily.com) for a free API key (1,000 searches/month).

### 3. Enable Bedrock model access
- Go to AWS Console → Amazon Bedrock → Model access
- Request access to `Anthropic Claude Sonnet 4.6`

### 4. Deploy the stack
```bash
cd agent
chmod +x deploy.sh
./deploy.sh your-email@example.com
```

This will:
- Deploy the CloudFormation stack (7 Lambdas, Step Functions, S3, SNS, API Gateway)
- Upload Lambda code from each function directory
- Upload the voice profile to S3 (`config/voice-profile.md`)

### 5. Confirm SNS subscription
Check your email and click the confirmation link.

## Usage

### Trigger via email (preferred)
Send an email to `blog@khaledzaky.com`:
- **Subject** = your blog topic or title idea
- **Body** = your draft, bullets, ideas, or stream of consciousness

The agent uses your content as the skeleton and polishes it in your voice.

#### Optional directives (add anywhere in the body)
```
Categories: tech, cloud, leadership
Tone: more technical
Hero: yes
```

### Trigger via CLI
```bash
aws stepfunctions start-execution \
  --state-machine-arn <STATE_MACHINE_ARN> \
  --input '{"topic": "Zero Trust Architecture in AWS", "categories": ["cloud", "aws", "security"], "author_content": "My bullets and ideas here..."}'
```

### Review the draft
You'll receive an email with:
- The full draft text (with charts embedded)
- Three one-click action links:
  - **Approve** — publishes the post and charts to GitHub immediately
  - **Request Revisions** — opens a feedback form; the agent revises and re-sends
  - **Reject** — discards the draft

All actions are handled via API Gateway — no CLI needed.

## Customization

### Update the voice profile
Edit `voice-profile.md` and redeploy (or upload directly):
```bash
aws s3 cp voice-profile.md s3://blog-agent-drafts/config/voice-profile.md
```

### Schedule automatic runs
Uncomment the `ScheduledTrigger` section in `template.yaml` and set your preferred schedule and default topic.

### Edit the prompts
- **Research enrichment:** `research/index.py` — controls how the agent finds supporting evidence
- **Draft polishing:** `draft/index.py` — controls how the agent structures and polishes your content
- **Chart style:** `chart/renderers/` — modular renderers for bar, pie, comparison, progression, stack, convergence, and venn diagrams. Theme constants in `renderers/theme.py` (colors, fonts, dark mode CSS custom properties)

### Change the model
The agent uses Claude Sonnet 4.6 via inference profile (`us.anthropic.claude-sonnet-4-6`). To change the model, update the `BedrockModelId` parameter in `template.yaml`.

## Ops & Observability

| Area | Detail |
|------|--------|
| **Alerting** | 3 CloudWatch alarms: pipeline execution failures, Lambda errors, API Gateway 5xx — all notify via SNS |
| **Logging** | Structured JSON logging with correlation IDs on all 7 Lambda functions; 30-day log retention |
| **Error Handling** | Lambda functions raise exceptions (not error dicts) so Step Functions sees real failures |
| **Retries** | Step Functions Retry with exponential backoff on all Task states; Publish Lambda retries GitHub API 3x |
| **Dead Letter Queue** | SQS DLQ on Ingest Lambda catches failed async invocations from SES (14-day retention) |
| **Cache Resilience** | Voice profile S3 cache backs off for 10 invocations on error before retrying |
| **Tracing** | X-Ray active on all 7 Lambda functions + Step Functions |
