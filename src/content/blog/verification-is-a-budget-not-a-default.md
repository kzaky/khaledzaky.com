---
title: "Verification Is a Budget, Not a Default"
date: 2026-07-05
author: "Khaled Zaky"
categories: ["identity", "security"]
description: "Modern verification systems face a fundamental constraint: unlimited scrutiny is impossible at scale. Allocate your finite verification budget strategically, reserving intensive review for high-risk cases."

---

## The Default Trap

"Verify everything" is a policy that emerges from contexts where verification volume was low enough to be thorough. A compliance officer reviewing ten contracts a week can read each line. A reporter filing one story a day can call every source. Neither model survives contact with modern information volumes.

I lived this at AWS Identity. When you're designing authentication flows that handle billions of requests, "verify the user" isn't a binary switch you can afford to flip to maximum for every single transaction. The cost of verification failure (fraud, account takeover) is real. But so is the cost of verification overhead (latency, abandonment, support tickets).

The entire design philosophy behind FIDO2 and WebAuthn, which I worked on through the FIDO Alliance and W3C, is built on this insight: make the right verification *cheap enough to be ubiquitous* through hardware and cryptographic proof, then reserve expensive human-in-the-loop scrutiny for the cases that actually warrant it.

That's not cutting corners. That's allocation.

## Verification as a Budget

The useful mental model is this: your team has a finite verification budget. It's measured in attention-hours, compute cycles, reviewer capacity, and calendar time. Every verification action you take has a cost, and that cost is paid whether or not the verification catches anything.

In my experience, the cost of verification follows a saturation curve. The first hour of review on a high-risk AI output catches real problems. The fifth hour of review on the same output catches formatting nits. The tenth hour catches nothing and burns reviewer trust in the process.

The software QA world has the most rigorous data on this. Testing accounts for 20 to 40 percent of total development costs in standard projects, rising above 50 percent for safety-critical systems, according to [Idealink Tech's cost breakdown analysis](https://cdn2.hubspot.net/hubfs/582328/making-safety-critical-affordable.pdf). That's not a bug in the process. It's evidence that verification is one of the largest line items in any serious engineering effort, and it deserves the same allocation discipline as any other budget.

![Bar chart showing software testing as percentage of total development budget: Low-complexity (12.5%), Standard (25%), Regulated/complex (35%), Safety-critical (50%+). Source: Idealink Tech](/postimages/charts/verification-is-a-budget-not-a-default-chart-1.svg)
*Source: Idealink Tech, Understanding Software Testing Costs Development Breakdown*

The canonical principle from QA literature is the cost-escalation curve: a defect caught at the requirements stage costs roughly 1x to fix, 10x if caught during testing, and 100x if it reaches production. This [1:10:100 framing from Galorath's ROI research](http://www.iceaaonline.com/wp-content/uploads/2014/03/Software-Test-Cost-and-ROI-Galorath-Feb-14-Hunt.pdf) applies directly to AI governance. Catching a hallucination or a governance failure early, before it's embedded in a downstream decision, is exponentially cheaper than discovering it after deployment.

![Bar chart showing relative cost to fix a defect by lifecycle stage: Requirements/design ($1), Testing phase ($10), Production ($100). Source: Galorath / Robbins Gioia](/postimages/charts/verification-is-a-budget-not-a-default-chart-2.svg)
*Source: Galorath / Robbins Gioia, Software Test Costs and Return on Investment (ROI) Issues*

The implication: your verification budget should be front-loaded, not evenly distributed.

## What Determines the Allocation

When I'm advising teams on where to spend their verification budget, I use three variables:

**Stakes:** What's the blast radius if this output is wrong? A customer-facing financial recommendation has different stakes than an internal summary document. The verification depth should reflect the consequence, not the content type.

**Reversibility:** Can you undo the decision if verification catches an error later? A draft blog post is reversible. A model deployed to production scoring credit applications is not (or at least, not cheaply). Irreversible decisions get more verification budget upfront.

**Epistemic uncertainty:** How confident are you in the system producing this output? A well-tested, constrained model with guardrails on a narrow domain needs less per-output verification than a general-purpose LLM operating in an open-ended context. I've written about this dynamic in [the context of guardrails and governance](https://khaledzaky.com/blog/evaluations-guardrails-and-governance-are-different-things/): knowing where your system's confidence drops is itself a verification input.

These three variables aren't a formula. They're a triage heuristic. In practice, you can classify most outputs into high/medium/low verification tiers in under a minute if you've done the upfront work of defining what "high stakes" and "irreversible" mean for your domain.

![Verification Tier Assignment](/postimages/charts/verification-is-a-budget-not-a-default-diagram-1.svg)

## What This Looks Like in Practice

**AI output evaluation.** On the platform I'm building, we don't apply the same evaluation depth to every model output. A model generating internal documentation summaries gets automated checks (format, factual grounding against source docs, policy compliance). A model generating content that informs a human decision on a regulated process gets automated checks *plus* structured human review with explicit sign-off. Same model, different verification budget, because the stakes and reversibility differ.

I've written about the infrastructure behind this in [building an automated model evaluation pipeline](https://khaledzaky.com/blog/building-an-automated-model-evaluation-pipeline-what-worked-what-didnt/). The design bar for that pipeline was explicitly: allocate compute and reviewer time to the outputs that justify it, and automate the rest.

**Identity systems.** A step-up authentication flow is verification budgeting in action. Low-risk session activity (browsing, reading) gets minimal re-verification. High-risk actions (fund transfer, permission change) trigger additional factors. The system isn't "trusting less" during low-risk moments. It's spending its verification budget where the expected loss is highest.

I've talked about [why platform engineers should care about identity systems](https://khaledzaky.com/blog/why-platform-engineers-should-care-about-identity-systems/) before, and this is the core reason: identity is the substrate that makes risk-proportionate verification possible.

**Knowledge work.** When I review my own blog agent's output (yes, [I built an AI agent that writes for this blog](https://khaledzaky.com/blog/i-built-an-ai-agent-that-writes-for-my-blog/)), I don't verify every sentence with equal intensity. I spend my budget on: factual claims with citations (are they real?), technical specifics (are they correct?), and voice (does it sound like me?). Formatting, grammar, and structural flow get a fast scan. That's not laziness. That's allocation based on where errors have the highest cost.

![Verification Tier Model](/postimages/charts/verification-is-a-budget-not-a-default-diagram-2.svg)

## Where Teams Get This Wrong

**Verifying cheap things expensively.** I've seen governance teams spend hours reviewing AI outputs that, if wrong, would cost nothing to fix and affect no one outside the team. The verification cost exceeded the error cost by orders of magnitude. When I ask "what happens if this is wrong?", the answer is often "well, nothing really." Then why are we spending reviewer hours on it?

**Under-verifying expensive things because the process is uniform.** When everything gets the same review, reviewers develop a constant pace. They can't shift into deep-scrutiny mode for the high-stakes item because they've been trained by the process to treat all items equally.

The [product recall data is instructive here](https://www.newfoodmagazine.com/label-errors-dominate-2024-us-food-recalls-costing-industry-192-billion/837701.article): label errors caused 45.5% of US food recalls in 2024, costing the industry an estimated $1.92 billion. These aren't complex manufacturing failures. They're verification allocation failures where the wrong checks were applied at the wrong points.

![Pie chart showing US food recall causes in 2024: Label errors (45.5%) vs. all other causes (54.5%), representing $1.92B in industry costs. Source: New Food Magazine](/postimages/charts/verification-is-a-budget-not-a-default-chart-3.svg)
*Source: New Food Magazine, Label errors dominate 2024 US food recalls*

**Confusing verification with validation.** Verification asks "is this output correct?" Validation asks "is this the right output to produce?" Most teams over-invest in verification (tactical, per-item checking) and under-invest in validation (strategic, system-level questioning).

I've seen teams meticulously verify every field in a model's output while never asking whether the model should be producing that output category at all. That's spending the budget on the wrong ledger entirely. I explored this distinction further in [the evaluation stack is not the governance platform](https://khaledzaky.com/blog/the-evaluation-stack-is-not-the-governance-platform/).

**Treating automation as a verification replacement rather than a budget multiplier.** Automation doesn't eliminate the need for verification budgeting. It changes the cost curve. Automated checks are cheap per-unit, so you can afford to run them broadly. Human review is expensive per-unit, so it should be reserved for the cases automation can't resolve.

The mistake is thinking "we automated verification, so we're done." The right framing is: automation expanded our budget, now we need to reallocate the human portion to higher-value targets.

## Next Steps

If you're running an AI governance program or any system where output quality matters, start by making the implicit explicit:

**Map your current verification spend.** Not in dollars (though that helps), but in hours. Where are your reviewers spending time? What's the stakes-to-effort ratio for each category? Most teams have never actually measured this, and the answer is usually surprising.

**Define your tiers.** If you're at startup scale, three tiers (high/medium/low) with clear criteria for each is plenty. If you're in a regulated enterprise, you probably need four or five tiers with documented rationale for each boundary. The criteria should be based on stakes, reversibility, and uncertainty, not on content type or team ownership.

**Automate the low-tier verification and reinvest the savings.** The point of automating routine checks isn't cost reduction (though you'll get that). It's freeing up human attention for the verification tasks that actually require judgment. I've written about what this looks like architecturally in [from periodic reviews to continuous governance](https://khaledzaky.com/blog/from-periodic-reviews-to-continuous-governance/).

**Audit quarterly.** Verification budgets drift. The model that was high-uncertainty six months ago might now have enough production data to move to a lower tier. The process that was low-stakes might have been promoted to customer-facing. Revisit your allocation on a regular cadence, not just when something fails.

The instinct to verify everything is a good instinct badly applied. The discipline isn't in the checking. It's in knowing where the checking matters most.

*Verification without allocation isn't rigor. It's anxiety with a checklist.*