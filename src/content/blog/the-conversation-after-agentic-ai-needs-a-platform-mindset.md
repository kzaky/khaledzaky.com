---
title: "The Conversation After: Agentic AI Needs a Platform Mindset"
date: 2026-02-26
author: "Khaled Zaky"
categories: ["tech", "ai"]
description: ""
---

**TL;DR:** The response to my last post surprised me, not because of agreement or disagreement, but because of *where* the conversation immediately went. Identity. Authorization. Delegation. Trust. The industry is already past "what can agents do" and is asking "how should agents be allowed to act." This post captures what I learned from that conversation and where I think the field is heading.

---

When I wrote [*Why Agentic AI Needs a Platform Mindset*](/posts/agentic-ai-platform-mindset), I expected discussion. What I did not expect was how quickly that discussion moved deeper.

The reaction was not really about the platform framing itself. It was about the layer underneath it. Almost immediately, practitioners started raising identity, authorization, delegation, and trust as the real open problems. Not as adjacent concerns. As the core of the challenge.

That tells me something.

The industry is already moving past what agents can do and toward how agents should be allowed to act.

## The Moment We Are In

Over the past week I have been genuinely grateful to see leaders like [Pamela Dingle](https://www.linkedin.com/posts/pameladingle_why-agentic-ai-needs-a-platform-mindset-activity-7431399561849565184--HLG?utm_source=share&utm_medium=member_desktop&rcm=ACoAAAPLMcsB7-ticCIP9S0tUybqwwYueCqJoh0) and [Sarah Cecchetti](https://www.linkedin.com/feed/update/urn:li:activity:7432495876998111232/) engage with the post and push the conversation forward.

Pamela made a point that resonated strongly: we largely understand the conceptual problems now. The harder work is identifying the concrete protocols and primitives that make agent systems safe, operable, and governable from an identity perspective. Not more frameworks. Actual primitives.

Sarah extended that into implementation reality, sharing work modeling an agent's world using Cedar policies and explicit authorization boundaries. That is not whiteboard thinking. That is someone working through what policy-as-code actually looks like when the actor is an agent.

That progression matters. We are collectively moving through a real shift:

Agents are interesting  
→ Agents need guardrails  
→ Agents require identity infrastructure  

And that shift changes the nature of the problem entirely.

## Agents Are Not Just Software

Here is the part that trips people up when they first approach this.

Agents do not behave like traditional applications. They operate on behalf of users. They move across systems. They invoke tools. They make chained decisions under changing context, often without a human in the loop for each step.

Traditional authentication and authorization models assumed relatively stable actors. A human signs in. A service calls an API. Permissions remain predictable.

Agents introduce something different: **delegated autonomy**.

We are no longer only granting access. We are granting authority to act.

That is a meaningful distinction. What we are building starts to look less like application security and more like a delegation system for autonomous actors. The mental model shift required here is significant, and most enterprise security and identity frameworks have not caught up yet.

## The Stack Is Starting to Converge

One of the strongest signals right now is that similar building blocks are emerging independently across standards communities, open source ecosystems, and enterprise platform teams.

Not as a coordinated effort. More like parallel evolution toward the same structural needs.

Some recurring patterns:

- **Workload identity:** SPIFFE and SPIRE enabling verifiable, cryptographic identities for non-human actors
- **Agent interaction protocols:** MCP emerging as an early attempt to standardize how agents connect to tools and environments
- **Authorization and policy:** Cedar and policy-as-code approaches enabling explicit, auditable delegation boundaries
- **Observability:** OpenTelemetry work extending tracing semantics into model execution, tool usage, and agent workflows
- **Human-in-the-loop controls (HITL):** intentional checkpoints where autonomy yields to human judgment
- **Evaluation systems:** continuous evals becoming core infrastructure for validating behavior, safety, and reliability over time
- **Platform abstractions:** SDK and control-plane layers encapsulating identity, authorization, evaluation, and execution safety so every team does not rebuild the same safeguards from scratch

None of these pieces alone defines an agent platform. Together, they start to resemble one.

<!-- CHART: Stages of agentic AI platform adoption: Stage 1 - Experimentation, Stage 2 - Reusable Platform, Stage 3 - Operationalized at Scale. Bar chart showing progression across adoption stages. Source: "Why Agentic AI Needs a Platform Mindset" - Khaled Zaky -->

The convergence is also showing up in how enterprise teams are thinking about this. Accenture's recent work on [platform strategy in the age of agentic AI](https://www.accenture.com/us-en/insights/strategy/new-rules-platform-strategy-agentic-ai) frames AI agents as the new "users" of enterprise systems and makes the case that static platforms cannot deliver the agility and governance required. That framing aligns with what I am seeing in practice: the platform itself needs to evolve, not just the models running on it.

## Why Identity Moves to the Center

If an agent can reason, plan, call systems, and execute actions, the primary question stops being:

*What is the model capable of?*

and becomes:

*Who authorized this action, under what scope, and can it be revoked or audited?*

Identity shifts from a login problem to a control plane problem.

We are no longer only authenticating humans. We are governing **intent execution** across humans, services, and autonomous systems. That is a fundamentally different design challenge.

It requires primitives many organizations are only beginning to formalize:

- Verifiable identities for agents and workloads
- Scoped and time-bound delegation
- Revocable authority
- Machine-readable policy
- Human override mechanisms
- Continuous evaluation and feedback loops
- Traceable action lineage

Sarah's work with Cedar policies is a concrete example of what this looks like in practice. Rather than relying on implicit trust or blanket permissions, you model the agent's world explicitly: what it can access, under what conditions, with what constraints. That kind of explicit authorization boundary is what makes an agent system auditable and, more importantly, correctable.

This is why I keep coming back to the same conviction: agentic AI succeeds or fails based on platform thinking, not model capability alone.

## Where These Ideas Come From

None of these reflections came from writing alone.

A lot of what I am describing here is shaped by ongoing conversations, whiteboarding sessions, and genuinely challenging discussions with people I have the privilege of building alongside at RBC Borealis:

- [Anushan](https://www.linkedin.com/in/anushanrajakulasingam/)
- [Gaurav](https://www.linkedin.com/in/gauravh-j/)
- [Mehrdad](https://www.linkedin.com/in/mehrdad-abdolghafari-26052656/)
- [Vinh](https://www.linkedin.com/in/vinhbtran/)

The questions we keep returning to are not abstract. How should agents authenticate? Where should policy live? What must remain human-controlled? What can safely become autonomous? Some of the best clarity comes from standing at a whiteboard, arguing through edge cases, and trying to design systems that will still make sense several years from now.

This post reflects those conversations as much as my own thinking.

## The Emerging Insight

The more discussions I have had since publishing the original post, the clearer one idea has become.

Agent ecosystems are unlikely to standardize around products.

They will standardize around protocols and primitives.

Vendors will build experiences. Frameworks will continue to evolve rapidly. But durable systems tend to form around shared foundations: identity, authorization, observability, evaluation, and governance. The history of the internet makes this case pretty well. HTTP, OAuth, and TLS are not products. They are primitives that made an entire ecosystem possible.

The agentic layer is going to need its equivalents. We are early, but the convergence is visible.

## Next Steps

The questions worth focusing on right now are not about which model wins or which framework gains the most adoption. They are:

- How does an agent receive authority?
- How is delegation expressed and constrained?
- When must a human remain in the loop?
- How do evaluation systems continuously validate behavior?
- How do we audit decisions made across autonomous workflows?
- Where does accountability live when software acts on behalf of people?

These are not purely AI problems. They sit at the intersection of identity, security, platform engineering, and governance. And that intersection is exactly where the most important conversations are already happening.

If you are building in this space right now: start with identity. Get your authorization model explicit before you scale autonomy. Instrument everything. And design your HITL checkpoints before you need them, not after.

---

To everyone who engaged, reposted, challenged ideas, and shared implementations after the original post: thank you. Seeing practitioners across identity, security, and platform engineering collectively push this discussion forward has been energizing.

The exciting part is not just that agents are becoming more capable. It is that we are beginning to build the infrastructure required to use them responsibly.

*More reflections as we keep building.*
