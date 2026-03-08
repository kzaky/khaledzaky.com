---
title: "Governing Autonomous Agents Is a Platform Problem"
date: 2026-03-03
author: "Khaled Zaky"
categories: ["ai", "leadership"]
description: "If agents are actors with delegated authority, then governance is not a compliance layer. It is architecture."
---

## TL;DR

If agents are actors with delegated authority, then governance is not a compliance layer. It is architecture.

I've been thinking about this a lot lately.

In earlier posts I argued that agentic AI forces a platform mindset. Then I argued that agents are not software. They behave more like participants inside your system than code you ship.

If that's true, then deployment stops being the main event. **Governance becomes the main event.**

## Agents Change the Failure Model

When I first started building agent systems, I caught myself asking the wrong question: "How do we deploy this safely?"

The honest answer is, that's not the hard part.

[McKinsey defines agentic AI](https://www.mckinsey.com/featured-insights/mckinsey-explainers/what-is-an-ai-agent) as systems that can execute multistep processes and act in the real world, not just generate text. That shift matters.

The moment your system can:

- Call tools
- Modify state 
- Chain decisions
- Retry autonomously
- Run asynchronously
- Interpret feedback

...it is no longer just producing output. **It is producing impact.**

Research on LLM-based autonomous agents [consistently breaks them into memory, planning, and action modules](https://arxiv.org/abs/2308.11432).

That framing resonated with me because it matches what we see in practice.

Once action enters the loop, governance cannot be a release gate. **It has to be continuous supervision.**

![Traditional Software](/postimages/charts/governing-autonomous-agents-is-a-platform-problem-diagram-1.svg)

## This Is Showing Up in the Market

You can spot this pattern pretty quickly.

[Gartner projects that more than 40 percent of agentic AI projects will be canceled by 2027](https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027) due to cost and unclear value, even while predicting heavy enterprise penetration. That is not a model quality issue. **That is an operating model issue.**

Microsoft has been [building agent identity and governance into its platform](https://blogs.microsoft.com/blog/2025/05/19/microsoft-build-2025-the-age-of-ai-agents-and-building-the-open-agentic-web/) since Build 2025, and later [introduced a control plane that can track, measure ROI for, and even quarantine AI agents](https://www.microsoft.com/en-us/microsoft-365/blog/2025/11/18/microsoft-agent-365-the-control-plane-for-ai-agents/). When vendors start talking about quarantine, you are not in deployment land anymore. **You are in governance land.**

![Platform Primitives](/postimages/charts/governing-autonomous-agents-is-a-platform-problem-diagram-2.svg)

## Governance Is Lifecycle Work

This is not just vendor positioning.

[NIST's AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework) makes it explicit: governance applies across the entire lifecycle, not just at deployment.

The [AI RMF Playbook](https://airc.nist.gov/docs/AI_RMF_Playbook.pdf) calls for:

- Clear responsibility chains
- Monitoring and audit frequency
- Integration with enterprise risk controls
- Formal change management

NIST also [highlights how AI risks differ from traditional software risks](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf): drift, opacity, emergent behavior, and difficulty knowing what to test. That line stuck with me. **If you don't know what to test, you can't rely on static gates. You need living governance.**

The [EU AI Act](https://artificialintelligenceact.eu/article/14/) reinforces this with explicit requirements for human oversight and post-market monitoring for high-risk systems. This is supervision over time. **Not a checklist.**

## Governance as Code

Here's what was bothering me for months.

Most organizations have AI policies. Very few have AI policies that survive a Git push.

Governance as code means:

- Policy is machine readable
- Version controlled
- Testable
- Enforced at runtime

[Open Policy Agent](https://www.openpolicyagent.org/) is one of the clearest examples of policy as code in practice. [Upsun summarized the problem well](https://upsun.com/blog/what-mid-market-it-teams-wish-they-knew-before-deploying-ai-agents/): policies in PDFs do not scale.

If you are at startup scale, you might gate autonomy through manual approvals. If you are in the enterprise, that breaks immediately. **The sweet spot is programmable delegation.** Explicit authority boundaries. Escalation rules in policy. Blast radius encoded, not assumed. That is governance as code.

## Preventative and Detective Controls

Autonomy needs both.

**Preventative**

[SailPoint frames agents as governed digital workers](https://www.sailpoint.com/blog/sailpoint-framework-governing-ai-agents/) whose access must be explicitly bounded by identity and time. That maps cleanly to what we see in real systems:

- Scoped delegation
- Time-bound credentials
- Tool allowlists
- Budget ceilings
- Approval gates

[OWASP's Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) adds another layer: prompt injection and insecure plugin design become materially worse when the system can execute tool calls. Preventative controls define what an agent may do.

**Detective**

Detective controls define what happens when autonomy drifts. [NIST's Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) recommends continuous monitoring of outcomes, anomaly detection, and post-deployment evaluation. The [EU AI Act](https://artificialintelligenceact.eu/article/26/) requires deployers to monitor operation and intervene when risk emerges.

The hard part is not setting boundaries. **The hard part is knowing when autonomy crosses them.** Can you reconstruct the action chain? Can you attribute authority? Can you quarantine safely? If you can't, you don't have governance. **You have hope.**

## Evaluation Is Governance Discipline

I've become convinced that evaluation is not just model testing. **It is governance discipline.**

[NIST's TEVV framework](https://www.nist.gov/ai-test-evaluation-validation-and-verification-tevv) treats testing, evaluation, verification, and validation as lifecycle work, including operational phase monitoring and incident tracking. That breaks down into two layers:

**Build-time evals**
- Scenario testing
- Policy adherence checks
- Red teaming
- Tool sequence validation

**Runtime evals**
- Drift detection
- Incident tracking
- Escalation rate analysis
- Emergent behavior monitoring

The [UK AI Safety Institute's Inspect framework](https://inspect.aisi.org.uk) shows how evaluation can even be embedded into agent tool loops directly. **If governance is code, evals are the test suite.** Without them, policy degrades silently.

## The Pilot to Production Gap

The [MIT NANDA "GenAI Divide" report](https://mlq.ai/media/quarterly_decks/v0.1_State_of_AI_in_Business_2025_Report.pdf) shows how many organizations evaluate generative AI tools, but very few reach sustained production use. [Gartner's 40 percent cancellation projection](https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027) reinforces this.

This is not about intelligence. **It is about supervision.** [IBM's governance guidance](https://www.ibm.com/thought-leadership/institute-business-value/en-us/report/ai-governance) emphasizes defined roles and reporting lines across the AI lifecycle. That matches what I've seen firsthand. If no one owns delegated authority, autonomy stalls. Or worse, it scales without supervision.

![Platform Maturity](/postimages/charts/governing-autonomous-agents-is-a-platform-problem-diagram-3.svg)

## The Real Shift

In earlier posts I argued that agents are not software. This is the continuation.

If agents are actors:

- Authority must be explicit
- Oversight must be continuous 
- Evaluation must be embedded
- Revocation must be possible

That is not a feature. **That is an operating model. That is platform design.**

## Next Steps

If you are experimenting with agents today:

- Map authority boundaries explicitly, who delegated what, for how long.
- Encode those boundaries as policy, not documentation.
- Add build-time policy tests before autonomy expands.
- Add runtime monitoring that can reconstruct action chains.
- Assign named owners for agent supervision, not just system uptime.

Autonomy scales fast. **Supervision must scale faster.** If you don't design governance into the platform, you will retrofit it under pressure later. *I've seen that movie before.*
