---
title: "The IETF is now working on agent authentication. Here is what that means."
date: 2026-03-07
author: "Khaled Zaky"
categories: ["ai", "cloud", "leadership"]
description: "This is the fourth post in a series that started with why agentic AI needs a platform mindset, then explored how the conversation immediately went to identity a..."
---

## Securing the Agent Frontier: The IETF New Standard for AI Identity and Authorization

This is the fourth post in a series that started with why [agentic AI needs a platform mindset](https://khaledzaky.com/blog/agents-are-not-software), then explored how the conversation immediately went to identity and delegation, and then landed on the core claim: agents are not software, they are system actors.

In March 2026, an IETF Internet-Draft landed that I think is a meaningful signal: [draft-klrc-aiagent-auth-00](https://datatracker.ietf.org/doc/html/draft-klrc-aiagent-auth-00), authored by [Pieter Kasselman](https://www.linkedin.com/in/pieter-kasselman-0259862/), [Jean-François Lombardo](https://www.linkedin.com/in/jflombardo/), [Yaroslav Rosomakho](https://www.linkedin.com/in/yaroslav-rosomakho-3b3b12b3/), and [Brian Campbell](https://www.linkedin.com/in/bcampbell/). The document is titled 'AI Agent Authentication and Authorization.' It is an early draft, expires September 2026, and carries no IETF consensus yet. But the fact that it exists matters.

Here are my reflections.

## What the draft actually says

The draft core position: agents are workloads. Not users. Not services in the traditional sense. Workloads with their own identifiers, credentials, attestation, provisioning, authentication, and authorization lifecycle.

It builds on existing standards rather than inventing new ones: **WIMSE (Workload Identity in Multi-System Environments)**, **SPIFFE**, **OAuth 2.0**, **Transaction Tokens**, **OpenID CIBA**, **HTTP Message Signatures**, **Shared Signals Framework**. The argument is that the primitives mostly already exist. The gap is in how they are composed and applied specifically to the agent case.

The authors define an **Agent Identity Management System (AIMS)**: not a product, but a conceptual stack of components: identifier, credentials, attestation, provisioning, authentication, authorization, observability, policy, compliance. In that order. Each layer depends on the one below it.

![Agent Identity Management System (AIMS)](/postimages/charts/the-ietf-is-now-working-on-agent-authentication-here-is-what-that-means-diagram-1.svg)

Key positions I found meaningful:

1. Static API keys are explicitly called an **antipattern for agent identity**. Bearer artifacts, not cryptographically bound, long-lived, operationally difficult to rotate. The draft says this directly. [^1]

<!-- DIAGRAM: comparison | Static API Keys | Short-Lived Dynamic Credentials | Long-lived and static;Bearer token, not cryptographically bound;Difficult to rotate operationally;High blast radius on compromise | Short-lived and dynamic;Cryptographically bound to workload;Automatic rotation;Limited blast radius on compromise -->

2. Agents must be **uniquely identified**: WIMSE identifier (or SPIFFE ID) as the primary. One identifier per agent. Stable for the lifetime of the workload identity. [^2]

3. Credentials must be **short-lived**. Dynamic issuance, automatic rotation, no manual expiration management. The draft points to SPIFFE as a deployed reference implementation. [^3]

4. Delegation has three flavors that need to be modeled explicitly: user delegates to agent (Authorization Code Grant), agent acts on its own behalf (Client Credentials), agent is invoked by another agent or system (agent-as-protected-resource). Each has a different OAuth flow. [^4]

![Static API Keys vs Short-Lived Dynamic Credentials](/postimages/charts/the-ietf-is-now-working-on-agent-authentication-here-is-what-that-means-diagram-2.svg)

5. **Transaction tokens** reduce risk in multi-agent chains. Rather than passing the original access token between microservices and downstream agents, the receiver exchanges it for a transaction-scoped, downscoped token bound to a specific operation. This limits blast radius. [^5]

6. **HITL (human in the loop)** is a first-class authorization concern, not just a UX pattern. The draft models it through CIBA (client-initiated backchannel authentication) where the authorization server can require explicit user confirmation out-of-band before granting the agent access. It explicitly says local UI confirmation alone is not sufficient authorization. The authorization event must be bound to a verifiable grant from the authorization server. [^6]

7. **Observability** is framed as a security control, not an operational feature. Deployments must produce durable, tamper-evident audit logs. The audit trail must include: authenticated agent identifier, delegated subject (user or system), resource/tool accessed, action requested, authorization decision, timestamp, attestation state, and remediation events. [^7]

## What this means to me

In ['Agents Are Not Software'](https://khaledzaky.com/blog/agents-are-not-software) I wrote: "We are introducing a new category of participant inside enterprise systems: non-human actors operating with delegated authority. Enterprise infrastructure was not originally designed for this."

This IETF draft is the standards community arriving at the same conclusion through a different path. Not theory. Not a vendor whitepaper. A structured attempt to compose existing internet-layer primitives into a coherent framework for agent identity and authorization.

A few things stand out.

**The antipattern call-out is important.** Static API keys as an antipattern is not a new idea. The security community has said this about service accounts for years. But having it stated explicitly in an IETF context, in the agent-specific framing, signals that this is the baseline expectation the community is converging on. 

Organizations still wiring agents through shared API keys are already behind where the draft sets the floor. [^1]

**AIMS as a conceptual stack.** The layered model (identifier → credentials → attestation → provisioning → authentication → authorization → observability → policy → compliance) is a useful frame. We have been building toward something like this at RBC Borealis but without a clean vocabulary for it.

The AIMS model gives a shared language. Not because the draft will become an RFC unchanged. Because having a name for the thing helps teams have the right conversations.

**Transaction tokens for agent chains.** This one deserves more attention than it usually gets. In a multi-agent system, you have authority propagating across hops. Agent A gets an access token from the user. Agent A calls Agent B. Agent B calls a service. 

If A's original token flows all the way through, you have a token with broad scope sitting in logs, crash dumps, and trace outputs across every hop. Transaction tokens scope each hop to its specific operation. The blast radius of a compromise shrinks dramatically. This is the delegation-chain security model I was trying to describe in ['Agents Are Not Software'](https://khaledzaky.com/blog/agents-are-not-software), now with a concrete mechanism. [^5]

**HITL as an authorization primitive, not a UX pattern.** This is the most important reframe in the draft for me. I run HITL in my own blog pipeline as a simple task-token callback: a human clicks approve, the token gets sent, the pipeline continues.

The draft is saying that pattern needs to be grounded in an authorization event at the OAuth layer. The human's approval should translate to a verifiable authorization grant, not just a UI confirmation. That distinction matters at scale. A UI click is easy to spoof or replay. An authorization grant issued by an authorization server is cryptographically verifiable and auditable. [^6]

**The draft is still early.** Section 14 (Security Considerations) and Section 15 (Privacy Considerations) both say 'TODO.' That is honest. This is genuinely work in progress. The cross-domain authorization section acknowledges that not all scenarios are fully covered. The CIBA-for-mid-execution HITL problem is flagged as needing more specification work. The authors are not overclaiming.

## The pattern I keep seeing

In ['The Conversation After'](https://khaledzaky.com/blog/the-conversation-after-agentic-ai-needs-a-platform-mindset) I wrote: "Agent ecosystems are unlikely to standardize around products. They will standardize around protocols and primitives."

This draft is evidence of that happening. WIMSE, SPIFFE, OAuth Token Exchange, Transaction Tokens, HTTP Message Signatures, CIBA, Shared Signals: none of these are new. They are existing, deployed, battle-tested primitives. The draft contribution is the composition: here is how you assemble them specifically for the agent case.

![Agent Identity &amp; Authorization Framework](/postimages/charts/the-ietf-is-now-working-on-agent-authentication-here-is-what-that-means-diagram-3.svg)

That is how internet standards usually work. HTTP existed before REST. OAuth existed before it became the default for API authorization. The primitive arrives first. The integration pattern gets specified second. Adoption follows.

For agent identity and authorization, the primitives are here. The integration patterns are being written now. The draft-klrc-aiagent-auth is an early version of that specification work.

## What I would focus on now

If you are building agent systems in a regulated environment:

1. Read the AIMS stack. Even if you do not implement it fully, the layer model helps you audit where your gaps are. If you do not have an answer for 'attestation' or 'credential provisioning,' you have gaps worth naming.

2. Move away from static credentials for agents now. Not because the draft says so, but because the security argument is independently correct. Short-lived, dynamically provisioned credentials via SPIFFE or equivalent is achievable today.

3. Model your delegation chains explicitly. Every time an agent invokes another agent or system, ask: what authority is being delegated, to what scope, for how long, and can it be revoked mid-execution? Transaction tokens are worth understanding even if you do not implement them yet.

4. Treat HITL as an authorization event. If your human approval flow is just a callback with no authorization-server binding, that is a gap. It may be acceptable today. It will not be acceptable in a regulated deployment at scale.

5. Instrument everything. The draft observability requirements are not aspirational. Tamper-evident audit logs, correlated across agents, tools, and LLMs. If you cannot reconstruct "which agent did what, using which authorization context, and why access changed over time," you are not ready for production at scale.

The space is moving fast. The draft expires in six months and will look different by then. But the direction is clear enough to act on now.

*These are reflections from building. The vocabulary is still forming, but the problems are real and the primitives are arriving.*

[^1]: The draft-klrc-aiagent-auth-00 IETF Internet-Draft explicitly calls static API keys an antipattern for agent identity, citing their lack of cryptographic binding, long lifetimes, and operational difficulty to rotate. [Source](https://datatracker.ietf.org/doc/html/draft-klrc-aiagent-auth-00)
[^2]: The draft requires agents to have unique, stable identifiers, citing WIMSE or SPIFFE IDs as the primary identifier. [Source](https://datatracker.ietf.org/doc/html/draft-klrc-aiagent-auth-00)
[^3]: The draft specifies that agent credentials must be short-lived with dynamic issuance and automatic rotation, pointing to SPIFFE as a deployed reference implementation. [Source](https://datatracker.ietf.org/doc/html/draft-klrc-aiagent-auth-00)
[^4]: The draft models three flavors of delegation: user delegates to agent, agent acts on its own behalf, agent is invoked by another agent or system, each with a different OAuth flow. [Source](https://datatracker.ietf.org/doc/html/draft-klrc-aiagent-auth-00)
[^5]: The draft introduces transaction tokens to reduce risk in multi-agent chains by scoping the token to a specific operation and downscoping the privileges. [Source](https://datatracker.ietf.org/doc/html/draft-klrc-aiagent-auth-00)
[^6]: The draft frames human-in-the-loop authorization as a first-class security concern, not just a UX pattern, requiring explicit user confirmation from the authorization server rather than just local UI confirmation. [Source](https://datatracker.ietf.org/doc/html/draft-klrc-aiagent-auth-00)
[^7]: The draft's observability requirements frame logging and auditing as a security control, not just an operational feature. [Source](https://datatracker.ietf.org/doc/html/draft-klrc-aiagent-auth-00)
