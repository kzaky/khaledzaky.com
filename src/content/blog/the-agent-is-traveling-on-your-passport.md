---
title: "The Agent Is Traveling on Your Passport"
date: 2026-10-28
author: "Khaled Zaky"
categories: ["ai"]
description: "Banks are blocking AI agents because of how agents currently access accounts: with customer passwords. Proper authentication standards exist but haven't been assembled for consumer banking yet."

---

> **TL;DR:** Banks are blocking AI agents because of how agents get in today: by using the customer's password or riding the customer's logged-in session. Many of the underlying standards already exist, but a complete, interoperable model for consumer-agent access is still emerging. Nobody has assembled them end to end for consumer banking yet, so blocking is the rational default until they do.

This month, a man asked a consumer AI agent to help him sell something on an online marketplace. By his account, the agent listed the item, accepted a lowball offer, and gave the buyer his home address. He hadn't approved any of it ([Money.ca](https://money.ca/banking/meta-muse-ai-agent-facebook-marketplace-banking-risks)).

The man had reportedly granted the agent "Allow Always" permission. He didn't lose money. But the failure illustrates what happens when consent is ambiguous and delegated authority is excessive: the agent acted within the permissions it was given, and those permissions turned out to be far broader than the user intended.

Move the same failure one system over, into a bank account, and the home address becomes a wire transfer.

That's roughly where the industry landed in October. Within a few weeks, several of the largest banks in North America said they're blocking or restricting third-party AI agents from customer accounts. Some customers had handed their banking passwords to agents, and banks were flagging and blocking the resulting transactions ([Reuters via Arise](https://www.arise.tv/us-banks-block-third-party-ai-agents-from-accessing-customers-accounts/)). One brokerage chief executive said he receives daily reports on how often AI agents are blocked ([Schwab Q3 2026 Earnings Call](https://stockanalysis.com/stocks/schw/transcripts/711046-q3-2026/)).

Those announcements keep coming back to me because of timing. Last week I wrote that [giving an agent an identity is becoming ordinary infrastructure](https://khaledzaky.com/blog/the-agent-has-an-identity-who-gave-it-authority/), and that the harder questions are what it may do and why. That post was about agents inside the enterprise, where someone issues the agent its own credentials.

The bank blocks are about the other end of the market: consumer agents operating in an environment where current banking access often can't distinguish a customer from an authorized software delegate, or enforce their separate permissions.

The blocks reflect a set of overlapping concerns: fraud risk, liability exposure, privacy, unclear customer consent, transaction risk, and the fact that banks have no way to identify or scope the agent independently. Identity is a necessary piece of that puzzle, but it isn't sufficient on its own.

## The agent has no passport, so it borrows yours

Bank security is built on one assumption: the entity at the keyboard is the account holder. Passwords, one-time codes, passkeys, device fingerprints, and fraud models all answer one question. Is this the customer?

A consumer AI agent is a **delegate**, something acting on the customer's behalf. Today's consumer banking login has no way to express that relationship, so agents do the only thing they can: they present themselves as the human.

Last week I used international travel as the analogy for agent identity. The analogy maps to four distinct capabilities:

- **Passport (authentication):** proves which agent is presenting, with its own verifiable credential
- **Visa (delegated permissions):** says what the agent may do, on whose behalf, with a scope and an expiry
- **Itinerary (customer-approved actions):** records what specific actions the customer authorized, with limits
- **Border controls (enforcement and revocation):** the bank's ability to monitor, restrict, and cut off an agent's access independently

The bank blocks are what happens when the traveler has no passport at all and shows up with yours. The border guard sees a valid document with your name on it. It has no way to know someone else is holding it, so it has two choices: wave everything through, or stop everyone carrying that passport who doesn't look quite right. Several large banks just chose the second option.

![Today: Agent Travels on Your Passport](/postimages/charts/the-agent-is-traveling-on-your-passport-diagram-2.svg)

Same three parties in both rows. The only change is what the bank can see, and therefore what it can scope and stop.

Regulators are already describing the second row: individual identifiers for AI agents, with their own access controls ([The Logic](https://thelogic.co/?p=2139652), [TechInformed](https://techinformed.com/fsb-calls-for-tighter-controls-on-agentic-ai-in-finance/)). You can't issue an employee badge to something traveling on the customer's passport.

## Where the human model breaks

The human login model fails at three specific seams, and each one gets worse as agents get more capable.

| Seam | What the system assumes | What agents do today | Result |
| --- | --- | --- | --- |
| 1. Credential sharing | The password belongs to one human | The customer hands it to the agent | The bank can't tell the customer from the delegate |
| 2. Session riding | Proving who you are at login covers the whole session | The human logs in, then the agent drives the logged-in browser | Strong login proves who opened the session, not who is acting 12 minutes later |
| 3. No accountability chain | Every action traces to a person who meant to do it | Every action traces to "the customer's session" | Nobody can revoke only the agent, or prove what the customer actually approved |

### 1. Credential sharing

Banks have told customers not to share passwords for decades. Agents turned that advice into a setup step.

A year ago I wrote, about agents inside the enterprise, that [shared credentials and broad permissions won't survive a security review](https://khaledzaky.com/blog/agentic-ai-in-financial-services/). I was thinking about service accounts and internal tools. I didn't expect the consumer version to arrive first, at scale, with customers handing over their own passwords voluntarily.

### 2. Session riding

This is the seam I find hardest to sit with.

I spent years on passkeys, at AWS and in the FIDO Alliance and W3C WebAuthn working groups. As I wrote in [Verification Is a Budget, Not a Default](https://khaledzaky.com/blog/verification-is-a-budget-not-a-default/), the whole point was to make strong login cheap enough to use everywhere. In my head, the hard problem was always the login itself: stopping phishing, binding the sign-in to a real person on a real device. I spent far less time on what happens after the login succeeds.

**Computer-use** and **browser-control** agents, the kind that see a screen and click and type like a person would, live entirely in that "after." The human passes the passkey check. The agent inherits a fully trusted session. The strongest login on the market did its job perfectly, and it had nothing to say about who acted next.

Session riding also brings a new attack surface. A browser agent reads every page it visits, and pages can contain instructions designed to manipulate the agent. That's **prompt injection**: text the agent reads as data that it then follows as a command. Any bank evaluating agent access should assume this surface exists and test for it directly.

### 3. No accountability chain

The first two seams are what make the third one expensive. When something goes wrong, nobody can answer the basic questions. Who authorized this? Within what limits? Can we stop only this agent without locking out the customer?

In [The Halt You Never Tested](https://khaledzaky.com/blog/the-halt-you-never-tested/), I argued that revocation is a propagation problem. Here it's worse: there's nothing separate to revoke. The agent's authority and the customer's authority are the same credential. The FSB's own final report says sound practices for agentic AI "remain nascent" ([Wealth Professional](https://www.wealthprofessional.ca/news/industry-news/fsb-finalizes-12-ai-practices-for-financial-firms-flags-robo-advice-risk/393798)).

## The paperwork exists, in pieces

Existing identity and authorization standards provide a foundation, but applying them to consumer agents requires additional architecture, enforcement, and operational controls. Each piece of a proper passport, visa, itinerary, and border control for consumer agents has a standard or a production program behind it. The catch is that a widely adopted, interoperable model for consumer banking has yet to emerge, and standards maturity doesn't equal operational readiness.

I mapped what exists against the questions a bank would need answered before letting an agent in. This is my reading of public specifications and product descriptions, not a conformance assessment.

| Travel document | Question for the bank | What it is, in plain English | Example | Maturity |
| --- | --- | --- | --- | --- |
| Passport | Which agent is this, really? | The agent presents its own verifiable credential, so the bank can check who sent the request | [IETF AIMS](https://datatracker.ietf.org/doc/html/draft-ietf-wimse-aims) (active Internet-Draft, discourages static API keys); [signed agent requests](https://datatracker.ietf.org/doc/html/draft-ietf-webbotauth-httpsig-protocol) (active Internet-Draft) | Drafts |
| Visa | On whose behalf, and allowed to do what? | A token exchange mechanism that can represent delegated authority; token contents, permissions, and enforcement depend on implementation | [OAuth token exchange, RFC 8693](https://www.rfc-editor.org/rfc/rfc8693), profiled for agents in the AIMS work | Published standard |
| Itinerary | Did the customer approve this specific action? | A signed, tamper-proof record of what the customer authorized, with limits | [Signed payment mandates](https://www.vellum.ai/blog/googles-ap2-a-new-protocol-for-ai-agent-payments); [agent-only card tokens with spend limits](https://eco.com/support/en/articles/14730449) | Production pilots (limited deployments) |
| Visa cancellation | Can we stop this agent without stopping the customer? | A signal between systems that a session or credential is no longer valid | [OpenID Shared Signals and CAEP](https://standards.apievangelist.com/store/shared-signals-framework/), final since September 2025 | Published standard (communication layer; actual revocation depends on implementation and enforcement) |
| Border rules | Which actions always need a human? | Prohibited actions, approval thresholds, and an audit trail | FSB sound practices: dual approval above a threshold, restricted payment access, audit of every agent transaction | Guidance |

A few notes on this table. RFC 8693 supports actor claims and delegation chains, so it can express multi-party delegation. What it doesn't do on its own is establish customer consent or enforce authorization boundaries. Those are separate problems that need separate mechanisms. The IETF AIMS work is an active Internet-Draft, not a published standard, and its guidance on agent authentication practices (including discouraging static API keys) may evolve as the draft matures.

In March I wrote that [RFC 8693 was built for pairwise exchange, not long agent chains](https://khaledzaky.com/blog/delegation-is-the-real-identity-problem-in-agentic-ai/). That framing was too narrow. RFC 8693 does support delegation chains through actor claims. The more precise point is that for consumer banking, the protocol mechanics are available, but consent, fraud controls, and enforcement at scale are the gaps that protocol support alone doesn't close.

Two things stand out to me.

### 1. Payment networks moved first

Some payment providers are developing agent-specific tokens with spend limits and merchant allowlists that can be revoked without reissuing the customer's card ([eco.com](https://eco.com/support/en/articles/14730449)). These are early, limited deployments, not generally available bank-account access. They demonstrate that the passport and visa pattern can work for card payments. Extending it to bank-account login and broader financial access is a different problem with different trust, regulatory, and infrastructure requirements.

### 2. The regulated door is coming, on a target schedule

Canada's consumer-driven banking framework, the country's version of open banking, is expected to move from read access to write access, including payment initiation, with a target of around mid-2027 ([Goodmans via Mondaq](https://webiis10.mondaq.com/canada/financial-services/1739572/canada-moves-forward-on-its-consumer-driven-banking-framework)). That timeline is a target, not a guaranteed launch. The framework replaces password sharing with API access under explicit, revocable consent ([MX](https://www.mx.com/blog/empowering-canadians/)), which is the right door for agents, but open banking APIs don't automatically provide agent identity or per-transaction authorization. Those layers would need to be built on top.

## What I'd do now

The practical path from "block everything" to "let agents in" is a progression, and where you sit in it depends on your role.

**If you're an executive**, ask three questions of any agent integration:

1. Can we tell which agent sent this request, separately from the customer?
2. Can we prove the customer approved this specific action, not just the login?
3. Can we cut off this one agent without locking the customer out?

If any answer is no, a block is the defensible default. If all three are yes, it's worth a scoped pilot.

**If you run identity or security at a financial institution**, the progression looks like this:

1. **Detect:** Measure unauthorized agent traffic before you set policy. Understand what's already happening in your environment.
2. **Enable sanctioned read-only access.** A balance lookup and a transfer carry very different risk. Treat them as different products.
3. **Establish delegated authorization.** Pair any restriction with a sanctioned path. A block with no alternative pushes customers toward worse workarounds.
4. **Require transaction-specific approval for consequential actions.** Money movement should need a signed, per-action approval from the human, not inherited session trust.
5. **Enforce monitoring and revocation.** Design revocation per agent. The goal is to cut one agent's access without forcing the customer to reset everything. Test the session-riding case directly: a human passes strong login, then hands the session to automation. Know what your controls see.

**If you build agents:**

- Stop asking for passwords. Collecting credentials is the fastest way to get blocked, and it should be.
- Sign your requests so the bank can identify your agent, not just your customer.
- Ask for the narrowest scope and the shortest lifetime. Read-only by default; money movement only with a signed, per-transaction approval from the human.
- Publish your prompt-injection testing results per surface. Institutions will trust measured risk faster than marketing claims.

## Blocking is a default with an expiry date

With today's plumbing, blocking password-based agent access is the rational call. A bank can't verify the agent, can't prove the customer's intent per action, and can't revoke the agent without disrupting the customer. Any one of those gaps would justify caution, and the fraud, liability, and consent concerns compound on top of them.

But a default should come with conditions for revisiting it. Here's what would change my mind, written as tests anyone can check:

- Agents present their own verifiable credential on every request
- Delegated tokens name both the customer and the agent, with a scope and an expiry
- Money movement requires a signed, per-transaction approval from the human
- One agent can be revoked without touching the customer's own access, and the revocation actually propagates through the enforcement layer
- Consented API access for write actions is live, so driving a browser is no longer the only path

When those conditions are met, the question changes from "why let agents in?" to "why block a delegate we can identify, scope, and stop?"

## Back to the marketplace

The agent in that marketplace story didn't need to be malicious to cause harm. The user had granted broad permission, but that permission did not adequately capture the limits he intended. The problem was that nobody, including the user, had a document that said "list the item, never share my address, check with me before accepting an offer," and the consent mechanism ("Allow Always") was too blunt to express those limits.

That's the itinerary from last week's post, showing up in a consumer app. Giving the agent its own credential is necessary, but it isn't the whole answer. The credential needs to be paired with provable, limited, enforceable authority: scoped permissions the customer actually understood, approval per consequential action, and a revocation path that works without disrupting the customer.

I said then that I'd spend the next few months on how a mission becomes a scoped, approved, provable grant of authority. The bank announcements made that question more urgent and a lot more concrete. I'll keep sharing what I learn as I go.