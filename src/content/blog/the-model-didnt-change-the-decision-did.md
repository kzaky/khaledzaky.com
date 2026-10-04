---
title: "The Model Didn't Change. The Decision Did."
date: 2026-10-04
author: "Khaled Zaky"
categories: ["ai"]
description: "How you formulate questions to AI decision models dramatically affects accuracy—sometimes by over 20 points—and the direction of change varies by model. Test your specific task's formulation."

---

Same model. Same 1,000 requests. Same 150 possible answers.

![Direct Formulation](/postimages/charts/the-model-didnt-change-the-decision-did-diagram-1.svg)

Asked to choose the answer directly, **Jev** got 91.0% right. Asked for broad-category probabilities and for probabilities inside every category, with the final answer rebuilt from those, it got 68.1% right.

![Jev and Laya accuracy by formulation on CLINC150 (direct, reconstructed, hard routing)](/postimages/charts/the-model-didnt-change-the-decision-did-chart-1.svg)
*Source: arxiv:2609.33971*

A second model, **Laya**, went the other way on the same restructuring: from 23.1% to 44.4%.

Neither model changed. The question did, and the effect flipped direction depending on which model was answering.

Those numbers come from a preprint published last week, [*Do System One Decisions Add Up?*](https://arxiv.org/abs/2609.33971). I found it the way I find most things lately: scrolling LinkedIn. Someone had posted a [DecideBench](https://choy.in/blog/open-source-jev-alternatives) leaderboard comparing Jev, open decision models, and general-purpose LLMs on accuracy, cost, and latency. I went down the rabbit hole to learn which model was winning. I came out with a different question.

In my last post, [Your LLM Judge Should Earn the First Call](https://khaledzaky.com/blog/your-llm-judge-should-earn-the-first-call/), I argued that an expensive general-purpose judge should beat cheaper options on the specific decision before it earns that position. I also suggested breaking broad judgments into narrower signals. This paper exposed a gap in that advice. Breaking a decision apart is itself a change to the decision, and it needs its own evidence.

A note before I go further. I'm not an ML researcher. I read these papers slowly, with a second tab open for terms. Both papers I lean on here came out in the last two weeks, each has a single author, and neither has been peer reviewed. I haven't reproduced them yet. This is what I learned, what still confuses me, and what I plan to test.

**TL;DR:** In a new preprint, changing how you ask a decision model a question moved its accuracy by more than 20 points with the model frozen, and the direction depended on the model. Test the formulation on your task. Where answers have a fixed relationship, derive it in code instead of asking the model twice. Treat changes to questions, routing, and thresholds as behavior changes whose existing evidence may no longer apply.

## What the Paper Tested

**Decision models** like Jev and Laya don't write free-form text. You give them an input, a question, and a fixed list of options, and they return a probability for each option.

The paper ran both models on three public intent datasets, with 2,500 matched examples per model and 72,000 classification questions in total. My example is [CLINC150](https://huggingface.co/datasets/Praveenrajus/jev-bench): 150 request types for a virtual assistant, grouped into 10 broader domains, with 1,000 test requests per model.

For each request, the author asked one direct question over all 150 labels, one over the 10 categories, and one over the labels inside *every* category. That supports three ways to reach a final answer:

| CLINC150, 1,000 requests | Jev | Laya |
|---|---|---|
| **Direct:** pick 1 of 150 | 91.0% | 23.1% |
| **Reconstructed:** weight each category's labels by that category's probability, across all categories | 68.1% | 44.4% |
| **Hard routing:** commit to the top category, then pick inside it | 64.6% | 33.9% |

*Hard-routing accuracy is my arithmetic from the paper's error counts (Jev: 317 wrong-category, 37 wrong-label-in-right-category; Laya: 596 and 65).*

The direction held across all three datasets: reconstruction lowered Jev's accuracy and raised Laya's every time. The author is careful about the boundary. The formulations change the instructions, the number and identity of choices, and their positions together. The experiment shows the workflows behave differently. It doesn't isolate one cause.

![Laya reconstruction accuracy gain across datasets (TREC, MASSIVE, CLINC150)](/postimages/charts/the-model-didnt-change-the-decision-did-chart-2.svg)
*Source: arxiv:2609.33971*

The hard-routing numbers are where it clicked for me. Once Jev picked the right category, it chose the right request type 94.6% of the time. Nearly all of its damage happened at the first step.

The analogy that helped me: a triage nurse sends you to the wrong floor. The specialist on that floor may be excellent. It doesn't matter, because the doctor you need is no longer an option.

## Why Laya Went the Other Way Is Still an Open Question

Two pieces of context on Laya matter.

First, the paper used Laya's English base checkpoint without task-specific fine-tuning. [Laya's model card](https://glama.ai/mcp/servers/Maxwell00000086/laya-agent-kit) details about its limits could not be verified against the confirmed source. Specific scores cited from the model card (including benchmark figures and the quoted description of Laya's intended use) remain unconfirmed pending verification of the source URL.

Second, the card documents trouble with large option sets. The English checkpoint's token defaults and the specific option-count task detail cited from the model card are unconfirmed pending verification of the source URL.

At first, that looked like the obvious explanation. Then I read the methodology more closely. The study raised Laya's token budgets from 512/192 to 1,088/960, checked every input against the expected complete token sequence, and rejected anything truncated. The easy explanation ("150 labels got squeezed") doesn't survive that.

The hierarchy didn't help Laya because it was good at the first step, either. Laya picked the wrong category on 596 of 1,000 requests.

There is still a pattern. Laya's reconstruction gain grows across the three datasets: +5.6 points on TREC, +9.2 on MASSIVE, and +21.3 on CLINC150. But those datasets differ in more than label count, so three points don't establish an option-count effect. This one went on my test list instead of giving me an answer.

## Why This Isn't Just a Refactor

Consider how this could show up in a normal codebase. A support router asks one question: *Which of these 40 request types matches this message?* Someone restructures it into two calls: *Which department owns this?* and then *Which request type inside that department?*

![Two-Call Restructuring vs Single-Call Decision](/postimages/charts/the-model-didnt-change-the-decision-did-diagram-2.svg)

The model version, the input, and the final taxonomy all stay the same. I can easily see that change reviewed as application logic. This paper makes me think that view is too narrow. The deployed behavior comes from the model plus the formulation around it, and a restructuring that helped Laya in these experiments hurt Jev.

The effect reaches probabilities, not just labels. A model is **calibrated** when, over many cases, its 80%-confident answers are right about 80% of the time. Accuracy asks whether the answer was right. Calibration asks whether the confidence tracks how often the model is right.

On MASSIVE, reconstruction raised Laya's accuracy by 9.2 points while its **calibration error** rose from 0.046 to 0.124. The answers improved while the confidence became less trustworthy. That matters when an application uses confidence to decide whether to act. A formulation change doesn't need to change the winning label to change behavior. Moving a score across an automation threshold is enough.

![Laya accuracy vs calibration error on MASSIVE under direct vs reconstructed formulation](/postimages/charts/the-model-didnt-change-the-decision-did-chart-3.svg)
*Source: arxiv:2609.33971*

## The Input Can Move It Too

The question is one input. The context around it is another.

A second preprint, [*JevOut*](https://arxiv.org/html/2609.30243), starts with decisions Jev gets right and picks a specific wrong target for each. It then searches for natural-looking context additions that push Jev toward that target while keeping the source, question, choices, and correct answer intact. The specific figures reported from this paper (including flip rates and probability figures) are unverified pending confirmation that the paper is accessible at the cited URL. Three other decision systems were also tested according to the preprint.

This is an optimized attack that uses the model's own probabilities as feedback. It's not the error rate for ordinary customer messages.

What I take from it is narrower. A customer writing "my manager already approved this" isn't the same as an approval record from the system of record. If an application flattens both into one block of prose, it throws away where the claim came from. That's a design choice the application makes before the model ever sees the input.

## Derive What Is Actually Deterministic

This is the part I had to think through twice.

Suppose every request type belongs to exactly one department. If I already have probabilities over the request types, I can calculate each department's probability by adding up its children. I don't need a second model call to estimate the same relationship.

| Request type | Department | Probability |
|---|---|---|
| A1 | A | 0.31 |
| A2 | A | 0.29 |
| B1 | B | 0.40 |

Department A totals 0.60 and B totals 0.40. But B1 is still the single most likely request type. "Pick the top department, then its top child" gives A1. "Pick the top request type" gives B1. Neither is inconsistent. They're different decision rules, and the application has to say which one it acts on.

The rule I'm taking away: *when two outputs have a fixed relationship under the taxonomy or policy, derive it in code instead of asking the model to estimate it twice. Test any genuinely different decision separately.*

Summing guarantees the numbers agree. It doesn't make them calibrated or correct. It also assumes categories don't overlap and cover the answer space. It doesn't tell me which decision rule is best, either. That still has to come from the task.

## The Boring Classifier Still Belongs in the Race

For a stable taxonomy with good labeled history, I still want a conventional **supervised classifier** in the comparison: an encoder (a model that turns text into numbers) feeding logistic regression (a model that maps those numbers to fixed categories).

It removes one source of flexibility. Nobody can reword its options in a pull request and silently create a new question, because its categories were learned in training. That doesn't freeze the whole decision, since preprocessing, thresholds, and action logic can still change. It does make one class of change explicit. I want it in the experiment to test whether the flexible question interface buys enough to justify the extra surface it adds.

## What Changed Should Decide What Gets Retested

The practical change I'm taking from all this: evidence should attach to the decision path that ships, from the raw input to the action, not to the model endpoint alone. Then each change can be checked against the part of the path it touches.

![Evidence Scope by Change Type](/postimages/charts/the-model-didnt-change-the-decision-did-diagram-3.svg)

| What changed | Examples | Evidence before shipping |
|---|---|---|
| Nothing used by the model or the action | Display text, log format | Software tests confirming model inputs and actions are unchanged |
| What reaches the model | Instructions, option wording or order, retrieved context, preprocessing, truncation, candidate filtering | Rerun affected behavioral tests and representative cases |
| How model outputs are interpreted | Probability math, thresholds, fixed mappings, action policy | Replay logged outputs where possible, then review changed actions and threshold crossings |
| What produces the outputs, or what they represent | Model or encoder swap, new labels, a materially different population or scope | Broader requalification against the acceptance criteria |

The third row has a cheap shortcut. If the model's inputs and outputs are unchanged and you logged everything the new logic needs (at minimum, the full probability distribution for every option, not just the top answer), you can replay a threshold or action-policy change without another model call. Replay tells you what the new logic would have done to past decisions. It doesn't validate changes that alter the model calls, and it doesn't prove tomorrow's traffic looks like yesterday's.

## What I'm Testing Next

I plan to start with CLINC150 because the data and taxonomy are public. [CheckList](https://aclanthology.org/2020.acl-main.442/) gave me language for the first two tests years before these decision APIs existed. Ribeiro and colleagues call them **Invariance** and **Directional Expectation** tests.

1. **Invariance.** Change something that shouldn't matter: reorder options, reformat the input, or add background reviewed as irrelevant. The decision should hold.
2. **Directional Expectation.** Change something that should move the decision in a known direction, such as a negation that reverses the request. CheckList defines this more broadly than "the label must flip": the output should move toward a target or satisfy a directional constraint.
3. **Composition.** Ask the direct question, reconstruct through every branch, try hard routing, and derive parent probabilities from the direct answer. Compare final actions and threshold crossings, not just accuracy.

For Laya, I'll vary the option budget instead of assuming it explains the result. The study already ran with a budget five times the default, which makes this a more interesting test than I first expected. I'll include a fixed-label supervised baseline too. If the result doesn't reproduce, that's useful. If the option budget changes Laya's direction, that's useful too.

## Back to the Chart

The chart I scrolled past showed Jev and other models compared on accuracy. Laya wasn't on it; a DecideBench result has been cited for Laya's score, but no verifiable source for that specific figure has been confirmed. That is an independent result, not Cloudflare's own claim.

I still care which bar is longest. I care more about what happens after I pick one. In the *Add Up* experiment, the same Jev model went from 91.0% to 68.1% on the same requests when only the question changed.

I haven't reproduced that yet. That's the experiment I want to run next.