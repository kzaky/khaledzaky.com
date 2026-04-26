---
title: "From Guardrails to Operating Model: The Agent Control Plane"
date: 2026-04-25
author: "Khaled Zaky"
categories: ["ai", "platform-engineering", "security"]
description: "TL;DR: Observability shows what happened."

---

**TL;DR:** Observability shows what happened. Evaluations score quality. Delegation governs authority. Guardrails constrain runtime behavior. But none of these, individually or together, creates an operating model. Regulated enterprises need a control plane for agents: a shared surface to inventory the fleet, supervise live activity, enforce policy, intervene when needed, quarantine unsafe behavior, and preserve evidence. This is the layer between agent development and enterprise accountability. It's also the layer many platform teams are only starting to recognize.

---

## The Tower

There's a useful way to think about where this series has been going.

[Observability](https://khaledzaky.com/blog/agent-observability-the-missing-layer-in-agentic-ai-platforms/) is the instrumentation. [Evaluations](https://khaledzaky.com/blog/evaluations-the-control-plane-for-ai-governance/) are the inspection. [Delegation](https://khaledzaky.com/blog/delegation-is-the-real-identity-problem-in-agentic-ai/) is who's allowed to act, on whose authority. [Dynamic guardrails](https://khaledzaky.com/blog/dynamic-guardrails-for-agentic-ai-why-static-rules-break-down-when-agents-can-delegate/) are the runtime constraints. Each of those is a layer. None of them is the control room.

Think about an air traffic control tower. The planes have altimeters, airspeed indicators, autopilot limits, brakes. Pilots have licenses and clearances. None of that adds up to an operational airspace. The tower is a different thing. It sees the whole fleet. It knows who's cleared for what corridor. It can ground a plane. It can re-route around weather. It coordinates intervention when something goes wrong, and it preserves the recording afterward.

That's what regulated enterprises need for their agent fleets. Not better instruments on individual agents. A tower.

The brakes work. But brakes don't drive the fleet.

![Agent Operating Model](/postimages/charts/from-guardrails-to-operating-model-the-agent-control-plane-diagram-1.svg)



## The Missing Layer

The **data plane** is where agents act. The **control plane** is where agents are registered, supervised, constrained, intervened on, quarantined, upgraded, retired, and audited.

That distinction is borrowed from Kubernetes, and it's useful but only up to a point. In Kubernetes, the data plane is pods executing deterministic workloads, and the control plane is `etcd`, the API server, the scheduler, the controllers. A pod that misbehaves gets restarted. A pod that crashes is replaced. The control loop is well understood because pods don't reinterpret their goals.

Agents do. Agents reason about intent, call tools creatively, delegate to other agents, and produce business decisions that affect customers. An agent that misbehaves doesn't get restarted. It gets quarantined, investigated, possibly retrained, sometimes retired. The control plane for agents inherits the architectural pattern from Kubernetes but can't inherit its assumptions.

The naming convergence is already visible in the industry, even if the language hasn't settled. There's an open-source project called Agent Control Plane built as a Kubernetes operator with custom resource definitions for LLMs, agents, tools, and tasks. Microsoft's Foundry materials increasingly treat observability in what they call the Foundry Control Plane as a first-class concern. The shape is converging. No single vendor has solved the full problem, and it would be premature to say any of them has.

## The Shape of What Is Already Happening

The practical problem is no longer hypothetical. Enterprises are moving from isolated agent pilots toward portfolios of specialized agents across customer service, compliance, engineering, risk, operations, and knowledge work. The pattern early adopters keep hitting is consistent: pilots succeed, second and third agents ship, and then the program stalls.

Not because the agents don't work. Because the team running them loses the ability to see fleet state, intervene quickly, or prove to risk that the portfolio is under control. Once that wall hits, the question changes from "can this agent work?" to "can we operate the fleet?"

That stall point is the mechanism worth naming. I've seen it show up as a credential revocation that had to be manually propagated across six agents because each team was managing its own identity configuration. I've seen it as a drift event that nobody caught because each agent team was watching their own dashboard, with no shared operational picture across the portfolio. It's not a model quality problem. It's not a prompt engineering problem. It's an operations problem, and it shows up reliably once the fleet has more than one or two agents running in production.

PwC's 2025 AI agent survey found that adopters are already reporting productivity gains, while also showing that many companies haven't yet redesigned their operating models around agents. Gartner has projected that 33% of enterprise software applications will include agentic AI by 2028, while warning that many early agentic AI projects will fail because of unclear value and weak operating discipline. Read together, those signals describe a measurable gap: the fleet is arriving before the tower is built. Adoption is moving on a 2025-to-2028 trajectory; operating model maturity isn't.

Academic work, including the Wang et al. survey on AgentOps, has formalized a four-stage operational discipline: monitoring, anomaly detection, root cause analysis, and resolution. Worth noticing that "resolution" as a clean fourth stage assumes you can isolate and fix a misbehaving agent without disturbing the rest of the chain. That assumption is exactly what the quarantine section below makes harder than it sounds.

![Agent Fleet Maturity](/postimages/charts/from-guardrails-to-operating-model-the-agent-control-plane-diagram-2.svg)



## What the Control Plane Actually Does

I find it useful to think about the control plane as six capabilities, each of which connects to a previous layer in this series.

**Inventory.** What agents exist, who owns them, which models they're bound to, what tools they can access, what data they can see, what version is deployed where. This is the fleet register, and it's the foundation of every other capability. You can't govern agents you can't find. This connects directly to identity and delegation: every agent in the inventory has a principal, a scope, and a chain of authority.

**Policy.** What models, tools, data, and other agents a given agent is allowed to use, under what conditions, with what approvals. Policy is the layer where governance decisions become machine-enforceable. Without it, the control plane is a dashboard. With it, the control plane is an enforcement surface. This is where frameworks like the FINOS AI Governance Framework and emerging common controls work plug in: codified controls that the control plane can apply across the fleet, rather than each agent team reimplementing them from scratch.

**Supervision.** Live state of every agent and every chain. Stuck runs, abnormal behavior, evaluation drift, guardrail activations, escalating context length, repeated tool failures. This is where observability and evaluations stop being separate dashboards and start being a shared operational picture. The supervisor, human or otherwise, is looking at the fleet, not at one trace.

**Intervention.** Pause, resume, approve, deny, reroute, revoke. The verbs of running production. An agent that's drifting can be narrowed in scope without being killed. A chain heading toward a sensitive action can be paused for human review. A revoked credential can be propagated across every agent that depended on it. This is the layer that regulators care about, because it's what makes "human oversight" something you can actually do at scale instead of something you can only describe in a policy document.

**Quarantine and remediation.** Isolate unsafe agents or chains without losing the context needed to investigate. This deserves its own treatment below, because it's where the operating model becomes most visible.

**Accountability.** Evidence, audit trail, ownership, replay, post-incident review. Every action an agent takes, in the context of who delegated it, what scope it had, what guardrails evaluated it, and what humans approved it. This is the system of record. It's also the deliverable in any regulatory examination.

![Agent Control Plane Capabilities](/postimages/charts/from-guardrails-to-operating-model-the-agent-control-plane-diagram-3.svg)



The reason policy deserves to be its own pillar, not folded into supervision, is that it's the layer where governance and engineering meet. Without an explicit policy capability, the control plane risks being marketed as a monitoring tool with extra screens. With policy as a first-class concern, it becomes infrastructure that the risk function can actually operate. That distinction matters more than it sounds.

## Quarantine Is Where the Operating Model Gets Real

A guardrail that fires gives you a binary outcome: allow or block. That's fine for a single agent answering a single question. It falls apart in a multi-agent business process.

Picture this. A loan origination workflow involves an intake agent, a documentation agent, a credit assessment agent, and a notification agent. The intake agent has already collected customer information. The documentation agent has pulled financial statements from a third-party data provider. The credit assessment agent is mid-evaluation when a guardrail fires on an unexpected scope expansion. What happens?

This is the question the operating model has to answer. Not in theory. In production, on a Tuesday afternoon, with a customer waiting.

Some of the questions that have to be designed for:

- Who owns the incident? Platform engineering? Risk? The business owner of the workflow?
- Is the entire chain quarantined, or just the agent that triggered the guardrail?
- What context is preserved, and for how long, before it expires or is purged?
- What downstream systems need rollback or notification? The third-party data provider has already been called and billed. The customer has already been told their application is processing.
- Can another agent resume the work safely, with narrowed scope? Or does the entire transaction need to terminate cleanly?
- What evidence is retained for risk, audit, and engineering, and where does it live?

A control plane is the place where these questions get answered consistently, not by every team building a slightly different convention. Block-and-error isn't an operating model. Pause, preserve context, notify the right oversight role, gate resumption on explicit authorization, and produce an auditable record of what happened: that's.

This is also where the limits of automation become honest. Not every quarantine should escalate to the same human. A confidence-threshold breach in a customer service agent is a different kind of incident than a transaction-risk breach in a payments agent. Routing matters. The control plane is where escalation routing lives.

## Supervisor Agents Help, but They Are Not Owners

Increasingly, the control plane itself includes agents. Supervisor patterns are becoming common in agent frameworks: Microsoft's Magentic-One orchestration, LangGraph's hierarchical patterns, supervisor-worker topologies in CrewAI and others. The premise is sensible. Humans can't watch every trace, every chain, every drift. Supervisor agents can triage, summarize, route, and recommend action faster than any operations team could.

I want to be careful here. A supervisor agent can help triage, summarize, route, and recommend action. It shouldn't become an accountability sink.

The principal/actor distinction from the [delegation post](https://khaledzaky.com/blog/delegation-is-the-real-identity-problem-in-agentic-ai/) matters. A supervisor agent has its own identity, its own delegated authority, and its own potential for context rot. It acts on behalf of someone: a platform team, a risk function, a developer group, a business process owner. That authority needs to be explicit, scoped, and auditable. The same governance discipline that applies to worker agents applies to supervisors. Same evaluations. Same guardrails. Same delegation tracking. A supervisor that isn't held to that standard becomes a single point of governance failure.

The cleanest framing I've found: human oversight is the floor, not the ceiling. Supervisor agents extend reach. They don't replace ownership of risk.

## Why Regulated Enterprises Should Care

The control plane argument is architectural first. The regulatory argument is second. The architecture matters because agents create an operations problem. Regulation matters because financial institutions have to prove that operations problem is under control.

I want to be precise about the regulatory point, because this is where it's easy to overclaim.

No regulator currently mandates an agent control plane by name. What regulators require is ongoing monitoring, human oversight, intervention capability, auditability, and accountability. A control plane is one practical architecture for operationalizing those obligations. The argument isn't "regulators say you must build this." The argument is: without something like this, the obligations are difficult to demonstrate at fleet scale.

A few specific anchors are worth naming.

In the United States, model risk guidance moved significantly in April 2026. The Federal Reserve, OCC, and FDIC jointly issued SR 26-2, which supersedes both SR 11-7 and SR 21-8. The guidance explicitly excludes generative AI and agentic AI from its scope, noting they're "novel and rapidly evolving," while stating that a banking organization's risk management and governance practices should guide the determination of appropriate controls for any tools, processes, or systems not covered. The agencies have also announced plans to issue a request for information on banks' use of AI, including generative and agentic AI. The practical read: the revised model risk framework doesn't yet cover generative or agentic AI, but firms still need governance and controls for systems outside the guidance. A control plane is one credible architecture for that.

In Canada, OSFI Guideline E-23 takes effect May 1, 2027. The guideline expands scope to all federally regulated financial institutions and explicitly includes AI/ML models, with requirements for model inventory, risk-based model risk management frameworks, ongoing monitoring across the lifecycle, and processes for tracking usage and decommissioning. Third-party model risk is included via Guideline B-10. Those expectations map directly to the primitives of an agent control plane: inventory, ownership, approved use, monitoring status, escalation, evidence, and decommissioning.

In Europe, the EU AI Act is fully applicable from August 2, 2026, with extended transition periods for high-risk systems embedded in regulated products until August 2, 2027. Article 14 requires high-risk AI systems to be designed with human-machine interface tools that allow natural persons to effectively oversee them during use. Article 12 requires automatic event logging over the lifetime of high-risk AI systems. Article 19 requires providers to keep automatically generated logs where they control them. None of those clauses say "build a control plane." All of them point toward capabilities a control plane can provide.

The pattern across these three jurisdictions is consistent: ongoing monitoring, human oversight, intervention capability, and evidence preservation. The implementation is left to the firm. A control plane is one defensible architecture for meeting those expectations at fleet scale. That's the argument most likely to land with a chief risk officer being asked how they'll operationalize Article 14 for a portfolio of agents.

## Industry Signals

The control plane shape is converging from several directions, and the naming hasn't settled. A short tour.

Microsoft's Agent Framework and Foundry materials increasingly use control-plane vocabulary: runtime, orchestration, deployment, evaluation, and observability as first-class concerns. LangGraph and LangSmith provide durable execution, human-in-the-loop primitives, and tracing for stateful agent workflows. The open-source AgentOps project, the IBM AgentOps research line, and platforms like UiPath Maestro all describe themselves with control-plane framing. FINOS has launched both an AI Governance Framework and a Common Controls for AI Services working group, aimed at codifying the policy layer that most platform tooling currently leaves to each team.

Here's the honest read on where this convergence stands: most of these tools address supervision and observability well. Some handle evaluation. Very few treat policy enforcement as a first-class primitive. That gap is the one the earlier sections of this post identified. Inventory, supervision, and accountability are getting tooling. The policy layer, the part that makes the control plane an enforcement surface rather than a monitoring dashboard, is still largely left to platform teams to build themselves.

That's not a criticism of any specific tool. It's a signal about where the hard work is. The observability problem is largely a solved engineering problem. The policy problem is a governance and engineering problem at the same time, and that's what makes it harder.

## Next Steps

If you're building or evaluating an agent platform, here's where I'd focus:

- **Start with inventory.** Before supervision, before policy, before anything else: know what agents exist, who owns them, and what they're authorized to do. You can't govern what you can't find.
- **Treat policy as infrastructure, not documentation.** A governance policy that lives in a Confluence page isn't enforceable at fleet scale. The control plane is where policy becomes machine-readable and machine-applied.
- **Design quarantine before you need it.** The loan origination scenario above isn't hypothetical. Define incident ownership, context preservation windows, and resumption gates before the first production guardrail fires.
- **Hold supervisor agents to the same standard as worker agents.** Same evaluations, same guardrails, same delegation tracking. A supervisor that's exempt from governance is a governance gap.
- **Map your regulatory obligations to control plane primitives.** If you're in a regulated financial institution, Article 14, E-23, and SR 26-2 all point toward the same capabilities. Inventory, monitoring, intervention, and evidence. Build toward those, not toward a generic "AI governance" checklist.

*Lifecycle is the natural next layer. The control plane is the space dimension of running agents. Lifecycle is the time dimension: how do you version, retire, and decommission agents in a way that respects the control plane? How do you handle ownership transfer when the team that built an agent moves on? How do you prevent governance debt from accumulating across the fleet? That's the next post.*

*The fleet is arriving before the tower is built. The teams that close that gap first won't just have better operations. They'll have the only credible answer when risk asks how the portfolio is under control.*