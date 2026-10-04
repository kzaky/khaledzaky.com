---
title: "The Model Didn't Change. The Decision Did."
date: 2026-10-04
author: "Khaled Zaky"
categories: ["ai"]
description: "Changing how you ask a decision model a question moved its accuracy by more than 20 points in a new preprint, and the direction depended on the model. Notes on what that means for testing production decision systems."

---

> **TL;DR:** Same model doesn't mean same decision. In a new preprint, changing only how a question was asked moved a model's accuracy by more than 20 points, up for one model and down for another. Change how you ask or assemble the question, and your old evals may no longer apply.

The same model answered the same 1,000 requests, each with the same 150 possible answers.

![Direct Formulation](/postimages/charts/the-model-didnt-change-the-decision-did-diagram-1.svg)

Asked to choose the answer directly, **Jev** got 91.0% right. Asked the same thing in two steps (how likely each broad category is, then how likely each answer is inside it, combined into one result), it got 68.1% right.

![Jev and Laya accuracy on CLINC150, asked directly vs in two steps](/postimages/charts/the-model-didnt-change-the-decision-did-chart-1.svg)
*Source: arxiv:2609.33971*

A second model, **Laya**, went the other way on the same restructuring: from 23.1% to 44.4%.

Neither model was retrained or swapped. Only the way the question was asked changed, and the effect flipped direction depending on which model was answering.

Those numbers come from a preprint published last week, [*Do System One Decisions Add Up?*](https://arxiv.org/abs/2609.33971). I found it the way I find most things lately, by scrolling LinkedIn. Someone had posted a [DecideBench](https://github.com/choyiny/decidebench) leaderboard comparing Jev, Cloudflare's new Clef models, open decision models, and general-purpose LLMs on accuracy, cost, and latency. I went down the rabbit hole to learn which model was winning and ended up with a different question.

In my last post, [Your LLM Judge Should Earn the First Call](https://khaledzaky.com/blog/your-llm-judge-should-earn-the-first-call/), I argued that an expensive general-purpose judge should beat cheaper options on the specific decision before it earns that position. I also suggested breaking broad judgments into narrower signals. This paper exposed a gap in that advice. Breaking a decision apart is itself a change to the decision, and it needs its own evidence.

A note before I go further. I'm not an ML researcher, and I'm not a data scientist. I read these papers slowly, with a second tab open for terms. To get up to speed, I had two AI models critique each other's reading of them, then opened every source myself to check who was right. Both papers came out in the last two weeks, each has a single author, and neither has been peer reviewed. I haven't reproduced them yet. This is what I learned, what I got wrong along the way, and what I plan to test.

## What the Paper Tested

Decision models like Jev and Laya don't write free-form text. You give them a message, a question, and a fixed list of answers, and they return how likely each answer is.

The paper tested both models on three public datasets of short requests, like the ones people type into a virtual assistant. My example is [CLINC150](https://github.com/clinc/oos-eval): 150 request types grouped into 10 broader categories.

| CLINC150, 1,000 requests | Jev | Laya |
|---|---|---|
| **Asked directly:** pick 1 of 150 | 91.0% | 23.1% |
| **Asked in two steps:** category, then answer, combined | 68.1% | 44.4% |

The same pattern held on all three datasets. The author is careful to say the study shows the two approaches behave differently, without pinning down a single cause.

The paper also tested the version most apps would actually build: commit to one category, then pick an answer inside it. That's where it clicked for me. When Jev picked the right category, it got the final answer right 94.6% of the time. But it picked the wrong category on 317 of the 1,000 requests, and once that happened, the right answer was gone.

The analogy that helped me is a triage nurse who sends you to the wrong floor. The specialist on that floor may be excellent. It doesn't matter, because the doctor you need is no longer an option.

## Why Laya Went the Other Way Is Still an Open Question

I got Laya wrong twice while writing this.

When I first saw the DecideBench chart, Laya wasn't on it, and I assumed it hadn't been tested. It had. It was in the full results, just not in the graphic.

Then I found a tidy explanation. [Laya's model card](https://huggingface.co/convaiinnovations/laya) says it struggles when a question has many options, and suggests splitting big option sets into a two-step hierarchy, which is exactly what helped it here. I thought I had my answer. Then I read how the study was run. Its code checks every input and rejects any that get cut off, so "too many options got squeezed" doesn't explain it.

Two things I'm confident about. The paper used Laya's base version without any tuning, and the card itself calls Laya "a fast base to specialise, not a zero-shot decision engine." So these results say more about an untuned model than about Laya at its best. Beyond that, I don't know why it went the other way. It's on my test list.

## Why This Isn't Just a Refactor

Consider how this could show up in a normal codebase. A support router asks one question: *Which of these 40 request types matches this message?* Someone restructures it into two calls: *Which department owns this?* and then *Which request type inside that department?*

![Two-Call Restructuring vs Single-Call Decision](/postimages/charts/the-model-didnt-change-the-decision-did-diagram-2.svg)

The model version, the input, and the final taxonomy all stay the same. I can easily see that change reviewed as application logic. This paper makes me think that view is too narrow. The deployed behavior comes from the model plus the formulation around it, and a restructuring that helped Laya in these experiments hurt Jev.

It can also change confidence. On one dataset, the two-step version made Laya more accurate but made its stated confidence match reality less well. That matters if your application uses confidence to decide whether to act on its own. A change can move a score across an automation threshold without changing a single answer.

## The Input Can Move It Too

Besides the question, the context around it can also move a decision.

A second preprint, [*JevOut*](https://arxiv.org/abs/2609.30243), starts with decisions Jev gets right and picks a specific wrong target for each. It then searches for natural-looking context additions that push Jev toward that target while keeping the source, question, choices, and correct answer intact. Within 64 attempts per decision, it flipped 312 of 508 correct decisions (61.4%). In 229 of those, Jev put at least 70% probability on the wrong answer. Three other decision systems flipped at rates of 64.9% to 73.2%.

This is an optimized attack that uses the model's own probabilities as feedback. It's not the error rate for ordinary customer messages.

What I take from it is narrower. A customer writing "my manager already approved this" isn't the same as an approval record from the system of record. If an application flattens both into one block of prose, it throws away where the claim came from. That's a design choice the application makes before the model ever sees the input.

## Derive What Is Actually Deterministic

I had to think this one through twice.

Suppose every request type belongs to exactly one department. If I already have probabilities over the request types, I can calculate each department's probability by adding up its children. I don't need a second model call to estimate the same relationship.

| Request type | Department | Probability |
|---|---|---|
| A1 | A | 0.31 |
| A2 | A | 0.29 |
| B1 | B | 0.40 |

Department A totals 0.60 and B totals 0.40. But B1 is still the single most likely request type. "Pick the top department, then its top child" gives A1. "Pick the top request type" gives B1. Neither is inconsistent. They're different decision rules, and the application has to say which one it acts on.

The rule I'm taking away is that *when two outputs have a fixed relationship under the taxonomy or policy, I derive it in code instead of asking the model to estimate it twice, and I test any genuinely different decision separately.*

Summing guarantees the numbers agree. It doesn't make them calibrated or correct. It also assumes categories don't overlap and cover the answer space. It doesn't tell me which decision rule is best, either. That still has to come from the task.

## The Boring Classifier Still Belongs in the Race

For a stable taxonomy with good labeled history, I still want a conventional **supervised classifier** in the comparison: an encoder (a model that turns text into numbers) feeding logistic regression (a model that maps those numbers to fixed categories).

It removes one source of flexibility. Nobody can reword its options in a pull request and silently create a new question, because its categories were learned in training. That doesn't freeze the whole decision, since preprocessing, thresholds, and action logic can still change. It does make one class of change explicit. I want it in the experiment to test whether the flexible question interface buys enough to justify the extra surface it adds.

## My Own Pipeline Did This to This Post

I draft with AI help, and I publish through a small agent I built that checks every citation before a post goes live. On this post, it decided two of the preprints couldn't exist, because their IDs looked wrong to it. Then its auto-repair step swapped several of my working links for "similar" pages. Laya's model card became a page for an unrelated tool. Then the fact-checker looked for Laya's benchmark numbers on that wrong page, didn't find them, and stripped the claims from my draft.

The models in that pipeline stayed the same. A repair step caused the damage, and each step's output became the next step's input. I caught it only because I read the final draft against my sources.

## What Changed Should Decide What Gets Retested

This connects directly to my day job. Much of my time goes into deciding what evidence should exist before an AI system is allowed to act. This paper, and my own pipeline, sharpened my answer. Evidence should attach to the whole decision path that ships, from the raw input to the action. Then each change can be checked against the part of the path it touches.

![Evidence Scope by Change Type](/postimages/charts/the-model-didnt-change-the-decision-did-diagram-3.svg)

| What changed | Examples | Evidence before shipping |
|---|---|---|
| Nothing used by the model or the action | Display text, log format | Software tests confirming model inputs and actions are unchanged |
| What reaches the model | Instructions, option wording or order, retrieved context, preprocessing, truncation, candidate filtering | Rerun affected behavioral tests and representative cases |
| How model outputs are interpreted | Probability math, thresholds, fixed mappings, action policy | Replay logged outputs where possible, then review changed actions and threshold crossings |
| What produces the outputs, or what they represent | Model or encoder swap, new labels, a materially different population or scope | Broader requalification against the acceptance criteria |

The third row has a cheap shortcut. If the model's inputs and outputs are unchanged and you logged everything the new logic needs (at minimum, the full probability distribution across every option, including the ones that didn't win), you can replay a threshold or action-policy change without another model call. Replay tells you what the new logic would have done to past decisions. It doesn't validate changes that alter the model calls, and it doesn't prove tomorrow's traffic looks like yesterday's.

## What I'm Testing Next

I plan to start with CLINC150 because the data and taxonomy are public. [CheckList](https://aclanthology.org/2020.acl-main.442/) gave me language for the first two tests years before these decision APIs existed. Ribeiro and colleagues call them **Invariance** and **Directional Expectation** tests.

1. **Invariance.** Change something that shouldn't matter: reorder options, reformat the input, or add background reviewed as irrelevant. The decision should hold.
2. **Directional Expectation.** Change something that should move the decision in a known direction, such as a negation that reverses the request.
3. **Composition.** Ask the question directly, ask it in two steps, commit to one category and pick inside it, and derive category probabilities from the direct answer. Compare final actions and threshold crossings as well as accuracy.

For Laya, I want to understand why the two-step version helped, starting with how many options each question carries. I'll include a fixed-label supervised baseline too. A result that doesn't reproduce would be useful, and so would a clear reason for Laya going the other way.

## Back to the Chart

The chart I scrolled past showed Jev at 98.0% and Clef at 94.8%. Laya wasn't on it; DecideBench's full v1.0 results put it below 60%.

I still care which bar is longest, but what happens after I pick a model matters more. In the *Add Up* experiment, the same Jev model went from 91.0% to 68.1% on the same requests when only the question changed.

I haven't reproduced that yet. That's the experiment I want to run next.