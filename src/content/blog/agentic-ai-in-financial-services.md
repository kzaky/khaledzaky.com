---
title: "Agentic AI in Financial Services"
date: 2025-11-22
author: "Khaled Zaky"
categories: ["ai", "leadership"]
description: "Agentic AI is not chatbots with extra steps. It is autonomous systems making decisions in regulated environments. Here is what I have learned building these systems at RBC Borealis, and what engineering leaders need to get right."
---

**TL;DR:** Agentic AI in financial services is not about bolting a language model onto a banking workflow. It is about building autonomous systems that can reason, act, and operate within strict regulatory boundaries. The hard part is not the AI. It is the platform layer: identity, access control, observability, and governance. Here is what I have seen work, what fails, and where to focus.

## What makes AI "agentic" (and why it matters for banking)

I lead Agentic AI Platform Engineering at RBC Borealis, where we are building the Lumina agentic platform. The question I get most often from engineering leaders is: "How is this different from what we already have?"

The honest answer: it is fundamentally different.

Traditional AI systems are reactive. You give them input, they give you output. Agentic AI systems maintain context, chain tasks together, make decisions within defined parameters, and take actions autonomously. In financial services, that means an agent can research a client portfolio, identify rebalancing opportunities, draft a recommendation, and route it for compliance review, all without a human manually orchestrating each step.

The trade-off here is between autonomy and control. More autonomy means more value. But in a regulated environment, unchecked autonomy is a non-starter.

## The real challenge is not the model

Most teams start with the model. They pick Claude, GPT-4, or an open-source alternative, build a demo, and show it to leadership. The demo looks great.

Then they try to put it into production.

This is where the hard questions show up:

- **Who is this agent acting on behalf of?** If an agent executes a trade recommendation, whose credentials did it use? Who is accountable?
- **What data can it access?** Financial data has strict access controls. An agent that can see everything is a compliance violation waiting to happen.
- **What happens when it fails mid-task?** A half-completed transaction is worse than no transaction.
- **How do you audit what it did?** Regulators will ask. "The AI decided" is not an acceptable answer.

That is not an AI problem. That is a platform problem. And it is exactly the kind of problem platform engineers need to own.

## What the platform layer needs to look like

Based on what I have seen building these systems, here are the primitives that matter most.

### Identity and access boundaries

Every agent needs its own identity. Not a shared service account. Not the credentials of the user who triggered it. A scoped, auditable identity with explicit permissions tied to the task it is performing.

If you are at startup scale, start with OAuth 2.0 scopes and short-lived tokens. If you are in the enterprise (especially in banking), you need fine-grained authorization that maps to your existing entitlements model, with real-time policy evaluation.

### Tool invocation controls

Agents are only as safe as the tools they can reach. In financial services, this means:

- **Explicit allowlists** for which APIs an agent can call
- **Parameter validation** before execution (an agent should not be able to change a trade amount arbitrarily)
- **Environment-specific restrictions** (sandbox vs. production)
- **Human-in-the-loop gates** for high-risk actions (anything above a dollar threshold, anything touching client data)

### Observability and traceability

Every action an agent takes needs to be logged with enough detail to reconstruct the full decision chain. This is not optional in financial services. It is a regulatory requirement.

What that looks like in practice:

- Structured logs for every tool invocation, including input, output, and policy checks
- Trace IDs that link an agent's actions back to the originating request
- Dashboards showing agent success/failure rates, latency, and cost
- Alerting on anomalous behavior (an agent making 10x more API calls than usual)

### Lifecycle and governance

Agents spread fast once teams see value. That is a good sign, but it creates a management problem.

Every agent should have:

- A named owner
- A defined scope of operation
- A review cadence
- A kill switch

Without this, you end up with dozens of agents running in production with no clear accountability. In financial services, that is an audit finding.

## Common failure modes

I see these patterns repeatedly:

**The "demo to production" gap.** A team builds an impressive demo with broad model access and no guardrails. It works in a sandbox. It cannot pass a security review for production. Months of rework follow.

**Shared credentials.** The agent uses a service account with broad permissions because "it was faster." This works until an incident requires you to trace exactly what the agent accessed and why.

**Prompt-only controls.** Teams try to enforce behavior through system prompts alone. Prompts help, but they are not a substitute for system-level access controls. A well-crafted prompt will not stop an agent from calling an API it should not have access to.

**No feedback loop.** The agent runs, produces output, and nobody systematically reviews whether the output was correct. Over time, quality degrades and nobody notices until a client or regulator does.

## A practical maturity model

Not every organization needs a full enterprise agent platform on day one. Here is how I think about the progression:

| Stage | Focus | What it looks like |
|-------|-------|-------------------|
| **1. Sandbox** | Learning and experimentation | Small experiments, limited data, manual oversight, fast iteration |
| **2. Guarded pilots** | Defined use cases with controls | Named owners, limited tool access, basic logging, human-in-the-loop |
| **3. Reusable platform** | Shared infrastructure | Standard onboarding, shared controls, policy enforcement, self-service |
| **4. Operationalized** | Enterprise scale | Strong governance, lifecycle management, cross-team standards, platform metrics |

Most financial institutions I work with are between Stage 1 and Stage 2. The ones moving fastest are the ones investing in the platform layer early, not just the model layer.

## Next Steps

If you are an engineering leader evaluating agentic AI for financial services:

1. **Start with the platform, not the model.** Pick your identity, access control, and observability patterns before you pick your LLM.
2. **Define your human-in-the-loop boundaries.** Which actions require human approval? Make this explicit from day one.
3. **Build for auditability.** Every agent action should be traceable. Regulators will ask, and "we can check the logs" needs to be a true statement.
4. **Scope narrowly, then expand.** Pick one well-defined use case. Get it to production with full controls. Then replicate the pattern.
5. **Invest in agent identity.** Shared credentials and broad permissions will not survive a security review. Solve this early.

Agentic AI in financial services is not a model problem. It is a platform, governance, and trust problem that happens to involve models. The teams that get the platform right will move faster and more safely than the ones chasing the next model release.
