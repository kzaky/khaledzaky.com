---
title: "Everyone Is Building Evaluators. Almost Nobody Is Building Decision Engines"
date: 2026-06-15
author: "Khaled Zaky"
categories: ["ai", "platform-engineering"]
description: "The eval stack is maturing. The decision engine — the layer that turns evidence into governed action — is still missing from most enterprise AI programs. Here is what it needs to contain, and why it starts with an org design problem, not an engineering one."

---

## TL;DR

The AI industry is getting better at evaluations. That's progress.

Evaluations don't make decisions. They produce evidence.

The harder enterprise problem is what happens after the evidence arrives. Should the output be allowed, rewritten, blocked, escalated, quarantined, recertified, or retired? Who is allowed to override the action? What policy version applies? What evidence is retained? What happens if the same failure repeats?

That layer isn't an eval framework. It isn't a dashboard. It isn't a guardrail.

It's a **decision engine**.

For regulated enterprises scaling agentic AI, building this layer well may be the hardest platform work ahead. And it starts with a problem that has nothing to do with engineering.

## The Moment Nobody Designed For

An enterprise agent completes a financial planning workflow. A grounding interrogator scores the response at 38%. The threshold is 60%.

The signal fires.

The dashboard shows it. The evaluation log records it. The alert reaches the monitoring queue.

Nothing else happens.

The response ships. The customer sees it.

Three weeks later, during a governance review, someone asks: what controls were in place? The team points to the evaluation layer. The evaluation layer produced a signal. The signal went to a dashboard. The dashboard didn't know what to do with it.

That's a missing decision engine, not a technology failure.

This isn't hypothetical. Galileo's 2026 State of AI Evaluations report, based on more than 500 enterprise AI practitioners, found that 84.9% of organizations experienced AI incidents within six months. The same report found that teams with 90–100% evaluation coverage reported much higher reliability than teams below 50% coverage.

That is the point.

Evaluations matter. Coverage matters. But coverage isn't control.

An evaluation can tell you something failed. It can't, by itself, decide what the enterprise is allowed to do next.

## The Eval Stack Is Maturing

A year ago, a lot of AI evaluation work was improvised.

Teams were writing notebook-based tests, running ad hoc LLM-as-judge prompts, and calling the result evaluation. That was useful, but fragile. Hard to reproduce, hard to audit, hard to connect to production behavior.

That has changed.

The eval stack is now real. Traces, datasets, scorer frameworks, prompt experiments, production monitoring, online evaluations, human review workflows, and trace-to-dataset loops. Teams can compare models, test prompt changes, measure regressions, and turn failed production examples into future regression tests.

That's meaningful progress. It's also creating a new trap.

Because the eval stack is getting better, it's easy to mistake it for the governance platform. It isn't.

The eval stack answers one question: what did we observe?

Governance has to answer a different question: what do we do about it?

That distinction sounds small until you try to operate AI systems at production scale in a regulated environment.

![Eval Stack](/postimages/charts/everyone-is-building-evaluators-almost-nobody-is-building-decision-engines-diagram-1.svg)




## A Score Is Not a Decision

Consider a simple example.

An enterprise assistant generates a response in a customer-facing workflow. A groundedness evaluator scores the response at 42%.

That's a signal. It may be a serious issue. It may be acceptable in context. It may require a rewrite. It may require a block. It may require human review. It may require no immediate action but become important if the pattern repeats.

The score doesn't tell you which one.

To make that decision, the system needs more context: What workflow is this? Is the output informational or advisory? Can it trigger a downstream action? What data class is involved? What risk tier applies? Which policy version governs this workflow? Has this failure happened before? Who owns the agent? Who is allowed to override the action?

None of that is in the score.

The score is evidence. The decision comes from combining that evidence with policy, context, authority, and risk.

That combination is where governance actually happens.

Before the action vocabulary can be defined, the failure taxonomy has to be. As I covered in [The Missing Runtime Contract Between AI Evals and AI Governance](https://khaledzaky.com/blog/the-missing-runtime-contract-between-ai-evals-and-ai-governance/), failures break into three distinct categories that require different responses.

A **hard fail** is a deterministic rule violation: schema error, prohibited-content match, restricted data class. The appropriate action is well-defined and doesn't require judgment.

A **soft fail** is a model-judged score below threshold. LLM-as-judge evaluators carry documented failure modes: position preference, verbosity preference, self-preference. A soft fail means the evidence warrants a response, not necessarily a block. The risk tier and failure context should determine the action.

**Drift** isn't a single-output failure. It's an aggregate signal: production scores trending away from the certified baseline over days or weeks. No individual output crossed a threshold, but the system has moved. Drift signals recertification, not blocking of individual responses.

Collapsing all three into "fail → block" is how governance systems end up either blocking too aggressively or getting disabled under pressure from the business teams they were supposed to protect.



## Dashboards Do Not Govern

A lot of enterprise AI programs will build dashboards before they build decision engines.

I understand why. Dashboards are visible. Easy to show. They make governance feel tangible. You can point to a chart and say: we're monitoring groundedness, safety, latency, hallucination risk, and policy compliance.

That's useful. Visibility isn't control.

A dashboard that shows a failing score without triggering a governed response is a monitoring surface, not a governance mechanism. The organization can see the risk, but the system doesn't know what to do with it.

That isn't runtime governance. It's delayed awareness.

Deloitte's 2026 State of AI in the Enterprise found that nearly three-quarters of companies plan to deploy agentic AI within two years, while only 21% report having a mature governance model for autonomous agents.

That is the operating gap.

![AI adoption vs governance maturity gap — organizations regularly using generative AI (71%) vs organizations with mature AI governance model (21%)](/postimages/charts/everyone-is-building-evaluators-almost-nobody-is-building-decision-engines-chart-2.svg)
*Source: Deloitte, 2026 State of AI in the Enterprise*



Agents are moving into production faster than the governance model around them is becoming executable. The issue isn't that enterprises lack policies. It's that many policies still don't resolve into runtime decisions.

In agentic systems, the cost of that gap compounds quickly. Agents don't just generate text. They call tools, retrieve data, delegate tasks, modify state, and trigger business workflows. A bad output can become a bad action before it surfaces on any dashboard.

The next governance primitive can't be another screen. It has to be a decision layer.

## Blocking Everything Is Not Governance Either

The opposite trap is just as common.

A team wires a validation check to a single action: block. The groundedness score is below threshold. Block. The policy classifier fires. Block. The confidence score drops. Block.

This feels safe. It's simple. It creates the impression of control.

But binary blocking breaks down quickly.

First, it treats very different situations the same way. A slightly under-threshold internal summary and a high-risk customer recommendation with unsupported claims get identical responses. That isn't risk-based governance. It's a blunt instrument.

Second, it creates pressure to loosen the control. If the system blocks too much legitimate work, teams route around it. They lower thresholds, add exceptions, move workflows outside the platform, or disable checks that create too much friction. The control disappears quietly.

Third, it often leaves poor evidence. A counter increments. A request fails. Nobody can answer what was blocked, why it was blocked, whether the block was correct, who could have overridden it, or whether the same pattern is recurring fleet-wide.

Block is a valid action. Block isn't an operating model.

A mature decision engine needs a broader vocabulary: allow, allow and log, rewrite, constrain, escalate, block, quarantine, require recertification, retire. The point isn't the length of the list. Different failures require different responses, and those responses have to be defined before production traffic hits them.

## The Missing Object Is the Decision Engine

The **decision engine** is the layer that turns evidence into governed action.

It consumes signals from the eval stack, guardrails, runtime traces, identity systems, policy engines, ownership records, and risk taxonomies. Then it returns a bounded action. Not a recommendation in a dashboard. Not an alert in a queue. A decision.

In the Enterprise AI Control Stack established in [Evaluations, Guardrails, and Governance Are Different Things](https://khaledzaky.com/blog/evaluations-guardrails-and-governance-are-different-things/), the layers from interrogators through evidence to runtime contracts are now covered in most mature governance programs. The governance actions layer (the thing that converts runtime contracts into bounded, accountable decisions) is where most programs stop short.

This isn't a tooling gap. The eval platforms, guardrail systems, and observability infrastructure are good enough to support a decision engine. The gap is the decision engine itself: the logic that takes all of that evidence and produces an action that someone is accountable for.

Without it, the stack produces signals but not control.


![Decision Engine: Evidence to Governed Action](/postimages/charts/everyone-is-building-evaluators-almost-nobody-is-building-decision-engines-diagram-2.svg)


## The Questions Engineering Cannot Answer Alone

Most organizations will try to build the decision engine as a technical artifact first.

That's backwards.

A decision engine isn't an engineering artifact first. It's the executable form of an authority model.

The platform can route the signal. It can apply the policy. It can store the evidence. It can trigger the workflow. It can enforce the block.

But it can't invent the organization's risk appetite. It can't decide who is allowed to override a Tier 1 governance action. It can't decide whether silence from a human reviewer means default allow or default block. It can't decide when a quarantined agent is safe to re-enter production.

Those aren't implementation details. They're governance decisions.

And if they aren't made explicitly, the platform will still make them implicitly.

That's usually where the real risk hides.

Four questions have to be answered by legal, risk, business leadership, and compliance before a line of production code is written:

**Who holds override authority for a Tier 1 block?** An agent in a high-consequence workflow is blocked by the decision engine. The production system needs to continue. Who has the authority to release it? An engineer with admin access? A product owner? A risk officer? A named committee? This has to be defined before the block fires. Discovered during a production incident, it defaults to whoever escalates loudest.

**What is the SLA before the system auto-escalates?** The decision engine escalates to human review. Nobody responds in four hours. Does the system default to allow, default to block, escalate to the next tier, or shut down the workflow? This is a risk posture question. Legal, risk, and the business owner have to answer it jointly. No engineer can make this call.

**What evidence is required to reverse a governance action?** An agent is quarantined. The team believes the quarantine was incorrect. How do they appeal? What evidence is required? Who adjudicates? What's the reversal SLA? Encoded into the platform, these become auditable. Left undefined, the only resolution path is informal escalation.

**Who owns the decision model itself?** Who can change the action vocabulary? Who approves a new risk tier definition? Who is accountable when the decision engine makes a wrong call? Most programs never answer these, which means the platform accumulates undocumented drift until something external forces the question.

This is the actual reason most organizations build evaluators and stop.

Evaluators are pure engineering work. Define a rubric, write a scorer, run it, measure it, improve it. One team can own the full loop.

Decision engines are cross-functional work. The engineering is the straightforward part. The hard part is getting legal, risk, business, and compliance to agree on an authority model before the next model rotation forces the question at the worst possible moment.

In my experience across enterprise AI programs, the differentiator isn't the technology. It's named owners for each accountability zone: who is responsible for what, with what authority, under what conditions. Organizations with explicit accountability for responsible AI achieve measurably higher governance maturity than those with diffuse or unclear ownership.

Build the authority model first. Then build the decision engine on top of it.

## What a Decision Engine Needs to Know

A decision engine doesn't start with model scores. It starts with context.

At minimum, it needs six categories of information.

**Evidence.** The score, the evaluator, the judge model, the judge prompt, the deterministic rule, the dataset version, the trace, the input, the output, and the confidence behind the finding. A groundedness score from a calibrated evaluator isn't the same as a quick LLM-as-judge opinion from an unversioned prompt. Evidence without provenance isn't evidence. It's a claim.

**Risk tier.** The same failure means different things in different workflows. A hallucinated citation in an internal research assistant is one kind of problem. A hallucinated citation in a regulatory disclosure workflow is another. Risk can't be an afterthought. It's the routing key.

**Policy mapping.** Which policy applies, not just "safe" or "unsafe," but the full control set: data handling rules, model-use restrictions, approval requirements, human oversight obligations, retention rules, geographic constraints, and business-specific risk appetite. This is where governance has to become machine-readable. A policy that only lives in a document can guide humans. It can't govern runtime behavior at scale.

**Authority.** Who can deploy the agent? Who can approve an exception? Who can override a block? Who can restart a quarantined workflow? Who accepts residual risk? This isn't just RBAC. It's governance authority. An engineer with admin access shouldn't automatically have the authority to override a high-risk governance control. Authority has to be explicit, scoped, and recorded, and defined before the decision engine is built, not after the first production block.

**Operating state.** A single soft failure may trigger allow-and-log. Ten similar failures in an hour may trigger escalation. A recurring failure after a prompt change may trigger rollback. A drift pattern over a week may trigger recertification. One event is a decision. Many events are intelligence. The decision engine should accumulate evidence across the fleet, not evaluate each request in isolation.

**Available actions.** Not every action is valid at every execution layer. Inline checks can block or allow, but they can't wait for committee review without breaking the user experience. Online checks can log, rewrite, notify, or escalate after the fact. Nearline checks can detect drift and trigger recertification at the workflow level. The decision engine should know which actions are technically and operationally valid at each point in the system.

## Why This Matters More for Agents

This problem exists for all AI systems, but agents make it sharper.

A model produces an output. An agent produces a trajectory.

An agent may plan, call tools, retrieve data, delegate work, invoke an MCP server, ask another agent for help, write to a system of record, or trigger a downstream workflow. The risk isn't only in the final answer. It's in the path.

Should this agent be allowed to call this tool? Should it be allowed to pass this context to another agent? Should it be allowed to continue after the plan changes? Should it be allowed to act three hops from the original user request? These are decision-engine questions that evaluate the path, not just the output.

As I covered in [Delegation Is the Real Identity Problem in Agentic AI](https://khaledzaky.com/blog/delegation-is-the-real-identity-problem-in-agentic-ai/), authority has to attenuate as it moves across delegation hops — not silently amplify. The decision engine is the layer where that attenuation is enforced at runtime, not just declared in policy.

Without a decision engine that understands delegation depth, tool scope, and agent identity, governance in multi-agent systems is effectively advisory. The system can observe what happened. It can’t prevent what shouldn’t have.

MCP is standardizing how agents connect to tools and data sources. A2A is pushing agents toward collaborating across frameworks and vendors. Identity providers are beginning to treat agents as governable identities with lifecycle and access controls. That direction is good. It is also why the decision layer matters more, not less, as interoperability expands.

Interoperability without decisioning is a larger blast radius.

Singapore’s Model AI Governance Framework for Agentic AI, launched at the World Economic Forum in January 2026 as the first national governance framework specifically designed for agentic systems, provides technical and non-technical measures for deploying agents responsibly, while emphasizing that humans remain ultimately accountable for their agents’ behaviors.

That accountability cannot live only in a policy document. It has to show up in the runtime path. The decision engine is how it gets there.

## Human Oversight Needs Routing, Not Theatre

Most governance conversations eventually land on “keep a human in the loop.”

That is directionally right and operationally incomplete.

Which human? At what point? With what context? With what authority? For how long? What happens if they do not respond? What evidence do they need? Can they override the system?

Human oversight is not a checkbox. It is a routing problem.

A decision engine should know when human review is required, who should receive it, what they are being asked to decide, and what happens after they decide. It should also know when human review is not the right answer.

Some failures are deterministic and should be blocked automatically. Some are low-risk and should be logged. Some require escalation to a product owner, not a risk committee. Some require stopping the workflow immediately.

Maximum human involvement is not the goal. The right human authority at the right point in the workflow, with enough evidence to make a defensible decision, is the goal.

That is a decision-engine responsibility.

## The Regulator Will Not Ask for Your Dashboard

In regulated environments, the question is rarely: do you have a dashboard?

The question is closer to: show me what happened. Show me what the system knew at the time. Show me which control applied. Show me who approved the system. Show me who owned the workflow. Show me what action was taken. Show me who could override it. Show me whether the override was used. Show me how long the exception lasted. Show me whether this failure happened before. Show me why the system was allowed to keep operating.

That is not a monitoring problem. It is an evidence and decisioning problem.

The eval team needs evidence to improve the system. The governance team needs evidence to demonstrate control. The risk team needs evidence to understand exposure. The incident team needs evidence to reconstruct what happened. The business owner needs evidence to decide whether the workflow should continue.

The decision engine is where that evidence becomes a structured record — not scattered across dashboards, tools, and Jira tickets, but a single artifact that answers the regulator’s question.

This is already becoming visible in financial services.

Reuters reported in June 2026 that U.S. banking regulators are asking banks how they govern AI use in higher-risk areas — including what data systems can access, what guardrails are in place, what contingency plans exist, whether there are kill switches, and specifically who has authority to intervene.

Not just: did you monitor the system?

But: when the system created risk, who or what had the authority to act?

## This Is Where Policy Becomes Infrastructure

The hard part is not technical.

Engineering teams can build the router, wire the eval stack, capture traces, encode policies, enforce access, store evidence, build human review queues, and trigger quarantine and recertification workflows.

But engineering cannot decide the organization’s risk appetite alone.

Someone has to define the action vocabulary. Someone has to decide which failures require escalation. Someone has to define override authority. Someone has to approve exception duration. Someone has to decide when a system is no longer allowed to operate. Someone has to accept residual risk.

Those are governance decisions. The platform makes them executable. It should not invent them in isolation.

Organizations that shortcut this sequence — engineering builds the decision engine, governance approves it retrospectively — produce platforms that governance teams do not trust, do not use, and eventually route around.

The right sequence: governance defines the authority model. Engineering encodes it. The platform enforces it. Evidence accumulates. Governance reviews and refines. That loop — define, encode, enforce, review — is what makes governance operational rather than aspirational.

Without that loop, you have a dashboard.

## What I Would Build First

If I were starting this from scratch, I would not try to build the full decision engine on day one.

I would start with the narrowest version that proves the loop.

**First, answer the four org design questions.** Override authority by risk tier. SLA before auto-escalation. Evidence required for reversal. Ownership of the decision model itself. Do not write code until these have explicit answers from legal, risk, business, and compliance.

**Second, define the action vocabulary.** Allow, allow and log, rewrite, block, escalate, quarantine, recertify, retire. Name the actions and define what each means before encoding anything. A vague action vocabulary creates vague governance.

**Third, map actions to risk tiers.** A soft failure in a low-risk internal workflow may be allowed and logged. The same failure in a high-risk customer workflow may require escalation. Risk tier is what makes the decision model proportional.

**Fourth, build the evidence schema before the dashboard.** Input, output, trace, evaluator, score, policy version, risk tier, action taken, authority used, override status, timestamp, affected workflow. The dashboard is a view. The evidence record is the primitive.

**Fifth, wire one runtime path end-to-end.** A deterministic policy rule, a schema violation, a restricted data class. Wire that signal to a bounded action and an evidence record. Prove the loop works. Then expand.

## The Architecture Is Becoming Clear

Across this series, the shape of the enterprise AI control stack has been coming into focus.

```
Agent
   ↓
Guardrails          — constrain behavior
   ↓
Interrogators       — generate specialized evidence
   ↓
Evidence            — establish confidence and traceability
   ↓
Runtime Contracts   — convert evidence into decisions
   ↓
Governance Actions  — establish accountability
```

The decision engine is what makes the last two layers operational.

It is the layer that turns evidence into an authorized action.

Without it, the stack produces signals but not control. With it, governance becomes executable.

The hard work now is connecting evidence to decisions, decisions to authority, and authority to action.

The organizations that get this right will not govern AI by slowing every team down.

They will make the trusted path the fastest path.

Not governance as friction.

Governance as infrastructure.