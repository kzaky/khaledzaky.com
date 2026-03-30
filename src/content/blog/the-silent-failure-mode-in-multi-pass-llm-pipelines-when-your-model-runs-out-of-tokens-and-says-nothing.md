---
title: "The Silent Failure Mode in Multi-Pass LLM Pipelines: When Your Model Runs Out of Tokens and Says Nothing"
date: 2026-03-30
author: "Khaled Zaky"
categories: ["tech", "ai"]
description: "A 7-pass AI pipeline was silently skipping two audit passes for months. No errors, no alarms — just fallback logic that made output token truncation look like success."

---

## TL;DR

My 7-pass AI blog pipeline had been silently skipping two audit passes for months. No errors. No alarms. Just quietly shipping unchecked drafts. The cause was output token truncation on Claude Haiku, and the real problem was fallback logic that made truncation look like success.

---

## The Bug That Looked Like Success

The citation audit had been running on every post for weeks. It never flagged anything. Turns out, it had never actually finished.

The pipeline was healthy by every observable metric. CloudWatch showed Lambda successes. No exceptions. No retries. Posts were publishing on schedule.

But the audits were doing nothing. And the pipeline had no way to tell the difference.

---

## How the Pipeline Is Built

I [built a blog agent](https://khaledzaky.com/blog/i-built-an-ai-agent-that-writes-for-my-blog/) that drafts posts through seven sequential passes, each one a separate Lambda invocation:

1. Research
2. Draft
3. Chart placeholders
4. Diagram placeholders
5. Citation audit
6. Voice audit
7. Insight audit

Each pass takes the output of the previous one as input, applies a specific transformation, and hands off a modified document. The pipeline is stateless between passes, and each Lambda either returns a corrected draft or the original, unchanged.

The citation and voice audits sat at passes 5 and 6. The insight audit at pass 7 also ran on Haiku, with a `4096` output token budget and a skip limit for posts over 2,500 words — a guard I'd added because Haiku couldn't reliably output a long draft back within that budget.

Three passes on Haiku. The decision made sense when I built it. Haiku is fast, cheap, and more than capable of reading a draft and applying targeted corrections.

The problem wasn't the model. It was the token budget — on two of those three passes.

![7-Pass Blog Pipeline](/postimages/charts/the-silent-failure-mode-in-multi-pass-llm-pipelines-when-your-model-runs-out-of-tokens-and-says-nothing-diagram-1.svg)

---

## What the Audits Were Supposed to Do

The contract for both audit passes was simple:

1. Read the full draft
2. Apply corrections (fix citation formatting, catch voice violations)
3. Output the corrected draft in full
4. Append a summary comment at the end (a structured marker I could parse)

The summary marker served two purposes. It gave me a human-readable audit trail, and it acted as a completion signal. My fallback logic read: if the marker isn't present in the output, return the original draft unchanged.

The intent was sound. If the model produced garbage or returned an empty response, I wanted the pipeline to degrade gracefully rather than corrupt the document.

What I didn't account for was the case where the model produces a perfectly valid, partial output and then runs out of tokens before reaching the marker.

---

## Why It Failed Silently

Here's the mechanism. A finished post runs somewhere between 1,500 and 2,500 words. The audit pass needs to read all of that, apply corrections inline, and then output the full corrected draft plus the summary marker. On any post of realistic length, that output easily exceeds `4096` tokens.

So the model would start writing the corrected draft, get most of the way through, and then stop. Mid-sentence, sometimes. No error. No warning. Just a clean, truncated response.

My fallback logic would then check for the summary marker, find nothing, and return the original draft unchanged.

From the pipeline's perspective, everything worked. Lambda returned `200`. The document passed through. No alarms fired.

From a correctness perspective, the audit had never run.

![Expected Behavior](/postimages/charts/the-silent-failure-mode-in-multi-pass-llm-pipelines-when-your-model-runs-out-of-tokens-and-says-nothing-diagram-2.svg)

This isn't a hallucination problem. It's not a wrong-answer problem. It's a **silent correctness failure**, where the output is structurally valid but semantically incomplete, and the surrounding logic has no way to distinguish it from a deliberate no-op.

The failure mode is worth naming clearly because it doesn't show up in the usual taxonomy of LLM failure modes. Most discussions focus on what the model says. This one is about what the model never got to say.

---

## The Fix

The immediate fix was straightforward: switch both audit passes to Claude Sonnet with an `8192` output token budget. That's enough headroom to output the full corrected draft plus summary marker for any realistic post length.


The cost difference between Haiku and Sonnet across two audit passes is roughly $0.09 per post. That's not a trade-off worth making on the wrong side of.

But the more important fix was to the fallback logic. The original behavior treated a missing summary marker as "no changes needed." The corrected behavior treats it as an error condition. If the marker is absent, the pass logs a warning (not just an info line) and flags the document for review rather than silently passing it through.

```python
if SUMMARY_MARKER not in model_output:
    logger.warning(
        "Audit pass did not complete. Summary marker absent. "
        "Returning original draft and flagging for review."
    )
    return {"status": "incomplete", "draft": original_draft}
```

That single change means a truncation event is now observable. It shows up in CloudWatch as a warning. It doesn't silently degrade into a pass.

---

## Pass 7: Same Root Cause, Different Symptom

After fixing passes 5 and 6, I looked at pass 7 with fresh eyes. The insight audit also ran on Haiku — and it had its own version of the same problem.

The failure mode was different. The insight audit doesn't output a corrected draft; it scans for weak paragraphs and annotates them with HTML comments. So truncation wasn't the issue. Instead, Haiku was occasionally prefixing its response with a task acknowledgment preamble — something like `I'll audit this draft for weak paragraphs that lack editorial insight...` — before returning the actual annotated draft.

That preamble got prepended to the post body. The auto-description generator, which reads the first meaningful paragraph of the post body to populate the frontmatter `description` field, grabbed it verbatim.

The result: a published post with the model's internal task monologue as its meta description and open graph card. It was live before I noticed.

Two fixes. Switch the insight audit to Sonnet 8192 tokens, consistent with passes 5 and 6. Add a preamble guard that compares the first meaningful line of the model's response against the original draft and strips any acknowledgment prefix if they diverge.

The 2,500-word skip limit also went away. That limit wasn't editorial logic — it was a Haiku output capacity workaround. With Sonnet at 8192 tokens, there's no reason to skip long posts. The insight audit now runs on everything.

The underlying pattern: fixing one Haiku-on-wrong-task problem immediately surfaced another. Once you have the mental model, the audit is fast.

---

## How I Found It

I found this during a dry run, which is something I do periodically on the pipeline: trigger it with a test topic and watch CloudWatch Logs in real time rather than waiting for a finished post.

The dry run is underrated for LLM pipelines. You can't unit test prompt quality. You can't write an assertion that checks whether the voice audit actually caught a style violation. But you can verify the plumbing. You can watch each pass execute, check that the output length is non-trivial, and confirm that the markers you're depending on are actually present in the output.

In this case, watching the logs in real time made the pattern obvious immediately. The audit Lambda was completing in under a second (a signal that something was off), and the output length was consistently short relative to the input.


If I had been relying on post-hoc log analysis, I might have missed it for longer.

---

## The Broader Lesson

Every pass in a multi-pass pipeline has a **contract**: a set of conditions that define whether the pass actually did its job. Lambda returning `200` isn't that contract. It's a liveness check, not a correctness check.

For passes that transform a document, the contract includes things like:

- Output length is within a plausible range relative to input length
- Required structural markers are present
- The output contains the expected sections or fields

If your pipeline doesn't verify those conditions, you're flying blind on correctness.

The model sizing question is also worth being deliberate about. Haiku is well-suited for structural tasks: inserting markers, classifying content, running find-and-replace style operations where the output is small relative to the input. Sonnet is better suited for tasks that require reading and rewriting the full text, where the output is roughly the same size as the input.

Passes 5, 6, and 7 were all the wrong shape of task for Haiku at `4096` tokens. The cost optimization made sense in isolation. Applied to the wrong pass, it introduced failure modes that were invisible until I went looking for them.

Don't let cost optimization on the wrong pass introduce silent quality degradation. The two aren't always in conflict, but when they are, correctness wins.

---

## Next Steps

If you're building a multi-pass LLM pipeline, here's what I'd check:

- **Audit your fallback logic.** If your fallback on any failure condition is "return input unchanged," ask whether that behavior is distinguishable from a successful no-op. If it isn't, add an observable signal.
- **Check output length distributions.** For any pass that rewrites a full document, log the input token count and output token count. A consistent pattern of short outputs on long inputs is a signal worth investigating.
- **Size models to the task shape, not just the cost.** Haiku for structural operations (find-and-insert, classification, marker injection). Sonnet for tasks that require reading and rewriting the full document or producing nuanced editorial judgment. The token budget needs to fit the output, not just the model tier.
- **When you find one misfit, audit the rest.** Fixing passes 5 and 6 immediately surfaced pass 7. The failure modes were different — truncation vs preamble contamination — but the root cause was the same. Use each fix as a prompt to review adjacent passes with the same lens.
- **Run dry runs on real-length content.** Test with posts at the upper end of your expected length range, not just short examples that fit comfortably within any budget.
- **Treat missing completion markers as errors, not no-ops.** A marker-not-found condition should produce a warning log and a flagged document, not a silent pass-through.

*The pipeline had been running cleanly for months. The audits had never actually run. Sometimes the most expensive bugs are the ones that never crash.*