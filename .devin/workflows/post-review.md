---
description: Human review checklist before approving or publishing any blog post
---

Run this when the HITL review email arrives (before hitting Approve), or before manually committing a post written outside the pipeline.

## 1. Read the full post top to bottom — one pass, no edits yet
Just read it as a reader would. Note anything that feels off before diving into specifics.

## 2. Authenticity check — do you own everything you're claiming?
- Are there benchmarks, metrics, or technical terms you're referencing without really knowing them? (e.g., BLEU, ROUGE, specific paper findings)
- Does the post sound like you researched this over a weekend, or like a published expert wrote it?
- Any claims that feel like the agent filled a gap with something you didn't actually say?

If yes → **Revise**, not Approve. Add a note explaining what to soften or remove.

## 3. Tone check — curious learner, not authority
- Does the opening invite the reader in, or lecture them?
- Are there declarative sentences that should be "I've been thinking about..." framing?
- Does the closing feel like a genuine reflection, not a summary paragraph?
- Any jargon used without explanation for a platform/software audience?

## 4. Check the pipeline's annotation flags
The review email will contain inline HTML comment flags from the pipeline:
- `<!-- ⚠️ CITATION FAIL: -->` — a link the Verify Lambda couldn't validate. Address before approving.
- `<!-- 💡 CITATION NOTE: -->` — soft citation concern. Use judgment.
- `<!-- ⚡ INSIGHT: -->` — paragraph the insight audit (Pass 9) flagged as generic. Worth reviewing.
- `<!-- 🔍 ENTITY CHECK: -->` — Pass 8 flagged a regulation, version, or named reference it couldn't verify. Review or soften before approving. Not emitted in revision mode.
- `<!-- ⚠️ STRUCTURE: -->` — Pass 7 detected a structural issue (e.g. missing headings) it couldn't auto-fix. Address before approving.

Note: Voice profile violations are **rewritten directly** by the pipeline (Sonnet audit, always on). No VOICE annotation flags appear in the review email — violations are fixed in-place before you see the draft.

Zero CITATION FAIL and zero ENTITY CHECK → safe to approve. Any FAIL or ENTITY CHECK → revise or manually resolve.

## 5. Frontmatter completeness
Check the top of the draft for:
- `title` — present and accurate?
- `description` — 1–2 sentence summary (pipeline auto-generates if missing, but verify it's good)
- `pubDate` — correct date?
- `categories` — relevant tags?
- `draft: true` — should NOT be present in the final (Publish Lambda strips it, but verify)

## 6. Personal info scan (for manually written posts only)
If this post was written outside the pipeline:
- No personal email addresses in the body
- No account IDs, API Gateway URLs, or internal tool references
- No SSM key names or specific resource identifiers

Pipeline-generated posts: already clean (pipeline doesn't inject personal info).

## 7. Length and structure sanity
- Is it between 800–3000 words? (pipeline doesn't hard-cap length, but manual posts may drift)
- Does it have a clear opening hook, 2–4 substantive sections, and a genuine closing?
- Are charts/diagrams present where data was discussed? (pipeline inserts these automatically)

## 8. Make your call
- **Approve** → post is ready as-is. Pipeline commits to GitHub, site deploys in ~2 min.
- **Revise** → write specific feedback in the revision form. Be concrete: "Soften the intro — sounds too authoritative" or "The MMLU mention needs a plain-English explanation."
- **Reject** → draft is too far off. Start a new run with refined input.

For **manual posts**: commit directly with `/git-sync` after review.
