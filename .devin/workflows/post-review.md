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

## 4. Read the review email's findings
The draft itself carries no review comments: the pipeline lifts them out and lists them in
the email. Searching the draft for `CITATION FAIL` and finding none proves nothing. Read
these blocks instead:
- **CITATION QUALITY** — Verify's per-link verdicts (passed, warnings, failures,
  unreachable), suggested replacement URLs, sentences stating a figure the source does not
  contain, and the freshest source's age. Verify only suggests: it never changes a link, so
  every FAIL or WARN is still in the post until you fix it. Unreachable means the page
  could not be read, not that it fails the claim; check those by hand.
- **SOURCE FIDELITY** — Draft's review findings: blocking citation findings, then advisory
  ones (could not verify, INSIGHT and ENTITY CHECK notes, structure notes and rewrites the
  shape guard rejected). For a finished article you sent as-is, SOURCE ALTERED means the
  body no longer matches your submission: do not approve.
- **PIPELINE WARNINGS** — the release gate's advisory prose findings (forbidden phrases,
  antithesis, italic closers, rule-of-three, `-ise` spelling) and the chart findings
  (a title that does not match its series, over-long titles).
- **RUBRIC PANEL** — the five seats' scores and findings. If the header says any
  BLOCKING finding remains after the repair pass, do not approve as-is.
- **INTENT CHECK** — whether the draft kept your claims and framing.

Any blocking rubric finding, citation FAIL, unsupported precision claim or chart finding →
revise or fix by hand. Advisory findings → use judgment.

## 5. Frontmatter completeness
Check the top of the draft for:
- `title` — present and accurate?
- `description` — 1–2 sentence summary (pipeline auto-generates if missing, but verify it's good)
- `date:` — correct date?
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
