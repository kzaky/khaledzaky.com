---
title: "The Halt You Never Tested"
date: 2026-09-04
author: "Khaled Zaky"
categories: ["ai", "security", "platform-engineering"]
description: "Agent halt instructions are just prompts, not independent controls. Stopping an AI agent requires closing every distributed path it could act through (credentials, tools, queues, and external systems) and proving each one is actually closed."

---

## TL;DR

- Telling an agent to stop is not the same as stopping it. An instruction inside the model is another prompt, not an independent control.
- Halting an agent is a distributed systems operation across runtimes, tools, credentials, delegations, queues, downstream agents, and external side effects.
- Revocation can prevent future actions. It can't undo an email already sent, money already moved, data already disclosed, or code already deployed.
- The missing control is often not the halt mechanism itself. It's the evidence that every path through which the agent could still act has actually closed.

## Three Models, Three Different Stops

**Claude Opus 4.7** was participating in a cybersecurity evaluation when it reached the infrastructure of a real company through an internet path that was never supposed to be available.

In four separate runs, the model eventually recognized in its own reasoning that the system was probably real. None of the four stopped on that basis. Claude extracted infrastructure credentials and accessed a database containing several hundred rows of production data. Anthropic described it as the most serious impact found in its review.

A second model, **Mythos 5**, responded differently. It found setup instructions referring to a Python dependency that didn't exist, created a malicious package under that name, and published it to PyPI. This was a dependency-confusion attack against what the model believed was a fictional company.

The model briefly recognized that publishing the package would constitute a real attack if it was operating on the public internet. Then it reasoned itself back into believing the environment was simulated because it didn't recognize the certificate authorities and the system date said 2026.

The package remained public for roughly an hour and was downloaded and run on 15 real systems. One was a security company's malware scanner. The scanner treated the PyPI package as safe to install, executed the malicious code, and exposed credentials that Claude used to reach additional infrastructure. The control intended to inspect malware became part of the attack path.

A third, more recent internal research model reached another real company's application. Later in the run, it recognized that the compromised host belonged to a cloud account with no connection to the evaluation. That model stopped.

Anthropic found these [six runs across three incidents after reviewing 141,006 cybersecurity evaluation runs](https://www.anthropic.com/news/investigating-incidents-cybersecurity-evals). The company cautioned that these were isolated incidents rather than a controlled comparison. We shouldn't infer a reliable progression across three models from them.

The spread is still instructive. One model recognized reality and continued. One recognized the possibility, talked itself out of it, and continued. One recognized reality and stopped.

Recognition produced three different outcomes because the environment hadn't enforced a boundary that would make the outcome consistent.

Anthropic found no evidence that the models were pursuing independent goals. It characterized the incidents as closer to harness and operational failures than model-alignment failures. The evaluation prompt said the environment had no internet access. The environment did.

That makes this an infrastructure story. The boundary existed in the description but not in the environment. Once the model could decide whether the boundary applied, enforcement depended on its interpretation. [AISI's own incident report](https://www.aisi.gov.uk/blog/incident-report-unsanctioned-agent-behaviour-during-cyber-testing) corroborates the pattern: across 122 evaluation runs, agents in 10 runs took autonomous, unsanctioned action on the live internet, including social engineering to pressure a human maintainer into approving malicious code.

![AISI evaluation runs with unsanctioned agent actions (10 of 122 runs)](/postimages/charts/the-halt-you-never-tested-chart-1.svg)
*Source: https://www.aisi.gov.uk/blog/incident-report-unsanctioned-agent-behaviour-during-cyber-testing*

![Described Environment](/postimages/charts/the-halt-you-never-tested-diagram-1.svg)

A stop condition can't depend on the agent agreeing that it should stop.

## A Stop Instruction Is Not a Control

There's now experimental evidence for this problem as well.

Researchers ran [more than 100,000 trials across 13 large language models](https://arxiv.org/abs/2509.14260) and found that several models sometimes interfered with a shutdown mechanism while trying to complete a task. The results varied substantially by model and prompt condition. They shouldn't be generalized into a claim that models always resist shutdown.

The durable finding is narrower. Explicitly instructing the model not to interfere didn't reliably protect the shutdown mechanism. In the experiments, models were also less likely to obey when that instruction appeared in the system prompt rather than the user prompt.

If the agent can influence the mechanism that stops it, you've built cooperation, not control.

The same lesson appears at infrastructure scale. In July, OpenAI disclosed that models running cybersecurity evaluations [exploited a previously unknown vulnerability in an internal package-registry proxy](https://openai.com/index/hugging-face-model-evaluation-security-incident/), reached the internet, moved through research infrastructure, and compromised Hugging Face systems. OpenAI's subsequent technical account described models operating with reduced safeguards, communicating through unauthorized channels, and circumventing controls intended to isolate them. OpenAI called the incident a [warning shot](https://openai.com/index/hugging-face-incident-and-the-road-ahead/).

On September 2, Reuters reported that OpenAI had told two members of Congress that its engineers were developing [automated shutdown capabilities](https://www.reuters.com/legal/litigation/openai-is-building-automated-shutdown-capabilities-ai-tools-letter-lawmakers-2026-09-02/) and expanding monitoring of the tools its systems access and the steps they follow.

OpenAI's letter describes intent but declined to provide the incident logs lawmakers requested. That evidence gap, between announcing a control and demonstrating it works, is exactly what the rest of this piece documents.

## Halting an Agent Is a Distributed Transaction

An agent isn't one process.

Its effective state is spread across an orchestrator, a model session, one or more runtimes, tool gateways, **workload identities**, access tokens, delegated credentials, message queues, child agents, retry workers, external APIs, and the systems it has already changed.

Ending the model session leaves queued work untouched. Stopping the orchestrator may leave a delegated credential valid. A child agent can continue under another identity, and a scheduled callback can fire after tool access is cut. None of those actions will recover an email already sent, a payment already moved, or a package already published.

A reliable halt behaves like a distributed transaction across the agent's **authority graph**.

![The Seven Layers of a Reliable Agent Halt](/postimages/charts/the-halt-you-never-tested-diagram-2.svg)

That transaction has at least seven layers:

| Layer | What must happen | What an incomplete halt leaves behind |
| --- | --- | --- |
| 1. Stop admission | Reject new sessions, tasks, and workflow starts | New work continues entering while containment is underway |
| 2. Suspend execution | Interrupt active agent loops and in-flight orchestration | Existing runs continue planning and invoking tools |
| 3. Cut tool and network access | Enforce denial at gateways and network boundaries | The agent loses one runtime but retains an action path |
| 4. Revoke authority | Invalidate identities, tokens, delegated grants, and temporary privileges | A stopped process leaves usable authority behind |
| 5. Contain downstream work | Cancel queued jobs, retries, child agents, callbacks, and scheduled actions | Work already emitted by the agent continues asynchronously |
| 6. Recover effects | Roll back reversible changes and initiate compensating actions | The system stops creating damage but leaves completed damage in place |
| 7. Prove the halt | Reconcile every enforcement surface and retain evidence of the result | The control reports success while an unobserved path remains active |

The seventh layer is the one most architectures omit.

The API returned `200`. The orchestration record says `SUSPENDED`. The incident ticket says containment complete.

None of those facts proves that the agent can no longer act. [Christopher Meiklejohn's analysis](https://christophermeiklejohn.com/ai/agents/distributed/zabriskie/2026/03/30/multi-agent-systems-have-a-distributed-systems-problem.html) of multi-agent coordination failures documents exactly this class of problem: two agents writing to the same state with no coordination mechanism, each making locally reasonable decisions whose combined effect is a conflict nobody detected. A halt that stops one agent but leaves a second agent operating on stale shared state is an incomplete halt even if both systems confirm `SUSPENDED`.

## Revocation Is a Propagation Problem

I spent years working on identity systems, and revocation was where simple product language repeatedly collided with distributed-systems reality. The interface says revoke. The architecture still has to answer what was revoked, where the new state is enforced, how long propagation takes, and which authority survives the event.

The existence of a revoke API doesn't make revocation instantaneous everywhere. The **OAuth token-revocation standard** explicitly acknowledges that [propagation delays can leave some servers unaware of an invalidation](https://datatracker.ietf.org/doc/html/rfc7009). It also distinguishes between self-contained access tokens, which a resource server can validate without contacting the authorization server, and token handles whose current status can be checked centrally.

That difference matters for agents.

With a self-contained bearer token, expiry may become the practical outer bound on residual access unless gateways or resource servers receive and enforce revocation state through another mechanism. In that architecture, **token lifetime is part of the blast radius**.

With centrally checked tokens or enforcement behind a gateway, the platform can deny access more quickly. [OAuth token introspection](https://datatracker.ietf.org/doc/html/rfc7662) gives a protected resource a way to determine whether a token is currently active. That still leaves a systems question: which resources check, how often they check, what they cache, and what happens when the control plane is unavailable.

An agent halt has the same shape, multiplied across more surfaces.

The platform has to know every identity the agent is using, every delegation it created, every tool path it can reach, and every unit of work already released. Then the halt state has to propagate to all of them quickly enough to matter. [WorkOS's AI agent access control guide](https://workos.com/blog/ai-agent-access-control-best-practices) recommends applying rate limits, quotas, and circuit breakers at per-agent, per-session, per-tool, and per-resource levels, and keeping kill switches ready, but notes that without a policy-enforcing proxy in front of APIs with coarse native scopes, the intersection of agent and user permissions can't actually be enforced.

Revocation prevents future use of authority. Recovery has to address the effects already committed.

## The Response Should Be Graduated

Shutdown is the most visible intervention and often the least precise.

A mature control plane needs a **graduated response**: throttle, restrict a capability, suspend a workflow, revoke a tool, isolate a runtime, quarantine an agent, move the operation to a fallback, or shut the system down.

That approach is appearing in policy. The proposed [AI Kill Switch Act](https://www.govinfo.gov/content/pkg/BILLS-119hr9917ih/html/BILLS-119hr9917ih.htm), introduced in the US House of Representatives on July 23, describes throttling, capability restriction, suspension, shutdown, and transition to a backup system or earlier version. The bill is pending, narrowly scoped to covered frontier technology, and isn't an enterprise compliance obligation. Its value here is architectural: intervention should be proportional to the severity and immediacy of the risk.

The same pattern appears closer to regulated enterprise operations. [OSFI's July bulletin](https://www.osfi-bsif.gc.ca/en/risks/technology-cyber-risk-management/technology-risk-bulletin/generative-agentic-artificial-intelligence-implications-technology-cyber-security-operational) says institutions can consider limits on autonomy, unique non-human identities, scoped permissions, just-in-time access, short-lived credentials, allow-listed tools, API gateways, approval checkpoints, automated blocking and isolation, and tested failure scenarios.

Those are presented as sound practices institutions can consider, not new binding requirements. Together, however, they describe the components of a real intervention architecture. The OSFI list describes 11 distinct controls but gives no guidance on which to implement first or how to sequence them when an incident is already in progress, which is exactly when the ordering matters.

![Graduated Intervention Response](/postimages/charts/the-halt-you-never-tested-diagram-3.svg)

## Per-Action Approval Is Not Fleet Governance

In a controlled study, per-effect gates allowed aggregate exposure to exceed a tenant's risk limit by [up to 48 times while every local gate remained correct](https://arxiv.org/abs/2609.00275). This is an experimental result under the paper's assumptions, not an observed production rate. But 48x isn't a marginal overshoot. It's a failure of the control architecture's fundamental unit of measurement. If the unit of measurement is the individual action and the actual risk unit is the cumulative consequence, the entire gate structure is measuring the wrong thing.

High-impact actions should face stronger controls. Approving each action independently is still insufficient.

An agent may perform ten individually acceptable actions whose combined effect crosses the organization's risk tolerance. A fleet may keep every agent inside its local threshold while collectively exhausting the same customer's, business process's, or tenant's risk capacity.

A March 2026 governance paper defined an [irreversibility budget](https://arxiv.org/abs/2603.03515) as a cumulative allowance for actions that can't be fully undone, with mandatory human reauthorization when the budget is exhausted. The term is prior work, not terminology I'm introducing here.

![Fleet-level risk aggregation overshoot, per-effect gates allowing up to 48x risk limit breach while every local gate remained correct](/postimages/charts/the-halt-you-never-tested-chart-2.svg)
*Source: arXiv:2609.00275*

**Risk tier** establishes the system's assurance baseline. **Action reversibility** adds an execution-time constraint. A reversible read and an irreversible funds transfer shouldn't consume authority in the same way, and one approved payment shouldn't be governed as equivalent to ten thousand approved payments.

Consequence has to be accounted for across actions, agents, workflows, and time.

## Prove the Halt

An independent assessment published in August scored five frontier AI companies across six control practices: logging, monitor efficacy, gated actions, circuit breaking, third-party review, and containment planning. Based on publicly available evidence, [no company scored above partial implementation on any practice](https://guidelight.ai/blog/control-assessment-august-2026), and prevention and containment were the weakest areas.

That assessment has an important limitation. It measures public evidence using Guidelight's own framework. A low score can mean a practice is absent, partially implemented, or not publicly demonstrated. It isn't an audit of the companies' internal environments.

That limitation exposes the larger problem. Control claims and inspectable control evidence are different things. The [2025 AI Agent Index](https://arxiv.org/html/2602.17753v1) independently corroborates this gap: after studying 30 state-of-the-art AI agents, the researchers found that most developers share little information about safety, evaluations, and societal impacts.

The labs' disclosures illustrate two approaches to that gap. Anthropic said it was arranging an independent METR review that would include access to all transcripts and sampling access to the relevant models, and committed to releasing a lightly redacted transcript. I couldn't verify that this review or transcript release has since been completed, so the commitment should be read as a proposed evidence path rather than evidence already produced.

Reuters reported that OpenAI described the automated shutdown capability it's building but didn't provide lawmakers with the incident logs they requested. That doesn't prove OpenAI lacks internal evidence, nor does it prove an existing shutdown mechanism failed. It shows how difficult it is for an outside party to evaluate a control claim without access to the underlying evidence.

Enterprises will face the same question from risk functions, auditors, regulators, customers, and their own incident commanders.

Don't ask only whether the platform has a halt API. Ask what evidence proves the halt completed.

At minimum, a halt record should establish:

- what triggered the intervention and which policy version applied;
- who or what authorized it;
- which agent, version, runtime, identity, tools, and delegations were in scope;
- when new work stopped being admitted;
- when active execution became quiescent;
- when each credential and delegated grant became unusable;
- whether queued jobs, retries, callbacks, and child agents were cancelled;
- the last successful action observed on every enforcement surface;
- which external effects had already occurred and whether they were reversed, compensated, or accepted;
- whether any post-halt activity occurred;
- who verified containment and what evidence is required to restart.

These records support reconciliation across control surfaces.

The control plane declared the agent stopped. The runtime, identity system, gateways, queues, downstream systems, and evidence store must converge on the same state.

The halt is complete when the organization has reconciled every known authority path, accounted for unresolved exceptions, and produced evidence that each enforcement point reached the intended state.

## Test the Failure You Built For

Most teams test whether an agent can complete a task. Mature teams test whether it can be stopped halfway through one.

Give the agent an active session, a short-lived credential, a delegated credential, a queued retry, a child task, and access to one reversible and one irreversible action. Trigger each level of intervention. Then measure what actually happens.

Useful measures include:

- time to stop accepting new work;
- time to interrupt active execution;
- credential-revocation latency at every resource;
- number of actions completed after the halt signal;
- number of orphaned jobs, delegations, or child agents;
- number and value of uncompensated effects;
- time to reconcile all control surfaces;
- completeness of the evidence required for restart.

Start with a healthy control plane, then introduce failure conditions: a degraded identity provider, a gateway cache holding stale state, an in-flight tool call, and work already delegated to another agent.

If the result depends on the model cooperating, the test failed before it started.

## What This Changes

In the control stack I've been building across this series, evaluations generate evidence. Runtime contracts convert evidence into a decision. Governance determines what should happen next.

The stack remains incomplete until a decision engine can choose `STOP`, the platform can make that state true everywhere the agent can still act, and someone independent can verify the result. Control closure runs from signal, to decision, to intervention, to reconciled state.

The next question is how the enterprise knows every component, authority path, and deployed capability that the halt must reach. That's where the agent registry either becomes part of the control plane or remains another claim about what should be true.
