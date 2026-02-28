---
title: "Teaching the Blog Agent to See: Conceptual Diagrams and Visual Thinking"
date: 2026-02-28
author: "Khaled Zaky"
categories: ["tech", "ai", "cloud"]
description: "The blog agent can now detect conceptual ideas in a draft and generate SVG diagrams automatically. Comparisons, maturity models, layered stacks, convergence patterns, and Venn diagrams, all rendered in code and matched to the site's design system. Here is how I built it and what I learned about giving an agent visual reasoning."
---

A week ago I wrote about [building an AI agent that writes for my blog](/blog/i-built-an-ai-agent-that-writes-for-my-blog). Two days later I [upgraded it](/blog/upgrading-the-blog-agent-sonnet-4-6-and-real-citations) with Sonnet 4.6, real web citations via Tavily, and a batch of bug fixes.

The agent was getting better at writing. But it was still blind.

Every post it produced was a wall of text. No visuals. No diagrams. The Chart Lambda could render bar and donut charts from numeric data, but most of my posts are not about numbers. They are about comparisons, layered architectures, maturity models, and converging trends. The kind of ideas that are easier to grasp in a diagram than in a paragraph.

So I taught the agent to see structure in prose and render it visually. Here is what changed, how it works, and what I learned.

## The Problem

Look at any post on this blog about platform engineering or agentic AI. The arguments follow patterns:

- **"X vs Y"** comparisons (traditional software vs agents, deterministic vs probabilistic)
- **Stage models** (sandbox, pilots, platform, operationalized at scale)
- **Layered stacks** (identity at the bottom, self-service at the top)
- **Convergence** (7 independent building blocks forming one platform)
- **Overlapping categories** (human, agent, machine identity)

These are not data points. They are conceptual structures. The old Chart Lambda had no idea what to do with them because it only understood `Label: number` pairs.

The result: I was manually creating SVGs for every post that needed a visual. That defeated the purpose of having an agent handle the publishing mechanics.

## What I Built

The solution has three parts:

1. A **new LLM pass** in the Draft Lambda that reads the finished draft and identifies where a conceptual diagram would help
2. A **structured placeholder format** that encodes the diagram type, labels, and relationships
3. **Five SVG template renderers** in the Chart Lambda that turn those specs into visuals matching the site's design system

The pipeline now runs five LLM calls per post instead of four: research, data extraction, draft generation, chart placeholder insertion, and diagram detection. The extra call costs about two cents.

## The Diagram Detection Pass

After the Draft Lambda generates the post and inserts chart placeholders for numeric data (the second pass), a third pass scans the finished draft for conceptual structures.

The prompt is specific about what qualifies:

- **Good candidates:** comparisons between two approaches, multi-stage models, layered architectures, converging trends, overlapping categories
- **Bad candidates:** simple bullet lists, chronological narratives, single-concept explanations
- **Hard limit:** at most 3 diagrams per post

The LLM outputs the complete draft with `<!-- DIAGRAM: type | field1 | field2 | ... -->` placeholders inserted after the relevant paragraphs. The format is pipe-delimited, with semicolons for sub-fields. It is ugly, but it is unambiguous and trivial to parse without regex gymnastics.

Here is what a comparison placeholder looks like:

```
<!-- DIAGRAM: comparison | Traditional Software | AI Agents | Deterministic:Probabilistic | Request/Response:Autonomous Action | Static Permissions:Dynamic Authority -->
```

And a progression (staircase model):

```
<!-- DIAGRAM: progression | Platform Maturity | Sandbox;Small experiments;Fast iteration | Guarded Pilots;Defined use cases;Basic logging | Reusable Platform;Shared controls;Self-service | Operationalized;Strong governance;Runtime controls -->
```

The format encodes everything the renderer needs: diagram type, headers, labels, and details. No second LLM call required to interpret it.

## Five Diagram Types

The Chart Lambda now handles two kinds of placeholders: `<!-- CHART: -->` for numeric data (unchanged) and `<!-- DIAGRAM: -->` for conceptual visuals. A dispatcher parses the type field and routes to the correct renderer.

| Type | Use Case | Example |
|------|----------|---------|
| **comparison** | Two-column "X vs Y" grids | Software vs Agents, Before vs After |
| **progression** | Ascending staircase stages | Maturity models, adoption curves |
| **stack** | Layered horizontal bars | Platform layers, architecture tiers |
| **convergence** | Items flowing into a center | Building blocks forming a platform |
| **venn** | 2-3 overlapping circles | Identity categories, role overlaps |

Each renderer is pure Python string manipulation. No external dependencies, no matplotlib, no headless browser. Just f-strings building SVG elements with calculated positions. The entire Chart Lambda still has zero pip dependencies.

## Matching the Site's Design System

The original chart visuals used a dark background (`#1a1a2e`) with bold colors inspired by Scott Galloway's charts. They looked good in isolation but clashed with the blog's clean, light aesthetic.

I replaced the entire color system:

| Property | Before | After |
|----------|--------|-------|
| Background | `#1a1a2e` (dark navy) | `#ffffff` (white) |
| Text | `#e0e0e0` (light gray) | `#111827` (gray-900) |
| Primary | `#3B82F6` (blue-500) | `#0284c7` (sky-600, site primary) |
| Font | Inter (already matched) | Inter (unchanged) |
| Borders | None | `#e5e7eb` (gray-200) |

Now every chart and diagram looks like it belongs on the page. The colors come from the same Tailwind tokens the site uses. Light mode works. Dark mode works (SVGs inherit the white background, which is fine against the dark page background because they have a subtle border).

## Hardening the Agent Infrastructure

While I was in the codebase, I addressed some of the gaps I flagged in the original post.

**Observability is no longer minimal.** X-Ray active tracing is enabled on all seven Lambda functions and the Step Functions state machine. Every pipeline execution generates a full trace showing latency per step, Bedrock call duration, and S3 read/write timing. Step Functions also logs errors to CloudWatch with structured log groups.

**The approval endpoint is rate-limited.** API Gateway now enforces 5 requests per second with a burst limit of 10. The task token is still the security mechanism, but rate limiting prevents abuse of the public endpoint.

**IAM got tighter.** The `StepFunctionsAccess` policy was scoped from `Resource: *` to the specific state machine ARN. Least-privilege is not a checkbox, it is a habit.

**Lambda cost dropped 20%.** All seven functions are now on `arm64` (Graviton2). Same code, same behavior, 20% cheaper per millisecond. The migration was a one-line change in the CloudFormation template per function. No code changes.

## Updated Cost Breakdown

The agent now runs five LLM calls per post instead of four (the diagram detection pass is new). Here is the updated breakdown:

| Resource | Per Post | Monthly (10 posts) |
|----------|----------|-------------------|
| Lambda (7 functions, arm64) | $0.000 | $0.00 |
| Step Functions | $0.000 | $0.00 |
| Bedrock Claude Sonnet 4.6 (5 calls) | $0.060 | $0.60 |
| Tavily web search (2 queries) | $0.000 | $0.00 |
| S3 storage | $0.000 | $0.00 |
| SNS + API Gateway + SES | $0.000 | $0.00 |
| **Total** | **~$0.06** | **~$0.60** |

The extra LLM call adds about two cents per post. The Graviton2 switch saves more than that on Lambda compute. Net cost is roughly the same as before.

## What I Learned

**Structured output beats freeform for rendering.** My first attempt had the LLM generate SVG directly. The output was inconsistent: sometimes valid, sometimes broken, always different dimensions. The structured placeholder approach (LLM decides *what* to draw, code decides *how* to draw it) is more reliable and produces consistent visuals every time.

**Conceptual diagrams are harder to automate than data charts.** A bar chart is mechanical: take numbers, draw bars. A comparison diagram requires understanding the argument structure. The LLM is surprisingly good at this, but it occasionally suggests diagrams for concepts that do not benefit from visualization. The "bad candidates" list in the prompt is critical for keeping quality high.

**Design system consistency matters more than individual chart beauty.** The dark Galloway-style charts looked impressive on their own but felt foreign on the page. The light-themed diagrams are less dramatic but feel native. For a blog, that is the right trade-off.

**The "What I Would Do Differently" section writes itself.** In the original post I flagged four gaps: dynamic model selection, revision memory, minimal observability, and rule-based chart generation. Two of those are now addressed (observability with X-Ray, and chart generation with LLM-driven diagram detection). The other two are still on the list. Shipping a real system and iterating is how you learn what actually matters.

## What Is Next

Two items remain from the original post's wish list:

- **Smarter model routing.** Use Haiku for structured extraction, Sonnet for creative writing. The orchestration layer should decide.
- **Revision memory.** Carry forward all feedback across revision rounds so the agent does not regress.

And one new item from this round:

- **Diagram refinement via feedback.** Right now, if a diagram is wrong, I have to reject the whole post or edit the SVG manually. A better flow would let me give diagram-specific feedback ("swap columns 1 and 2", "add a 5th stage") that the agent can act on without redrafting the entire post.

## Next Steps

If you are building an agent that produces content:

- **Separate detection from rendering.** Let the LLM identify *what* visual would help. Use deterministic code to render it. You get the LLM's reasoning without its inconsistent output formatting.
- **Match your design system.** Generated visuals that clash with the surrounding page erode trust. Pull your colors, fonts, and spacing from the same source as the rest of your site.
- **Iterate on the "What I Would Do Differently" list.** If you are honest about the gaps when you ship v1, v2 writes itself.

---

*This post was written by me. The diagrams referenced throughout the blog were generated by the agent pipeline described here. Full source code is [on GitHub](https://github.com/kzaky/khaledzaky.com/tree/master/agent).*
