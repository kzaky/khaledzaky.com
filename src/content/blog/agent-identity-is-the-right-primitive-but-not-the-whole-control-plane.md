---
title: "Agent identity is the right primitive, but not the whole control plane"
date: 2026-06-27
author: "Khaled Zaky"
categories: ["ai", "identity", "platform-engineering"]
description: "Agent identity alone cannot govern AI systems. Production agentic architectures require four additional layers: dynamic authorization, intent validation, delegation verification, and observability to ensure safe, accountable agent behavior."

---

Here is the blog post draft with the weak paragraphs annotated:

Most teams building agentic AI systems eventually arrive at the same conclusion: identity is the control plane. I've made this argument myself, including in my post on [why identity is the substrate the governance stack is missing](https://khaledzaky.com/blog/identity-is-the-substrate-the-governance-stack-is-missing/). And I still believe agent identity is the *right primitive* to anchor everything else on.

But after spending the last several months working through real agent governance challenges, and watching the standards landscape evolve, I've come to a more nuanced position: identity is necessary, but it's architecturally insufficient. Treating it as the entire control plane conflates authentication with governance, and that conflation creates real gaps in production systems.

<!-- INSIGHT: Provide specific examples of the "real agent governance challenges" you've encountered, and how they reveal the limitations of treating identity as the entire control plane. -->

## TL;DR

Agent identity solves "who is this actor?" It doesn't solve "why is it acting?", "is this action aligned with sanctioned intent?", or "should this be allowed in this specific runtime context?" The actual control plane for agentic systems requires at least four layers beyond identity: dynamic authorization, intent validation, delegation chain verification, and observability. The standards stack to support all of this is roughly 12 to 18 months behind where production architectures already are.

![The Four Layers Beyond Identity](/postimages/charts/agent-identity-is-the-right-primitive-but-not-the-whole-control-plane-diagram-1.svg)

## The Mismatch Between Identity Standards and Agent Behavior

[SPIFFE/SPIRE](https://spiffe.io/) is the most mature workload identity standard we have. It's CNCF-graduated, widely deployed, and solves the hard "bottom turtle" problem of bootstrapping trust without long-lived secrets. I've advocated for it in the past.

But it has a structural problem for agents.

[Solo.io's analysis of SPIFFE for agent identity](https://www.solo.io/blog/agent-identity-and-access-management---can-spiffe-work) identifies the core issue: current Kubernetes implementations treat all replicas of a deployment as identical. Every pod in a ReplicaSet gets the same SPIFFE SVID. For a deterministic microservice that processes requests identically regardless of which replica handles them, this is fine.

AI agents aren't deterministic. Two replicas of the same agent, given the same input, can make different tool calls, access different data, and produce different outputs. If they share one identity, you cannot:

- Revoke one instance without revoking all of them
- Audit which specific instance took which action
- Scope one instance's access differently based on its runtime context

The "shared service account" antipattern, which the industry spent a decade eliminating, reappears at the agent layer.

[Aembit's assessment](https://aembit.io/blog/everyone-wants-spiffe-almost-no-one-can-afford-to-build-it-right) adds an operational dimension: SPIFFE "does not solve the SaaS access problem, legacy credential types, or AI agent identity" and most teams underestimate the deployment effort by "a year and two engineers."

![Traditional Software](/postimages/charts/agent-identity-is-the-right-primitive-but-not-the-whole-control-plane-diagram-2.svg)

## Why RBAC Breaks Down for Agents

I wrote about [delegation as the real identity problem](https://khaledzaky.com/blog/delegation-is-the-real-identity-problem-in-agentic-ai/) earlier this year. The authorization side of the problem is equally structural.

Role-Based Access Control works by assigning permissions to roles, then assigning roles to actors. A "clinical documentation agent" role might grant access to a PHI repository. But regulatory frameworks like HIPAA and [NIST 800-171](https://csrc.nist.gov/publications/detail/sp/800-171/rev-2/final) (control 3.1.2) require something more specific: access limited to the *particular authorized task*, not just the role's general permission set.

<!-- INSIGHT: Cite a specific example of how RBAC fails to meet regulatory requirements for agent access control, such as the Kiteworks example about limiting access to specific patient records for a documentation task. -->

[Kiteworks frames this clearly](https://www.kiteworks.com/cybersecurity-risk-management/abac-rbac-ai-access-control): a clinical documentation agent needs access to three specific encounter records, for a specific patient, for a specific documentation task, delegated by a specific clinician, expiring at the end of the current session. RBAC can't express that. It wasn't designed to evaluate context at request time.

The fix isn't to abandon RBAC. It's to layer Attribute-Based Access Control (ABAC) and policy engines on top of RBAC baselines. Roles for coarse groupings (agent type, environment tier). Attribute-based policies for runtime decisions that incorporate data sensitivity, task context, delegation source, and temporal constraints.

RESEARCH SOURCES (look for "URL:" entries and "Verified:" confirmations):
# Research Notes: Agent Identity Is the Right Primitive, But Not the Whole Control Plane

## 1. Key Points

1. **Agent identity is necessary but architecturally insufficient** — Identity answers "who is this actor?" but cannot answer "why is it acting?", "is this action aligned with sanctioned intent?", or "should this be allowed in this specific runtime context?" The control plane requires at least five additional layers beyond identity primitives.

2. **SPIFFE/SPIRE breaks down for agents** — The most mature workload identity standard treats all replicas of a deployment as identical. AI agents are non-deterministic, context-dependent, and delegation-heavy — a fundamental mismatch that creates compliance and attribution gaps even when identity is cryptographically sound.

3. **The "identity = control plane" meme conflates authentication with governance** — Authentication tells you the actor is who it claims to be; governance tells you whether its *authority* is warranted in context. Legacy IAM was built for humans who log in and out; agents operate 24/7, make decisions inside the perimeter with valid credentials, and act on behalf of someone not at the keyboard.

4. **RBAC is structurally incapable of satisfying minimum-necessary requirements for agents** — Regulatory frameworks (HIPAA, CMMC AC.2.006, NIST 800-171 3.1.2) require access limited to the *specific authorized task*, not just the role's general permission set. RBAC cannot evaluate context at request time.

5. **The real control plane is at least four-layered** — Identity (who), Authorization (what scope, evaluated dynamically), Intent/Policy Enforcement (why, validated at runtime), and Observability (what happened, attributable to a specific agent instance and delegation chain).

6. **Delegation chains are the primary attack surface in multi-agent systems** — Each link from human → agent → sub-agent must be verifiable. Broken or unverifiable chains let a compromised agent exercise unbounded authority with valid credentials.

7. **Standards are lagging architecture by 12-18 months** — The IETF draft on agent auth (March 2026) explicitly avoids new protocols, instead showing how to compose existing ones. OpenTelemetry genAI semantic conventions remain experimental. No stable specification covers skill-level identity propagation or cost attribution.

8. **Non-human identities already outnumber human ones 40:1 or more** — The volume problem means that manual governance is impossible; the control plane must be automated, policy-driven, and capable of lifecycle management at machine scale.

---

## 2. Background Context

The identity-as-control-plane thesis emerged from two converging trends:

**Zero Trust maturation**: Forrester introduced "zero trust" in 2010; by 2024, [over two-thirds of organizations report implementing zero trust policies across their enterprises](https://www.ibm.com/think/topics/zero-trust). The core move was from perimeter-based trust to identity-based trust — every connection verified, every session scoped. Identity became *the* enforcement point.

**Non-human identity explosion**: As organizations decomposed monoliths into microservices and adopted cloud-native architectures, machine identities (service accounts, API keys, workload certificates) proliferated. [Industry reports peg the ratio of machine-to-human identities anywhere from 45:1 to 80:1](https://www.cerbos.dev/news/securing-cloud-architectures-non-human-identities-ephemeral-services). SPIFFE/SPIRE emerged as the CNCF-graduated standard for workload identity, solving the "bottom turtle" problem of bootstrapping trust without long-lived secrets.

**The agent inflection**: AI agents combine properties no prior digital actor combined: they are non-deterministic, initiative-taking, and authority-bearing. [A traditional microservice authenticates to one or two APIs using a single credential type. An AI agent authenticates to an LLM provider via API key, an enterprise API via OAuth, a cloud database via managed identity, and a tool server via MCP token — all within the same task execution](https://aembit.io/blog/ai-agent-identity-security). This multi-protocol reality broke the assumption that identity = a single credential in a single trust domain.

The W3C WebAuthn and FIDO Alliance work established that strong, phishing-resistant authentication is achievable for humans. The open question is whether equivalent assurance can be constructed for autonomous agents whose "sessions" span hours, spawn children, pause across infrastructure restarts, and cross organizational boundaries.

---

## 3. Current State

**Standards activity (2025-2026)**:
- The [IETF Internet-Draft `draft-klrc-aiagent-auth-00`](https://www.ietf.org/archive/id/draft-klrc-aiagent-auth-00.html) (March 2026), co-authored by engineers from Defakto Security, AWS, Zscaler, and Ping Identity, maps existing OAuth 2.0 and WIMSE standards to agent authentication scenarios. It explicitly does *not* define new protocols — it identifies gaps.
- The [OpenID Foundation released a whitepaper on Identity Management for Agentic AI](https://openid.net/new-whitepaper-tackles-ai-agent-identity-challenges) (October 2025), noting that "existing frameworks can only handle today's simple agents" and calling for new standards around delegated authority and agent-native identity.
- [Forrester's research on agent control planes](https://www.forrester.com/blogs/agent-control-planes-still-need-a-robust-standards-stack) (2026) identifies three categories of standards gaps: incomplete instrumentation standards, missing identity propagation standards, and absent cross-orchestrator governance protocols.

**Vendor convergence on "agent control plane" as category**:
- Microsoft, GitHub, ServiceNow, and Fiddler AI all launched products in the agent control plane category within a six-month window. [Gravitee defines an AI Agent Management Platform](https://www.gravitee.io/blog/ai-agent-management-platform-architects-guide) as governing identity, traffic, tooling, and observability — explicitly stating "standard human IAM cannot express agent delegation, MCP authorization, or fine-grained tool access."
- [Forrester polled 47 tech vendors](https://www.forrester.com/blogs/agent-control-planes-still-need-a-robust-standards-stack) in February 2026 and found the architecture of build/orchestrate/control planes is converging, but the standards stack underneath remains incomplete.

**SPIFFE hitting limits in agent contexts**:
- [Solo.io's analysis of SPIFFE for agent identity](https://www.solo.io/blog/agent-identity-and-access-management---can-spiffe-work) finds that while SPIFFE *can* technically provide agent identities, "current Kubernetes implementations treat all replicas as identical — a fundamental mismatch with agents' non-deterministic, context-dependent behavior that creates compliance and attribution gaps."
- [Aembit's assessment](https://aembit.io/blog/everyone-wants-spiffe-almost-no-one-can-afford-to-build-it-right) notes that SPIFFE "does not solve the SaaS access problem, legacy credential types, or AI agent identity" and requires "a dedicated team to deploy, scale, maintain, and secure" — with most teams underestimating by "a year and two engineers."

**The "80% unintended actions" signal**:
- [Dan Cumberland Labs reports](https://dancumberlandlabs.com/blog/agentic-ai-control-plane-architecture) that according to Security Boulevard, 80% of companies have already experienced unintended AI agent actions. While this is a single-source figure worth treating as directional, it maps to a structural problem: identity alone cannot prevent a correctly-authenticated agent from taking the wrong action.

---

## 4. Expert Opinions / Data

**On why RBAC fails for agents:**
> "A 'clinical documentation agent' role that grants access to the PHI repository doesn't express that *this particular agent instance* is authorized to access three specific encounter records for a specific patient, for a specific documentation task, delegated by a specific clinician, expiring at the end of the current session. RBAC was built for the first kind of access. ABAC is built for the second."
— [Kiteworks, ABAC vs. RBAC for AI Agent Access Control](https://www.kiteworks.com/cybersecurity-risk-management/abac-rbac-ai-access-control)

**On the multi-protocol identity gap:**
> "A traditional microservice authenticates to one or two APIs using a single credential type. An AI agent authenticates to an LLM provider via API key, an enterprise API via OAuth, a cloud database via managed identity and a tool server via MCP token, all within the same task execution. Each protocol has its own token format, validation requirements and permission model."
— [Aembit, AI Agent Identity: The Multi-Protocol Authentication Gap](https://aembit.io/blog/ai-agent-identity-security)

**On why identity ≠ governance:**
> "The architectural question this raises is not 'how do we restrict access?' It is 'how do we govern authority?'... OAuth, OIDC, and SAML were designed for humans who log in, do work, and log out. Traditional IAM systems built around them lack the capability to handle agents that operate 24/7, make decisions inside the perimeter with valid credentials, and act on behalf of someone not at the keyboard."
— [Dan Cumberland Labs, Identity Is the Real AI Control Plane](https://dancumberlandlabs.com/blog/agentic-ai-control-plane-architecture)

**On the standards gap:**
> "We are in the 'dial-up internet' phase of the agentic era. The architecture is emerging faster than the standards needed to make it work cleanly at enterprise scale."
— [Leslie Joseph, Principal Analyst, Forrester](https://www.forrester.com/blogs/agent-control-planes-still-need-a-robust-standards-stack)

**On SPIFFE's limits for agents:**
> "While SPIFFE can technically provide agent identities, current Kubernetes implementations treat all replicas as identical — a fundamental mismatch with agents' non-deterministic, context-dependent behavior that creates compliance and attribution gaps."
— [Christian Posta, Solo.io](https://www.solo.io/blog/agent-identity-and-access-management---can-spiffe-work)

**On the Identity Control Plane architecture (academic):**
> "Identity is often fragmented across human, workload, and automation domains — leading to inconsistent policy enforcement, static privileges, and limited auditability... ICP enables dynamic, intent-aware access control using attribute-based policy engines."
— [Identity Control Plane: The Unifying Layer for Zero Trust Infrastructure, arXiv](https://arxiv.org/html/2504.17759v1)

---

## 5. Quantitative Data Points

- **Data point**: Non-human identities (NHIs) vs. human identities in enterprise environments
  - **Values**: NHI-to-human ratio: 40:1 (conservative), 45:1 to 80:1 (industry range)
  - **Source**: [Strata.io AI Agent Authentication Guide](https://www.strata.io/glossary/agent-authentication); [Cerbos, Securing Cloud Architectures in the Age of Non-Human Identities](https://www.cerbos.dev/news/securing-cloud-architectures-non-human-identities-ephemeral-services)
  - **Chart type**: comparison

- **Data point**: Organizations implementing zero trust policies
  - **Values**: More than 67% of organizations: implementing enterprise-wide, 2024
  - **Source**: [IBM, What Is Zero Trust (citing 2024 TechTarget ESG report)](https://www.ibm.com/think/topics/zero-trust)
  - **Chart type**: bar

- **Data point**: AI agents market growth rate
  - **Values**: CAGR: ~46%
  - **Source**: [Aembit (citing Yahoo Finance/market research