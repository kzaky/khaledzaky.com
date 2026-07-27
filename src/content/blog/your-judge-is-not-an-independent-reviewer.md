---
title: "Your Judge Is Not an Independent Reviewer"
date: 2026-07-27
author: "Khaled Zaky"
categories: ["ai"]
description: "Language models miss nearly a third of their own errors when self-reviewing code, not due to capability gaps but because self-evaluation creates structural bias that prompt engineering cannot fix."

---

## TL;DR

- Models miss nearly a third of their own semantic drift, not because they lack capability, but because the reviewer isn't independent. This is a structural problem, not a quality one.
- Self-preference bias is mechanistic: LLM judges favour low-perplexity text, and a model's own output is by construction low-perplexity to that model. Prompt engineering doesn't remove it.
- Agreement statistics (Cohen's kappa included) become unreliable in high-pass-rate regimes, which is exactly where deployed production systems live. Report prevalence alongside agreement, or you'll draw a confident and wrong conclusion.

---

Researchers at AWS ran 1,980 real code modernization jobs across 11 production language models from 7 different families. Legacy Python 2 in, modern Python 3 out. Then they checked every output against a behavioral oracle to find the cases where the rewrite silently changed what the code actually did. Then they asked each model to review its own work.

The models missed 31.7% of their own semantic drift. Not the drift of some other model. Their own.



The detail that should stop you is in the failure transcripts. There are cases where a model explicitly explains the difference between Python 2 and Python 3 behavior, names the exact semantics that changed, and then declares that behavior was preserved. It saw the defect. It described the defect. It passed itself anyway. Research on [self-attribution bias](https://arxiv.org/html/2603.04582v1) offers a mechanistic explanation: monitors fail to report high-risk actions more often when evaluation follows a previous assistant turn in which the action was generated. The failure mode is structural and conversational, not declarative.

The study also found that drift rate was non-monotone in model capability and price, so buying a smarter model doesn't fix it. The reviewer wasn't independent, and that's a structural problem with a name in every risk function in every regulated institution on earth.

## The Thing We Built Without Noticing

In my [last post](https://khaledzaky.com/blog/verification-is-a-budget-not-a-default/) I argued that verification is a budget rather than a default, and that the substrate you spend it on should climb with risk. LLM judge at the bottom, small deterministic models in the middle, formal methods and automated reasoning at the top.

I wrote one sentence in that post and moved on too quickly: using an LLM to certify an LLM is asking a probabilistic system to vouch for a probabilistic system. This post is what happens when you take that sentence seriously.

Here's the shape of the problem. Most enterprise AI evaluation today rests on an LLM judge. The judge produces a score. The score goes on a dashboard. The dashboard becomes the evidence that the system was validated. And when a second line of defence reviewer eventually asks how you know the system works, that dashboard is the answer.

Now read what OSFI's [Guideline E-23](https://www.osfi-bsif.gc.ca/en/guidance/guidance-library/guideline-e-23-model-risk-management-2027-letter) expects, effective May 1, 2027. Functional separation between model developers, model owners, and independent reviewers. Independent assessment of whether a model is properly specified, working as intended, and fit for purpose. Documentation with enough detail to establish that validation was genuine rather than a self-attestation exercise.

If your validation evidence is a score produced by a model closely related to the model being validated, you haven't built independent review. You've built a self-attestation exercise with better graphics.

Anyone who has worked in access control already knows this shape. **Separation of duties** is not a suggestion, it's the control. You don't let the same principal both request and approve. Not because the principal is dishonest, but because the architecture can't demonstrate that it wasn't. Independence is a property of the arrangement, not the intent.

![Self-Review Architecture](/postimages/charts/your-judge-is-not-an-independent-reviewer-diagram-1.svg)

## Why a Related Judge Cannot Be Independent

The research here is specific, and it's stronger than most people writing about evals seem to realise.

[Panickssery, Bowman and Feng](https://arxiv.org/html/2404.13076v1) showed at NeurIPS 2024 that LLM evaluators recognise their own generations and score them higher than human annotators judge them to deserve. The important part is the causal link they establish: self-preference strength correlates linearly with self-recognition capability. The better a model is at knowing its own writing, the more it favours it. GPT-4 and Llama 2 both show non-trivial accuracy at distinguishing themselves from other LLMs and humans out of the box.

Wataoka and colleagues gave the cleaner mechanistic account. Judges favour low-perplexity text regardless of who wrote it, and a model's own output is by construction low-perplexity to that model. This isn't vanity. It's **fluency preference**, and it's a property of how the system computes, which is why prompt engineering doesn't remove it.

Then it gets worse for the obvious fix. The standard mitigation is to use a held-out judge, a different model from the generator. Research on model similarity and AI oversight tested this directly across a large set of judge and model pairs on MMLU-Pro, and found a significant positive correlation between judgment scores and model similarity for every judge tested. The authors make the implication explicit: excluding the judge model from the rankings doesn't circumvent the problem, because similarity is a continuous confounder rather than a binary one. Spiliopoulou and colleagues found the same thing at family level, with judges rating their own model family more favourably independent of underlying quality.

Human interviewers have a name for this. **Affinity bias.** You favour the candidate who thinks like you, and you experience it as merit.

So the practical rule is sharper than "use a different model." It's: **use a judge from a genuinely different lineage, and treat similarity as a variable you have to account for rather than a box you ticked.** Adding a second judge from a distant family and looking at where the two diverge is a cheap way to make the bias visible. One [practitioner case study](https://eliteaiadvantage.com/blog/prevent-ai-coding-assistants-broken-links-hallucinations) quantified this directly: Claude self-reviewing its own link references caught 4 of 30 errors, while GPT-4 reviewing the same output caught 26 of 30.

![Cross-model vs. same-model hallucination detection — same-model caught 13.3% vs. cross-model caught 86.7%](/postimages/charts/your-judge-is-not-an-independent-reviewer-chart-2.svg)
*Source: eliteaiadvantage.com/blog/prevent-ai-coding-assistants-broken-links-hallucinations*

Two honest caveats, because this literature is young and moving.

First, not every case of a model preferring its own output is bias. Sometimes the stronger model is simply right. The harmful component is narrower: the failure to penalise its own errors. That's what the AWS modernization study measured, and that's the thing to test for.

Second, a 2026 study of structured regulatory evaluation found no self-preference at all across its judge panel, with every same-family score at or below the cross-family mean. The authors' explanation is worth acting on: their rubric was a set of binary sub-questions with explicit compliance criteria, which appears to suppress the fluency-preference mechanism because the judge is scoring compliance rather than style. That result needs replication before anyone leans on it. But it points somewhere useful. **Rubrics built as binary, criterion-by-criterion checks are more defensible than a judge asked for a holistic score.** Position bias findings have also weakened on current models compared to 2023. Bias results age. Re-test yours.

## The Statistic That Lies in Exactly Your Situation

Suppose you accept all of that and decide to calibrate properly. You sample production traces, have humans label them, and measure agreement between your judge and your humans.

Every guide will tell you the same thing: don't use raw percentage agreement, use **Cohen's kappa**, because kappa corrects for chance. Then it will hand you the Landis and Koch scale from 1977. Above 0.61 substantial, above 0.81 almost perfect.

Two problems, and the second one is serious.

The first is minor but worth stating. The Landis and Koch scale is empirical rather than mathematically derived. Fleiss and Altman published competing scales with different cut points. Say which scale you're using when you report a number.

The second problem is that Cohen's kappa is unreliable as a standalone statistic precisely when one class is rare. Feinstein and Cicchetti documented this in 1990 as the **kappa paradox**: a high observed agreement can be driven down to a very low or even negative kappa by imbalance in the marginal totals. Byrt and colleagues extended the analysis in 1993. The consensus across that literature has held for thirty years.

Now look at your production evaluation data. What's your pass rate? For most deployed systems it's well above 90%. Failures are rare, which is the entire point of shipping the system.

You're sitting in the exact regime where kappa stops being informative, because expected chance agreement approaches one and the correction eats the signal. Two annotators can agree on 195 of 200 records and produce a kappa that looks mediocre, not because the reviewers are inconsistent but because the prevalence is skewed.

So raw agreement inflates and kappa deflates, on the same data, for the same underlying reason. If you report only one of them you'll draw a confident and wrong conclusion in either direction.

The fix isn't exotic. Report raw agreement, Cohen's kappa, **Gwet's AC1**, and the marginal prevalence together. AC1 was designed for the rare-class case. Prevalence-adjusted bias-adjusted kappa is another option. Then stratify your sample rather than drawing it randomly, because random sampling systematically underrepresents the tail you actually care about: the confidently wrong answers and the low-frequency edge cases.

![Agreement Metric Reliability by Pass Rate Regime](/postimages/charts/your-judge-is-not-an-independent-reviewer-diagram-2.svg)

## Ground Truth Is a Staffing Problem

Here's the part that belongs in a budget conversation rather than a data science one.

In the last post I priced verification in tokens and milliseconds. That was incomplete. The dominant cost of a trustworthy judge isn't the judge. It's the humans required to establish that the judge is trustworthy, and unlike the judge, that cost recurs.

The market rates as of mid-2026 are public and they're not small. Generalist annotators run roughly $15 to $35 an hour. Domain experts in legal, medical and technical fields run $40 to $70. Expert-tier contract work runs from around $60 an hour for generalist experts up to $130 to $300 an hour for board-certified specialists in medicine and law, because you're paying a physician to write a grounded clinical answer or a tax attorney to work a multi-jurisdiction edge case. One reported figure puts roughly 600 high-quality RLHF annotations at around $60,000, which was approximately 167 times the compute cost of the training run they supported.



Human ground truth isn't a rounding error against inference spend. It's frequently the larger number.

And it doesn't buy you certainty either. Northcutt, Athalye and Mueller found label errors averaging 3.4% across ten of the most heavily used benchmark datasets in machine learning, with about 6% of the ImageNet validation set mislabelled. Even MNIST, benchmarked in tens of thousands of papers, contains validated label errors. When they had crowdworkers check the algorithmically flagged candidates, only about half were confirmed as genuine errors, which tells you something about how much humans disagree even about what a mistake looks like.

One finding in that paper deserves attention. On corrected labels, ResNet-18 outperforms ResNet-50 once mislabelled prevalence rises by around six points. Lower capacity models can be more useful than higher capacity ones when the data is noisy. That's the same shape as the result I wrote about earlier in this series, where smaller models at temperature zero produced consistent outputs while a much larger model didn't. Different decade, different domain, same lesson. Bigger isn't the axis.

Then there's the part of this market nobody puts on a slide. Annotation vendors in 2026 have had to build controls against annotators quietly outsourcing their labeling work to ChatGPT. Think about what that does to the whole edifice. You hired humans to be the independent ground truth against which you calibrate a model, and some of them are running a model.

So the operating model matters more than the metric. There are three sourcing patterns, and each fails differently.

| Pattern | Strength | How it fails |
|---|---|---|
| Dedicated annotation pool | Consistent, measurable, scales with volume | Drifts away from the business; annotators lack the domain authority to adjudicate hard cases |
| Embedded subject matter expert time | Real authority, defensible to a reviewer | SMEs have day jobs; throughput collapses the moment volume rises |
| Distributed peer review | Cheap, broad coverage, builds shared literacy | Rubric applied inconsistently; agreement decays quickly without adjudication |

None of them is right alone. Tier them the same way you tier verification. High-risk rubrics get SME authorship and SME adjudication. Volume goes to the pool. Distributed review is a useful signal, not a ground truth.

And track three numbers, not one: accuracy against gold, inter-annotator agreement, and drift on rolling samples. A labeller can be 95% accurate against your gold set while disagreeing with the rest of the team on a large share of cases, which doesn't mean the labeller is bad. It means your rubric has gaps.

Finally, treat the gold set as a perishable asset. It's a versioned artifact, not a file. It goes stale as your prompts, models and product surfaces change, and a stale gold set produces a confident green number about a system that no longer exists.

## The Failure Mode Behind the Failure Mode

There's one more result worth sitting with, because it undercuts the assumption that better judges would solve this.

A 2026 study of production multi-turn transaction agents examined why a capable LLM gate misses so many real defects. The answer was mostly not perception. The judge frequently saw the problem. The rubric had no axis to record it, so a guardrail or state-tracking violation got filed under something like brand voice in 113 of 114 cases. And the shipping gate was wired only to hard assertions and hangs, not to the rubric, so across 220 rounds that produced 125 raw notes, zero rounds failed the gate.

The judge produced 125 signals. The gate acted on none of them.

I've been making a version of this argument across this [entire series](https://khaledzaky.com/blog/evaluations-guardrails-and-governance-are-different-things/): a signal without a defined action is an alert, not governance. That study is the empirical version of it. The judge wasn't the weakest link. The vocabulary it was given and the gate it was wired to were.

The authors' conclusion is the right one. Automated judging should be treated as a **regression floor** (cheap, always on, good at catching known defects recurring) rather than as the primary signal for whether the system is good. Research on [deterministic integrity gates](https://arxiv.org/html/2606.09500v3) in clinical manuscript preparation reinforces this: deterministic checks detected all 27 injected defects with zero false positives, while a generic single-prompt LLM reviewer caught only 11 of 27. The halt-on-failure requirement is the architectural expression of this point: if the signal can't halt the process, the check is decorative.

## What This Changes About the Ladder

In the budget post I argued you climb the substrate ladder because higher rungs buy assurance proportional to risk. This adds a second reason, and it's a financial one.

An LLM judge carries a permanent **calibration liability**. To trust it you need human labels, and to keep trusting it you need human labels again, quarterly, forever, with the gold set refreshed and the agreement statistics recomputed and the drift monitored. A deterministic rule doesn't need any of that. Neither does a formal policy check. They're not more trustworthy because someone measured their agreement with humans. They're more trustworthy because they can't vary.

Climbing the ladder doesn't just buy you assurance. It retires a recurring human cost. For any check that's specifiable, that changes the payback maths considerably.

*The models that reviewed their own work in that AWS study weren't broken. They were doing exactly what the architecture asked of them. The architecture was the problem.*