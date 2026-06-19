---
title: "Identity Is the Substrate the Governance Stack Is Missing"
date: 2026-06-15
author: "Khaled Zaky"
categories: ["ai", "identity", "platform-engineering"]
description: "I paused on agent identity in March because the standards were immature. Three months of governance work pulled me back. The decision engine, the runtime contract, the authority model — all of them assume identity is resolved upstream. For most teams, it isn't."

---

## TL;DR

The governance stack I've been building in this series (decision engines, runtime contracts, authority models) implicitly assumes identity is resolved upstream. For most teams, it isn't. The standards landscape has advanced enough since March to say something concrete now. This post names the substrate the whole stack was always sitting on top of.

## The Sentence That Pulled Me Back

Earlier this week I wrote that a [decision engine governing multi-agent systems](https://khaledzaky.com/blog/everyone-is-building-evaluators-almost-nobody-is-building-decision-engines/) is "effectively advisory" without understanding delegation depth, tool scope, and agent identity. That sentence pulled me back to a thread I deliberately left open in March.

Not because the problem was solved back then. I paused because the standards were immature and I didn't want to overstate the architecture. The [IETF agent authentication draft I covered](https://khaledzaky.com/blog/the-ietf-is-now-working-on-agent-authentication-here-is-what-that-means/) was at revision -00. Security considerations were literally marked TODO. Transaction tokens work was forming but not stable. Vendor language around agent identity was early, lots of positioning, thin on implementation.

So I moved up the stack instead. [Observability](https://khaledzaky.com/blog/agent-observability-the-missing-layer-in-agentic-ai-platforms/). [Evals](https://khaledzaky.com/blog/evaluations-the-control-plane-for-ai-governance/). [Guardrails](https://khaledzaky.com/blog/dynamic-guardrails-for-agentic-ai-why-static-rules-break-down-when-agents-can-delegate/). [Lifecycle](https://khaledzaky.com/blog/where-ai-governance-debt-accumulates-the-agent-lifecycle/). [Runtime contracts](https://khaledzaky.com/blog/the-missing-runtime-contract-between-ai-evals-and-ai-governance/). [Decision engines](https://khaledzaky.com/blog/everyone-is-building-evaluators-almost-nobody-is-building-decision-engines/). Problems I could say something useful about without waiting for the identity layer to settle.

Three months of governance work later, I've arrived back at identity from the other side.

## What the Governance Stack Is Actually Assuming

The [runtime contract post](https://khaledzaky.com/blog/the-missing-runtime-contract-between-ai-evals-and-ai-governance/) introduced an `authority` field: who can override a governance action, scoped by risk tier. The [decision engine post](https://khaledzaky.com/blog/everyone-is-building-evaluators-almost-nobody-is-building-decision-engines/) said the system needs to know who can deploy an agent, who can approve an exception, who can release a quarantine.

Both posts assume identity is resolved upstream.

It isn't, for most teams.

You can't make a runtime governance decision about an agent action without knowing:

- **Which agent** is acting
- Under **what delegated authority**
- Tracing back to **which principal**
- In **which delegation context**
- Whether that authority has **narrowed or widened** across hops

Without this, the governance stack produces signals. It doesn't produce control. As [LoginRadius's multi-agent security research](https://www.loginradius.com/blog/engineering/building-secure-multi-agent-ecosystems) puts it: "Identity boundaries define ecosystem boundaries. When identities are tightly scoped, the blast radius remains limited even if one agent is compromised." But when identities aren't scoped at all, the governance layer has nothing to bind decisions to.

![What the Governance Stack Assumes from Identity](/postimages/charts/identity-is-the-substrate-the-governance-stack-is-missing-diagram-1.svg)

![Agent access governance gaps — share of organizations where agents receive more access than necessary vs. cannot distinguish AI agent from human activity in logs](/postimages/charts/identity-is-the-substrate-the-governance-stack-is-missing-chart-1.svg)
*Source: labs.cloudsecurityalliance.org/research/csa-research-note-cisa-agentic-ai-adoption-guide-enterprise*

## Why Multi-Hop Delegation Is the Hard Part

Within a single trust domain, the direction is clearer now. One agent, one principal, one set of scoped permissions, one audit trail. The tooling exists.

The problem is what happens across hops. If Agent A delegated to Agent B which delegated to Agent C, and A's authorization is revoked mid-execution, does C stop?

Most implementations don't have an answer. The ones that do usually default to "finish the transaction" rather than propagate the revocation.

[O'Reilly Radar's "Who Authorized That?" analysis](https://oreillyradar.substack.com/p/who-authorized-that-the-delegation) describes this precisely: MCP "doesn't address what happens when Agent A receives that token, delegates a subtask to Agent B, and Agent B spawns Agent C. Each hop in that chain either reuses the original token (overprivileged) or has no token at all (untracked)."

There's a related failure mode I covered in the [delegation post](https://khaledzaky.com/blog/delegation-is-the-real-identity-problem-in-agentic-ai/) under "context drift." Authorization doesn't break because the token expired. It breaks because the chain of delegated actions has drifted far enough from the original user intent that the authorization model is no longer grounded in what was actually asked. The token is still valid. The action is no longer legitimate.

[WorkOS documented a concrete attack pattern](https://workos.com/blog/ai-agent-delegation-multi-agent-security) they call **Agent Session Smuggling**: a sub-agent embeds a silent action inside an otherwise routine response, the parent agent processes it, executes the embedded action, and the transaction goes through with no prompt and no visibility to the user. This isn't a theoretical vulnerability. It's a demonstrated failure of delegation without identity substrate.

![Multi-Hop Delegation Failure Modes](/postimages/charts/identity-is-the-substrate-the-governance-stack-is-missing-diagram-2.svg)

## The Standards Landscape: March vs. Now

Three concrete signals worth covering.

### IETF Draft Progression

The [IETF agent authentication draft (draft-klrc-aiagent-auth-01)](https://datatracker.ietf.org/doc/draft-klrc-aiagent-auth/), authored by Kasselman (Defakto Security), Lombardo (AWS), Rosomakho (Zscaler), Campbell (Ping Identity), and Steele (OpenAI), has advanced since March. This matters not because the draft is settled (it isn't, it's still an individual draft, not WG-adopted) but because it signals the standards community has real industry weight behind the work now, not just security vendors. The TODO sections from -00 are being filled in. The draft's **Agent Identity Management System** model (identifiers, credentials, attestation, provisioning, authentication, authorization, observability, policy, compliance) is a useful vocabulary even before it becomes an RFC.

### MCP Formalized OAuth 2.1

When I wrote the IETF post in March, MCP auth was fragmented. Now there's a spec, a direction, and vendor implementations building to it. [O'Reilly Radar confirms](https://oreillyradar.substack.com/p/who-authorized-that-the-delegation) that "MCP describes a protected server as an OAuth 2.1 resource server, with the MCP client acting as an OAuth client making requests on behalf of a resource owner."

**Session-scoped authorization** is emerging as the enterprise pattern: access time-limited to a specific task, expires automatically, human must approve renewal. This is the closest thing to what I described in the [delegation post](https://khaledzaky.com/blog/delegation-is-the-real-identity-problem-in-agentic-ai/) as the right model. It's landing in product, not just drafts.

### Vendor Productization

Microsoft Entra Agent ID, Okta positioning agents as first-class identities, identity vendors building MCP-native auth layers. This matters less for the standards argument and more for adoption: the "wait until vendors catch up" reason for pausing is weaker now.

![Standards Landscape: March](/postimages/charts/identity-is-the-substrate-the-governance-stack-is-missing-diagram-3.svg)

## What Is Still Not Solved

This section belongs here, not as a footnote.

**Cross-domain delegation** remains the hardest open problem. I said this in March. It's still true. Within one trust domain, the direction is clearer. Across domains (different organizations, different identity systems, different control planes) scope attenuation, revocation propagation, and audit continuity are genuinely unsolved. The [Authorization Propagation paper](https://arxiv.org/html/2605.05440v1) identifies three sub-problems: transitive delegation, aggregation inference, and temporal validity. It states the field is "converging on the problem, but not yet on a complete architecture."

**Runtime revocation at hop three** has no clean solution. If A's authorization is revoked, C should stop. In practice, most systems can't propagate that signal in time or don't try.

**Intent drift and delegation lineage** is still the place where authorization breaks down in practice. Not because the token expired but because the chain has drifted. The [Berkeley Technology Law Journal](https://btlj.org/2026/06/multi-agent-ai-is-outpacing-the-liability-frameworks-built-for-single-agent-systems) adds a dimension I hadn't considered deeply in March: "When a coordinator agent autonomously selects and delegates to specialist agents across provider boundaries, the delegation itself is an emergent runtime decision, no human chose the specific combination of agents that executed the task." The revocation question isn't just technical. It has legal liability implications that current frameworks aren't built for.

## Next Steps

Five priorities, in order of what you can act on now:

1. **Treat agent identity as a workload identity problem**, not a user identity extension. SPIFFE or equivalent, short-lived, dynamically provisioned. The IETF AIMS model is a useful audit checklist even before any of it becomes an RFC.

2. **Implement session-scoped authorization** for any agent with access to consequential tools. Time-bound to the task, not the session. Human renewal required.

3. **Separate actor from principal in every log.** The agent that took the action isn't the principal on whose behalf it acted. If your observability layer collapses these, you don't have a real audit trail. [O'Reilly Radar captures the failure mode](https://oreillyradar.substack.com/p/who-authorized-that-the-delegation): "The logs may show that a service called another service. But they can't show that the delegation itself was authorized."

4. **Map your delegation chain and ask the revocation question explicitly:** if authority is revoked at hop one, what happens at hop three? If you don't have an answer, you have a gap worth naming before a regulator names it for you.

5. **Start within your trust domain.** Don't wait for cross-domain delegation to be solved before building anything. Get the identity and lineage model right there first. The cross-domain problem is real but it shouldn't block progress on the piece you can control.

![Enterprise agent identity strategy adoption — share of organizations with vs. without a formal agent identity strategy](/postimages/charts/identity-is-the-substrate-the-governance-stack-is-missing-chart-2.svg)
*Source: arxiv.org/html/2604.02767v1 (SentinelAgent paper)*

## Where This Leaves the Series

The decision engine I described last week needs identity to function, not as a feature integration but as the layer that makes authority fields resolvable, quarantine decisions enforceable, and delegation depth visible. The [runtime contract](https://khaledzaky.com/blog/the-missing-runtime-contract-between-ai-evals-and-ai-governance/) can't be explicit about who holds override authority if "who" isn't a cryptographically verifiable answer.

The industry is far enough along to build concretely within a single trust domain. Not far enough to claim cross-domain delegation is solved. That's the honest position, and it's more useful than either silence or overclaiming.

*The governance stack isn't broken. It was built on an assumption nobody wrote down. Now you can write it down.*