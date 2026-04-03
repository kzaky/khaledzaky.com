---
title: "Dynamic Guardrails for Agentic AI: Why Static Rules Break Down When Agents Can Delegate"
date: 2026-04-03
author: "Khaled Zaky"
categories: ["tech"]
description: "TL;DR: Static guardrails work when agents operate in isolation on predictable tasks."

---

**TL;DR:** Static guardrails work when agents operate in isolation on predictable tasks. Once agents delegate, chain actions across systems, and adapt their behavior at runtime, those guardrails become either too rigid to be useful or too loose to be safe. Dynamic guardrails, constraints that adjust based on delegation depth, risk signals, evaluation scores, and authorization context, are the platform primitive that connects everything this series has been building toward. They're the brakes on the car. And right now, most teams are driving without them.

---

## The Brakes Analogy

There's a useful way to think about where we are in enterprise agentic AI.

Over the past several posts in this series, I've been building up the layers a platform needs before agents can operate safely at scale. [Observability](https://khaledzaky.com/blog/agent-observability-the-missing-layer-in-agentic-ai-platforms/) is the dashboard. [Evaluations](https://khaledzaky.com/blog/evaluations-the-control-plane-for-ai-governance/) are the quality checks. [Delegation](https://khaledzaky.com/blog/delegation-is-the-real-identity-problem-in-agentic-ai/) is the trust model that governs how authority flows between agents.

But there's a piece missing. What actually happens when something goes wrong at runtime?

Think of it this way. Observability lets you see where the car is and how fast it's going. Evaluations tell you whether it stayed on the road last time. Delegation tells you who's allowed to drive and on whose authority. But none of those things stop the car.

**Guardrails** are the brakes. And the question for enterprise platforms is whether those brakes are mechanical, always on, always the same pressure regardless of context, or whether they're adaptive, applying different force depending on speed, conditions, and risk.

That's the distinction between static and dynamic guardrails. And it matters a lot more once agents can delegate.

![Platform Layers for Safe Agent Operations](/postimages/charts/dynamic-guardrails-for-agentic-ai-why-static-rules-break-down-when-agents-can-delegate-diagram-1.svg)

---

## What Static Guardrails Actually Look Like

Most teams building agent systems today start with static guardrails. That's entirely reasonable. You need something, and static rules are fast to implement.

Static guardrails are typically things like: blocklists for sensitive topics, regex-based PII filters, hardcoded token limits, fixed lists of allowed tools, binary content classifiers, and manual approval gates at predetermined points in a workflow.

They share a few properties. They're defined at build time or configuration time. They don't change based on what the agent is doing at runtime. They apply uniformly regardless of context, risk level, delegation depth, or the nature of the request.

For a single agent answering questions in a low-stakes environment, this works fine. The guardrails are simple because the risk surface is simple.

But that changes the moment agents start doing real work.

---

## Where Static Breaks Down

The problem with static guardrails isn't that they're wrong. It's that they're context-blind. And agent systems, especially multi-agent systems, are fundamentally context-dependent.

Here's what I keep running into.

A static guardrail that blocks all access to customer financial data makes sense as a default. But when a loan processing agent needs to pull a credit score to complete a task the user explicitly requested, that same guardrail blocks the legitimate workflow. The team disables it for that agent. Now the guardrail is gone entirely for that agent, in all contexts, for all tasks.

A static token limit of 4,000 tokens per tool call is sensible for most interactions. But an agent doing deep document analysis on a 50-page regulatory filing needs more. The team raises the limit globally. Now every agent has the higher ceiling, whether it needs it or not.

A static approval gate at the "send email" step is good practice. But when a multi-agent workflow generates 200 internal notifications as part of a batch operation, the approval gate becomes a bottleneck that teams route around.

The pattern is consistent. Static guardrails either block legitimate work or get loosened to the point where they no longer provide meaningful protection. The more capable the agents become, the faster this happens.

I wrote in [Agents Are Not Software](https://khaledzaky.com/blog/agents-are-not-software/) that agents behave more like system actors with autonomy and delegated intent. Static guardrails were designed for deterministic software. They assume you can predict the full set of actions at design time. Agents invalidate that assumption by definition.

![Static Guardrails](/postimages/charts/dynamic-guardrails-for-agentic-ai-why-static-rules-break-down-when-agents-can-delegate-diagram-2.svg)

---

## The Delegation Problem Makes This Worse

This is where the [delegation post](https://khaledzaky.com/blog/delegation-is-the-real-identity-problem-in-agentic-ai/) connects directly.

In a multi-agent system, authority propagates across hops. Agent A delegates to Agent B, which calls Agent C. The original user approved the first step. The guardrails that apply to Agent A may not apply to Agent B. Agent C might be operating in a different trust domain entirely.

Static guardrails have no way to account for this. They're set per-agent or per-workflow at configuration time. They don't know where in the delegation chain they're being evaluated. They don't know whether the scope has narrowed or widened since the original request. They don't know whether the action being taken is still aligned with the original user intent.

This isn't a theoretical concern. The [confused deputy problem](https://sosafe-awareness.com/blog/agentic-ai-security-delegation-risk/) is a structural consequence of how delegation works in multi-agent systems: a lower-privileged agent can request a higher-privileged agent to perform actions on its behalf, effectively bypassing access controls. Static guardrails operate at the wrong layer to catch this, because the problem isn't a policy violation at a single hop. It's a trust inheritance pattern that spans the whole chain.

It's the exact gap where context rot and intent drift become dangerous. And it's why guardrails, done properly, need to be aware of the delegation context I described in the previous post: who's the principal, who's the acting agent, what scope was delegated, and how deep in the chain are we?

A guardrail that knows it's evaluating an action three hops into a delegation chain, on behalf of a user who originally asked for a loan estimate, should behave differently than a guardrail evaluating a direct user request to the same agent. That's what dynamic means.

---

## What Dynamic Guardrails Look Like in Practice

Dynamic guardrails are constraints that adjust based on runtime context. They're not harder to build than static guardrails. They're harder to design, because they require you to think carefully about which signals should influence enforcement.

From what I see building platform capabilities, the signals that matter most are:

**Delegation depth.** How many hops has this action traveled from the original request? The deeper the chain, the more caution the system should apply. A direct user request might get a lighter check. An action three agents deep should face a stricter evaluation before proceeding.

**Evaluation scores.** If the evaluation layer is running continuously (and it should be, as I argued in the [evaluations post](https://khaledzaky.com/blog/evaluations-the-control-plane-for-ai-governance/)), then the guardrail system can consume those scores. An agent whose recent groundedness score dropped below threshold should have its tool access tightened automatically, not after a weekly review meeting.

**Risk classification of the action.** Not all tool calls carry the same risk. Reading a document is different from modifying a database record, which is different from initiating a financial transaction. Dynamic guardrails route actions through different enforcement paths based on the risk category.

**Authorization context.** The transaction token or delegation artifact from the identity layer tells the guardrail what scope is in play. If the scope says "read-only," the guardrail should block write operations regardless of what the agent's instructions say.

**Time and session context.** How long has this agent been running? How many actions has it taken in this session? Is this the first time it's attempted this particular tool call? Behavioral drift tends to increase over extended sessions, and guardrails should account for that.

The practical architecture is closer to a policy engine than a filter. Think of it less like a blocklist and more like a decision function that takes context as input and returns an enforcement action: allow, block, escalate to human review, narrow scope, or quarantine.

![Dynamic Guardrail Decision Engine](/postimages/charts/dynamic-guardrails-for-agentic-ai-why-static-rules-break-down-when-agents-can-delegate-diagram-3.svg)

---

## Guardrails as a Platform Responsibility

One of the mistakes I see teams make is treating guardrails as an application concern. Each agent development team builds their own safety checks, applies their own filters, sets their own limits. This works in prototype. It collapses in production.

The same argument I made in the [platform mindset post](https://khaledzaky.com/blog/why-agentic-ai-needs-a-platform-mindset/) applies here. Guardrails should be a platform primitive, not an application feature. The platform should own the policy engine, the enforcement points, and the integration with the identity, observability, and evaluation layers.

The industry is moving in this direction. [Galileo's Agent Control](https://galileo.ai/blog/agent-guardrails-for-autonomous-agents) is an open-source control plane for writing behavioral policies once and enforcing them across all agent deployments. Meta's LlamaFirewall takes a layered approach: PromptGuard for input filtering, AlignmentCheck for auditing the agent's chain-of-thought reasoning in real time, and CodeShield for static analysis of generated code.

The key insight in that architecture is that guardrails operate at multiple layers simultaneously, not just on input and output but on the reasoning process itself. These approaches are converging on the same conclusion. The guardrail isn't a feature of the agent. It's a feature of the platform the agent runs on. And the platform needs to enforce it in a way the agent can't circumvent.

---

## What Quarantine Looks Like

A concept I think is underexplored is what happens after a guardrail fires.

In most current implementations, a guardrail produces a binary outcome: allow or block. But in a multi-agent system with delegation chains, the failure mode is more nuanced. If Agent C, three hops into a chain, triggers a guardrail, what should the system do?

Block the action and return an error to Agent B? That might cause Agent B to retry with a different approach, potentially creating a loop. Kill the entire chain? That wastes all the work done by Agents A and B. Escalate to a human? Which human, and do they have enough context to make a decision?

The right model is closer to **quarantine**. When a guardrail fires in a delegation chain, the system should pause the chain, preserve the full state and context, notify the appropriate human or oversight function with enough information to make a decision, and wait for explicit authorization before continuing, rolling back, or terminating.

That sounds simple, but it requires the guardrail system to have deep integration with the delegation layer (to know the chain state), the observability layer (to provide the context), and the identity layer (to know who can authorize the resumption).

This is where the brakes analogy extends further. Good brakes don't just stop the car. They bring it to a controlled stop, in a safe place, with the driver informed about why. A guardrail that fires and kills a workflow with a generic error message isn't a brake. It's a wall.

---

## The Evaluation-Guardrail Feedback Loop

There's a compounding benefit that emerges when evaluations and guardrails are both platform primitives talking to each other.

Evaluations produce scores. Guardrails consume those scores to calibrate enforcement. Guardrail activations produce events. Evaluations consume those events to refine their models.

An agent that repeatedly triggers the PII guardrail should get a lower trust score in the evaluation layer, which should tighten the guardrail thresholds for that agent's future actions. An agent that consistently passes evaluations with high scores and never triggers guardrails could earn lighter enforcement, though never zero enforcement.

This creates what I think of as a **governance feedback loop**. The system gets smarter about enforcement over time, not through manual policy updates, but through the interaction between the evaluation and guardrail layers.

It also gives you something valuable for regulated environments: a continuous, auditable record of how the enforcement posture changed over time and why. That's materially different from a static policy document that gets reviewed annually.

---

## Where I Think This Is Heading

The guardrails space is moving fast. A few directional signals stand out.

Guardrails are moving from content filtering to behavioral enforcement. The early guardrails focused on what the agent said. The next generation focuses on what the agent does, and whether what it does is consistent with what it was asked to do.

Guardrails are moving from per-agent to fleet-wide. A model where policies apply across all agents in the organization is more sustainable than per-agent configuration. The governance overhead of managing guardrails agent-by-agent doesn't scale.

Guardrails are moving from the application layer to the runtime layer. Enforcing constraints at the runtime level, rather than asking each agent to self-police, is architecturally sounder. Asking agents to enforce their own guardrails is like asking the car to decide how fast it should go. The road needs the speed limit, not the driver.

And guardrails are becoming delegation-aware. I don't think this is fully realized in any product today. But the signals from transaction token work, identity integration efforts, and emerging agent identity models all point in the same direction: enforcement that knows the delegation context.

---

## What I Would Focus On Now

If you're building or operating an agent platform and want to start thinking about this:

**Audit your current guardrails.** Are they static or dynamic? Do they know the difference between a direct user request and a delegated action three hops deep? If the answer is no, you've got a gap worth naming.

**Separate policy from enforcement.** Define your guardrail policies centrally and enforce them at the platform layer. Don't let each agent team invent their own safety checks. That creates inconsistency and makes audit much harder.

**Connect your guardrails to your evaluation layer.** If you built the evaluation infrastructure from the earlier posts in this series, the guardrail system should consume evaluation scores as input signals. Guardrails that can't see evaluation data are making enforcement decisions with partial information.

**Design for quarantine, not just block.** A guardrail that kills a workflow is better than no guardrail. But a guardrail that pauses a workflow, preserves context, and enables an informed human decision is much better. That requires investment in the integration between the guardrail system, the delegation layer, and the observability layer.

**Don't wait for perfect products.** The tooling is maturing quickly, but most organizations will need to compose their own guardrail architecture from available primitives. The platform team's job is to assemble those primitives into a coherent enforcement layer, not to wait for a single vendor to solve the whole problem.

---

*This series has been building from agents as actors, through identity, observability, evaluations, and delegation, to the enforcement layer that makes the rest of it operational. Static guardrails were the first attempt. Dynamic guardrails are the real thing.*

*Next, I want to look at the agent control plane and operating model: what happens when you need to supervise, quarantine, escalate, and remediate across a fleet of agents at scale. That's where guardrails, evaluations, and delegation converge into an operating model.*