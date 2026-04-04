---
title: "Practicing What I Preach: What I Added (and Skipped) When Auditing My Own Blogging Agent"
date: 2026-04-04
author: "Khaled Zaky"
categories: ["tech", "ai", "agentic-ai"]
description: "- I audited my own blogging agent against the eval and guardrail standards I write about professionally."

---

## TL;DR

- I audited my own blogging agent against the eval and guardrail standards I write about professionally.
- I added two lightweight checks: CloudWatch quality metrics and an author intent preservation score.
- I deliberately skipped golden datasets, A/B prompt testing, and external eval platforms. Here's why that was the right call.

---

## How It Started (and How It Grew)

I built this pipeline to save myself time. I went back today to change one thing and spent an hour just reading my own code.

[The original agent](https://khaledzaky.com/blog/i-built-an-ai-agent-that-writes-for-my-blog/) was simple: write some bullets or a rough draft, send it as an email, and an AI pipeline enriches, verifies citations, polishes to my voice, and queues it for my review before publishing. That was the idea.

What I found when I opened the code was something else entirely. The `Draft Lambda` alone now runs seven sequential LLM passes: a thinking plan, a full draft generation, chart placeholder insertion, diagram placeholder insertion, a citation audit (Sonnet, full rewrite, 8192 tokens), a voice profile audit (Sonnet, always rewrites, never truncates), and an insight audit.

On top of that, there's a dedicated `Verify Lambda` that fetches every URL in the post and LLM-checks each claim against the actual page content, a `Chart Lambda` that renders SVGs in five visual styles, and a category inference pass.

It had grown. A lot.

---

## The Audit: What I Found

I write about [evals](https://khaledzaky.com/blog/evaluations-the-control-plane-for-ai-governance/), [guardrails](https://khaledzaky.com/blog/dynamic-guardrails-for-agentic-ai-why-static-rules-break-down-when-agents-can-delegate/), and [human-in-the-loop pipelines](https://khaledzaky.com/blog/from-periodic-reviews-to-continuous-governance/) for enterprise AI systems constantly. I have opinions. The question I had to sit with was: am I practicing what I preach on my own agent?

So I made a list. Everything I talk about in the eval and guardrail space: golden dataset testing, LLM-as-judge eval frameworks, automated acceptance criteria, A/B prompt testing, drift detection, confidence scoring, HITL pipelines, structured output validation, citation quality scoring, observability and metrics.

Then I went through each one and asked a harder question: is this actually useful for a personal blog agent with one author, 4 to 6 posts per month, and a human reviewing every single draft before it publishes?

The answer wasn't "yes" across the board.



---

## What I Added (and Why)

### CloudWatch Quality Metrics

I was already computing a citation quality percentage inside the `Notify Lambda` (passed links divided by reachable links). I was logging it and throwing it away.

It took about 20 lines to emit it as an actual CloudWatch metric. `CitationQualityScore` and `PostWordCount` from the `Notify Lambda`. `HITLApproved`, `HITLRevised`, or `HITLRejected` from the `Approve Lambda` on each decision.

```python
def _emit_pipeline_metrics(citation_score: float, word_count: int) -> None:
    cloudwatch = boto3.client("cloudwatch")
    cloudwatch.put_metric_data(
        Namespace="BlogAgent/Quality",
        MetricData=[
            {
                "MetricName": "CitationQualityScore",
                "Value": citation_score,
                "Unit": "Percent",
            },
            {
                "MetricName": "PostWordCount",
                "Value": word_count,
                "Unit": "Count",
            },
        ],
    )
```

Now I have trend data. Did citation quality drop after I changed the `Verify Lambda` prompt? Did I revise more often this week than last? These are questions I can now answer. Cost: essentially zero. Value: real.

### Author Intent Preservation Check

This one felt the most true to the purpose of the pipeline. My agent is an editorial assistant, not a content generator. I give it my ideas, my opinions, my rough framing. The whole point is that it polishes my voice, not that it replaces it.

But polishing can drift. A Haiku LLM pass in the `Notify Lambda` now scores 0 to 10: did the final draft preserve my original claims and framing, or did it drift into generic AI commentary? The score and a short list of preserved versus drifted claims appear right in the HITL review email.

```python
def _check_author_intent(original_bullets: str, final_draft: str) -> dict:
    prompt = f"""Score 0-10: did the final draft preserve the author's
original claims and framing, or did it drift toward generic commentary?

Original input:
{original_bullets}

Final draft:
{final_draft}

Return JSON: {{"score": int, "preserved": [str], "drifted": [str]}}"""

    response = anthropic_client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(response.content[0].text)
```

If the agent softened a contrarian take, I catch it before approving. One Haiku call at 512 tokens. Negligible cost. Real value.

---

## What I Deliberately Skipped (and Why)

**Golden dataset evals.** This would require labeling historical posts, defining what "correct" looks like, and maintaining a test suite over time. For 4 to 6 posts per month on a personal blog, the maintenance overhead exceeds the benefit. HITL is my eval. I see every post.

**Automated acceptance criteria on LLM output.** Same reasoning. The pipeline already has a human exit gate. I'm the acceptance test.

**A/B prompt testing.** I'm the only user. There's no statistical significance to chase. When I update a prompt and the next post is better, that's my signal.

**External eval platforms.** I'd spend more time integrating and maintaining the eval infrastructure than writing posts. This is a personal blog, not a production AI product.

The through-line in everything I skipped: the value of these tools scales with volume, team size, and the invisibility of failures. My pipeline has low volume, one user, and a mandatory human review gate. The proportional response is surgical, lightweight checks, not enterprise-grade eval harnesses.

![Practitioner-reported top bottlenecks in AI content pipelines (hallucination detection vs. citation verification vs. voice consistency)](/postimages/charts/practicing-what-i-preach-what-i-added-and-skipped-when-auditing-my-own-blogging-agent-chart-1.svg)
*Source: State of AI Report 2025*

![Enterprise AI System](/postimages/charts/practicing-what-i-preach-what-i-added-and-skipped-when-auditing-my-own-blogging-agent-diagram-1.svg)

---

## The Pipeline, Annotated

Here's where the two new checks live relative to the full pipeline:



```architecture
Research → Draft (7 LLM passes) → Verify → Chart → Notify (intent check + metrics) → HITL → Publish
```

![Blog Agent Pipeline](/postimages/charts/practicing-what-i-preach-what-i-added-and-skipped-when-auditing-my-own-blogging-agent-diagram-2.svg)

The `Notify Lambda` is the right insertion point for both additions. It sits after all enrichment is complete and before the human review gate, which means it catches drift and quality issues at exactly the moment I need to act on them.

---

## The Meta-Lesson

There's a seductive trap in this field where we apply enterprise patterns to personal-scale problems because that's what we know and what gets applause. I've written about [governance as infrastructure](https://khaledzaky.com/blog/from-governance-is-a-platform-problem-to-governance-is-infrastructure/) and [agent observability](https://khaledzaky.com/blog/agent-observability-the-missing-layer-in-agentic-ai-platforms/) in the context of platforms serving hundreds of engineers. Those patterns are right at that scale.

They're not automatically right here.

Real engineering judgment is knowing when not to build something. The most important architecture decision I made today was the list of things I chose not to implement.

Auditing your own systems is different from auditing someone else's. There's no stakeholder to impress, no design review to pass. The only question is whether the system actually serves its purpose. Mine does. I made it slightly better. I stopped there.

---

## Actionable Takeaways

- **Before adding any eval mechanism, ask:** does the failure mode I'm guarding against actually occur in my system, at my scale? If you have a mandatory human review gate, that gate is doing real work. Don't duplicate it with automated checks that add friction without adding coverage.
- **Emit metrics before you need them.** The CloudWatch change took 20 lines. The value isn't in the metrics today; it's in having a baseline when something changes. Do this early.
- **Intent preservation is underrated.** If your pipeline takes human input and transforms it, you need at least one check that the transformation preserved the original framing. A single lightweight LLM pass at the end of the pipeline is enough.
- **Proportionality is a design principle.** Match your eval infrastructure to your actual failure surface, not to what looks impressive in a conference talk.

*The hardest audit is always the one you run on yourself.*