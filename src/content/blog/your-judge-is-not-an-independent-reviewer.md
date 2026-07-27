---
title: "Your Judge Is Not an Independent Reviewer"
date: 2026-07-27
author: "Khaled Zaky"
categories: ["ai"]
description: "Language models miss nearly a third of their own errors when self-reviewing code, not due to capability gaps but because self-evaluation creates structural bias that prompt engineering cannot fix."

---

## TL;DR

- Models miss nearly a third of their own semantic drift. The reviewer isn't independent, and that's a structural problem: more capability doesn't fix it.
- Self-preference bias is mechanistic: LLM judges favour low-perplexity text, and a model's own output is by construction low-perplexity to that model. Prompt engineering doesn't remove it.
- Agreement statistics (Cohen's kappa included) become unreliable in high-pass-rate regimes, which is exactly where deployed production systems live. Report prevalence alongside agreement, or you'll draw a confident and wrong conclusion.

---

[Researchers at AWS](https://arxiv.org/abs/2605.21537) ran 1,980 real code modernization jobs across 11 production language models from 7 different families. Legacy Python 2 in, modern Python 3 out. Then they checked every output against a behavioral oracle to find the cases where the rewrite silently changed what the code actually did. Then they asked each model to review its own work.

The models missed 31.7% of their own semantic drift. Their own, not some other model's.



Look at the failure transcripts and you'll see why. In several cases a model explains the exact difference between Python 2 and Python 3 behavior, names the specific semantics that changed, then declares the behavior was preserved anyway. It identified its own defect and passed itself regardless. Research on [self-attribution bias](https://arxiv.org/html/2603.04582v1) offers a mechanistic explanation: monitors fail to report high-risk actions more often when evaluation follows a previous assistant turn in which the action was generated. The failure mode is structural and conversational, not declarative.

The study also found that drift rate was non-monotone in model capability and price, so buying a smarter model doesn't fix it. The reviewer wasn't independent, and that's a structural problem with a name in every risk function in every regulated institution on earth.

## The Thing We Built Without Noticing

In my [last post](https://khaledzaky.com/blog/verification-is-a-budget-not-a-default/) I argued that verification is a budget rather than a default, and that the substrate you spend it on should climb with risk. LLM judge at the bottom, small deterministic models in the middle, formal methods and automated reasoning at the top.

I wrote one sentence in that post and moved on too quickly: using an LLM to certify an LLM is asking a probabilistic system to vouch for a probabilistic system. This post is what happens when you take that sentence seriously.

Most enterprise AI evaluation today rests on an LLM judge. The judge produces a score. The score goes on a dashboard. The dashboard becomes the evidence that the system was validated. And when a second line of defence reviewer eventually asks how you know the system works, that dashboard is the answer.

Now read what OSFI's [Guideline E-23](https://www.osfi-bsif.gc.ca/en/guidance/guidance-library/guideline-e-23-model-risk-management-2027-letter) expects, effective May 1, 2027. Functional separation between model developers, model owners, and independent reviewers. Independent assessment of whether a model is properly specified, working as intended, and fit for purpose. Documentation with enough detail to establish that validation was genuine rather than a self-attestation exercise.

If your validation evidence is a score produced by a model closely related to the model being validated, you haven't built independent review. You've built a self-attestation exercise with better graphics.

Anyone who has worked in access control already knows this pattern. **Separation of duties** governs it: you don't let the same principal both request and approve. The rule holds regardless of whether the principal is trustworthy, because the architecture has to demonstrate independence rather than assume it. Independence lives in the arrangement itself, whatever the intent behind it.

![Self-Review Architecture](/postimages/charts/your-judge-is-not-an-independent-reviewer-diagram-1.svg)

## Why a Related Judge Cannot Be Independent

The research here is specific, and it's stronger than most people writing about evals seem to realise.

[Panickssery, Bowman and Feng](https://arxiv.org/html/2404.13076v1) showed at NeurIPS 2024 that LLM evaluators recognise their own generations and score them higher than human annotators judge them to deserve. The important part is the causal link they establish: self-preference strength correlates linearly with self-recognition capability. The better a model is at knowing its own writing, the more it favours it. GPT-4 and Llama 2 both show non-trivial accuracy at distinguishing themselves from other LLMs and humans out of the box.

[Wataoka and colleagues](https://arxiv.org/abs/2410.21819) gave the cleaner mechanistic account. Judges favour low-perplexity text regardless of who wrote it, and a model's own output is by construction low-perplexity to that model. Call it **fluency preference** rather than vanity: it's a property of how the system computes, and no amount of prompt engineering touches it.

The obvious fix doesn't hold up either. The standard mitigation is to use a held-out judge, a different model from the generator. [Research on model similarity and AI oversight](https://arxiv.org/abs/2502.04313) tested this directly across a large set of judge and model pairs on MMLU-Pro, and found a significant positive correlation between judgment scores and model similarity for every judge tested. The authors make the implication explicit: excluding the judge model from the rankings doesn't circumvent the problem, because similarity is a continuous confounder rather than a binary one. [Spiliopoulou and colleagues](https://arxiv.org/abs/2508.06709) found the same thing at family level, with judges rating their own model family more favourably independent of underlying quality.

Human interviewers have a name for this. **Affinity bias.** You favour the candidate who thinks like you, and you experience it as merit.

The practical rule is sharper than "use a different model." Use a judge from a genuinely different lineage, and treat similarity as a variable to account for, not a box you ticked. Adding a second judge from a distant family and looking at where the two diverge is a cheap way to make the bias visible.

Two honest caveats, because this literature is young and moving.

First, not every case of a model preferring its own output is bias. Sometimes the stronger model is simply right. The harmful component is narrower: the failure to penalise its own errors. That's what the AWS modernization study measured, and that's the thing to test for.

Second, [a 2026 study of structured regulatory evaluation](https://arxiv.org/abs/2605.24737) found no self-preference at all across its judge panel, with every same-family score at or below the cross-family mean. The explanation deserves attention: their rubric was a set of binary sub-questions with explicit compliance criteria, which appears to suppress the fluency-preference mechanism because the judge is scoring compliance rather than style. That result needs replication before anyone leans on it, but it points somewhere useful. Rubrics built as **binary, criterion-by-criterion checks** are more defensible than a judge asked for a holistic score. Position bias findings have also weakened on current models compared to 2023. Bias results age. Re-test yours.

## The Statistic That Lies in Exactly Your Situation

I need to be honest before this section, because I am about to walk through statistics and I am not a statistician.

Statistics was never my subject. I did not enjoy it in school and I have spent most of my career comfortably downstream of it, building identity systems and platforms where I could reason about correctness without reasoning about distributions. I know people who are considerably smarter than I am in this space, and when one of them started pulling on how you actually calibrate a judge, my options were to nod along or to go learn it.

Amazon taught me to dive deep and to be curious, and those two habits don't let you nod along, so there went a weekend.

What follows is roughly the order I found it in.

**Start with the obvious approach.** You want to know whether your judge agrees with your humans, so you count how often they reached the same verdict. That number comes back high and it is almost worthless. If 95% of your outputs pass, a judge that says "pass" to everything agrees with your humans 95% of the time while understanding nothing.

**The obvious fix is to correct for luck.** That is what Cohen's kappa does. It subtracts the agreement you would expect from chance alone and reports what is left. Every practitioner guide will tell you to use it, then hand you [the Landis and Koch scale from 1977](https://doi.org/10.2307/2529310): above 0.61 substantial, above 0.81 almost perfect. That scale is empirical rather than mathematically derived, and Fleiss and Altman published competing scales with different cut points. Say which one you are using.

**This is where it cost me the weekend.** The correction over-corrects when one outcome dominates.

Cohen's kappa is unreliable as a standalone statistic precisely when one class is rare. [Feinstein and Cicchetti documented this in 1990](https://pubmed.ncbi.nlm.nih.gov/2348207/) as the **kappa paradox**: a high observed agreement can be driven down to a very low or even negative kappa by imbalance in the marginal totals. Byrt and colleagues extended the analysis in 1993. The consensus across that literature has held for thirty years.

Now look at your production evaluation data. What's your pass rate? For most deployed systems it's well above 90%. Failures are rare, which is the entire point of shipping the system.

You're sitting in the exact regime where kappa stops being informative, because expected chance agreement approaches one and the correction eats the signal. Two annotators can agree on 195 of 200 records and still produce a kappa that looks mediocre. The cause is skewed prevalence, not inconsistent reviewers.

Raw agreement inflates and kappa deflates on the same data, for the same underlying reason. If you report only one of them you'll draw a confident and wrong conclusion in either direction.

The fix isn't exotic. Report raw agreement, Cohen's kappa, **Gwet's AC1**, and the marginal prevalence together. AC1 was designed for the rare-class case. Prevalence-adjusted bias-adjusted kappa is another option. Then stratify your sample rather than drawing it randomly, because random sampling systematically underrepresents the tail you actually care about: the confidently wrong answers and the low-frequency edge cases.

None of that is advanced statistics. It is thirty-year-old methodology literature that the evaluation tooling market has largely not absorbed. I found it because someone more rigorous than me pushed me to go look.

![Agreement Metric Reliability by Pass Rate Regime](/postimages/charts/your-judge-is-not-an-independent-reviewer-diagram-2.svg)

## Ground Truth Is a Staffing Problem

This section exists because [Richard Song](https://www.linkedin.com/in/richardmcsong) asked me a question I could not answer cleanly. Not how to measure agreement, which is a solvable problem. How you would actually staff the humans behind it, at volume, without the whole thing quietly degrading.

That turned into a longer back and forth with [Navpreet Kaur](https://www.linkedin.com/in/navpreet-kaur-99848564) and [Karsten Economou](https://www.linkedin.com/in/karsteneconomou) about the three ways an organisation could source human judgment at scale, and the fact that all three are unsatisfying in different ways. I have not landed anywhere I am confident about. That debate matters more here than the answer does, because anyone thinking seriously about evaluation eventually arrives at the same fork.

This next part belongs in a budget conversation, not a data science one.

In the last post I priced verification in tokens and milliseconds. That was incomplete. The dominant cost of a trustworthy judge isn't the judge. It's the humans required to establish that the judge is trustworthy, and unlike the judge, that cost recurs.

The market rates as of mid-2026 are public and they're not small, though the figures below come from vendors selling annotation services rather than from peer-reviewed work, so treat them as directional. [Generalist annotators run roughly $15 to $35 an hour](https://labelstud.io/learningcenter/when-generalist-annotators-arent-enough/). At the top end, expert-tier contract work runs up to $130 to $300 an hour for [board-certified specialists in medicine and law](https://www.lxt.ai/blog/data-annotation-outsourcing/), because you're paying a physician to write a grounded clinical answer or a tax attorney to work a multi-jurisdiction edge case. [One reported figure puts roughly 600 high-quality RLHF annotations](https://labelyourdata.com/articles/how-to-evaluate-ai-trainers) at around $60,000, which was approximately 167 times the compute cost of the training run they supported.



Against inference spend, human ground truth is frequently the larger number, not a rounding error.

And it doesn't buy you certainty either. [Northcutt, Athalye and Mueller](https://arxiv.org/abs/2103.14749) found label errors averaging 3.4% across ten of the most heavily used benchmark datasets in machine learning, with about 6% of the ImageNet validation set mislabelled. Even MNIST, benchmarked in tens of thousands of papers, contains validated label errors. When they had crowdworkers check the algorithmically flagged candidates, only about half were confirmed as genuine errors, which tells you something about how much humans disagree even about what a mistake looks like.

One finding in that paper deserves attention. On corrected labels, ResNet-18 outperforms ResNet-50 once mislabelled prevalence rises by around six points. Lower capacity models can be more useful than higher capacity ones when the data is noisy. This mirrors a result I wrote about earlier in this series, where smaller models at temperature zero produced consistent outputs while a much larger model didn't. Different decade, different domain, same lesson. Bigger isn't the axis.

This market has a side nobody puts on a slide. Annotation vendors in 2026 have had to build controls against [annotators quietly outsourcing their labeling work to ChatGPT](https://www.lxt.ai/blog/data-annotation-outsourcing/). Think about what that does to the whole edifice. You hired humans to be the independent ground truth against which you calibrate a model, and some of them are running a model.

The operating model ends up mattering more than the metric. There are three sourcing patterns, and each fails differently.

| Option | Why it is tempting | How it fails |
| --- | --- | --- |
| Gamify it | Cheap, broad coverage, builds shared literacy across the org | Rubric applied inconsistently; incentives distort labels; agreement decays fast without adjudication |
| Build a centre of excellence | Consistent, measurable, accumulates institutional memory | Drifts away from the business; becomes a bottleneck; lacks the domain authority to adjudicate the hard cases |
| Go third party | Elastic capacity, real access to credentialed specialists | Expensive at expert tier, heavy context-transfer overhead, and you inherit their quality controls |

None of them is right alone. Tier them the way you tier verification. High-risk rubrics need genuine domain authority to author and adjudicate. Volume can be industrialised. Gamified review is a useful signal, not a ground truth. The third row is where the ChatGPT problem above bites hardest, because you are trusting someone else's controls on the exact input your calibration depends on.

Track three numbers together: accuracy against gold, inter-annotator agreement, and drift on rolling samples. A labeller can be 95% accurate against your gold set while disagreeing with the rest of the team on a large share of cases. That usually means your rubric has gaps, not that the labeller is bad.

Finally, treat the gold set as a perishable asset, a versioned artifact rather than a static file. It goes stale as your prompts, models and product surfaces change, and a stale gold set produces a confident green number about a system that no longer exists.

## The Failure Mode Behind the Failure Mode

There's one more result worth sitting with, because it undercuts the assumption that better judges would solve this.

[A 2026 study of production multi-turn transaction agents](https://arxiv.org/abs/2606.10315) examined why a capable LLM gate misses so many real defects. Perception wasn't the problem: the judge frequently saw the issue. The rubric simply had no axis to record it, so a guardrail or state-tracking violation got filed under something like brand voice in 113 of 114 cases. The shipping gate was wired only to hard assertions and hangs, leaving the rubric disconnected, so across 220 rounds that produced 125 raw notes, zero rounds failed the gate.

The judge produced 125 signals. The gate acted on none of them.

I've been making a version of this argument across this [entire series](https://khaledzaky.com/blog/evaluations-guardrails-and-governance-are-different-things/): a signal without a defined action is an alert rather than governance. That study is the empirical version of it. The vocabulary the judge was given, and the gate it was wired to, were the actual weak link, not the judge itself.

The authors' conclusion is the right one. Automated judging should be treated as a **regression floor** (cheap, always on, good at catching known defects recurring) rather than as the primary signal for whether the system is good. Research on [deterministic integrity gates](https://arxiv.org/html/2606.09500v3) in clinical manuscript preparation reinforces this: deterministic checks detected all 27 injected defects with zero false positives, while a generic single-prompt LLM reviewer caught only 11 of 27. The halt-on-failure requirement is the architectural expression of this point: if the signal can't halt the process, the check is decorative.

## What This Changes About the Ladder

In the budget post I argued you climb the substrate ladder because higher rungs buy assurance proportional to risk. This adds a second reason, and it's a financial one.

An LLM judge carries a permanent **calibration liability**. To trust it you need human labels, and to keep trusting it you need human labels again, quarterly, forever, with the gold set refreshed and the agreement statistics recomputed and the drift monitored. A deterministic rule doesn't need any of that. Neither does a formal policy check. Their trustworthiness has nothing to do with someone measuring their agreement with humans. It comes from the fact that they can't vary.

Climbing the ladder doesn't just buy you assurance. It retires a recurring human cost. For any check that's specifiable, that changes the payback maths considerably.

## What To Do

1. **Check the lineage of your judge against your generator.** If they share a family, your validation evidence has an independence problem before you look at a single score. Add a judge from a distant lineage and inspect where the two disagree.
2. **Test whether your judge penalises its own errors** rather than whether it agrees with humans on average. Average agreement is the wrong measurement; the AWS modernization study measured the right one.
3. **Report prevalence alongside agreement.** Raw agreement, kappa, Gwet's AC1, and the marginal distribution, together. One number alone will mislead you in a rare-failure regime.
4. **Write rubrics as binary criterion-level checks** rather than holistic scores. More defensible, easier to adjudicate, and there is early evidence it suppresses the fluency-preference mechanism.
5. **Put calibration in the budget as a recurring human line item**, with a named sourcing model per risk tier. If it is not budgeted it will not happen, and an uncalibrated judge is worse than no judge because it produces evidence.
6. **Wire the rubric to the gate.** If your judge can record a concern that cannot fail a release, you have built an alerting system and called it governance.

The models in that AWS study weren't broken. They did precisely what their architecture asked of them. That's the point this whole post has been building toward: independence is an architectural property, not a prompting outcome.