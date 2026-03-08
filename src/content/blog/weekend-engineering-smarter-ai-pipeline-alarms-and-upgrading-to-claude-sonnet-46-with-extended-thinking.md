---
title: "Weekend engineering: smarter AI pipeline alarms and upgrading to Claude Sonnet 4.6 with extended thinking"
date: 2026-03-07
author: "Khaled Zaky"
categories: ["cloud", "ai", "devops"]
description: "I spent my weekend making some real improvements to the AI blog pipeline that powers this site. Here's what I shipped:"
---

I spent my weekend making some real improvements to the AI blog pipeline that powers this site. Here's what I shipped:

### Readable Alarm Emails for My AI Blog Pipeline

The blog agent pipeline (**Step Functions + Lambda**) used to send raw CloudWatch alarm JSON to my email whenever something failed. Those raw JSON emails were completely useless — you couldn't tell at a glance what'd broken or what to do about it.

So I built an alarm-formatter Lambda that intercepts those CloudWatch alarm messages, queries Step Functions for the actual failed execution, and enriches the email with helpful context: the error type, which state failed, the topic being processed, the start and stop times, and a direct console link. The signal-to-noise improvement is massive.

Before, it was just a wall of JSON. Now, the subject line tells you exactly what happened, and the body has one link to take you straight to the console.

<!-- DIAGRAM: comparison | Raw CloudWatch Alarm | Formatted Alarm Email | Wall of JSON;Useless at a glance | Classified error type;Actionable | No context;Requires manual investigation | Failed state + topic + timestamps;Direct console link -->

I also created a new SNS topic specifically for these formatted alarm emails, separate from the raw review topic that gets the HITL approval links. This way, I can triage and respond to real issues quickly without getting bogged down in the noise of normal HITL timeouts (which the formatter now classifies differently).

### Upgraded to Claude Sonnet 4.6 with Extended Thinking

I was already using Sonnet 4.6 for the blog pipeline, but I hadn't enabled the extended thinking mode via the Bedrock converse API. So I went ahead and added that.

One interesting constraint I hit: the cross-region inference profiles in Anthropic's API cap the max tokens at 4096, which isn't enough for a full thinking pass plus the full generated output in one call. So I ended up building a two-pass architecture:

1. The first pass is a short `converse+thinking` call that produces a research plan or writing plan (which easily fits in 4096 tokens).
2. The second pass then injects that plan into the main generation prompt and runs `invoke_model` for the full output.

![Extended Thinking Pipeline](/postimages/charts/weekend-engineering-smarter-ai-pipeline-alarms-and-upgrading-to-claude-sonnet-46-with-extended-thinking-diagram-2.svg)

The thinking pass reasons about things like the best research angles, what claims in the draft need verification, and the ideal post structure and hooks. I decided to only enable this thinking on the high-value creative passes (research synthesis, draft writing) — the four deterministic passes (chart insertion, diagram insertion, citation audit, voice audit) stay on plain `invoke_model`, since the thinking adds cost with zero benefit.

If the thinking pass fails for any reason, the pipeline gracefully falls back to plain generation. No hard dependency.

The Lambda timeouts have increased as a result: Research is now 600s, Draft is 900s.

### Reflections

The alarm formatter is a good example of making the signal useful. A raw alarm is just noise, but a classified and enriched alarm is something I can actually action.

The thinking constraint discovery was also interesting. You assume a capability exists uniformly, then you hit an API limit that forces you to get creative. The two-pass approach arguably works better anyway — separating planning from execution is a cleaner design.

Extended thinking on Claude is real. The research output with the planning pass feels noticeably more structured, and the cost tradeoff is worth it for a pipeline that only runs a few times a month.

The cost tradeoff is also worth considering. Sonnet sits meaningfully below Opus on both input and output pricing, which matters when you're running a multi-pass pipeline with several LLM calls per post. For a low-volume personal pipeline the dollar difference is small, but the principle carries: match the model tier to the task, and don't pay for capability you don't need.

### Next Steps

If you're running any kind of AI-powered blog, newsletter, or content pipeline, I'd highly recommend looking into a similar alarm-formatting setup. It makes triage and response so much easier.

And if you're running any AI pipeline, the model sizing principle is simple: use the best model only where judgment and creativity actually matter. Everything else should be the fastest, cheapest model that can do the job reliably.

*All changes described in this post were made on a single Sunday morning. Total downtime: zero.*
