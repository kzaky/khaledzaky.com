# Blog agent quality gates: plan, evidence, and what shipped

_Last updated 2026-09-10. Companion to `agent/README.md` (how the pipeline works) and
`agent/evals/README.md` (the ground-truth corpus)._

## The problem, in numbers

Five of the last five agent-published posts needed hand fixes after publication:
15 fix commits, ~230 lines rewritten by hand. The pipeline had ~12 checks arranged as
a flat chain in which nothing but a missing chart file could stop a post. The 15 fixes
classify into six defect classes; the two September escapes (a body wrapped in a
```` ```markdown ```` fence with a second frontmatter nested inside; six missing source
links) were rendering and citation defects, not style.

| Class | Fixes | Example | Why the old check missed it |
|---|---|---|---|
| Citation / source integrity | 7 | arXiv `2609.00275` → `2603.03515`; a vendor PDF cited for numbers it never states | Verify judged from a 1,000-char excerpt of a 32KB fetch (navigation chrome, on arXiv); the research fact-check compared claims against source **titles** |
| AI-writing patterns | 4 | three-beat italic closers, "not X. That's Y.", "the part that…" ×5 | the regex net covered one shape and its findings were discarded (`post_body, _ = _lint_slop(...)`) |
| Rendering / structure | 4 | fenced body; raw research notes published; SVG overflow ×2 | nothing checked "one frontmatter, body not fenced, renders as headings" |
| Overclaiming / precision | 3 | "doubles the cost", "proven over all inputs" | no gate asked whether a figure is quotable from its source |
| Voice / credibility | 4 | employer named as authority; credibility hook cut; `-ise` spellings | the voice profile is a style sheet |
| Content loss | 2 | sections dropped by a full-rewrite pass | four passes regenerate the whole post at 8,192 tokens with no shape invariant |

Two structural findings mattered more than any single defect: the structure audit
**mandated** an italic closing line that the voice audit forbids and the author
deleted by hand; and every judge was Sonnet 4.6 grading Sonnet/Opus 4.6 output —
the pattern the blog's own "Your Judge Is Not an Independent Reviewer" post argues
against.

## Design principles

1. **Deterministic first, model for the residue.** Anything expressible as a regex or
   a parse is a regex or a parse (the "Verification Is a Budget" ladder). Models only
   grade what regexes cannot: claim–source entailment, overreach, intent, voice.
2. **Evaluate, then repair; never rewrite to evaluate.** Seats emit findings anchored
   to quoted text. One targeted repair pass applies them, and only survives if the
   post's shape is intact.
3. **Independence per seat, best fit per seat.** Taste seats run on a different model
   family than the drafter (via Bedrock Converse); the mechanical claim check runs on
   the cheapest model that can read a whole page.
4. **Calibrate on the author, not on the agent.** Advisory thresholds come from the
   18 posts written before the agent launched (2026-02-21); errors are calibrated
   for zero false positives across all 52.
5. **Advisory until measured.** Taste seats do not block. They can once judge/human
   agreement is measured on the corpus (see "Next").

## Architecture (as shipped)

```
Research → Draft (Opus once; guarded audit passes)
   → Verify        L1  one Haiku call per link on the full page; precision backstop; source dates
   → Evaluate      L0 gate + L2 five-seat panel → one guarded repair → re-check blocking seats
   → Chart
   → Notify        L0 gate hard-fails; scorecard + lint findings + precision/recency on the email
   → HITL          approve / revise (re-enters at Verify) / reject
   → Publish       strips every review annotation (emoji-optional, multi-line)
   → CodeBuild     npm run check:render fails the deploy if a built page is malformed
```

| Layer | Blocks | What it checks | Where |
|---|---|---|---|
| L0 release gate | errors | frontmatter count/nesting, fenced body, LLM preamble, section count, leaked annotations, unrendered placeholders; advisory: forbidden phrases, antithesis, italic closers, rule-of-three, stacked contrasts, `-ise` | `agent/common/gate.py` |
| L1 claim verification | FAIL annotations | per-link entailment with quote; figures must appear in the source; URL swaps marked `CITATION REPLACED`; `min_source_age_days` | `agent/verify/` |
| L2 rubric panel | fact-check blocking findings, intent < 5 | fact_checker, target_reader, skeptical_expert, voice_fidelity (vs pre-agent posts), author_intent (full text) | `agent/evaluate/` |
| Repair | ≤ 1 pass | minimal edits for blocking findings; `gate.guard_rewrite` invariants | `agent/evaluate/` |
| Edge | fails deploy | one `<h1>`, section headings, `<pre>` share, leaked comments, placeholders on built HTML | `scripts/check-render-shape.mjs` in CI and `buildspec.yml` |

## Calibration evidence

Split of the 52 published posts at the agent's launch date:

| Signal | Pre-agent (n=18) | Agent-era (n=34) | Rule |
|---|---|---|---|
| Rule-of-three triplet on one line | 0 % of posts | 41 % | flag from the first occurrence |
| Italic closing line | 1 of 18 (single beat) | 26 of 34 (13 three-beat) | flag any; name the slogan shape |
| `not X, but Y` ≥ 2 | 0 % | 6 % | flag at 2 |
| Antithesis "That's not X. That's Y." | 17 % have one | 9 % | advisory (author does use it) |
| Bold terms used at all | 56 % | 100 % (up to 52) | voice audit bolds sparingly |
| `-ise` spellings | corrected by hand (00f126c) | — | flag |
| `behavior` (US spelling) | author's own (48 uses) | — | never flagged |
| Median words | 640 | 1,906 | reported |

Errors: zero false positives on all 52 published posts (`agent/evals/run_gate.py`).
Corpus: 9 of 14 hand fixes carry a deterministic signal and all 9 pass; the other 5
(employer references, a lost credibility hook, wrong-but-resolving ids, overclaimed
precision) are the L1/L2 layers' job and are listed by the runner so the split
cannot drift unnoticed.

## Bugs found while building the gates

- Publish's annotation strip never matched `⚠️ CITATION FAIL` (two code points in a
  character class), emoji-less `CITATION NOTE`/`FAIL` from the draft audit, or
  multi-line `CITATION WARN` — all three shapes were live on the site (halt,
  agent-observability, governance-debt posts). Fixed and cleaned.
- Publish's "unclosed comment" safety net deleted closed comments placed right after
  the frontmatter.
- `budget_tokens` in both thinking passes is deprecated on the 4.6 models and
  rejected by the 5-generation ones; the next `update-models.sh` bump would have
  broken them. Now adaptive-first with a cached fallback; `temperature` is dropped
  for models that reject it.
- Four unrendered `CHART`/`DIAGRAM` placeholders and one duplicate `<h1>` in older
  posts (now caught at the edge).

## Operating it

- **Enable the judge model once.** Bedrock → Model access → the `JudgeModelId`
  profile (default `openai.gpt-oss-120b-1:0`, us-east-1). Until then every
  independent seat logs `judge_fallback` once and runs on Sonnet.
- **Deploy** with `cd agent && ./deploy.sh <email>`; it packages the new `evaluate`
  function and uploads `voice-references.txt`'s posts to
  `config/voice-references/`.
- **Watch**: `PrecisionClaimsUnsupported`, `SourceRecencyDays`, the existing
  `CitationQualityScore`, and the pipeline-failure alarm (a gate error routes to
  `PipelineFailed`). The scorecard on each review email is the per-post view.
- **When a post needs a hand fix after publication**, add the fix commit to
  `agent/evals/manifest.json` with its class and expectation, run
  `python3 agent/evals/build_cases.py`, and make the gate pass it. That is how the
  corpus grows and how "fewer hand fixes per post" gets measured.

## Metrics and targets

| Metric | Baseline (last 5 posts) | Target |
|---|---|---|
| Posts needing post-publication fixes | 5 / 5 | ≤ 1 in 5 |
| Median hand-churn per post, 30 days after publish | 124 lines | < 20 |
| Citations replaced silently | unknown | 0 (all marked inline) |
| Precision claims without a quotable figure at publish | not measured | 0 |
| Judge / human agreement per seat (on the corpus) | not measured | ≥ 90 % before any taste seat blocks |
| Cost per published post | ~$0.65 (+ revisions) | ≤ ~$1.00 |

## Next (not in this change)

1. **Judge calibration run.** Score the 14 corpus cases with each L2 seat and report
   per-seat agreement with the author's fixes; flip a seat to blocking only above
   90 % on clear-cut cases. Requires Bedrock credentials; the harness shape is in
   place.
2. **Retire the citation-audit rewrite pass** once L1 has run on a few posts: it is
   the content-loss risk L1 makes redundant.
3. **Model bump** to the 5-generation Sonnet/Opus profiles via `update-models.sh`;
   the code paths that would have broken are already model-aware.
