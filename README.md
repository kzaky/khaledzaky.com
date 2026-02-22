# khaledzaky.com

[![AWS CodeBuild](https://codebuild.us-east-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoiZWpnQ1BCdDZlK1hTVnQvRExheDg2V1VCQ3Zzb2U1N1JnQUdyWlpkS0dta2g2T3ZjSTZDLzc1M1F2K2FEVk1MNVg4b0Zha2pzTHJXc3ZMZENpVG9ZOWVFPSIsIml2UGFyYW1ldGVyU3BlYyI6IklTaTVYNERaL0R5K2gvRDciLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=master)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Astro](https://img.shields.io/badge/Astro-v5-BC52EE?logo=astro&logoColor=white)](https://astro.build)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v3-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![AWS Lambda](https://img.shields.io/badge/AWS_Lambda-Serverless-FF9900?logo=awslambda&logoColor=white)](https://aws.amazon.com/lambda/)
[![Amazon Bedrock](https://img.shields.io/badge/Amazon_Bedrock-Claude_3.5_Sonnet-232F3E?logo=amazonaws&logoColor=white)](https://aws.amazon.com/bedrock/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![Infrastructure as Code](https://img.shields.io/badge/IaC-CloudFormation-FF4F8B?logo=amazonaws&logoColor=white)](https://aws.amazon.com/cloudformation/)

My personal website and blog — [khaledzaky.com](https://khaledzaky.com)

Built with [Astro](https://astro.build) and [Tailwind CSS](https://tailwindcss.com), deployed on AWS, with an AI-powered blog agent that researches, drafts, and publishes posts with human-in-the-loop approval.

---

## Architecture Overview

```mermaid
graph LR
    subgraph "Content & Build"
        A[Markdown Posts] --> B[Astro v5 + Tailwind]
        B --> C[Static HTML/CSS/JS]
    end

    subgraph "CI/CD"
        D[GitHub Push] --> E[AWS CodeBuild]
        E --> F[S3 Bucket]
        F --> G[CloudFront CDN]
    end

    C --> D
    G --> H[khaledzaky.com]
```

```mermaid
graph TD
    subgraph "AI Blog Agent"
        EM[Email to blog@khaledzaky.com] --> IG[Ingest Lambda]
        CLI[CLI Trigger] --> SF
        IG --> SF[Step Functions]
        SF --> R[Research Lambda]
        R -->|Claude 3.5 Sonnet| D[Draft Lambda]
        D --> N[Notify Lambda]
        N -->|SNS Email| U[Human Review]
        U -->|Approve| AP[Approve Lambda]
        U -->|Request Revisions| AP
        U -->|Reject| AP
        AP -->|Approved| P[Publish Lambda]
        AP -->|Revise with Feedback| D
        P -->|GitHub API| GH[GitHub Commit]
        GH --> CB[CodeBuild Auto-Deploy]
    end

    subgraph "AWS Services"
        SES[Amazon SES] -.-> IG
        S3[S3 Drafts Bucket] -.-> N
        S3 -.-> P
        BK[Amazon Bedrock] -.-> R
        BK -.-> D
        AG[API Gateway] -.-> AP
    end
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Framework** | Astro v5 with Tailwind CSS v3 + `@tailwindcss/typography` |
| **Content** | Markdown with Astro content collections |
| **Build** | AWS CodeBuild (Node.js 20) |
| **Hosting** | Amazon S3 (OAC-locked) + CloudFront (HTTPS-only, compressed, security headers) |
| **TLS** | AWS Certificate Manager |
| **AI Model** | Claude 3.5 Sonnet v2 via Amazon Bedrock |
| **Orchestration** | AWS Step Functions |
| **Approval** | API Gateway HTTP API + Lambda |
| **Notifications** | Amazon SNS (email) |
| **Email Ingest** | Amazon SES (inbound) + Route 53 MX |
| **DNS** | Amazon Route 53 |
| **Secrets** | AWS SSM Parameter Store (SecureString) |
| **Source Control** | GitHub (master branch, webhook-triggered deploys) |

## Project Structure

```
khaledzaky.com/
├── src/
│   ├── components/       # Astro components (Header, Footer, SectionCard, CredibilityRow)
│   ├── content/blog/     # Markdown blog posts (content collection)
│   ├── layouts/          # BaseLayout, BlogPost layout
│   ├── pages/            # index, about, work, blog routes (includes rss.xml.js)
│   └── styles/           # Global CSS
├── public/               # Static assets (images, favicon)
├── agent/                # AI blog agent (Lambda functions + IaC)
│   ├── research/         # Topic research via Bedrock
│   ├── draft/            # Blog post drafting via Bedrock
│   ├── notify/           # SNS email with one-click approve/revise/reject
│   ├── approve/          # API Gateway handler for approval + revision feedback
│   ├── publish/          # Commits approved posts to GitHub
│   ├── ingest/           # SES email trigger — parses topic from inbound email
│   ├── template.yaml     # CloudFormation (SAM) template
│   └── deploy.sh         # One-command deployment script
├── buildspec.yml         # AWS CodeBuild build specification
├── astro.config.mjs      # Astro configuration
├── tailwind.config.cjs   # Tailwind configuration
└── package.json
```

## Running Locally

```bash
# Clone the repo
git clone https://github.com/kzaky/khaledzaky.com.git
cd khaledzaky.com

# Install dependencies
npm install

# Start dev server
npm run dev
# → http://localhost:4321

# Build for production
npm run build
# → outputs to dist/
```

## Deployment

Deployment is fully automated. Pushing to `master` triggers AWS CodeBuild, which:

1. Installs dependencies (`npm ci`, with local cache for `node_modules`)
2. Builds the site (`npm run build`)
3. Syncs `dist/` to the S3 bucket (`--delete` to remove stale files)
4. Invalidates the CloudFront cache

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GH as GitHub
    participant CB as CodeBuild
    participant S3 as S3 Bucket
    participant CF as CloudFront

    Dev->>GH: git push origin master
    GH->>CB: Webhook trigger
    CB->>CB: npm ci && npm run build
    CB->>S3: aws s3 sync dist/
    CB->>CF: create-invalidation /*
    CF->>CF: Cache refreshed
```

## AI Blog Agent

The blog agent is a serverless pipeline that researches topics, drafts blog posts using Claude, and publishes them with human approval.

### How It Works

1. **Trigger** — Send an email to `blog@khaledzaky.com` or run the CLI command with a topic
2. **Ingest** (email only) — SES receives the email, stores it in S3, and the Ingest Lambda parses the subject (topic) and body (notes) to start the pipeline
3. **Research** — Claude researches the topic and produces structured notes
4. **Draft** — Claude writes a complete Markdown blog post with Astro frontmatter
5. **Notify** — Draft is saved to S3 and an email is sent with a preview and three one-click actions
6. **Review** — The pipeline pauses and waits for human action (up to 7 days):
   - **Approve** — publishes the post immediately
   - **Request Revisions** — opens a feedback form; the agent revises the draft and re-sends for review
   - **Reject** — discards the draft
7. **Publish** — On approval, the post is committed to GitHub via API, triggering auto-deploy

### Deploying the Agent

Prerequisites:
- AWS CLI configured with appropriate credentials
- GitHub Personal Access Token stored in SSM:
  ```bash
  aws ssm put-parameter --name "/blog-agent/github-token" \
    --type SecureString --value "ghp_YOUR_TOKEN"
  ```
- Amazon Bedrock model access enabled for Anthropic Claude

Deploy:
```bash
cd agent
./deploy.sh your-email@example.com
```

Confirm the SNS email subscription when you receive it.

### Triggering a New Post

**Option 1: Email** (preferred)

Send an email from your authorized address to `blog@khaledzaky.com`:
- **Subject** = the blog topic
- **Body** = optional notes, context, or TL;DR to guide research
- Optionally include `Categories: tech, cloud, leadership` in the body

**Option 2: CLI**

```bash
aws stepfunctions start-execution \
  --state-machine-arn $(aws cloudformation describe-stacks \
    --stack-name blog-agent \
    --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
    --output text) \
  --input '{"topic": "Your topic here", "categories": ["tech", "cloud"]}'
```

### Agent Architecture

```mermaid
stateDiagram-v2
    [*] --> Research
    Research --> Draft
    Draft --> NotifyForReview
    NotifyForReview --> WaitForApproval
    WaitForApproval --> CheckApproval: Human clicks link
    CheckApproval --> Publish: Approved
    CheckApproval --> Revise: Request Revisions
    CheckApproval --> Rejected: Rejected
    Revise --> Draft: Feedback included
    Publish --> [*]
    Rejected --> [*]
```

### Security

- **Secrets** — GitHub token stored in SSM Parameter Store as SecureString, never in code or environment variables
- **IAM** — Lambda role follows least-privilege with scoped policies per service; `StartExecution` scoped to specific state machine ARN
- **API Gateway** — Approval endpoint is public but uses one-time Step Functions task tokens that expire after 7 days
- **S3** — AES-256 server-side encryption enabled; all public access blocked (4/4 settings); Origin Access Control (OAC) restricts reads to CloudFront only; S3 website hosting disabled
- **SES** — TLS required on inbound email; spam and virus scanning enabled; only authorized sender processed
- **Encryption** — SSM parameters use AWS-managed KMS
- **No hardcoded credentials** — All sensitive values injected via environment variables or SSM at runtime
- **Lifecycle** — Draft objects auto-expire after 90 days

### Cost Estimate

The agent is designed to be extremely cheap to run:

| Resource | Cost |
|----------|------|
| Lambda (6 functions, ~30s/invocation) | ~$0.00 per post |
| Step Functions (1 execution) | ~$0.00 per post |
| Bedrock Claude 3.5 Sonnet (~2K tokens in, ~4K out) | ~$0.03 per post |
| S3 (draft storage) | ~$0.00 |
| SNS (1 email) | ~$0.00 |
| API Gateway (1-3 requests) | ~$0.00 |
| SES (1 inbound email) | ~$0.00 |
| **Total per post** | **~$0.03** |

At 10 posts/month, the agent costs roughly **$0.30/month**. The website infrastructure itself costs ~$3.50/month (primarily Route 53 hosted zone fees).

## Infrastructure Hardening

The hosting infrastructure has been hardened across security, performance, and cost:

| Area | Detail |
|------|--------|
| **S3 Access** | Public access fully blocked; Origin Access Control (OAC) restricts reads to CloudFront distribution ARN only |
| **HTTPS** | HTTP requests 301-redirect to HTTPS; TLS 1.2 minimum enforced |
| **Security Headers** | HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, X-XSS-Protection via managed policy |
| **Compression** | Gzip + Brotli enabled on CloudFront |
| **URL Rewriting** | CloudFront Function handles `index.html` resolution (replaces S3 website hosting) |
| **Custom Errors** | 403 and 404 mapped to `/404.html` |
| **TLS Certificate** | Wildcard ACM cert (`*.khaledzaky.com` + apex), auto-renewing |
| **Price Class** | PriceClass_100 (NA + EU edge locations) |
| **Build Cache** | CodeBuild local cache for `node_modules` |
| **HTTP/2 + HTTP/3** | Both enabled on CloudFront |

## License & Copyright

Copyright Khaled Zaky. All rights reserved for the following — you may not reuse without written permission:
- `src/content/blog/` (blog post content)
- `public/img/` (personal images)

The code and styles are licensed under the [MIT License](LICENSE).
