---
title: "Upgrading the Blog Agent: Sonnet 4.6, Web Search, and Bug Fixes"
date: 2026-02-26
author: "Khaled Zaky"
categories: ["tech", "ai", "cloud"]
description: "A quick walkthrough of the improvements I shipped to my AI blog agent tonight: Claude Sonnet 4.6, Tavily web search for real citations, full-text review emails, and a handful of bug fixes."
---

I shipped a round of improvements to the blog agent tonight. Nothing dramatic, but the kind of changes that make the difference between a demo and a tool I actually trust.

Here is what changed.

## Model Upgrade: Claude Sonnet 4.6

The agent was running Claude 3.5 Sonnet v2 (`us.anthropic.claude-3-5-sonnet-20241022-v2:0`). That model was solid for drafting, but Anthropic has been shipping fast. Claude Sonnet 4.6 is the latest, and benchmarks show meaningful improvements in instruction following, long-form writing, and citation accuracy.

The upgrade was a one-line change in the CloudFormation template:

```yaml
BedrockModelId:
  Type: String
  Default: us.anthropic.claude-sonnet-4-6
```

The hard part was not the code. It was discovering that my Lambda environment variables had drifted from what CloudFormation thought they were. The Research and Draft Lambdas were both stuck on `anthropic.claude-3-haiku-20240307-v1:0`, which was never even in my template. Someone (me, months ago) had manually overridden the env vars via CLI, and CloudFormation stopped detecting changes.

The fix was a manual `update-function-configuration` call, plus a mental note to never touch Lambda env vars outside of CloudFormation again.

## Tavily Web Search: Real Citations

This was the bigger change. Before tonight, the Research Lambda had one source of information: Claude's training data. That meant every citation was either something the model remembered or something it hallucinated. No URLs, no verifiable sources.

Now the Research Lambda calls [Tavily](https://tavily.com) before it calls Bedrock. Tavily is a search API built specifically for AI agents. It returns structured results (title, URL, content excerpt, relevance score) optimized for LLM consumption.

The flow:

1. Build 1 to 2 targeted search queries from the topic and author content
2. Call Tavily's `/search` endpoint (advanced depth, 5 results per query)
3. Deduplicate results by URL
4. Inject the sources into the prompt with explicit citation rules

The prompt now includes a `REAL SOURCES FROM WEB SEARCH` block and tells Claude to prefer those sources over training data, always include URLs, and never fabricate citations.

The first test returned 10 results from arXiv, InfoQ, GitLab, and platformengineering.org. The output had 8 real, clickable URLs. That is a meaningful improvement over "according to a 2024 report" with no link.

The Tavily API key lives in SSM Parameter Store (`/blog-agent/tavily-api-key`) as a SecureString. The Lambda retrieves it at runtime. If the key is missing or the search fails, the agent falls back gracefully to model knowledge only. No hard dependency.

Cost: Tavily's free tier gives you 1,000 searches per month. At 2 queries per blog post, that is 500 posts before I pay anything.

## Full-Text Review Emails

The notification email was truncating the draft at 3,000 characters and linking to an S3 path (`s3://blog-agent-drafts/drafts/...`) that was not actually clickable. Not useful.

Now the email includes the full markdown post (SNS supports up to 256KB, and posts are typically 5 to 15KB). It also includes a presigned S3 download URL that expires after 7 days, matching the HITL approval timeout. Actions (approve, revise, reject) are at the top of the email so I do not have to scroll past the entire post to find them.

## Bug Fixes

A few things broke during testing and got fixed:

**Revise endpoint was broken.** The feedback form stored a URL-encoded task token in a hidden field, then the browser URL-encoded it again on POST. Double encoding. The Step Functions API received a garbled token and returned an error. Fix: store the raw token in the form field and let the browser handle the single encoding.

**Frontmatter YAML was invalid.** The Draft Lambda was generating titles like `""The Conversation After...""`  (double-double quotes) and categories like `["[\"tech\"]"]` (double-serialized JSON). Both broke the Astro build. Fix: sanitize titles by stripping outer quotes and escaping inner ones, and unwrap any double-serialized category arrays.

## What Is Next

The agent is in a good spot now. Sonnet 4.6 writes better, Tavily gives it real sources, and the review flow actually works end to end.

A few things I want to tackle next:

- **Smarter model routing.** Use a cheaper model (Haiku) for structured data extraction in Research, and Sonnet for creative writing in Draft. The orchestration layer should decide, not the Lambda code.
- **Revision memory.** Right now each revision only sees the last draft and latest feedback. It should carry forward all feedback across rounds.
- **Better chart generation.** The Chart Lambda uses regex parsing, which is fragile. An LLM pass to interpret ambiguous data formats would make it more robust.

## Next Steps

If you are running a similar agent setup, here is what I would prioritize:

- **Add web search.** The jump from hallucinated citations to real URLs is worth the 30 minutes of integration work. Tavily's free tier makes the cost argument trivial.
- **Pin your model via IaC.** If you are setting Lambda env vars manually, stop. CloudFormation drift is silent and annoying. Let the template be the source of truth.
- **Test the full loop.** It is easy to test individual Lambdas and call it done. The bugs I found tonight (double encoding, frontmatter YAML) only surfaced in the end-to-end flow.

---

*All of these changes were made, tested, and deployed in a single evening session. Total cost of the upgrades: $0.00 (Tavily free tier, Bedrock pay-per-use, everything else serverless). The agent wrote and published a separate post tonight using the new pipeline, with real citations and zero manual intervention after approval.*
