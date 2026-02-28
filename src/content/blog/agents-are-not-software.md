---
title: "Agents Are Not Software"
date: 2026-02-28
author: "Khaled Zaky"
categories: ["tech"]
description: ""
---

## TL;DR

Agents are not software. They are system actors. The hardest problems in agentic AI are not about reasoning quality or model capability. They are about identity, authorization, delegation, and governance. If your platform isn't designed for autonomous actors, it will eventually break in ways that feel unfamiliar.

---

Over the past few months building agent systems, one realization kept resurfacing.

The challenges we were running into didn't look like normal software problems.

At first, everything felt familiar. You build an agent in Python with FastAPI, try out LangChain, connect it to tools, give it access to data and MCPs, add some guardrails, run a few workflows. It works. Then something subtle happens.

The questions change.

Not *what can the agent do?* But *what is the agent allowed to do?* Not *how do we deploy it?* But *how do we control it?*

That was the moment it became clear. Agents are not software. They are system actors.

---

## Software Executes. Agents Act.

Traditional software lives inside boundaries we understand well. Applications execute predefined logic. Services respond to requests. APIs operate under known permissions. It is all deterministic.

Even distributed systems, for all their complexity, remain fundamentally deterministic. We know who initiated an action, why it ran, and which identity was responsible.

Agents break that mental model.

An agent can decide which tools to call, plan multi-step actions, operate asynchronously, delegate work to other agents, adapt based on context, and continue acting long after the original request ends. According to Wizeline, agents "don't just talk, they can listen, reason about a request or specified task and, most importantly, act on it flexibly by leveraging tools, data, and other services at their disposal." That flexibility is the point. It is also where the operational complexity begins.

The system is no longer executing instructions. It is hosting actors capable of taking actions. That distinction sounds small. Operationally, it changes everything, especially in regulated industries where traceability of every action and change is a hard requirement.

![Traditional Software vs AI Agents — comparison across five dimensions](/postimages/charts/agents-are-not-software-comparison.svg)

---

## The First Thing That Breaks Isn't the Model

Early conversations around agentic AI often center on reasoning quality, prompting techniques, or model capability. In practice, those are rarely the problems that slow teams down.

The friction shows up somewhere else.

Teams begin asking questions like: Which identity is this agent using? Why does it suddenly need broader permissions? Who approved this action? Why did it run again hours later? Which agent actually triggered this downstream change?

None of these are model problems. They are platform problems.

Many organizations introduce agents using patterns that worked for earlier automation: shared service accounts, inherited user credentials, or long-lived API keys. These shortcuts work initially because agents start small. But as autonomy increases, those assumptions collapse. Permissions accumulate. Delegation becomes invisible. Audit trails blur. Ownership becomes unclear.

The system loses a clear understanding of who is acting. And once that happens, trust erodes quickly.

This pattern is well-documented beyond our own experience. Research into enterprise agent deployments points to a consistent failure mode: teams treat AI agents like traditional software, and that framing eventually breaks. Agents are probabilistic, adaptive systems. They reason, plan, invoke tools, and evolve with context. That breaks many assumptions we have relied on for years around SDLC, testing, security, and governance. According to a study on developer challenges in AI agent systems, roughly 60% of enterprise agent deployments encounter significant failure due to applying traditional software assumptions to agents that require fundamentally different operational models.


Most teams are still in the early or experimental phase. The platform gaps I'm describing are going to hit a lot of organizations at roughly the same time.

---

## Identity Moves to the Center

One of the most interesting signals from conversations after my earlier posts was how quickly discussions shifted toward identity and authorization.

That felt meaningful.

When something can independently initiate actions inside enterprise systems, it requires identity. Not authentication in the traditional login sense. Identity as a foundational architectural primitive.

An agent needs its own identity, scoped authority, time-bound permissions, explicit delegation chains, revocable access, and auditable intent.

Treating agents as extensions of human users or generic machine workloads stops working at scale. We are introducing a new category of participant inside enterprise systems: non-human actors operating with delegated authority. Enterprise infrastructure was not originally designed for this.

Like many enterprises, we already had mature identity approaches for two well-understood categories: human identities and machine identities. Agents sit somewhere uncomfortably in between.

From an infrastructure perspective, they resemble machines. From an operational perspective, they behave more like humans, making decisions, delegating tasks, and acting with intent. Existing models don't map cleanly.

If we force agents into human identity systems, agility suffers. If we treat them purely as machines, the security posture weakens. Both models begin to strain.

![Agent Identity — a new category between human and machine identity](/postimages/charts/agents-are-not-software-identity.svg)

Because much of our platform runs on Kubernetes, we naturally looked toward patterns emerging in the CNCF ecosystem. **SPIFFE** stood out as an interesting starting point. Workload identity tied to runtime context begins to approximate what agents need: cryptographic identity, dynamic trust, and short-lived credentials instead of static ownership.

But identity alone is only part of the equation. **Authorization and policy** quickly become equally important. Agents need tools, data, and access to systems to deliver value, but how you govern that access properly is the hard part. Policy languages like **Cedar** introduce expressive authorization models that can capture intent rather than just permissions. Starting with coarse-grained policies and drilling deeper over time felt like a reasonable starting point.

We also encountered emerging concepts like **Entra Agent Identity**, which reflect similar thinking appearing across vendors and platforms. The appeal there is real: agent identity tied to your existing IdP, without federating new systems or acquiring new tooling.

What became clear is that the industry is collectively searching for a model rather than converging on one. Everyone recognizes the gap. No single standard has emerged yet. That uncertainty is probably expected. We are still early. That's how it feels from where I stand.

---

## Delegation Is the Real Complexity

Agents rarely operate alone.

One agent invokes another. A human invokes an agent. That agent triggers workflows. Workflows access data or infrastructure. Authority propagates across systems.

We are no longer managing permissions for applications. We are managing flows of delegated authority.

Who authorized the action? Was delegation intentional? Is the permission still valid? Should the agent continue operating?

The platform becomes responsible for mediating autonomy itself. That is a fundamentally different design problem than anything we solved for traditional software. Research into multi-agent system architectures reinforces this: the challenge is not coordination between agents, it is maintaining a coherent and auditable chain of authority as delegation propagates across system boundaries.

![Delegation chain — authority propagates from human through agents to infrastructure](/postimages/charts/agents-are-not-software-delegation.svg)

---

## How We Started Thinking About This

This realization didn't emerge from theory. It evolved through ongoing conversations and whiteboarding with peers. [Gaurav](https://www.linkedin.com/in/gauravh-j/) and I found ourselves independently arriving at very similar conclusions while working through real platform design questions.

That convergence felt meaningful. When different teams solving different problems land in the same place, it usually signals a broader architectural shift.

A thought from [Bob Blainey](https://www.linkedin.com/in/bblainey/), a leader I deeply respect, resonated particularly well here. Reflecting on earlier API transformation initiatives, he described how many teams relied heavily on **shims** layered on top of legacy systems. Those approaches enabled short-term progress and met the immediate data requirements, but often postponed deeper modernization and introduced long-term complexity.

There is a similar risk with agents.

We can adapt existing identity and authorization systems just enough to make agents work today. Forcing non-OAuth systems to fit modern patterns, or layering shims that make the end-to-end security model inconsistent, can get you moving. But if agents truly represent a new class of system actor, incremental adaptation may not be enough. Where we start may not be where we end up a year from now.

---

## From Applications to Actors

I remember the early days of cloud adoption at banks and how cloud computing forced organizations to rethink infrastructure entirely. Zero trust forced a rethink of network boundaries. Agentic AI appears to be forcing a rethink of system participation.

Instead of applications running inside infrastructure, we now have actors operating within it. Actors that reason. Actors that plan. Actors that act.

Once you view it this way, familiar platform concerns change meaning:

- **Observability** becomes understanding decisions, not just metrics.
- **Governance** becomes continuous authorization rather than static access control.
- **Deployment** becomes lifecycle management of autonomous behavior.
- **Safety** becomes an operational discipline, not only a model problem.

The platform stops being a place where software runs. It becomes a control plane for autonomous actors.

This mirrors early cloud adoption closely. Organizations first experimented with individual workloads before realizing they needed shared foundations to operate safely at scale. Agent systems appear to be following the same trajectory. The hard problem is not creating intelligence. It is operating autonomy.

---

## Where This Seems to Be Heading

Many teams begin building agents believing they are adding AI features. At some point, that framing stops fitting.

The work shifts toward identity, authorization, evaluation, guardrails, human oversight, and operational trust. In other words, the work starts looking like platform engineering again.

If agents are system actors, enterprises will likely need new platform primitives:

- Agent identity models
- Intent-based authorization
- Short-lived delegated credentials
- Evaluation and learning loops
- Lifecycle governance for autonomous systems

The vocabulary is still forming. Standards are still emerging. It is entirely possible that where many of us start will look different a year from now.

But one pattern is becoming clearer. The future of agentic AI will not be defined by better models alone. It will be defined by the platforms that make autonomous behavior safe, observable, and trustworthy inside real systems.

---

## Next Steps

If you are building or evaluating agent systems, here is where I would focus attention:

1. **Audit your current identity assumptions.** Are agents running under shared service accounts or inherited user credentials? That is the first thing to fix.
2. **Start modeling delegation explicitly.** Every time an agent invokes another agent or system, that is a delegation event. Treat it as one.
3. **Look at SPIFFE, Cedar, and Entra Agent ID.** None has a complete answer yet, but each offers useful primitives for workload identity and expressive authorization. Worth understanding now, before you need them urgently.
4. **Separate model evaluation from platform evaluation.** If your agent reviews are only asking "does it reason well?", you are missing half the question. Ask "can we audit, revoke, and govern this?" too.
5. **Expect your mental model to shift.** The teams that adapt fastest are the ones that stop treating agents like fancy automation and start treating them like a new class of system participant.

*These are the patterns we are observing while building. The space is moving too quickly for premature certainty, but the direction is clear enough to act on.*
