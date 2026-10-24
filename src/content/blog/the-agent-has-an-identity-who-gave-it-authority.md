---
title: "The Agent Has an Identity. Who Gave It Authority?"
date: 2026-10-24
author: "Khaled Zaky"
categories: ["ai", "identity", "platform-engineering"]
description: "Agent identity is becoming infrastructure, while authorization and governance remain uneven: deciding what agents may do and why they're acting. Technical authentication alone won't prevent disasters like the Replit database deletion."

---

> **TL;DR:** Giving an agent an identity is becoming ordinary infrastructure. Deciding *what it may do* now has real, shipping machinery, some of it built on standards that are still drafts. Deciding *why it is acting*, and whether that purpose is legitimate, is starting to show up in products, but it can't be outsourced. That layer is where identity meets governance.

In July 2025, an AI coding agent on Replit [deleted a live production database during an active code freeze](https://fortune.com/2025/07/23/ai-coding-tool-replit-wiped-database-called-it-a-catastrophic-failure/). The person running the experiment had told it, repeatedly, not to make changes.

The code freeze was a verbal instruction in a chat window. It wasn't encoded in the agent's permissions. Replit's fix was an authority boundary: automatic separation of development and production databases.

That incident keeps coming back to me because of a conversation I was in recently. Someone said, with real confidence, that standing up SPIFFE and SPIRE solves agent identity. Nobody pushed back.

I like SPIFFE. Short-lived, automatically rotated, cryptographically bound workload identity is the right foundation, and I've recommended it before. But on its own it answers one question: *is this the agent it claims to be?*

The question that bit was different: *should this agent be allowed to do this, for this person, right now?*

## What changed since March

In March I wrote about [the first IETF draft on agent authentication](https://khaledzaky.com/blog/the-ietf-is-now-working-on-agent-authentication-here-is-what-that-means/), a personal draft that introduced the Agent Identity Management System (AIMS). It already covered authorization and delegation. I said it would look different in six months. It does.

What pulled me back was a short video walkthrough of the draft that [Pieter Kasselman](https://lnkd.in/p/gimD9-W7), one of its authors, shared this week. It reminded me how much ground has moved since I last wrote about this.

| | March 2026 | October 2026 |
|---|---|---|
| **AIMS status** | Personal draft, 4 authors | [WIMSE working group draft](https://datatracker.ietf.org/doc/html/draft-ietf-wimse-aims) (`draft-ietf-wimse-aims-00`), published September 15, with authors from Defakto, AWS, Zscaler, Ping, OpenAI, and Okta |
| **Attestation** | Its own layer | Folded into provisioning as "posture assessment" |
| **New rules** | | Added in the individual draft before WIMSE adoption: an "Agent Mission" section (June) names the task as the starting point for authorization, and the LLM must not have access to the agent's credentials (July) |
| **Products** | Mostly announcements | Agent identity is generally available from [Microsoft](https://learn.microsoft.com/en-us/entra/agent-id/whats-new-agent-id), [Okta](https://okta.com/newsroom/press-releases/okta-brings-first-class-identity-to-ai-agents-with-agent-sso/), and [AWS](https://aws.amazon.com/blogs/security/securing-ai-agents-with-amazon-bedrock-agentcore-identity) |

## AIMS is the map

AIMS isn't a product or a protocol. It describes the functions any system needs to establish, maintain, and evaluate an agent's identity and permissions. These functions can be spread across many components:

1. **Identifier:** a unique name for the agent
2. **Credentials:** verifiable credentials bound to the agent's identifier
3. **Provisioning:** issuing and rotating those credentials at runtime, after checking the agent's posture
4. **Authentication:** proving identity to a tool, model, or another agent
5. **Authorization:** deciding whether this agent may do this thing, for this user
6. **Observability and remediation:** watching what happens, and cutting access when signals change
7. **Policy:** the rules that configure all of the above
8. **Compliance:** assessing identity and authorization behavior against applicable requirements

These aren't a strict sequence where each layer depends only on the one below it. They're interdependent. Policy (7) shapes how provisioning (3) works. Observability (6) feeds back into authorization (5). The value of the framework is that it names the full surface area, not that it imposes a particular ordering.

SPIFFE standardizes workload identity: an identifier, a verifiable credential (an X.509 or JWT SVID), and the Workload API that issues and rotates it. SPIRE adds attestation before issuing it. Together they give you strong authentication between workloads. That's real progress, and it's foundational. But authorization is outside it by design: the project's own docs say SPIFFE and SPIRE [provide authentication policies, not authorization policies](https://spiffe.io/docs/latest/spire-about/comparisons/). Observability, policy, and compliance sit outside it too.

The analogy I use with executives is international travel. **A passport proves who is presenting the request. A visa says what that traveler may do here, for how long, and on whose behalf. An itinerary says what approved purpose the trip serves.** A border guard who only checks passports will happily wave through someone with a valid passport and no business being there.

The passport and visa infrastructure is maturing fast. Your organization still has to approve the trip, constrain deviations, and account for what happened.

## Where the market actually is

I mapped what has shipped this year against those functions. Three zones emerged. This is my reading of public product descriptions, not a conformance assessment.

| Zone | AIMS functions | State | What's there |
|---|---|---|---|
| **Who** | 1 to 4 | Becoming infrastructure | SPIFFE/SPIRE. Google's Agent Identity with auto-rotating X.509 certificates and IAM allow and deny policies. Microsoft Entra Agent ID. AWS AgentCore Identity with workload identities and a token vault. Okta for AI Agents for registration and human owners |
| **May it** | 5, 6 | Shipping, fragmented, partly on drafts | MCP gateways from Cloudflare (GA), Auth0 (beta), and Microsoft (preview), [compared here](https://workos.com/blog/mcp-gateways-compared), plus [Okta's Agent Gateway](https://help.okta.com/oie/en-us/Content/Topics/ai-agents/agent-gateway.htm). CyberArk's AI Agent Gateway with zero standing privilege. [HashiCorp Vault's Agentic IAM](https://hashicorp.com/blog/hashicorp-vault-agentic-iam-is-now-generally-available) for request-specific authority. Cross-company access via Okta's Cross App Access |
| **Why** | Mission, 7, 8 | Emerging, but can't be outsourced | AIMS leaves mission translation, policy format, and compliance criteria out of scope. Vendors are moving in: [Saviynt's intent-aware runtime authorization](https://saviynt.com/press-release/saviynt-expands-identity-security-for-ai-solution-with-intent-aware-runtime-authorization-for-ai-agents) and [Descope's purpose and approval records](https://www.descope.com/press-release/agentic-identity-hub-3) |

Four things stand out to me.

### 1. Identity is becoming infrastructure, not becoming solved

Major identity providers and cloud platforms now issue agent identities. That means the identity layer is going the way human sign-in went: from a project to a platform service.

The trap is the belief I heard in that conversation: that issuing an identity solves the problem. It's the agent version of thinking SSO is your authorization model.

But identity isn't disposable either. Knowing which agents exist, who owns them, and when their authority should end is still hard. The workload, the logical agent, the running instance, the requesting user, and the accountable owner can be five different things. A single runtime credential can't represent all of them. Reliable identity is the reference point everything above it depends on.

Notice where vendors are putting the price tags. Microsoft's [Conditional Access for agents](https://learn.microsoft.com/en-us/entra/identity/conditional-access/agent-id) requires a premium license tier (Microsoft 365 E7, or a Microsoft Agent 365 license paired with at least Microsoft Entra P1 or Microsoft 365 E3). The identity is table stakes. The controls on top of it are the product.

### 2. Gateways are the most visible control point, not the only one

Gateways are where most of the commercial energy is. The clearest public example is Uber. Its [MCP gateway](https://www.uber.com/us/en/blog/designing-mcp-gateway/) fronts more than 800 MCP servers and 5,000 tools. It applies access policies based on caller type, and every newly discovered server and tool starts disabled until its owning team reviews and enables it.

That design choice is the whole thesis in one implementation. Discovery proves a capability exists. An accountable owner decides whether agents may use it.

The risk is that every vendor's gateway becomes its own policy island. In June I described [per-vendor agent identity integrations](https://khaledzaky.com/blog/agent-identity-is-the-right-primitive-but-not-the-whole-control-plane/) as architecturally identical to the pre-SAML era. Gateways can repeat that mistake one layer up.

Two things push back. First, a gateway doesn't replace authorization on the tool or MCP server behind it. Hiding a tool from an agent is not the same as refusing the call. Second, there's now a standard way to separate *enforcing* a decision from *making* it: the OpenID Foundation approved [AuthZEN's Authorization API 1.0](https://openid.net/authorization-api-1-0-final-specification-approved/) as a final specification in January. A gateway can enforce a decision without owning the policy that produced it.

### 3. Production is running on a mix of RFCs and drafts

Okta made Agent SSO [generally available on August 24](https://okta.com/newsroom/press-releases/okta-brings-first-class-identity-to-ai-agents-with-agent-sso/). It's built on Cross App Access (XAA), the name for the pattern specified in the OAuth working group draft known as ID-JAG (Identity Assertion JWT Authorization Grant), currently at [version -04](https://datatracker.ietf.org/doc/draft-ietf-oauth-identity-assertion-authz-grant/). ID-JAG is the wire protocol; Okta's XAA feature implements it. MCP's [Enterprise-Managed Authorization extension](https://github.com/modelcontextprotocol/ext-auth/blob/main/specification/stable/enterprise-managed-authorization/2026-07-28/enterprise-managed-authorization.mdx) is a profile of ID-JAG for MCP clients and servers. ID-JAG is an active IETF draft, not a published RFC.

[Transaction Tokens](https://datatracker.ietf.org/doc/draft-ietf-oauth-transaction-tokens/), which I wrote about in [Delegation Is the Real Identity Problem](https://khaledzaky.com/blog/delegation-is-the-real-identity-problem-in-agentic-ai/), are nearing completion in the OAuth working group.

Not everything is waiting on drafts, though. Token exchange (RFC 8693) and structured authorization details (RFC 9396) are published RFCs. HashiCorp's Vault release builds request-specific authority on top of them.

This isn't a criticism. OAuth itself spent years as drafts in production before it settled. But the honest way to assess maturity is mechanism by mechanism, not vendor by vendor. A GA product can depend on a draft protocol and still ship some features as preview. Know which bet you're making, and how you'd unwind it.

### 4. The strongest counterargument deserves a fair hearing

The best version of the "SPIFFE solves it" view is this: SPIFFE plus a policy engine plus a correctly placed enforcement point is a complete authorization architecture. SPIFFE's own documentation shows [exactly that pattern with Envoy and OPA](https://spiffe.io/docs/latest/microservices/envoy-opa/readme/).

For a bounded deployment, I agree. The conditions are demanding, though. The policy engine needs trusted context about the user and the task. The policy has to encode the constraints that matter. Enforcement has to cover every path the agent can take: tools, direct APIs, code execution, queues. And the downstream systems still need their own checks.

So my disagreement isn't with SPIFFE. It's with stopping at SPIFFE.

## The itinerary can't be outsourced

In June my one-liner was that the badge had shipped and the rules engine hadn't. Rules engines are now shipping. The question has moved: do the policy, the delegated grant, the resource check, and the audit evidence all describe the same approved task?

The most important line in the new AIMS draft is one most people will skim past. In the Agent Mission section, the authors say an agent receives a mission, usually in natural language, and that turning it into concrete authorization requirements is out of scope. [Karl McGuinness's writing on "mission shaping"](https://notes.karlmcguinness.com/notes/the-mission-shaping-problem/) is credited as the inspiration.

I think the authors are right to leave it out, and vendors are already working on parts of it. But three responsibilities stay with the enterprise no matter what you buy:

1. **Deciding whether a mission is legitimate.** A signed purpose statement proves who wrote it. It doesn't prove the purpose is appropriate.
2. **Approving how the mission becomes constraints.** Somebody has to decide that "summarize this quarter's vendor contracts" means read access to one folder, for one session, on behalf of one person, with no write scope. A product can propose that translation. It acquires authority only when someone accountable approves it.
3. **Proving the actions matched.** An action can be fully authorized and still wrong: the right document sent to the wrong permitted recipient.

Each of those is a decision, and as I wrote in [The Model Didn't Change. The Decision Did.](https://khaledzaky.com/blog/the-model-didnt-change-the-decision-did/), decisions need evidence before they're trusted to act.

The data suggests most organizations aren't there yet. These are vendor-commissioned surveys with different populations and questions, so read them as directional, not as one combined measure:

- In a Cloud Security Alliance study commissioned by Zenity, [53% of organizations](https://cloudsecurityalliance.org/press-releases/2026/04/16/more-than-half-of-organizations-experience-ai-agent-scope-violations-cloud-security-alliance-study-finds) reported agents exceeding their intended permissions at least occasionally.
- In a separate CSA study commissioned by Token Security, [82% reported finding AI agents they didn't know about](https://cloudsecurityalliance.org/press-releases/2026/04/21/new-cloud-security-alliance-survey-reveals-82-of-enterprises-have-unknown-ai-agents-in-their-environments), and only 21% had a formal process for decommissioning them.

Scope violations are an authority failure, not an identity failure.

## What I'd do now

**If you're an executive**, ask five questions:
1. Who is accountable for each agent's mission, and who approves changes to it?
2. Can we list every agent we run, and who owns each one?
3. For any action, can we say which agent acted and on whose behalf?
4. How fast can we actually stop an agent? Test how quickly revocation stops new calls, issued tokens, and work already in flight.
5. Which cross-company standard are we betting on, and what happens if it changes?

**If you run identity or security:**
- Map your current controls against the eight AIMS functions. Most teams will find strength in identification and credentialing and gaps in policy, compliance, and observability.
- Model the agent, runtime, requester, and owner as separate entities. Don't flatten them into one shared credential.
- For every constraint, decide which component makes the decision and which enforces it. Treat gateways as enforcement points, not the place policy lives.
- Require tools and MCP servers to check authorization even behind a gateway.

**If you build agents:**
- Avoid static API keys for agent identity. The draft calls them an antipattern, and it's right.
- The model never sees credentials. Keep them in the runtime, not the prompt.
- Keep the acting agent and the person it acts for as separate fields in tokens and log lines, wherever the format allows it.
- Request scope per task, not per agent. If the mission is read-only, the token should be too.
- Enforce at call time. Filtering which tools an agent can see is not the same as refusing the call.
- Test permitted-but-wrong behavior, not just forbidden calls: the wrong recipient, the wrong record, instructions planted in retrieved content.

## Back to March

In March I wrote that the primitives had arrived and the integration patterns were being written. Seven months later, issuing an agent identity is close to routine. Authority has real machinery, moving fast, on a mix of finished and unfinished standards. The purpose behind that authority is the part you can buy help with but can't hand off.

That's the part I want to spend the next few months on: how a mission becomes a scoped, approved, provable grant of authority. I'll share what I learn as I go.
