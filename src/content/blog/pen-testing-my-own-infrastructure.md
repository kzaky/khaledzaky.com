---
title: "Pen Testing My Own Infrastructure: What I Found When I Attacked My Own Stack"
date: 2026-03-01
author: "Khaled Zaky"
categories: ["security", "cloud", "aws"]
description: "I spent a Sunday running a full penetration test across my personal website, AI blog agent, and AWS infrastructure. Here is every vulnerability I found, how I fixed each one, and why this matters even for small projects."
---

I spent this Sunday morning doing something most engineers never do with their personal projects: I attacked my own infrastructure.

Not a casual "let me check my S3 bucket policies" review. A proper, structured penetration test across every layer: CloudFormation templates, Lambda functions, frontend code, CI/CD pipeline, IAM roles, and the AI blog agent that helps me write these posts. Two full passes, fresh eyes on the second round.

The results were humbling. Eleven findings. Three critical. On a stack I had already audited a week earlier.

## Why Pen Test a Personal Site?

The honest answer: because I build agentic AI platforms for a living, and if I can't secure my own setup, I have no business advising anyone else on theirs.

At RBC Borealis, I think about security across every layer of the Lumina agentic platform. LLM prompt injection, IAM boundaries, data exfiltration, supply chain risk. These are not abstract threats. They are the design constraints we work within every day.

My personal site runs a seven-function Lambda pipeline that takes my draft notes, enriches them with web research, generates SVG charts, and publishes polished posts. That pipeline touches Bedrock, S3, SNS, SES, API Gateway, Step Functions, and GitHub. It is a miniature version of the same attack surface I deal with at work.

So I blocked off the morning, opened the codebase, and started looking for ways to break it.

## The Approach

I ran two passes. The first was systematic: read every CloudFormation template, every Lambda handler, every frontend component, every build config. The second was adversarial: I pretended I was a pen tester reviewing the first tester's work, specifically looking for things the first pass missed.

![Pen test methodology — five stages from infrastructure templates to adversarial review](/postimages/charts/pen-test-methodology.svg)

The second pass is where the real findings came from.

## The Findings

Eleven total. Here is the breakdown by severity.

![Findings by severity — critical through low across four layers](/postimages/charts/pen-test-findings-severity.svg)

### Critical: Path Traversal in the Publish Lambda

This was the worst one.

When the AI agent drafts a blog post, it generates a slug (like `my-new-post`). The Publish Lambda takes that slug and commits a file to GitHub at `src/content/blog/{slug}.md` using the Git Trees API.

The problem: no validation on the slug. If the LLM produced a slug containing `../`, the Lambda would write to an arbitrary path in the GitHub repo. A slug like `../../.github/workflows/evil` would create a file at `.github/workflows/evil.md`. That is arbitrary file write to a GitHub repo, which means potential code execution via workflow injection.

The same issue existed for chart filenames and the date field used to construct S3 keys.

**The fix:** Regex allowlists. Slugs must match `^[a-z0-9]+(?:-[a-z0-9]+)*$`. Dates must be `YYYY-MM-DD`. Chart filenames must match `^[a-z0-9-]+\.svg$`. Anything else gets rejected before it touches GitHub or S3.

```python
_SAFE_SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
_SAFE_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_SAFE_FILENAME = re.compile(r'^[a-z0-9-]+\.svg$')

if slug and not _SAFE_SLUG.match(slug):
    return {"published": False, "reason": "Invalid slug"}
```

This is a pattern I have seen repeatedly in agentic systems: the LLM generates structured output that flows into downstream systems without validation. The LLM is not the threat, the missing validation layer is.

### Critical: Unbounded Feedback to the LLM

The approval flow lets me submit revision feedback through a textarea. That feedback gets passed through Step Functions into the Draft Lambda, where it is injected directly into a Bedrock prompt.

No length limit. An attacker who intercepted a task token could submit megabytes of text, causing prompt injection or cost amplification on Bedrock.

**The fix:** 5,000 character cap, enforced both server-side and with an HTML `maxlength` attribute. The server-side check is the one that matters (client-side is just UX).

```python
MAX_FEEDBACK_LENGTH = 5000

if len(feedback) > MAX_FEEDBACK_LENGTH:
    feedback = feedback[:MAX_FEEDBACK_LENGTH]
```

### High: Mermaid CDN with a Floating Version Tag

My blog posts use Mermaid for architecture diagrams. The import used a floating version tag:

```javascript
// Before — floating version, any 11.x loads
await import('https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs');
```

If someone published a malicious version of Mermaid 11.x (or if jsdelivr itself was compromised), arbitrary JavaScript would run on every page of my blog. The CSP allowed scripts from the entire `cdn.jsdelivr.net` domain, meaning any npm package on that CDN could be loaded.

**The fix:** Pin to an exact version and restrict the CSP to only that path.

```javascript
// After — exact version, no surprises
await import('https://cdn.jsdelivr.net/npm/mermaid@11.12.3/dist/mermaid.esm.min.mjs');
```

```
script-src 'self' 'unsafe-inline' https://www.googletagmanager.com
  https://cdn.jsdelivr.net/npm/mermaid@11.12.3/;
```

This is supply chain security 101, but it is easy to miss when you are moving fast.

### High: Ingest Lambda Accepted Any Sender

The Ingest Lambda receives emails via SES and triggers the blog agent pipeline. It checks that the sender matches an `ALLOWED_SENDER` environment variable. But if that variable was empty (misconfiguration), the check was skipped entirely, and any sender's email was accepted.

The return value also included the rejected sender's email address, which leaked information into CloudWatch logs.

**The fix:** Fail closed. If `ALLOWED_SENDER` is not configured, reject everything. And never include the sender address in the response.

```python
if not ALLOWED_SENDER:
    return {"processed": False, "reason": "ALLOWED_SENDER not configured"}
if sender.lower() != ALLOWED_SENDER.lower():
    return {"processed": False, "reason": "Unauthorized sender"}
```

### Medium: All Seven Lambdas Shared One IAM Role

This one bothered me the most because I should have caught it earlier.

Every Lambda function in the pipeline (Ingest, Research, Draft, Chart, Notify, Approve, Publish) used the same IAM role. That role had permissions for Bedrock, S3 (read and write), SNS, SSM (both the Tavily key and the GitHub token), and Step Functions.

This meant the Ingest Lambda (triggered by external email via SES) had access to Bedrock, the GitHub token, and the ability to write to S3. It needed none of those things. A compromised Ingest function could exfiltrate the GitHub token, invoke Bedrock, or overwrite draft files.

![Shared role vs per-function roles — before and after IAM comparison](/postimages/charts/pen-test-iam-comparison.svg)

**The fix:** Seven separate IAM roles, each scoped to exactly what that function needs. The Approve Lambda can only send task tokens. The Chart Lambda can only write to the `charts/*` prefix. The Publish Lambda can only read drafts and access the GitHub token. No function can touch resources it does not need.

This is the principle of least privilege applied properly. Not "one role with scoped policies" but "one role per function, each with the minimum permissions."

### The Rest

| # | Severity | Finding | Fix |
|---|----------|---------|-----|
| 1 | Critical | Path traversal via slug/date/filename | Regex allowlists |
| 2 | Critical | Unvalidated S3 key construction | Date format validation |
| 3 | Critical | Unbounded feedback to LLM | 5,000 char server-side cap |
| 4 | High | Mermaid CDN floating version, broad CSP | Pinned version + path-scoped CSP |
| 5 | High | Ingest accepts any sender if misconfigured | Fail closed + no info leak |
| 6 | High | API Gateway has no authorizer | Accepted risk (task token is the auth) |
| 7 | Medium | CSP `unsafe-inline` weakens XSS protection | Noted for future nonce-based refactor |
| 8 | Medium | Shared IAM role across all Lambdas | 7 per-function roles |
| 9 | Medium | S3 PutObject allows overwrites | Noted (DenyOverwrite condition planned) |
| 10 | Low | CodeBuild caches `node_modules` | Removed cache entirely |
| 11 | Low | No `npm audit` in CI | Added `npm audit --audit-level=high` |

## What This Taught Me

### Agentic Systems Need Input Validation at Every Boundary

The path traversal finding is the most important lesson. In a traditional web app, you validate user input at the API boundary. In an agentic system, the LLM generates structured data (slugs, filenames, dates) that flows into downstream Lambdas, S3, and GitHub. That LLM output is not trusted input. It needs the same validation you would apply to user input.

This is not hypothetical. Prompt injection research has shown that LLMs can be manipulated into producing adversarial structured output. The fix is not "trust the LLM more," it is "validate everything downstream."

### The Second Pass Always Finds Things

I had already done a full security audit a week earlier. I found and fixed twelve issues in that first audit. Then I came back with fresh eyes and found eleven more.

The first pass catches the obvious things: open S3 buckets, missing encryption, overly broad IAM policies. The second pass catches the subtle things: path traversal via LLM output, supply chain risks in CDN imports, fail-open defaults on sender validation.

If you only do one pass, you are leaving vulnerabilities on the table.

### Least Privilege Means Per-Function, Not Per-Service

Before this audit, my IAM setup was "one role with multiple scoped policies." That sounds reasonable until you realize the Ingest Lambda (which processes external email) had the same permissions as the Publish Lambda (which holds the GitHub token). The blast radius of a single compromised function was the entire pipeline.

Per-function roles are more YAML to maintain, but the security boundary is real. When you work in regulated environments (and I have spent years in financial services and identity), this is not optional. It is table stakes.

### Personal Projects Are Production Systems

I sometimes hear engineers say "it is just a personal site" as a reason to skip security hygiene. But personal projects are where you build the habits that carry into production. If you practice least privilege, input validation, and supply chain security on your side projects, you will do them instinctively at work.

And if your personal site runs an AI agent that commits code to your GitHub repo via API? That is a production system, whether you call it one or not.

## Next Steps

Three things I am planning but have not done yet:

1. **Nonce-based CSP** to eliminate `unsafe-inline`. This requires changes to how Astro handles inline scripts in static output mode. Not trivial, but it is the right direction.
2. **S3 DenyOverwrite condition** on the drafts bucket to prevent any Lambda from overwriting the voice profile or CloudTrail logs.
3. **Automated security scanning** in the CI pipeline beyond `npm audit`, potentially including SAST for the Python Lambda code.

The full diff is two commits, eight files, 222 lines changed. Everything described in this post is live on [the GitHub repo](https://github.com/kzaky/khaledzaky.com).

*All changes described in this post were made on a single Sunday morning. Total findings: eleven. Time to fix: about two hours. Downtime: zero.*
