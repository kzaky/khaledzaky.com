---
title: "I spent a Saturday debugging my AI blog agent and ended up rebuilding how it thinks"
date: 2026-03-21
author: "Khaled Zaky"
categories: ["ai", "platform-engineering"]
description: "The research step in my blog agent had been bugging me for months. Not broken. Working. Just not earning its place in the pipeline"
---

## It Was Working. That Was the Problem.

The research step in my blog agent had been bugging me for months. Not broken. Working. Just not earning its place in the pipeline.

That's a harder problem to fix than something that is outright broken. When a system fails loudly, the path is clear. When it works adequately, you have to convince yourself the friction is real before you do anything about it.

I spent this past Saturday convincing myself, and then fixing it.

---

## What the Pipeline Actually Does

The blog agent is an AWS-native editorial pipeline. Give it a draft or a set of bullets, and it enriches the content with research, polishes the prose in my voice, generates charts where relevant, and queues the result for my review before anything gets published. I wrote about the original build [here](https://khaledzaky.com/blog/i-built-an-ai-agent-that-writes-for-my-blog/), and the subsequent upgrades [here](https://khaledzaky.com/blog/upgrading-the-blog-agent-sonnet-4-6-and-real-citations/) and [here](https://khaledzaky.com/blog/weekend-engineering-smarter-ai-pipeline-alarms-and-upgrading-to-claude-sonnet-46-with-extended-thinking/).

The design philosophy has always been the same: the AI raises the bar on your ideas. It does not replace them.

The research step is what makes that possible. If the sources are thin, the enrichment is thin. The model can only work with what it receives.

![Blog Agent Pipeline](/postimages/charts/i-spent-a-saturday-debugging-my-ai-blog-agent-and-ended-up-rebuilding-how-it-thinks-diagram-1.svg)

---

## The Architectural Smell I Kept Ignoring

The pipeline was built on **Tavily**, which is a solid API. Built specifically for LLM and agent use cases, with semantic search, structured extraction, and real-time results. The right tool for this job.

But I kept hitting the same problems, and kept patching around them instead of addressing the root cause.

The results I was seeing were technically relevant but intellectually thin. I kept seeing the same source types dominating: Medium posts, Reddit threads, Quora answers. High volume, low signal. The kind of content that ranks well because it's everywhere, not because it's authoritative.

Dead links were making it through to drafts and getting cited. I added URL verification. That helped, but it meant some queries came back with fewer usable results than expected, so I added blocked-domain retry logic. That helped too. Then I added full article fetch for the top results to get beyond the snippet. Each patch was reasonable. Each one addressed a real symptom.

The problem was I was patching symptoms. The underlying issue was architectural: one search engine is a single point of failure for **source diversity**. Same index, same ranking signals, same blind spots, every single query.

![Single Search Engine](/postimages/charts/i-spent-a-saturday-debugging-my-ai-blog-agent-and-ended-up-rebuilding-how-it-thinks-diagram-2.svg)

---

## What I Changed and Why

The fix was not more patching. It was adding a second independent research layer.

I added **Perplexity** alongside Tavily. Not as a replacement. As a parallel track with a fundamentally different job.

The design works like this: Tavily runs all queries for breadth, using its `search_depth` and `max_results` parameters to pull structured sources across the full query set. Perplexity's `sonar-pro` model runs on the first two queries for synthesis, it reads its sources, distills them, and returns a coherent narrative with citations already embedded. Both run simultaneously. The results merge: Tavily's structured sources plus Perplexity's synthesis plus any net-new citation URLs that Perplexity surfaces from its own index.

The point is not more results. The point is two different **epistemologies** operating on the same question at the same time. Tavily gives breadth and raw sources. Perplexity gives synthesis from a different index with different ranking logic. The LLM writing the enrichment now receives both perspectives and has to reconcile them.

That reconciliation is where the quality improvement actually comes from. The model is not just pattern-matching against a list of URLs anymore. It's working with a richer, more contested picture of the topic.

![Enriched Content](/postimages/charts/i-spent-a-saturday-debugging-my-ai-blog-agent-and-ended-up-rebuilding-how-it-thinks-diagram-3.svg)

---

## The Alarm System Was Also Broken (In a Different Way)

While I was in there, I fixed the alerting.

The pipeline has a human-in-the-loop review window: seven days. If I don't approve a draft within that window, the state machine routes it to an expired state. This was triggering failure alarms. Every time I was busy for a week, I got paged about a "pipeline failure."

Those aren't failures. That's me being busy.

I added a `HITLExpired` success state to route those silently. Not a failure path. Not an alert. Just a clean terminal state that acknowledges the draft aged out without approval.

The second fix was more important: wiring actual error type and cause into the failure alert payload. Before, a real failure would fire an alarm that told me the pipeline had failed. Not helpful. Now the alert tells me what broke and why. When something real goes wrong, the signal is actually readable.

This is the distributed systems reliability problem in miniature. **False positives** aren't just annoying. They train you to ignore alerts. By the time a real failure fires, you've already learned to dismiss the noise. The fix isn't a louder alarm. It's a cleaner one.

---

## What I Took Away

The model is the least interesting part of making these systems reliable.

That sounds counterintuitive when you're working on an AI pipeline, but it's the honest answer after a day like Saturday. The interesting work is what sources you feed the model, how you verify those sources are real, how you handle partial failures without collapsing the whole run, and how you reduce noise so the signal actually stands out.

I build agentic AI platforms professionally, at a bank, at scale, with compliance constraints that make every architectural decision more consequential. The patterns are the same. The vocabulary around [governance](https://khaledzaky.com/blog/governing-autonomous-agents-is-a-platform-problem/) and [observability](https://khaledzaky.com/blog/agent-observability-the-missing-layer-in-agentic-ai-platforms/) is different. The underlying work is not.

Reliability is boring. That's not a criticism. Boring is what you want. Boring means the system is doing its job without demanding your attention.

You can read every API doc Tavily publishes. You can read every architecture pattern writeup that exists. You won't learn what I learned on Saturday. That gap is the whole point of building your own things.

*The draft enrichment quality improved. I noticed it immediately. I can't prove it to you, and I don't need to.*
