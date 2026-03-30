---
title: "Delegation Is the Real Identity Problem in Agentic AI"
date: 2026-03-29
author: "Khaled Zaky"
categories: ["tech"]
description: "I have been spending a lot of time thinking about a problem that starts simple and then gets complicated very quickly"

---

I have been spending a lot of time thinking about a problem that starts simple and then gets complicated very quickly.

When one agent acts on behalf of a user, the model is fairly intuitive. A user asks for something. The agent has some identity. It gets access to a tool or a system. It takes an action. You can reason about who asked, who acted, and what happened.

But the moment that agent calls another agent, and that second agent calls a downstream service, the problem changes shape.

Now authority is moving across hops. Scope has to narrow as work gets delegated. The original user's intent is further and further away from the eventual action. And if you are building an enterprise platform, especially in a regulated environment, you very quickly realize that this is not just an application design problem. It is an identity, authorization, and auditability problem.

That is what sent me down this research path.

I am working on an agentic platform for developers inside a bank. If we want agents to do real work, not just chat, summarize, and answer questions, then sooner or later they need to invoke tools, interact with systems, call other agents, and operate with some bounded form of authority. That sounds powerful, but it also raises uncomfortable questions.

Who exactly is acting?

On whose behalf?

What was the original intent?

How does that intent survive delegation?

How do we keep permissions from widening as work fans out?

How do we reconstruct the full chain later for security, compliance, or incident response?

And maybe the most important one: are the standards we already have actually enough for this?

The answer, at least from what I found, is not really.

![Multi-Agent Delegation Problem](/postimages/charts/delegation-is-the-real-identity-problem-in-agentic-ai-diagram-1.svg)

## I started with OAuth token exchange, but it was not built for this

A natural place to begin is **OAuth 2.0 Token Exchange**, [`RFC 8693`](https://www.rfc-editor.org/rfc/rfc8693).

At first glance, it seems close to what we need. One party presents a token. Another token gets issued. There is even support for subject and actor semantics. In theory, that sounds like a useful building block for delegation.

But the deeper I dug, the more it became clear that `RFC 8693` was designed for pairwise token exchange, not for multi-hop agent chains.

It can express delegation. It can carry actor information. It can even nest actor claims for auditing. But it does not give you what an agentic platform actually needs if authority is going to move across multiple services and agents.

It does not require stepwise scope narrowing.

It does not bind the token to a specific transaction.

It does not give you strong protections against replay across related operations.

It does not solve for trust domain boundaries.

And while it can record chain information, those nested claims are not really meant to become the authorization model itself.

That gap matters a lot more in multi-agent systems than it does in traditional service-to-service architectures. Because in agent systems, delegation is not a side case. It is the workload.

![OAuth 2.0 Token Exchange (RFC 8693)](/postimages/charts/delegation-is-the-real-identity-problem-in-agentic-ai-diagram-2.svg)

## Then I found Transaction Tokens, and things started to click

What really caught my attention was the IETF work on **Transaction Tokens**.

The base draft has matured significantly, and the idea is surprisingly practical. Instead of passing around broad access tokens through a call chain, workloads exchange them for short-lived, transaction-bound, scope-narrowed JWTs that are tied to a specific trust domain and a specific unit of work.

That sounds subtle, but it changes the model in an important way.

A **Transaction Token** is not trying to be a general passport. It is much closer to a constrained authorization artifact for one bounded transaction. It carries context about the request, the requester, and the chain of workloads involved. It has a unique transaction identifier. It is supposed to expire quickly. And most importantly, replacement flows are not allowed to expand scope as the token moves downstream.

That last part is critical.

In a multi-agent system, one of the easiest ways to get into trouble is to let delegated authority become broader as it travels. If Agent A has limited authority and asks Agent B for help, Agent B should not be able to come back with something stronger. The whole point of delegation should be attenuation, not amplification.

That is one of the strongest ideas in the Transaction Token model. The token becomes a cryptographic carrier for bounded authority as work moves through the chain.

The more I read, the more I started to see why this matters for enterprise agents. Not because the standards are elegant on paper, but because they are trying to solve the exact operational problem that starts showing up once agents do real work across systems.

## The next question was obvious: what about agents specifically?

The base Transaction Token work is useful, but the more interesting extension is what happens when you add agent semantics to it.

That is where the draft for Transaction Tokens for agents gets interesting.

It introduces explicit claims for the **actor**, the **principal**, and what it calls **agentic context**.

That may sound like a minor extension, but I think it gets at the heart of the problem.

The actor is the agent doing the work. The principal is the human or system on whose behalf the work began. And the agentic context starts to describe the operational intent and constraints around that action.

That matters because "who is the agent?" is not enough.

In enterprise settings, especially in financial services, "who started this?" and "under what intended bounds?" are often just as important as the runtime identity of the workload itself.

Once you see that, you stop thinking about delegation as a simple bearer-token problem. You start thinking about preserving lineage.

Agent X is acting on behalf of principal Y. Agent B is acting because Agent A delegated a narrower subtask. The downstream tool is being called as part of transaction Z.

That chain has to remain intact if you want meaningful auditability and any chance of enforcing least privilege across hops.

![Transaction Token for Agents](/postimages/charts/delegation-is-the-real-identity-problem-in-agentic-ai-diagram-3.svg)

## The real enemy here is not only overpermissioning. It is drift

One of the reasons I find this space so interesting is that the authorization problem overlaps with another problem many people in agentic AI are already talking about: **context drift**.

Or context rot. Or intent drift. Different people use different terms, but the underlying issue is similar.

Agents accumulate context. They explore. They call tools. They retry. They reason across intermediate outputs. They hand off to other agents. Over time, the original user request can become increasingly distant from the current execution path.

Even if the relevant information is technically still in context, it may no longer be salient.

And that is where the security model starts to break down if it is too loose. Because least privilege is not just about what an agent could do. It is also about whether the system still remembers what it was supposed to be doing in the first place.

This is why the distinction emerging in the A2A profile work is actually important. The idea of separating immutable user input from mutable agent context is more than just clean protocol design. It is a way to preserve the original intent even as the operational context evolves.

If you let every layer rewrite the meaning of the task, then eventually authorization is no longer grounded in the original ask. It is grounded in whatever the chain has become.

That is dangerous.

## Most agent frameworks do not solve this natively

Another thing that became clear while looking through this space is that the popular agent frameworks are not really trying to solve this at the cryptographic authorization layer.

They solve orchestration. They solve routing. They solve tool use. They solve handoffs, state machines, agent-as-tool patterns, hierarchical control flows, memory, and observability to varying degrees.

But they generally do not give you native enforcement for delegation lineage, scope attenuation, transaction binding, or immutable actor-principal preservation across hops.

That is not necessarily a criticism. It just means the platform layer still has work to do.

If you are building serious enterprise agent systems, especially in environments where authority and auditability matter, you probably cannot stop at the framework. You need an identity and authorization architecture around it. I wrote about [why platform engineers should care about identity systems](https://khaledzaky.com/blog/why-platform-engineers-should-care-about-identity-systems/) earlier this year, and that argument only gets stronger once agents start delegating to other agents.

## The regulatory angle makes this much more urgent

If I were just building a hobbyist agent stack, this would still be an interesting technical topic.

But I am not. And many of us working in banks, insurance, and other regulated industries are not.

That changes the conversation.

When I looked across frameworks like SR 11-7, OSFI Guideline E-23, the EU AI Act, and MAS's evolving direction, the pattern was hard to miss. They all push toward the same underlying expectations.

You need traceability. You need explainability. You need human oversight in meaningful places. You need to know what systems are in play, how decisions are made, and how to audit them later. You need post-deployment monitoring, not just one-time approval.

And once agents start taking actions across systems, those expectations do not become less relevant. They become more relevant.

That is why I do not see delegation as just a standards curiosity. I see it as one of the infrastructure questions underneath enterprise agentic AI. If the platform cannot preserve intent, constrain authority, and produce a reliable audit trail across delegated actions, then the governance story is going to collapse under real usage. I explored some of this in [governing agents in financial services](https://khaledzaky.com/blog/agentic-ai-in-financial-services/), but the identity thread deserves its own treatment.

## Cross-domain delegation still feels like the hardest open problem

Even with all of this progress, I do not think the hardest part is solved yet.

Within one trust domain, the direction of travel is getting clearer. Short-lived agent identities. Transaction-bound downscoped tokens. Preserved actor and principal context. Better observability. Human-in-the-loop patterns tied back to verifiable authorization.

That stack is starting to take shape.

But the moment delegation crosses domains, things get much harder.

How do you establish trust between organizations or platform boundaries at scale? How do you preserve attenuated authority across those boundaries without reintroducing overbroad translation artifacts? How does revocation propagate? How do you reconstruct one coherent audit trail when the transaction spans multiple identity systems and control planes? How do delegation rules like "read only," "one-time," or "no more than two hops" actually travel with the authorization artifact in a way both sides can trust?

I saw promising pieces around identity chaining, shared signals, and newer capability-oriented models. But I would not call the problem solved. Not yet.

And I suspect this is where a lot of platform work will end up in the next wave of enterprise agent architecture. The [IETF is already working on agent authentication](https://khaledzaky.com/blog/the-ietf-is-now-working-on-agent-authentication-here-is-what-that-means/), which is a necessary first step, but authentication and delegation are not the same problem.

## What changed in my thinking

Before digging into this space, I was already convinced that identity mattered for agents.

What changed is that I now think **delegation** is the sharper problem.

Authentication tells you what the agent is. Delegation tells you whether that agent should be allowed to do this specific thing, in this specific context, on behalf of this specific originator, across this specific chain.

That is a much harder problem. And it is also much closer to where the real risk sits.

Because most enterprise failures in agentic systems are probably not going to come from not having a UUID for the agent. They are going to come from sloppy authority propagation, weak boundaries, missing lineage, and poor observability when one action turns into five delegated steps and nobody can fully explain how the final operation was authorized.

That is why I went down this rabbit hole.

I am trying to build a platform where developers can safely build and run agents at scale inside a bank. That means I cannot just think about prompts, tools, and runtimes. I have to think about how authority moves.

And the more I looked, the more it became clear that the standards world is starting to converge around the same conclusion.

## Where I have landed, for now

My current view is that the emerging stack for serious multi-agent systems is starting to form around a few ideas.

Agents should be treated as workloads, not magical exceptions to existing identity systems. Delegated authority should become narrower as work moves downstream, not broader. Authorization artifacts should be bound to transactions, not treated like general-purpose passports. The original principal, the acting agent, and the delegation chain need to survive across hops. Human approval, where needed, has to map back to a verifiable authorization event, not just a button in a UI. And observability is not separate from governance here. It is part of the control surface.

I do not think the ecosystem is fully there yet. But I do think the shape of the problem is becoming clearer.

And for those of us building agent platforms in enterprise environments, that clarity matters. Because multi-agent systems are not just introducing new orchestration patterns. They are forcing us to revisit some of the deepest assumptions in identity and access control.

Delegation, not just authentication, is becoming the real boundary problem.

---

## Next Steps

If you are building or evaluating agent platforms and want to pressure-test the delegation layer, here is where I would start:

- **Map your delegation chain.** For any multi-agent workflow in your system, draw out every hop. Identify where authority is passed, and whether it is attenuated or silently amplified at each step.
- **Audit your token lifetimes.** If your agents are operating on long-lived tokens that were not scoped to a specific transaction, that is the first thing to tighten. Short-lived, transaction-bound credentials are the direction the standards are heading.
- **Separate actor from principal in your observability layer.** Your logs should distinguish between the agent that took an action and the human or system that originated the request. If those are collapsed into one identity today, you do not have a real audit trail.
- **Read the Transaction Token drafts.** The IETF work here is practical and grounded. It is worth understanding even if you are not implementing it today, because it will shape how enterprise agent platforms handle authorization over the next few years.
- **Do not wait for the frameworks to solve this for you.** Orchestration frameworks solve routing and tool use. The authorization architecture is still your responsibility.

*The hardest part of building agentic platforms is not making agents capable. It is making them accountable. Delegation is where that work actually lives.*