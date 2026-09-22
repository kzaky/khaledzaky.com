---
title: "Your LLM Judge Should Earn the First Call"
date: 2026-09-22
author: "Khaled Zaky"
categories: ["ai", "security"]
description: "Jev changed how I think about the first evaluation call. Qualify each decision, start with the least expensive check that meets the bar, and escalate when needed."

---

> **TL;DR:** I thought Jev was hype, then my own untuned safety testing returned ROC AUC between 0.96 and 0.99. The [public phishing data](https://raw.githubusercontent.com/anisselbd/jev-phishing-bench/main/results/report.md) tells a different story, with Jev losing to Haiku on another task. The lesson is to qualify each decision, then start with the least expensive evaluator that clears the bar and escalate from there. That makes the [verification budget](https://khaledzaky.com/blog/verification-is-a-budget-not-a-default) something you allocate within a workflow, not just when you design it.

A hosting-list rule scores **91.6% accuracy** on a synthetic-email phishing benchmark. Jev’s broad verdict scores **62.6%**. Claude Haiku 4.5 scores **81.3%**. [Both models lose to the simpler check](https://raw.githubusercontent.com/anisselbd/jev-phishing-bench/main/results/report.md).

I am writing about a new model, and the baseline is already giving me homework.

One of the things I value most about working around smart, curious people is that they keep sending me things that force me to revisit assumptions I thought were settled.

[Karsten Economou](https://www.linkedin.com/in/karsteneconomou) sends me a link to Jev and says we should look at it.

[TypeSafe has just come out of stealth](https://typesafe.ai/blog/introducing-system-one-models-and-jev). Jev launched on September 15. I fill out the waitlist form.

On the drive home, I ask Grok to explain what I have just signed up for. How does a model that does not generate text differ from an LLM? Where would a typed decision help?

A generative model is explaining a non-generative one to me on the drive home. That is how this starts.

I get home with the start of a conclusion and no data behind it.

My assumption is that this is hype.

Then I run it against safety checks I already know well: prompt harm, response harm, and refusal detection. I score the results against human annotations. I use a one-shot prompt, with no tuning and no prompt experimentation. One-shot here means the model got a single example of the task and nothing else.

**ROC AUC lands between 0.96 and 0.99 across the three checks.**

In plain English, the model was very good at ranking harmful examples above safe ones. That still does not tell me where to put a blocking threshold in production.

The combined request returns in **roughly 340 milliseconds, plus or minus 100 milliseconds**. The checks cover both input and output and are answered in parallel in one request.

Adding another safety check adds input tokens. [TypeSafe’s published pricing leaves output unbilled](https://typesafe.ai/blog/introducing-system-one-models-and-jev). For the checks I am adding, the marginal inference cost is **near zero**.

These are my own measurements of one configuration, not a benchmark. The ROC AUC results describe ranking performance, not a qualified blocking threshold.

On my checks, there is something real behind the hype. In the public phishing benchmark, Jev’s broad verdict loses to Haiku. Both are true.

The question I bring into the weekend is whether the heavy LLM judge still needs to be the default.

In [Your Judge Is Not an Independent Reviewer](https://khaledzaky.com/blog/your-judge-is-not-an-independent-reviewer/), I had to slow down and learn what the statistics actually established before carrying the argument further.

This time, I have encouraging results of my own and public results pointing the other way. Qualifying the decision, rather than approving the model in the abstract, is what makes sense of both.

## The Week Moved Faster Than My Draft

That happens again later in the week.

[Gaurav](https://www.linkedin.com/in/gauravh-j/) points me to [jevals](https://github.com/openlayer-ai/jevals), an evaluation library built around the same typed-decision interface.

We have a habit of arriving at similar questions from different directions. This time, there is already a repository implementing parts of the answer.

Look at the sequence.

**September 15:** [TypeSafe exits stealth and launches Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev).

**September 17:** [LangChain publishes a Jev harness](https://www.langchain.com/blog/building-a-harness-with-jev), including middleware that can block proposed tool calls.

**September 17:** [Kev’s repository appears](https://github.com/jaredpalmer/kev) with a compatible decision interface.

**September 19:** [Vercel publishes its Jev and AI SDK guide](https://vercel.com/kb/guide/typesafe-jev-and-ai-sdk).

**September 19:** [Laya gets a local MLX runtime](https://github.com/mizorewww/laya-mlx) for its typed-decision models.

**September 20:** [LangChain publishes its Jev-as-an-evaluator experiment](https://www.langchain.com/blog/jev-agent-evals-langsmith).

**September 20:** [jevals publishes its first version](https://github.com/openlayer-ai/jevals/commit/bce3988df1657b0ac296c76f7884f83721963090), combining evaluation definitions with runtime gates.

By this point, it is a Jev maxxing weekend.

I expect more Jev conversations in the coming weeks. But the part I am watching is not just Jev. Independent projects are adopting a similar request shape, and an evaluation library is building around it. That looks like a category forming.

jevals also arrives at arguments I recognize.

Its README says [“the gate in production enforces exactly what you measured offline”](https://github.com/openlayer-ai/jevals). That is the implementation direction I wanted in [June’s distinction between evaluations and guardrails](https://khaledzaky.com/blog/evaluations-guardrails-and-governance-are-different-things): reuse the judgment, while making its different roles explicit.

It also says [“don't let the classifier become the authorizer”](https://github.com/openlayer-ai/jevals). That connects directly to the [decision-engine argument](https://khaledzaky.com/blog/everyone-is-building-evaluators-almost-nobody-is-building-decision-engines).

The authors explicitly retain [LLM judges for evaluations requiring substantial reasoning or written critique](https://github.com/openlayer-ai/jevals#what-this-isnt).

[Openlayer sells evaluation tooling](https://www.openlayer.com/), so a vendor building in this direction is both a meaningful product signal and a commercial interest.

jevals is still [alpha, with a short initial commit history](https://github.com/openlayer-ai/jevals/commits/main/). It has already given me a concrete design to inspect.

## Did Jev Already Lose to Open Weights?

I also try Laya and find it weak out of the box. Its authors report **0.362 zero-shot accuracy against a random baseline of 0.318** on typed-decisions, and [describe the base as something to specialize](https://huggingface.co/convaiinnovations/laya#honest-limits). That fine-tunability is the part that interests me. Their [specialist checkpoint reports 0.766 accuracy against a published Jev result of 0.727](https://huggingface.co/convaiinnovations/laya-typed-decisions) on four synthetic workflows it was fine-tuned for. Those are author-reported results, unreproduced here. The authors did not run Jev themselves, and the prompts and sample sizes differ. The specialist’s calibration error is also higher: **0.213 against Jev’s quoted 0.144**. On [Kev’s new-source development suite](https://github.com/jaredpalmer/kev#models), the authors report **0.790 for the earlier Qwen3 Kev-4B and 0.796 for Kev-8B, against Jev’s 0.857**. Those sources were unseen by Kev; Jev’s training exposure is unknown. My read of these comparisons is that Jev has the stronger case for zero-shot generality, while open weights offer a path to a task-specific lead after fine-tuning.

Zero-shot means using the model as it ships, without training it on examples from your own task. Fine-tuning means adapting it using examples from your own data. On calibration error, lower is better.

The interface itself is already portable. [Kev serves a TypeSafe-compatible endpoint](https://huggingface.co/jaredpalmer/kev-4b), so the same client can point at a local server without rewriting the questions. The [openJev-verdict-2.0 author reports fine-tuning an approximately 150M-parameter model in 8.8 hours on a consumer laptop GPU](https://github.com/Heman10x-NGU/openJev-verdict-2.0). That is self-reported, but it makes the specialization question concrete. And the safety tasks themselves are not new: [WildGuard, an open 7B model published in 2024](https://arxiv.org/abs/2406.18495), already covers prompt harm, response harm, and refusal detection. I would not look to the request format for a moat now that independent implementations have copied it within the launch week. This deserves its own post, and I will come back to it.

## What I Am Actually Excited About

[Jev accepts state and bounded questions, then returns typed answers with probabilities](https://docs.typesafe.ai/concepts/system-one).

The application defines the answer space before making the request.

A bounded semantic question is one where I fix the possible answers in advance, so the model picks among them instead of writing prose.

![A typed decision interface: application state feeds a bounded semantic question, which returns probabilities over defined answers, which feed application policy](/postimages/charts/your-llm-judge-should-earn-the-first-call-diagram-2.svg)

That is useful when your application needs a judgment it can consume directly.

The schema guarantees the answer’s form, not its correctness. But it gives me another implementation to test before asking a general-purpose model to produce a full assessment.

In [Verification Is a Budget, Not a Default](https://khaledzaky.com/blog/verification-is-a-budget-not-a-default), I argued for choosing the verification approach that meets the required bar rather than automatically buying another large-model call.

Jev makes that question concrete.

## There Are Two Costs Here

### The Dollars

[TypeSafe lists $0.042 per million input tokens, with no output charge](https://typesafe.ai/blog/introducing-system-one-models-and-jev). That is vendor-reported and unreproduced here.

A community phishing benchmark provides a comparison using recorded token usage and list prices:

![Estimated cost per 1,000 emails: Jev $0.0384, Claude Haiku 4.5 $0.4622](/postimages/charts/your-llm-judge-should-earn-the-first-call-chart-2.svg)

*Source: [Jev phishing benchmark](https://raw.githubusercontent.com/anisselbd/jev-phishing-bench/main/results/report.md). Community-reported usage priced at list rates. Haiku is claude-haiku-4-5. Jev’s request included multiple questions; Haiku’s original request asked for the broad verdict.*

That is substantially less money spent on the first check.

The budget can reach more cases, or support more checks on each case. It can also leave more room for expensive review where the first check needs help.

### The Waiting

The same benchmark reports a separate advantage in elapsed time:

![End-to-end latency: at p50 Jev 239 ms and Claude Haiku 4.5 687 ms; at p95 Jev 331 ms and Claude Haiku 4.5 980 ms](/postimages/charts/your-llm-judge-should-earn-the-first-call-chart-3.svg)

*Source: [Jev phishing benchmark](https://raw.githubusercontent.com/anisselbd/jev-phishing-bench/main/results/report.md). Author-reported measurements from one machine in France, using sequential calls over a reused connection. These include network time.*

p50 is the typical call. p95 shows the slow end that users will still experience regularly.

This matters independently of the token bill.

If a check fits your latency budget before an action executes, you can use it to affect that action. A check applied only to sampled, completed traces cannot prevent those completed actions.

Openlayer’s jevals README adds a measured workflow comparison:

| Evaluation implementation | Cost per 1,000 samples | Wall time for the 20-sample run |
|---|---:|---:|
| Ragas with gpt-4.1-mini | $2.60 | 22 to 35 seconds |
| jevals with gpt-4.1-mini emulating the decision interface | $0.46 | 4 seconds |
| jevals with Jev | $0.03 | 0.8 seconds |

*Source: [jevals README, Numbers](https://github.com/openlayer-ai/jevals#numbers). Vendor-run and unreproduced. Measured on September 20, 2026, using 20 rows from a small RAG dataset shipped with the package, by a company that sells evaluation tooling. Costs use list pricing.*

The README reports agreement on the verdicts across the measured implementations. Even keeping gpt-4.1-mini, changing the evaluation implementation reduced the reported cost and runtime. Jev reduced them further.

That is a reason to inspect how we build the evaluation, as well as which model answers it.

It also connects to [September’s coverage argument](https://khaledzaky.com/blog/your-agent-control-plane-has-a-coverage-problem). Lower cost can make inspecting more activity practical. Lower latency can put more of that inspection before execution.

Two honest caveats before I turn those wins into an architecture.

First, these are narrow comparisons: synthetic emails and a vendor’s own 20-row RAG sample measured on one day. RAG means the system retrieves documents before answering, so that sample tests a different job than phishing. The jevals comparison changes the evaluation implementation, and its [README records a completion-count mismatch in Ragas’ answer-relevancy call](https://github.com/openlayer-ai/jevals#numbers). Treat it as a comparison of the tested implementations, rather than an isolated measure of model superiority.

Second, the budget belongs to the complete path. Deferred cases still need processing. Errors still need correcting. Measure those costs alongside the first-call wins.

## Then I Read the Accuracy Results

Here is where the replacement story breaks.

On the same synthetic-email benchmark, **Jev’s broad verdict achieved 62.6% accuracy against Haiku’s 81.3%**. Jev’s expected calibration error was **0.154 against Haiku’s 0.097**, where lower is better. [Haiku was both more accurate and better calibrated on this task](https://raw.githubusercontent.com/anisselbd/jev-phishing-bench/main/results/report.md).

Calibration asks whether the confidence number deserves to be believed. A model that says it is 90% confident should be right roughly nine times out of ten on cases like that.

![Phishing detection accuracy by method. Full-set broad verdicts: Jev 62.6%, Claude Haiku 4.5 81.3%, hosting-list rule 91.6%. Held-out fitted-classifier results: Jev five signals 95.0%, Haiku five signals 93.2%, two non-AI heuristic features 91.8%](/postimages/charts/your-llm-judge-should-earn-the-first-call-chart-1.svg)
*Source: [Jev phishing benchmark](https://raw.githubusercontent.com/anisselbd/jev-phishing-bench/main/results/report.md). The first three bars are broad-verdict accuracy on the full dataset. The last three are held-out results from the separately fitted classifier experiment, which is not the same evaluation setup.*

I cannot use that benchmark to celebrate the cost and latency, then omit what it says about the decision.

Selecting only higher-confidence predictions did not automatically rescue Jev.

The idea is to let the model handle only the cases it is most sure about, and send everything else to review.

At a predicted-class probability threshold of **0.90**, Jev retained **30.8% of cases at 73.9% accuracy**. Haiku retained **55.4% at 82.5% accuracy**. Haiku handled more cases and made proportionally fewer errors within its retained subset. [Jev’s confidence bins were also non-monotonic](https://raw.githubusercontent.com/anisselbd/jev-phishing-bench/main/results/report.md).

Non-monotonic means more confidence did not reliably mean more accuracy, so the number could not be trusted to sort the easy cases from the hard ones.

Those thresholds use the probability assigned to the predicted class, not Jev’s separate `confidence` field.

Three separate things are in play. There is the model’s confidence score, there is the chance the answer is actually right, and there is the threshold your application chooses. A high confidence number is not permission to act.

The more interesting result comes from changing the check.

The hosting-list rule from the opening achieved **91.6% accuracy**, beating both Jev’s **62.6%** and Haiku’s **81.3%** broad verdicts. [The rule required no model and no fitting to labels](https://raw.githubusercontent.com/anisselbd/jev-phishing-bench/main/results/report.md).

I had already written that we should look for checks that beat an LLM judge. Here was a source giving me a reason to follow my own advice.

The author then asked five narrow signal questions and combined the answers with logistic regression, fitting on one half of the dataset and evaluating on the other.

Think of the logistic layer as a small statistical combiner that learns how much weight to give each signal. Held-out means the second half was not used to fit that combiner, so it is the closer test of whether the pattern survives beyond the examples used to build it.

A false positive here means a legitimate email gets flagged as phishing.

| Inputs to the classifier | Held-out accuracy | False-positive rate |
|---|---:|---:|
| Jev’s five atomic signal probabilities | 95.0% | 7.0% |
| Haiku’s answers to the same five questions | 93.2% | 5.4% |
| Two non-AI heuristic features | 91.8% | 0.2% |

*Source: [Phishing benchmark, Control 2](https://raw.githubusercontent.com/anisselbd/jev-phishing-bench/main/results/report.md). Classifiers fitted on half A and evaluated on half B. The Jev-versus-Haiku paired comparison returned p = 0.0630, not significant at the conventional 0.05 threshold.*

That last number matters. The measured difference was not strong enough to confidently call one approach better in that experiment.

The broad-verdict results describe the full dataset. The fitted-classifier results describe its held-out half. This is not a matched claim that decomposition alone caused an improvement from 62.6% to 95.0%. The author also [designed the features with knowledge of the synthetic dataset’s URL patterns](https://raw.githubusercontent.com/anisselbd/jev-phishing-bench/main/results/report.md).

There is a useful design to investigate:

![Two paths worth investigating: one broad model verdict compared against a simpler baseline; and several narrow semantic judgments feeding a separately fitted and evaluated classifier, then application policy](/postimages/charts/your-llm-judge-should-earn-the-first-call-diagram-3.svg)

The logistic layer is another predictive model. Writing it in Python does not turn it into an authorization rule.

What changes my thinking is that the right question may be less “Which judge should replace this judge?” and more “Why did I ask one broad question in the first place?”

## Start With the Cheapest Check That Clears the Bar

**Selective automation asks:** Which cases can clear this check without another round of verification?

Start with the least expensive approach that demonstrates acceptable performance for the decision. Escalate the cases outside its qualified scope. Qualified scope means the cases you have actually shown it handles well enough, not the cases you hope it handles.

![Selective automation as an escalating verification ladder: a request passes mandatory deterministic controls, where a violation blocks; then the lowest-cost qualified semantic check, where sufficient evidence applies policy and an unresolved case escalates to an LLM judge, which either applies policy or sends the case to human review](/postimages/charts/your-llm-judge-should-earn-the-first-call-diagram-1.svg)

*Illustrative design. Required approvals remain required on every path.*

For a check that needs substantial reasoning, the LLM judge may remain the first qualified option. Do not insert a cheaper model merely to say you used one.

But for a bounded check, the large judge should earn its position rather than inherit it.

This makes July’s verification ladder operational at the level of individual requests. Two cases in the same workflow can need different amounts of additional verification.

Take a refund request. One customer clearly identifies an order. Another gives conflicting instructions about several purchases. You might qualify a simpler interpretation check for the first subset while retaining additional review for the second.

Both paths retain eligibility checks and authorization.

A useful confidence ranking can support this selection without every numerical value being a literal probability of correctness. [Selective classification already studies that trade-off](https://papers.nips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html). That is the practice of letting a model answer only the cases it handles well and routing the rest somewhere else. What matters operationally is the measured error among the cases your rule accepts, alongside how much work it accepts.

Calibrating down means reducing the cost of meeting the bar. It does not mean lowering the bar.

## This Is Bigger Than Evals

The interface becomes relevant wherever a system needs to interpret uncertain information before applying a rule.

For customer-facing conversational systems, I would put input and output safety checks in the baseline design. Internal question-answering tools deserve the same attention to harmful responses and inappropriate refusals.

For fraud detection, I would investigate narrow semantic signals. Does a customer’s message describe pressure to transfer money? Does a payment-change request conflict with earlier instructions?

Those are hypotheses to evaluate alongside transaction evidence. Payment authorization remains a separate decision.

The same pattern could support document triage or route a disputed-payment request to the right process. An entitlement pre-check might identify which permission needs checking. The authoritative entitlement lookup must still decide whether access exists.

These are proposed industry applications.

As I wrote in the [September post](https://khaledzaky.com/blog/your-agent-control-plane-has-a-coverage-problem): **“Don’t turn a known transaction limit into an LLM prompt.”**

Keep the known limit in code. Test the model on the interpretation that code cannot supply.

The local implementations widen that investigation. [jevals supports Kev and Laya backends](https://github.com/openlayer-ai/jevals), allowing evaluation definitions to run against local models rather than only a hosted Jev API.

For regulated industries, that creates a different self-hosting and data-residency option to assess. Qualify the local model’s behavior and the surrounding controls separately.

A shared request format makes implementations easier to exchange. Each backend still needs its own threshold validation. The [jevals documentation explicitly calls for recalibration when changing backends](https://github.com/openlayer-ai/jevals).

## What the Confidence Number Does Not Tell You

This is the part I do not want to hide beneath the enthusiasm.

[PrimeLine reports calibration errors of 0.012 for Noul, 0.086 for Choice, and 0.254 for Score](https://primeline.cc/blog/typesafe-jev-pre-registered-test). The populations and confidence constructions differ. Its separate applied-task corpora came from one developer’s project; 56.5% of the 4,000-commit source history carried a Claude co-author trailer. The site discloses AI-assisted writing. That contamination caveat concerns the applied corpora, not the public calibration datasets.

Haiku beat Jev on one applied job in the same report.

The useful repair was narrower: one yes/no question before a broad classification recovered **23 of 53 known failures, or 43.4%**. No new errors appeared on a length-matched control, which was not matched on category or confusability. [That is a targeted failure repair](https://primeline.cc/blog/typesafe-jev-pre-registered-test).

Then there is the arithmetic behind `confidence`.

[Stanislav Yurin’s analysis](https://bernoulli.app/confidence.html) gives Choice confidence as:

```text
C = (N * p_max - 1) / (N - 1)

N     = number of answer options
p_max = probability of the leading answer
```

At a fixed top probability of **0.60**, confidence is **0.200 with two options** and **0.579 with twenty**. The answer schema changed while the top probability stayed fixed.

**Option-count qualification rule:** A threshold belongs to the exact question and answer schema. Changing the option count requires revalidation.

For Score, Yurin explains a different calculation based on distance from the most probable rubric level. His [September 20 update links TypeSafe’s published implementation confirming both formulas](https://bernoulli.app/confidence.html). Keep their meanings separate when setting thresholds.

Repeatability is where Jev earns some of my excitement.

[LangChain’s vendor-reported, unreproduced experiment](https://www.langchain.com/blog/jev-agent-evals-langsmith) found Jev’s mean per-case quality-score variance **92 to 913 times lower** than three LLM judges. That was **five fixed cases, each scored 100 times**. Lower variance means that when you send the same case again, the score moves less.

Alongside that, [Yurin reports](https://bernoulli.app/confidence.html) ten identical calls moving confidence between **0.84 and 0.88** on an ambiguous item. On a closer case, the selected label changed.

Both findings can be true. Repeated scoring can be substantially more stable while genuinely close calls still flip. Your threshold determines whether the remaining variation changes the action your system takes.

Prompt injection belongs in the test set too. That is when the content being reviewed carries text designed to hijack the instructions the model is following. [PrimeLine’s 40 matched pairs](https://primeline.cc/blog/typesafe-jev-pre-registered-test) produced **22.5% misclassification on injected versions**, with mean absolute score movement of **0.193**. One innocent message moved from **0.04 to 0.66** on suspiciousness after injection: a false alarm, not an action bypass. [TypeSafe documents the adversarial-input risk](https://docs.typesafe.ai/model-jaggedness/jev-1.13#adversarial-content).

## The Default That Becomes Your Policy

**Qualification asks:** What evidence supports this exact check controlling this exact action?

The unit is not “Jev approved.” It is the model version together with the question, the supplied state, and the selection rule. The permitted action and failure behavior belong in the same record.

In the [September framework](https://khaledzaky.com/blog/your-agent-control-plane-has-a-coverage-problem), I already required **“defined behaviour when the evaluator is unavailable.”**

jevals provides a concrete reason to care.

During Openlayer’s vendor-run, unreproduced testing, the gateway hung on some connections. The client retried with backoff, waiting longer between each attempt, and **p95 latency for that run reached one minute**. [The README records the slow path during its September 20 testing](https://github.com/openlayer-ai/jevals#numbers).

Its [documented gate behavior](https://github.com/openlayer-ai/jevals#guardrails) retries backend failures, then lets the call through by default if the backend remains unavailable. The README explicitly recommends `on_error="block"` for gates in front of anything irreversible.

That default is fail-open. Fail-open means the protected action proceeds when the evaluator is unavailable. Fail-closed means the action is blocked instead.

![When the evaluator is unavailable after retries: the default allows the call, while on_error="block" blocks it](/postimages/charts/your-llm-judge-should-earn-the-first-call-diagram-4.svg)

*Source: [jevals gate documentation](https://github.com/openlayer-ai/jevals#guardrails).*

I can understand an availability-friendly default in a development library.

But the recommendation is block, and the default is allow. Following the recommendation requires configuration. Put that gate in front of a tool that moves money, and the configuration becomes a governance decision.

Blocking also needs a recovery path and a defined way to handle unresolved work.

This is why I would put qualification alongside coverage, binding, and closure:

![Four questions a control must answer. Coverage: have you found the action paths? Binding: does the control apply on those paths? Closure: did the required action take effect? Qualification: was the judgment fit for that action?](/postimages/charts/your-llm-judge-should-earn-the-first-call-diagram-5.svg)

Qualification applies across the control, rather than adding another sequential runtime step.

Your platform can enforce the wrong judgment exactly as configured. Lower inference cost increases the importance of qualifying the judgment before expanding its reach.

The [June distinction](https://khaledzaky.com/blog/everyone-is-building-evaluators-almost-nobody-is-building-decision-engines) remains: **a score is not a decision**.

The jevals README includes a concrete example. A **$49 refund that the customer explicitly requested still escalates**, on the `destructive` signal alone. The example’s policy sends money-moving actions to a human regardless of grounding. [That is Openlayer’s reported gate behavior](https://github.com/openlayer-ai/jevals#guardrails), not an independently reproduced control test.

More confidence about the customer’s request would not remove the approval requirement. The judgment answers one question. The policy governs what can happen next.

Cheap typed judgment makes it more practical to place scores throughout an application. That raises the stakes on the decision layer.

## What To Do

1. **Pick one bounded check and define the acceptance criteria first.** Specify the errors you cannot tolerate and the cases outside scope. Keep mandatory approvals separate from any optional interpretation review.

2. **Benchmark against code and the existing judge.** Include the simplest credible baseline. Run Jev in shadow mode without changing outcomes. Compare the work each approach can handle at the same error requirement.

3. **Select on development data, then freeze the configuration.** Test the frozen question, schema, and threshold on held-out cases. Report error within the automatically handled subset and the amount of work retained. Do not use the same cases to keep adjusting the threshold and declare success.

4. **Measure the complete execution path.** Account for deferred cases and retries. Test the fallback on the cases it actually receives. Measure dollars separately from latency, including the slow end of the distribution.

5. **Test the ways the gate can fail.** Include prompt injection and repeated calls near the threshold. Make backend-outage behavior explicit. Requalify when changing the model or answer options.

6. **Keep checking the cases that pass automatically.** Do not review only escalations. Preserve a route back to the previous review process, and identify who can authorize a threshold change. Expand automation only after the accepted cases continue to meet the criteria you set.