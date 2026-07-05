---
title: "Verification Is a Budget, Not a Default"
date: 2026-07-05
author: "Khaled Zaky"
categories: ["identity", "security"]
description: "Modern verification systems face a fundamental constraint: unlimited scrutiny is impossible at scale. Allocate your finite verification budget strategically, reserving intensive review for high-risk cases."

---

A team ships an AI feature, and to make it safe they add a second model to check the first. An LLM judge on every output: grounding, tone, policy, all of it. It works, so they run it everywhere. Then two numbers start climbing. The token bill, because every output now costs a second inference. And the tail latency, because every response waits on a judge before it reaches the user. The email summarizer is paying the same verification tax as the tool that moves money. A lot of that spend is proving things that never needed proving.

Verifying everything is a good instinct applied without a budget. This post is about giving it one, and about the checks that beat an LLM judge on cost and certainty once you do.

## The Default Trap

"Verify everything" is a policy that emerges from contexts where verification volume was low enough to be thorough. A compliance officer reviewing ten contracts a week can read each line. A reporter filing one story a day can call every source. Neither model survives contact with modern information volumes.

I lived this at AWS Identity. When you're designing authentication flows that handle billions of requests, "verify the user" isn't a binary switch you can afford to flip to maximum for every single transaction. The cost of verification failure (fraud, account takeover) is real. But so is the cost of verification overhead (latency, abandonment, support tickets).

The entire design philosophy behind FIDO2 and WebAuthn, which I worked on through the FIDO Alliance and W3C, is built on this insight: make the right verification *cheap enough to be ubiquitous* through hardware and cryptographic proof, then reserve expensive human-in-the-loop scrutiny for the cases that actually warrant it.

That's not cutting corners. That's allocation.

## Verification as a Budget

The useful mental model is this: your team has a finite verification budget. It's measured in attention-hours, compute cycles, reviewer capacity, and calendar time. Every verification action you take has a cost, and that cost is paid whether or not the verification catches anything.

In my experience, the cost of verification follows a saturation curve. The first hour of review on a high-risk AI output catches real problems. By the fifth hour you are flagging formatting nits, and every hour after that catches nothing while quietly eroding reviewer trust in the process.

The software QA world treats this as a major line item rather than an afterthought. One industry vendor estimate, from [Idealink Tech](https://cdn2.hubspot.net/hubfs/582328/making-safety-critical-affordable.pdf), puts testing at roughly 20 to 40 percent of total development cost on standard projects and higher still for safety-critical work. Read that as a directional figure from a vendor, not a rigorous study. The point survives either way: verification is one of the largest line items in any serious engineering effort, and it deserves the same allocation discipline as any other budget.

![Bar chart showing software testing as percentage of total development budget: Low-complexity (12.5%), Standard (25%), Regulated/complex (35%), Safety-critical (50%+). Source: Idealink Tech](/postimages/charts/verification-is-a-budget-not-a-default-chart-1.svg)
*Directional vendor estimate, not a rigorous study. Source: Idealink Tech, Understanding Software Testing Costs Development Breakdown*

QA lore has a widely cited rule of thumb: a defect gets roughly an order of magnitude more expensive to fix at each stage it survives, often quoted as 1x at requirements, 10x in testing, and 100x in production. The precise figures and their exact origin are debated, so treat this as a directional heuristic, not a settled measurement. One version of the framing appears in [Galorath's ROI research](http://www.iceaaonline.com/wp-content/uploads/2014/03/Software-Test-Cost-and-ROI-Galorath-Feb-14-Hunt.pdf). The shape still maps onto AI governance. Catching a hallucination or a governance failure early, before it is embedded in a downstream decision, is far cheaper than catching it after deployment.

![Bar chart showing relative cost to fix a defect by lifecycle stage: Requirements/design ($1), Testing phase ($10), Production ($100). Source: Galorath / Robbins Gioia](/postimages/charts/verification-is-a-budget-not-a-default-chart-2.svg)
*Widely cited rule of thumb, exact provenance debated. One version: Galorath / Robbins Gioia, Software Test Costs and Return on Investment (ROI) Issues*

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

**Knowledge work.** When I review my own blog agent's output (yes, [I built an AI agent that writes for this blog](https://khaledzaky.com/blog/i-built-an-ai-agent-that-writes-for-my-blog/)), I don't verify every sentence with equal intensity. Factual claims with citations get the hard look: are they real? Technical specifics get checked for correctness, and the voice gets a read for whether it actually sounds like me. Formatting and grammar get a fast scan and nothing more. That is not laziness. It is allocation based on where an error would cost the most.

![Verification Tier Model](/postimages/charts/verification-is-a-budget-not-a-default-diagram-2.svg)

## Not Every Check Should Be an LLM

Once you accept that verification is a budget, the next question is what you spend it on. Most teams spend it on one thing: a large language model acting as a judge. An LLM judge is flexible and fast to stand up. It scores grounding, tone, completeness, and policy fit from a prompt, with no training data. That flexibility is why it became the default.

It is also the slowest and most expensive option, and it is probabilistic. A judge is a second inference stacked on the first. You pay for its tokens whether or not it catches anything, and every response it inspects waits on it before it reaches the user. A judge of comparable size roughly doubles the cost of the step it checks and adds its own latency on top. The exact numbers move with model and length. The shape does not. And there is a deeper problem: an LLM judge fails in the same ways the output it judges fails, because it is the same class of system. Using an LLM to certify an LLM is asking a probabilistic system to vouch for a probabilistic system.

That is fine when the stakes are low. It stops being fine as you climb the risk tiers, and the fix is not a bigger judge. It is a different substrate. Think of it as a ladder you climb only as far as the risk tier demands.

| Rung | Substrate | Nature | Cost and latency | Best for |
|------|-----------|--------|------------------|----------|
| 1 | LLM as judge | Probabilistic | Highest per check | Fuzzy, subjective checks where a wrong answer is cheap to reverse |
| 2 | Small or deterministic models and rules | Deterministic at temperature zero | Low, fast | Well-scoped checks: PII, schema conformance, numeric ranges |
| 3 | Formal methods and automated reasoning | Proven over all inputs | Expensive to set up, cheap to run, provable | Specifiable, high-stakes, irreversible policy checks |

Rung two is where an earlier finding on this blog lands. In [an earlier post on output validation](https://khaledzaky.com/blog/ai-output-validation-is-the-risk-layer-every-enterprise-is-skipping/) I showed that smaller models at temperature zero produced consistent outputs where a much larger model did not. For a compliance bar, reproducibility is the point, and a small task-specific classifier or a plain deterministic rule beats a frontier judge on cost, latency, and auditability for well-scoped checks. Vendors like Plurai are pushing small-model guardrails in this direction. Bench them against a deterministic baseline before you assume they beat a regular expression.

Rung three is where it gets interesting, and where most enterprises are not looking yet.

## What Proving It Actually Looks Like

I watched this work before it had anything to do with generative AI. I worked in identity at AWS, and identity is where automated reasoning earned its keep. AWS has a system called Zelkova that takes an access policy, an IAM policy or an S3 bucket policy, and translates it into precise mathematical logic. It hands that logic to SMT solvers (satisfiability modulo theories solvers, the industrial descendants of the SAT solvers you meet in school) and answers questions like "can anyone outside this account read this bucket." ([source](https://www.allthingsdistributed.com/2019/06/proving-security-at-scale-with-automated-reasoning.html))

The kind of answer matters. A test checks the requests you thought to try. Zelkova checks every possible request, because it reasons over the math instead of sampling the behavior. IAM Access Analyzer, the capability many AWS customers use to find resources exposed outside their zone of trust, is Zelkova underneath, and Zelkova answers more than a billion of these logic questions a day across AWS. ([source](https://www.amazon.science/blog/a-billion-smt-queries-a-day)) AWS calls it provable security.

Here is the part that connects it to evaluation. Byron Cook, who co-authored the Zelkova work, now leads the AWS group that took the same technique to generative AI. In August 2025 AWS shipped Automated Reasoning checks in Amazon Bedrock Guardrails. ([source](https://aws.amazon.com/about-aws/whats-new/2025/08/automated-reasoning-checks-amazon-bedrock-guardrails/)) The mechanism is the tell: a language model translates a natural-language policy and a model output into logical formulas, then a constraint solver verifies whether the output is consistent with the policy, with AWS reporting up to 99% accuracy at identifying verifiable responses and an explanation of which rule was satisfied or violated. ([source](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-automated-reasoning-checks.html)) The same math that proved an S3 bucket was not public is now proving that a model did not contradict a disclosure policy.

That is the top rung. Now the honest limit, because this is not magic. Automated reasoning works only where you can state the policy precisely. A capital-adequacy rule, a disclosure requirement, an entitlement boundary, a numeric threshold: specifiable, and provable. "Was this answer helpful and on-brand" is not, and no solver will help you. There is a second catch. The first stage still uses a language model to turn natural language into formal logic, and that translation can be imperfect in ways that verifying hand-written code is not. ([source](https://www.cognitiverevolution.ai/the-great-security-update-ai-formal-methods-with-kathleen-fisher-of-rand-byron-cook-of-aws/)) You are proving the output against the formalized policy, which is only as good as the formalization. That is exactly why this substrate belongs at the top of the ladder and not under every check. You reserve it for the tier where the cost of being wrong justifies the cost of formalizing the rule.

## Who Gets To Say What Good Means

There is a reason evaluation feels like a data-science problem. The people who can specify what a correct answer looks like are usually not the people who can build an evaluator. A compliance officer knows the disclosure rule cold. A relationship manager knows what a suitable recommendation is. Neither of them writes prompts or SMT formulas, so "what good looks like" gets translated, lossily, by an engineer who does not own the risk.

The most important thing about the Zelkova model was never the solver. It was the interface. AWS did not ask customers to write logic. It had the service ask the question on their behalf, so a customer could get a mathematical guarantee without knowing what an SMT solver is. ([source](https://www.amazon.science/blog/a-billion-smt-queries-a-day)) Byron Cook makes the same point about the generative-AI version: the goal is to put automated reasoning in the hands of non-scientists. ([source](https://www.allthingsdistributed.com/2026/02/a-chat-with-byron-cook-on-automated-reasoning-and-trust-in-ai-systems.html))

That is the design principle an enterprise evaluation platform needs. The business owner authors the policy in language they own. The platform compiles it down to the right substrate for the risk tier: a prompt for the judge, a rule for the deterministic check, a formal policy for the solver. The owner never sees the substrate. They see whether the answer met the bar they set. AI is a business transformation, not a science project, and evaluation only earns that word when the business can state its own definition of good and trust that the machinery underneath enforces it.

## Where Teams Get This Wrong

**Verifying cheap things expensively.** I've seen governance teams spend hours reviewing AI outputs that, if wrong, would cost nothing to fix and affect no one outside the team. The verification cost exceeded the error cost by orders of magnitude. When I ask "what happens if this is wrong?", the answer is often "well, nothing really." Then why are we spending reviewer hours on it?

**Under-verifying expensive things because the process is uniform.** When everything gets the same review, reviewers develop a constant pace. They can't shift into deep-scrutiny mode for the high-stakes item because they've been trained by the process to treat all items equally. The result is not weak checking so much as flat checking, where the wrong depth of scrutiny lands on the wrong items.

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

A note on where this one came from. A colleague on my team, Richard Song, asked me recently how I decide what to write and how I get from a blank page to a draft. The honest answer is unglamorous. I record voice notes when I am driving, I keep scratch notes that are half formal and half nonsense, and I collate the fragments until an argument shows up. This post started as one of those fragments, after I watched Byron Cook talk about automated reasoning and realized the thing that wowed me in identity years ago had quietly become the answer to a question my evaluation work kept hitting. Kudos to Richard for the nudge. The best posts usually start as a question someone else asked you.

Verification is a budget. Spend it where the risk is, on the cheapest substrate that clears the bar. The trusted path should be the fastest and cheapest path when the risk does not justify the spend, and a proven one when it does.