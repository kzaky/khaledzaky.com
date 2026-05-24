---
title: "The Missing Runtime Contract Between AI Evals and AI Governance"
date: 2026-05-24
author: "Khaled Zaky"
categories: ["ai", "platform-engineering"]
description: "A score is not a control. An alert is not accountability. When an AI output fails validation, the platform has to know what happens next, and that decision is a contract most teams haven't written down."

---

## The Moment Nobody Designed For

Picture the failure: your agentic system generates a response, a validation layer scores it below threshold, and the platform needs to act. Right now. Not in a quarterly review. Not during the next audit cycle. Right now.

I've seen what actually happens in most setups. The checker fires, logs a metric, and the output ships anyway because nobody wired the scorer to a blocking decision. Or the system drops the response silently, the user sees nothing, and no record exists of what was suppressed or why. Or you have a hard kill switch that treats a borderline confidence score the same as a clear policy violation, blocking legitimate traffic with no nuance.

That's not governance. That's observability with better labels.

The missing piece isn't another dashboard. It's a decision framework that triggers at the moment of failure: what action is taken, who authorized that action, what evidence is retained, and what severity justified the response. I'm calling that missing artifact the **runtime contract**.

## Fail Is Not One Thing

The reason most systems default to on/off blocking is that they treat all validation failures as equivalent. They're not. There are at least three distinct failure types, and each one demands a different response:

**Hard fail:** A deterministic rule fires. Schema violation, policy-backed exact match, deterministic prohibited-content rule. There's no ambiguity here. The output violated a bright-line constraint. The appropriate action is well-defined and doesn't require judgment.

**Soft fail:** A model-judged score falls below threshold. This is where it gets complicated. LLM-as-judge evaluations carry known biases: position bias, verbosity preference, self-preference, and in some studies, same-family preference. A soft fail carries less certainty than a hard fail. The action attached to it should reflect that uncertainty.

**Drift:** Not a single-output failure, but an aggregate trend away from the certified baseline. No individual response crossed a threshold, but the distribution shifted. This is a pattern signal, not a point signal, and the response cadence is different (hours or days, not milliseconds).

Collapsing these three into a single "fail" category is how you end up with systems that either block too aggressively or don't block at all. The runtime contract needs to distinguish between them and attach different action vocabularies to each.



![Binary Fail (Current State)](/postimages/charts/the-missing-runtime-contract-between-ai-evals-and-ai-governance-diagram-1.svg)

## The Graded Action Ladder

If "fail" isn't one thing, then "block" can't be the only response. The vocabulary of action needs to be richer:

| Action | When It Applies | What Happens |
|--------|----------------|--------------|
| **Allow** | Validation passes all thresholds | Output proceeds normally |
| **Allow and log** | Score is marginal but above hard threshold | Output proceeds; event is recorded for pattern analysis |
| **Rewrite** | Specific content triggers a soft-fail rule with a known remediation | Output is modified before delivery; original and modified versions retained |
| **Block** | Hard fail on a deterministic rule | Output is suppressed; user receives a graceful fallback |
| **Escalate** | Soft fail in a high-risk tier where human judgment is required | Output held pending human review within a defined SLA |
| **Recertify** | Drift threshold crossed at the aggregate level | System flagged for re-evaluation; existing traffic may continue under elevated monitoring |
| **Quarantine** | Novel failure pattern with no existing policy match | Output held; incident record created; governance team notified for policy determination |

Governance becomes real not in the existence of a score, but in the decision attached to the score. The action ladder is the core of the runtime contract. Without it, you have metrics. With it, you have control.

## What the Contract Should Contain

I've been working on [agentic AI platforms](https://khaledzaky.com/blog/why-agentic-ai-needs-a-platform-mindset/) long enough to have opinions about what belongs in this artifact. Here's the minimum viable structure:

**What was validated:** Which model version, which prompt template, which tool-access configuration, which eval suite. Not "passed safety benchmarks" but "evaluated against [specific suite] under [specific conditions] on [specific date]."

**Severity classification:** Hard fail, soft fail, or drift. The contract maps each validation output to one of these categories explicitly.

**Risk tier:** Not every workflow carries the same consequence. A customer-facing financial recommendation and an internal document summary don't warrant the same response to the same score. The contract binds the action ladder to the risk tier of the affected workflow.

**Affected workflow:** Which agent, which pipeline stage, which downstream actions depend on this output. In agentic systems, a single model output can trigger tool calls, data writes, or delegation to other agents. The contract specifies the blast radius.

**Action:** What happens next. One of the seven actions from the ladder above, selected based on the intersection of severity and risk tier.

**Who can override:** The organization decides who is allowed to override an automated decision. The platform enforces and records it. A blocked output in a Tier 1 workflow might require a senior risk officer to release. A soft-fail in a Tier 3 workflow might allow the requesting engineer to override with a justification logged.

**What evidence is retained:** The original output, the validation score, the rule or model that produced the score, the action taken, the actor who authorized it (human or automated), and the timestamp. This is the audit trail that makes governance demonstrable after the fact.

This isn't an eval-metadata schema. It's a decision-execution schema. The eval tells you what was tested. The contract tells you what happens when something fails.

![Runtime Contract Execution Flow](/postimages/charts/the-missing-runtime-contract-between-ai-evals-and-ai-governance-diagram-2.svg)

## The Dashboard Trap

Most organizations respond to the eval-governance gap by building dashboards. Dashboards show you scores. They show you trends. They don't make decisions.

I've seen teams invest months in beautiful observability layers that surface every validation score in real time, then route exactly zero of those signals to an automated action. The dashboard becomes a comfort object: governance teams can point to it during audits, but no output was ever blocked, escalated, or rewritten because of what it showed.

Visibility isn't control. A dashboard that shows you a failing score without triggering a graded response is a monitoring system, not a governance system. The runtime contract is what sits between the score and the action.

## The Blocking Trap

The opposite failure mode is equally common. Teams that do wire validation to action wire it to a single action: block. The checker fires, the output is suppressed, end of story.

This creates two problems. First, it's brittle. A single threshold governs wildly different situations. A response that's slightly below a confidence threshold gets the same treatment as one that contains a clear policy violation. Business teams lose trust, route around the system, and you end up with shadow deployments that have no validation at all.

Second, it's invisible. Blocked outputs often leave no meaningful record beyond a counter increment. Nobody knows what was blocked, why, whether the block was appropriate, or whether legitimate traffic was suppressed. There's no evidence trail, no override mechanism, no escalation path.

The runtime contract replaces the binary with a gradient. Block is one option, not the only option.

## Inline, Online, Nearline

Where the contract executes matters as much as what it contains. Validation and action happen at different timescales depending on the failure type:

**Inline (synchronous, in the request path):** Hard-fail rules execute here. Schema validation, prohibited-content exact matches, deterministic policy checks. These add latency, so they need to be fast and narrow. The action is immediate: block or allow.

**Online (asynchronous, near-real-time):** Soft-fail model-judged evaluations execute here. Online evaluation runs within seconds of output generation and is used where the risk tier permits the output to proceed pending the score. If the risk tier doesn't permit that (high-consequence workflows where a bad output can't be recalled), the control belongs inline, not here. When a score falls below threshold in an online check, the contract triggers post-delivery remediation: log, escalate, flag for rewrite on the next interaction, or notify the user that the prior response is under review.

**Nearline (batch, periodic):** Drift detection executes here. Aggregate scores are computed over windows (hourly, daily). When a drift threshold is crossed, the contract triggers recertification or quarantine at the workflow level, not the individual-output level.

The runtime contract specifies which validation checks run at which layer, and which actions are available at each. You don't escalate from an inline check (that would block the request indefinitely). You don't run expensive model-judged evaluations in the synchronous path unless the risk tier demands it.



![Validation Execution Layers](/postimages/charts/the-missing-runtime-contract-between-ai-evals-and-ai-governance-diagram-3.svg)

## The Shared Evidence Path

One thing that became clear to me while building [governance into the platform layer](https://khaledzaky.com/blog/the-evaluation-stack-is-not-the-governance-platform/) is that eval teams, governance teams, and incident-response teams all need access to the same evidence, but they currently produce and consume it in incompatible formats.

The eval team generates benchmark scores in a Jupyter notebook. The governance team reads a PDF summary three months later. The incident-response team, when something goes wrong, reconstructs what happened from scattered logs.

The runtime contract solves this by defining a single evidence schema that's generated at the moment of failure. Every time the contract fires (every time a validation check produces a result and an action is taken), it produces a record containing:

- The input that triggered the check
- The output that was evaluated
- The validation method and score
- The action taken
- The authorization (automated rule or human actor)
- The risk tier and affected workflow

This record is the shared artifact. Eval teams can query it to understand how their checks perform in production. Governance teams can query it to demonstrate compliance. Incident-response teams can query it to reconstruct decision chains. One schema, three audiences.



## From One Output to a Pattern

A single contract execution is an event. A thousand contract executions are a signal. The runtime contract isn't just a per-output decision mechanism; it's the data source for aggregate governance intelligence.

When you retain structured evidence from every validation event, you can answer questions that no dashboard or periodic review can:

- Which workflows trigger escalation most frequently?
- Which validation checks produce the most overrides (suggesting the threshold is miscalibrated)?
- Which model versions show drift earliest?
- Which risk tiers generate the most quarantine events?

These are the questions that turn reactive compliance into proactive governance. They're only answerable if the per-output decision is structured, retained, and queryable. The contract generates the data. The platform aggregates it. Governance teams consume it.

## The Regulatory Anchors

Three regulatory frameworks provide grounding for why this matters now, not someday:

**[EU AI Act, Article 14](https://artificialintelligenceact.eu/article/14/):** Requires human oversight commensurate with risk, autonomy, and context. Specifically: the capability to monitor, understand, intervene, and halt. Not review-every-decision. The same instinct as the argument in this post, expressed in regulatory language. Article 14 stops short of specifying the runtime contract, but it creates the obligation that the contract would satisfy.

**[OSFI E-23](https://www.osfi-bsif.gc.ca/en/guidance/guidance-library/guideline-e-23-model-risk-management-2027) (effective May 1, 2027):** Canada's banking regulator requires ongoing monitoring with defined quantitative and qualitative criteria, thresholds, contingency plans, escalation procedures, and role accountability. This is remarkably close to what the runtime contract contains: severity thresholds, actions, escalation paths, and named responsible parties.

**[SR 26-2](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm) (issued April 2026):** U.S. supervisory guidance that supersedes SR 11-7. Explicitly places generative and agentic AI out of scope as novel and rapidly evolving, and points institutions back to their own risk management and governance practices. SR 26-2 doesn't prescribe a specific governance approach for generative AI. It tells you that you need one, and that existing model risk frameworks aren't sufficient.

The regulatory direction is consistent: ongoing oversight, graded response, documented decisions, human authority over automated systems. The runtime contract is the engineering artifact that operationalizes these requirements at the platform layer.

## The Real Control-Plane Questions

If you're building this, the hard questions aren't technical. They're organizational:

**Who decides the action vocabulary?** The seven actions in the ladder above are a starting point. Your organization might need more, fewer, or different ones. The decision about what actions are available is a governance decision, not an engineering decision. The platform implements it; the organization defines it.

**Who sets the thresholds?** A soft-fail threshold that's too aggressive blocks legitimate traffic. One that's too permissive lets risky outputs through. Threshold-setting is a risk decision that requires input from business, legal, and engineering. The platform enforces the threshold; the organization owns it.

**Who can override?** Override authority is the sharpest governance question. An engineer who can override any block has effectively nullified the contract. An override mechanism with no path at all creates rigidity that drives shadow deployments. The answer depends on risk tier, severity, and organizational role.

**What's the SLA for escalation?** If "escalate" is an action, someone has to respond. Within what timeframe? What happens if nobody responds? Does the system default to allow or block after the SLA expires? These are policy decisions that the contract must encode.

**How do you recertify?** When drift triggers a recertification event, what does the re-evaluation look like? Is it the full eval suite or a targeted subset? Who signs off on the results? The contract's expiry mechanism is only meaningful if the renewal process is defined.

## Next Steps

- **Define the action vocabulary with governance and legal before touching the platform.** Get organizational sign-off on the seven actions (or your variant of them) before encoding anything in code.
- **Start with hard-fail inline checks wired to block.** Schema violations and deterministic policy rules are uncontroversial; implement these first to establish a functioning contract at the narrowest scope.
- **Add soft-fail online checks with allow-and-log as the default action.** Build a production baseline and calibrate thresholds against real traffic before escalating to block or escalate actions.
- **Build the evidence schema before the dashboard.** The structured record (input, output, score, action, authorization, timestamp) is the primitive everything else is a view on top of.
- **Name override authority explicitly for each risk tier.** Document and encode in access control who can override what, under what conditions, and with what justification requirements, before an incident forces the question.

## Access, Enablement, Control

The runtime contract sits at the intersection of three platform capabilities:

**Access:** Who can deploy a model or agent into a workflow? Who can modify the validation rules? Who can change a threshold? These are identity and authorization questions that the platform must enforce.

**Enablement:** What tooling exists for teams to define their contract clauses? Can a product team specify their risk tier, their action preferences, and their override authorities without filing a ticket? Self-service enablement is what prevents governance from becoming a bottleneck.

**Control:** What happens when the contract fires? Is the action executed reliably? Is the evidence retained durably? Is the override mechanism available when needed? Control is the runtime enforcement that makes governance real rather than aspirational.

The platform provides all three. The organization defines the policies that flow through them. The runtime contract is the formal object that binds the two together.

*The eval tells you what you tested. The contract tells you what happens when something fails.*