---
title: "AI Governance Needs an Interrogator Network, Not One More Judge"
date: 2026-06-04
author: "Khaled Zaky"
categories: ["ai", "platform-engineering", "security"]
description: "A single LLM-as-judge can tell you whether an agent's output looks good."

---

## TL;DR

A single LLM-as-judge can tell you whether an agent's output looks good. It can't tell you whether the agent had the right authority, followed policy, used appropriate evidence, or took a path anyone would approve. Agentic AI needs a network of specialized interrogators, each designed to challenge one failure mode, composed dynamically by a governance platform based on context. The trusted path should be the fastest path.

## The Question Everyone Asks (And Why It's Not Enough)

Most teams start AI evaluation with a simple question:

*Did the model give a good answer?*

That question is useful. It's also not enough.

A model can give an answer that looks good and still be wrong. An agent can complete a task and still exceed its authority. A workflow can produce a polished response while relying on weak evidence, missing a policy constraint, leaking sensitive context, or taking a path no one would approve if they saw the full trace.

This is the part of agentic AI that makes evaluation hard.

The risk is no longer only in the final answer. It sits across the full path: the prompt, the retrieved context, the tools selected, the intermediate reasoning, the delegation chain, the policy constraints, the user's authority, the output, and the action that follows.

A single judge can't cover all of that.

## The Single-Judge Trap

The first version of many evaluation systems looks roughly the same.

You take an input. You take an output. You ask a stronger model to judge the answer. You add a rubric. You ask for a score or a rationale. Then you log the result somewhere and use it to compare versions.

That works for comparing prompts, models, and retrieval changes. But once agents start acting inside enterprise workflows, one generic judge becomes too blunt.

The judge may tell you the answer was helpful, even grounded. But it won't know whether the agent had the right authority to call the tool, whether the workflow crossed a policy boundary, whether the evidence is sufficient for the risk tier, or whether the response should be allowed, rewritten, escalated, or blocked.

Research confirms this structural gap. Label Studio's evaluation methods guide identifies that LLM-as-judge ["introduces model biases"](https://labelstud.io/learningcenter/llm-evaluation-methods-how-to-trust-what-your-model-says) and must be validated carefully. And Georgetown CSET's workshop on AI testing notes that [evaluation methodologies have yet to match the pace of AI change](https://cset.georgetown.edu/article/how-to-improve-ai-red-teaming-challenges-and-recommendations). If the field's most cited evaluation practice lacks a stable definition, a single generic judge inherits the ambiguity.

Most evaluation systems stall here. They can produce a score but can't explain what kind of failure happened, can't route it to the right control, and can't tell a team whether the system is still safe to operate. That's an operating model gap, not just an evaluation gap.

![Single LLM-as-Judge](/postimages/charts/ai-governance-needs-an-interrogator-network-not-one-more-judge-diagram-1.svg)

## Risk Lives in the Path, Not the Output

Traditional software usually fails in ways we can isolate. A service is down. A dependency timed out. A permission check failed. A schema changed.

Agentic systems fail differently.

They can fail while still producing a fluent response. They can fail while completing the task. They can fail because the answer wasn't grounded, because retrieved evidence was incomplete, because the agent used the wrong tool, because the user's intent drifted across multiple steps, because one agent delegated work to another without preserving the right authority boundary, or because the output is acceptable in one context and unacceptable in another.

A [large-scale study analyzing 13,602 closed issues across 40 open-source agentic AI repositories](https://arxiv.org/html/2603.06847v1) identified five architectural fault dimensions, 13 symptom classes, and 12 root-cause categories. Critically, faults in agentic systems frequently traverse architectural boundaries, propagating from token management logic to authentication failures, from state management defects to memory-related symptoms. This validates what I've seen building production agents: the final answer isn't enough.

For agentic systems, the thing we need to evaluate isn't only the response. It's the **behaviour**. That includes:

- What the agent was asked to do
- What context it used and what tools it selected
- What intermediate steps it took and what assumptions it made
- What authority it exercised and what evidence it relied on
- What output it produced
- What action the system took after evaluation

Once you accept that, the evaluation architecture changes. You stop thinking about one judge. You start thinking about a network of specialized interrogators.

## What I Mean by an Interrogator

I don't mean a human review team manually inspecting every AI output. I also don't mean security theatre where every answer is blocked until someone signs off.

I mean a **reusable evaluator** designed to actively challenge one specific failure mode. The word "interrogator" is deliberate: an evaluator scores passively, an interrogator probes for a specific weakness.

A **grounding interrogator** asks whether the output is supported by the evidence provided.

A **privacy interrogator** asks whether the output exposes sensitive information or combines context in a way that creates risk.

A **tool-use interrogator** asks whether the agent selected the right tool, called it with the right parameters, and used the result correctly. [Machine Learning Mastery's agent-specific metrics](https://machinelearningmastery.com/beyond-accuracy-5-metrics-that-actually-matter-for-ai-agents) identifies Tool Selection Accuracy as one of five metrics that matter beyond accuracy for agents, defined as how precisely the agent selects and executes the right function.

A **delegation interrogator** asks whether authority was preserved across agent-to-agent or agent-to-tool handoffs. [Strata's guide to agentic AI governance](https://www.strata.io/blog/agentic-identity/agentic-ai-governance-how-to-approach-it) explicitly warns that each agent should be treated as a first-class, non-human identity with lifecycle governance.

A **policy interrogator** asks whether the behaviour fits the rules that apply to the workflow.

A **numerical accuracy interrogator** asks whether the calculations, comparisons, and units are correct.

An **evidence-completeness interrogator** asks whether the answer is supported by enough information for the decision being made.

A **trajectory interrogator** asks whether the path the agent took makes sense, not just whether the final answer reads well.

Each one has a narrow job. That narrowness is the point.

The mistake is asking one evaluator to behave like a general-purpose governance system. It will miss things. Or it will become so broad that the score is hard to interpret. Or it will produce a rationale that sounds reasonable without giving the platform a clear decision.

Specialized interrogators create sharper signals. They make it possible to say: this answer is fluent, but not grounded. This action is correct, but the user didn't have the right authority. This workflow completed, but the evidence trail isn't sufficient for production use. This response can ship after a rewrite. This one needs escalation. This one should be blocked.

That's the level of precision enterprise AI needs.

![Governance Decision](/postimages/charts/ai-governance-needs-an-interrogator-network-not-one-more-judge-diagram-2.svg)

## The Governance Platform Decides Which Interrogators Apply

Not every workflow needs every evaluator.

A low-risk summarization use case may need grounding, completeness, and tone checks. A customer-impacting financial recommendation may need grounding, suitability, policy fit, evidence quality, numerical accuracy, and human escalation paths. An agent that can call tools may need tool-use, authorization, delegation, and state-change checks.

The governance platform should decide which interrogators apply based on context: the system type, risk tier, user role, data classification, tool permissions, customer impact, regulatory obligations, and runtime confidence.

The **evaluation stack** gives us the primitives: datasets, traces, scorers, judges, experiments, online checks, and human review loops.

The **governance platform** decides how those primitives are assembled into an operating model. I've written about this distinction in [The Evaluation Stack Is Not the Governance Platform](https://khaledzaky.com/blog/the-evaluation-stack-is-not-the-governance-platform/).

It answers questions like: What must be tested before release? What must be checked at runtime? Which failures require a rewrite? Which failures require escalation? Which failures block the output? Which evidence must be retained? Which risks require recertification before the system can continue operating?

The [California Management Review's "Agentic Operating Model"](https://cmr.berkeley.edu/2026/03/governing-the-agentic-enterprise-a-new-operating-model-for-autonomous-ai-at-scale) proposes four interdependent layers (cognitive specialization, coordination architecture, real-time control, and organizational governance), arguing that failures in agentic systems typically arise from misalignment across these layers rather than from deficiencies in model performance. That aligns with what I've seen: the platform must orchestrate specialized checks, not just score outputs.

Without that decision layer, evaluations remain signals. Useful signals, but still signals. The platform turns them into action.

![Governance Platform: From Signal to Action](/postimages/charts/ai-governance-needs-an-interrogator-network-not-one-more-judge-diagram-3.svg)

## Before Release: The Wind Tunnel

The analogy I keep coming back to is the **wind tunnel**.

Before an aircraft flies, engineers don't inspect the final shape and declare it safe. They instrument it with sensor arrays — each measuring a different stress dimension: thermal, vibration, pressure, aerodynamic flutter. No single instrument covers all failure modes. The test engineer decides which arrays to activate based on the aircraft's flight envelope.

That's the interrogator network. Each interrogator is a sensor array tuned to one failure mode. The governance platform is the test engineer who decides which checks run based on the agent's risk profile. The evidence pack is the flight test certificate: proof the system was challenged, not just inspected.

Before release, the interrogator network should run against curated datasets, adversarial cases, regression cases, known failure patterns, policy scenarios, and historical incidents. The goal is to understand how the system fails, where it fails, and which controls are required before it's allowed into production. The DoD's [Developmental Test and Evaluation of Autonomous Systems Guidebook](https://www.cto.mil/wp-content/uploads/2025/10/DTE-of-AS-GB.pdf) describes exactly this pattern for high-assurance autonomous systems: extensive use of modeling, simulation, and iterative testing for evidence aggregation and ongoing validation before deployment.

This is also where evaluation becomes a **compounding asset**. Every issue found during testing should become a future test case. Every production incident should become a regression. Every policy clarification should become a new evaluator or a sharper rubric. Every human review decision should improve the next automated check.

The library gets stronger over time. That's the difference between running evals and building an evaluation platform.

## At Runtime: The Live Halo

Pre-release testing covers the system you shipped. It doesn't cover the system as it operates — with changing prompts, shifting context, updated retrieval data, new tools, evolving user intent, and revised business rules. The same agent can behave differently depending on the workflow and the state of the world around it.

That's why the interrogator network has to travel with the agent, not sit at a static gate. I call this the **live halo**: a ring of specialized checks that surrounds every agent action at runtime, moving with it rather than waiting at a checkpoint it already passed.

Before an output ships or an action is taken, the platform routes the behaviour through the right set of checks. Some checks are lightweight and fast. Some run only for higher-risk workflows. Some run asynchronously for monitoring. Some trigger human review when confidence drops or impact rises.

The important part is that the result can't be just a score. A failed runtime check needs a **contract**.

- If the grounding check fails, the answer should be rewritten with a narrower claim.
- If the privacy check fails, the sensitive section should be removed.
- If the tool-use check fails, the action should be blocked.
- If the evidence check fails, the user should be told the system doesn't have enough information.
- If the policy check fails, the case should be escalated.

A runtime evaluator without a runtime action is only an alert. Alerts have value. But they aren't governance. I covered the relationship between runtime contracts and governance infrastructure in [The Missing Runtime Contract Between AI Evals and AI Governance](https://khaledzaky.com/blog/the-missing-runtime-contract-between-ai-evals-and-ai-governance/).

## The Library Is the Product

The most important asset in this model isn't one model, one judge, or one dashboard. It's the **library of reusable interrogators**.

If every team builds its own checks from scratch, governance becomes fragmented. One team has a good grounding rubric. Another has a better privacy check. Another has strong human review workflows. Another has a useful adversarial dataset. But nothing compounds across the organization. The same failure modes get rediscovered. The same controls get rebuilt. The same evidence gets collected in different formats.

[IBM's Cost of a Data Breach Report 2025](https://www.cloudfuze.com/agentic-ai-security-risks) found that 63% of companies lack proper AI governance policies. If most organizations can't maintain governance policies consistently, the fragmentation of evaluation approaches across teams is the predictable failure mode.

![Organizations lacking proper AI governance policies vs. those with policies (63% vs. 37%)](/postimages/charts/ai-governance-needs-an-interrogator-network-not-one-more-judge-chart-1.svg)
*Source: IBM Cost of a Data Breach Report 2025, cited via CloudFuze*

A platform approach changes that. A new privacy failure becomes a reusable privacy interrogator. A new tool-use issue becomes a reusable tool-use check. A new policy requirement becomes a reusable policy evaluator. A new production incident becomes a regression case for every similar system. A new human review pattern becomes training data for a better future evaluator.

This is how the organization moves from bespoke governance to shared infrastructure. Not because every AI system is the same. Because many failure modes repeat.

## The Human Role Changes, But It Does Not Disappear

This isn't an argument for removing humans from governance. It's the opposite.

The point of an interrogator network is to stop wasting human attention on work the platform can do consistently, and to route human judgment to the places where it matters most.

Humans should define the policies. Humans should approve risk thresholds. Humans should review ambiguous cases. Humans should investigate failures. Humans should decide what tradeoffs the organization is willing to accept. Humans should own the accountability model.

But humans shouldn't have to manually rediscover the same failure mode across every new AI use case. That's what the platform should absorb.

The best governance systems will combine automated checks, human review, evidence capture, and runtime controls into one loop. The human doesn't disappear. The human gets leverage.

## Why This Matters Now

The industry is moving quickly from AI applications that answer questions to agents that perform work. [Gartner predicted that 30% of generative AI projects would be abandoned after proof of concept by end of 2025](https://kili-technology.com/blog/ai-model-evaluation-guide-methods-metrics-and-why-it-determines-production-success), citing poor data quality and inadequate risk controls. Those projects didn't fail because governance slowed them down. They failed because the absence of governance infrastructure made production-grade deployment unachievable.

![Generative AI projects abandoned after proof of concept vs. continuing (30% vs. 70%)](/postimages/charts/ai-governance-needs-an-interrogator-network-not-one-more-judge-chart-2.svg)
*Source: Gartner, cited via Kili Technology*

That shift from answering to acting changes the governance problem.

When an AI system only drafts a response, the risk is mostly in the content. When an AI system retrieves data, calls tools, delegates to other agents, updates records, generates recommendations, or triggers downstream actions, the risk moves into the workflow.

Evaluation has to follow that shift. A static checklist won't be enough. A single judge won't be enough. A dashboard won't be enough.

Enterprises need an evaluation layer that can challenge agent behaviour from multiple angles, route failures to the right control, and preserve the evidence needed to explain what happened.

## Next Steps

Five things I'd do before the next model rotation:

1. **Audit your current evaluation surface.** Are you evaluating only final outputs, or the full agent trace (tool selection, delegation, evidence quality, authority)? If it's output-only, you have blind spots.

2. **Identify your top three failure modes.** Don't boil the ocean. Pick the failure modes that carry the most risk for your specific workflows (grounding, tool misuse, policy violation, delegation drift) and build interrogators for those first.

3. **Wire evaluators to runtime actions, not just dashboards.** A score without a contract (rewrite, escalate, block) is an alert, not governance. Define what the platform does when each check fails before you ship.

4. **Build the library, not just the check.** Every failure found in testing or production should become a reusable interrogator or a regression case. The library is the compounding asset.

5. **Let the governance platform decide which interrogators apply.** Not every workflow needs every check. Risk tier, data classification, tool permissions, and user role should drive interrogator selection dynamically.

*The trusted path should be the fastest path. The interrogator network is how you make that true at scale.*