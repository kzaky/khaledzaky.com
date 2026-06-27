---
title: "Agent identity is the right primitive, but not the whole control plane"
date: 2026-06-27
author: "Khaled Zaky"
categories: ["ai", "identity", "platform-engineering"]
description: "Claude Tag introduces agent-scoped identity instead of user credentials, marking a conceptual shift in how AI systems access enterprise tools and data securely."

---

I spent a good chunk of my career on human identity: MFA, passkeys, sign-in, the WebAuthn and FIDO standards work. So when a vendor ships an "agent identity" model, I read it through a particular lens. I've watched human identity make almost exactly this journey before.

## What Anthropic Actually Shipped

[Claude Tag](https://claude.com/blog/agent-identity-access-model), which launched in late June and replaces the older Claude-in-Slack app, puts Claude into shared team channels as a taggable participant. The access model underneath it is the interesting part.

Instead of borrowing a human's credentials, Claude gets its own identity, scoped by admins to a workspace or channel. Each private channel gets a distinct identity; public channels share a workspace-level one. Admins attach the tools, repositories, API keys, connectors, skills, plugins, and standing instructions that identity is allowed to use.

Credentials are linked to the channel identity and injected only when needed. Outbound calls to systems that weren't approved are blocked. Memory respects the boundary: what Claude learns in a private channel doesn't leak into the wider workspace. Every action is logged. And because the identity is distinct, access can be revoked at the agent level instead of being chased across many user accounts.

The conceptual shift is the headline. The question moves from *what can this user do?* to *what can this agent do in this compartment?* Anthropic also names the work still ahead: just-in-time credential grants, and identity-aware overlays where both the channel profile and the requesting user's permissions have to allow an action.

That's a real shift, and it's the right one.

## The Journey Human Identity Already Took

Here's why I read this as a first step rather than a finished one. Human enterprise identity walked this same road, and the order is instructive.

We started with per-application passwords, every system its own silo of credentials. It didn't scale and it wasn't safe. We moved to federated identity, so one principal could be recognized across systems. Then we learned that recognizing the principal wasn't the hard part, authorizing the action was.

That's why delegated authorization (the OAuth-style "this app may act on my behalf, for these scopes, for this long") became the real workhorse. And finally we moved to portable, phishing-resistant credentials (passkeys and FIDO) which only worked because they were a cross-vendor standard rather than one company's login.

Agent identity is roughly at the per-application-password stage of that arc. Claude Tag gives the agent a real identity inside one product's compartments. That's genuine progress. But the lessons from human identity are already visible on the horizon: recognizing the actor is the easy 20%, delegated authority is the hard 80%, and none of it becomes infrastructure until it's portable across vendors.

![The Human Identity Arc (and Where Agent Identity Sits)](/postimages/charts/agent-identity-is-the-right-primitive-but-not-the-whole-control-plane-diagram-1.svg)

The [OpenID Foundation's whitepaper on Identity Management for Agentic AI](https://openid.net/wp-content/uploads/2025/10/Identity-Management-for-Agentic-AI.pdf) makes this explicit, warning that "agent identity fragmentation" across proprietary systems will "reduce developer velocity" and "compromise security by creating multiple security models."

This is also why I keep coming back to the same claim: that agent identity isn't IAM plumbing, it's the substrate that makes governance enforceable. I've [written before](https://khaledzaky.com/blog/agents-are-not-software/) that agents aren't software, they're system actors, and that without a known runtime actor your policies, risk tiers, evaluations, dashboards, and approvals stay advisory. The runtime can't enforce something it can't attribute.

The single question every agentic system needs to answer for any meaningful action is: **who acted, for whom, under what authority, for what task, through which tools, under which policy decision, and with what evidence left behind.**

## What Anthropic Gets Right

Four things, and they matter:

1. **Identity as infrastructure, not a feature.** Claude gets its own identity instead of silently inheriting a person's. Agents become first-class actors that can be scoped, observed, revoked, and audited.
2. **Authority over access.** The move from user access to agent authority-in-a-compartment is the correct framing, the right starting point even if not the finish line.
3. **Runtime boundaries.** Credentials at the network boundary, blocked outbound calls, audited actions. Tools, models, MCP servers, and memory shouldn't be directly reachable without a governed control point.
4. **Identity-level revocation.** Killing the agent identity to cut access, rather than reconciling actions across user accounts, is the right primitive to build revocation on.

## The Tension (Which Anthropic Flags Itself)

The model lets a channel member who has *no* direct access to a repo ask Claude to read that repo, as long as the channel's agent profile grants it. To their credit, Anthropic calls this out as unusual and frames it as a deliberate step toward an access model for autonomous, multiplayer agents.

That trade-off may be reasonable for a collaborative product. In a regulated environment it's a governance fault line: it's exactly the **confused deputy** problem human IAM spent years learning to contain. [Oso's research on authorizing AI agents](https://www.osohq.com/learn/best-practices-of-authorizing-ai-agents) makes the danger concrete: "Your employees ignore 96% of their permissions. Agents won't."

Humans self-limit; agents will use every permission they have, which makes over-provisioned agent access categorically more dangerous than the human-IAM analogue suggests.

Which is why the future overlay Anthropic describes, where the agent's scope **and** the requesting user's permissions both have to allow an action, is the part I'd push hardest on. I've [argued before](https://khaledzaky.com/blog/delegation-is-the-real-identity-problem-in-agentic-ai/) that delegation, not authentication, is the real boundary problem in agentic AI: authority has to narrow as work moves across hops, and the platform has to preserve intent and produce an audit trail across delegated actions. This is the same problem, surfacing inside a shipped product.

Enterprise agent access should sit at the *intersection* of agent identity, requesting-user authority, task scope, data and tool policy, runtime risk, and session constraints. That isn't access control. It's delegated authority management: the OAuth lesson, arriving for agents.

The clean way to say it: agent identity is the badge. Delegated authority is the rule about which doors that badge opens, for whom, in which room, and for how long. Anthropic shipped the badge. The enterprise still needs the rules engine around it.

![Delegated Authority: The Intersection That Governs Action](/postimages/charts/agent-identity-is-the-right-primitive-but-not-the-whole-control-plane-diagram-2.svg)

## What Is Still Missing

The model is scoped to Claude Tag. The enterprise question is what happens when the agent is *not* Claude Tag, when it's built on LangGraph, Bedrock Agents, OpenAI Assistants, Semantic Kernel, CrewAI, an internal harness, or several models behind one workflow. "Claude has a channel identity" doesn't answer that.

Notice a related signal. Critics have already pointed out that Claude Tag shifts lock-in from model choice to control over organizational memory and workflows. That's the portability problem from the other side: if identity, memory, and access are bound to one vendor's product, they can't serve as the enterprise's control plane. **Identity has to survive the model boundary.** Passkeys mattered because they were a standard, not a login. Agent identity will matter the same way, or it will stay a per-product feature.

We're already seeing the cost of this. [SailPoint's Claude Enterprise Connector](https://www.sailpoint.com/blog/sailpoint-anthropic-governing-ai-access) and [Saviynt's parallel integration](https://saviynt.com/blog/bringing-identity-security-to-claude-enterprise-with-saviynt) both required bespoke connectors to Anthropic's Compliance API. Each vendor requires its own integration. This is architecturally identical to the pre-SAML era of per-application identity silos.

![Enterprise AI agent adoption vs. governance readiness gap (91% using agents in production vs. 10% with well-developed NHI/agent identity strategy)](/postimages/charts/agent-identity-is-the-right-primitive-but-not-the-whole-control-plane-chart-1.svg)
*Source: Okta AI at Work 2025*

There's also the difference between logs and evidence. Audit logs are a security camera: they tell you something happened. Regulated governance needs the case file, normalized evidence binding the request, the user, the agent identity, the model, the tool call, the data touched, the policy decision, the evaluation result, the human approval, any exception, the final output, and the revocation path.

That's where identity connects to [evaluation](https://khaledzaky.com/blog/evaluations-the-control-plane-for-ai-governance/), [observability](https://khaledzaky.com/blog/agent-observability-the-missing-layer-in-agentic-ai-platforms/), and [governance](https://khaledzaky.com/blog/from-governance-is-a-platform-problem-to-governance-is-infrastructure/).

## Where the Architecture Goes

Strip away the product names and the shape is straightforward. A runtime control plane (locked-down agent runtime, governed model and tool and agent-to-agent gateways, identity and credential mediation, runtime policy, controlled outbound access) produces governed telemetry. A governance and assurance layer turns that telemetry into evaluation, certification, runtime decisions (allow, redact, repair, block, escalate), and audit-grade evidence.

![Enterprise Agent Governance Architecture](/postimages/charts/agent-identity-is-the-right-primitive-but-not-the-whole-control-plane-diagram-3.svg)

[Speakeasy's reference architecture](https://www.speakeasy.com/resources/ai-control-plane) maps a similar structure across four capabilities: connect, control, secure, and observe, across every AI agent and every system those agents reach. [Activant Capital's research](https://activantcapital.com/research/the-agent-control-plane) arrives at the same conclusion from a different angle, describing the current state as an "AI Frankenstack" of overlapping copilots and shadow keys that requires "a different architecture entirely."

[Anthropic's post](https://claude.com/blog/agent-identity-access-model) is about the runtime identity primitive at the bottom of that stack. Everything that makes it *enforceable* is what you build around it.

## Next Steps

[Anthropic's post](https://claude.com/blog/agent-identity-access-model) is a strong first step. It makes the agent visible as an actor, and that matters.

For enterprise AI, the path forward requires making that identity:

- **Portable** across any framework or model (not locked to one vendor's workspace)
- **Delegation-aware** so authority is the intersection of agent and user, narrowing at every hop
- **Runtime-enforced** through real control points, not advisory policy
- **Revocable** at fine grain, per-task and per-session, not just per-workspace
- **Evidence-producing** for audit and certification, not just logging

If you're at startup scale, the design question is: can your agent identity survive a model swap? If you're in the enterprise, the question is: can your identity and governance layer span every framework your teams are building on?

The standards bodies are moving. [Proof joined the FIDO Alliance](https://www.proof.com/blog/proof-joins-fido-alliance-to-link-ai-agent-actions-to-verified-human-identity) in May specifically to link AI agent actions to verified human identity. OpenAI joined FIDO's Board of Directors. Google contributed its Agent Payments Protocol. These are signals, not solutions, but they point in the right direction.

![Non-human identity proliferation and security risk (50% of organizations experienced breaches from compromised machine identities; 42% lack a cohesive NHI strategy)](/postimages/charts/agent-identity-is-the-right-primitive-but-not-the-whole-control-plane-chart-2.svg)
*Source: CyberArk 2025 State of Machine Identity Security Report*

We did this once already for humans. The question is whether the agent identity ecosystem learns from that history or repeats it from scratch.

*The badge is shipped. The rules engine is not. Build accordingly.*
