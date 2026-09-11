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

## Update 2026-09-10: model-upgrade infrastructure

A separate pass, prompted by "make sure we're upgrading to the latest models and
not hitting the Haiku truncation problem again." Two things were true at once:

**Token-budget audit.** Draft's own Opus generation pass had already been bumped
to 16000 tokens after a July truncation bug (a citation-heavy post exceeding
8192). But five downstream passes that reproduce the *entire* post body — the
citation, voice, insight, structure and named-entity audits — were still capped
at the old 8192, and Research's synthesis pass (which Draft is built from) was
still at 4096. All bumped to 16000. Evaluate's own seat calls (added in this same
change set) were at 2000 tokens against a schema that can need ~2450 at its own
stated limits — bumped to 4000 before it ever shipped as a live bug.

**Model-upgrade infrastructure.** `scripts/update-models.sh` already existed to
discover and probe the latest Anthropic inference profiles, but had two bugs that
meant it had never actually worked: its SSM-write step used `for path val in
...; do`, which is not valid bash (confirmed with `bash -n` against the
previously-committed version — it fails identically); and its version-parsing
regex only recognized two-number IDs (`opus-4-8`), not the bare single-number
naming Bedrock uses for the newest generation (`us.anthropic.claude-opus-5`,
which is listed ACTIVE in the target account) — so even fixed, it would never have
discovered that generation. Both fixed. `deploy.sh` also never
read the SSM parameters update-models.sh writes as "the source of truth for
future deploys" — it hardcoded its own `--parameter-overrides`, so any deploy
after a model bump would have silently reverted it. Fixed: `deploy.sh` now reads
`/blog-agent/models/*` from SSM first. `HaikuModelId` was a literal string
copy-pasted across four Lambda env vars rather than a stack parameter; promoted.

**Non-Anthropic models.** No Claude model ID string was hardcoded as "the
latest" without live verification — Bedrock inference-profile naming isn't
predictable enough to guess safely, and a wrong guess fails harder than a
throttle (a `ValidationException` on an invalid model id wasn't treated as a
recoverable fallback condition before this change; now it is, the same as
access-denied). The same caution applies harder to non-Anthropic models: there
is no evidence "GPT-5.6" or "GPT-6" exist on Bedrock. `JudgeModelId` is now a
comma-separated **priority list** (`invoke_judge` tries each candidate in order,
only reaching the Anthropic fallback once all are exhausted), and
`scripts/update-judge-model.sh` discovers what's actually live in the account
across both Bedrock catalogs (on-demand models and cross-region inference
profiles — a live audit found OpenAI's models registered only in the latter)
rather than the pipeline ever guessing a model name.

**Correction (2026-09-10, after live probing).** An earlier revision of this document
said newer Anthropic profiles were "ACTIVE **and accessible**" in the account, citing a
live audit. That overstated what the audit established: it had confirmed the profiles
were *listed* as ACTIVE and had explicitly not invoked anything. Direct probes since
show every profile newer than the 4-6 line — `sonnet-5`, `opus-4-7`, `opus-4-8`,
`opus-5`, `fable-5-1` — returns `AccessDeniedException` ("not available for this
account"). **Listed is not entitled.** Nothing newer than 4-6 is usable today, so
`update-models.sh` correctly selects 4-6 and the "bump to the 5-generation" item below
is blocked on account entitlement, not on code. The same applies to the third-party
catalogue: `gpt-5.6-luna/sol/terra` and `gpt-6-astra` appear ACTIVE and are all
AccessDenied, alongside `grok-4.6`, `glm-5` and others — a pattern that reads as an
unentitled preview catalogue rather than an available menu. None of them are referenced
anywhere in this codebase.

What the account audit *did* establish, and what live probing confirms: all three
currently-pinned model IDs are ACTIVE and accessible; IAM is already wildcard-scoped
for `bedrock:InvokeModel`, so no policy change is needed to adopt any model that does
become entitled (`Converse` was already added to the Evaluate role for the judge
seats); and the models actually invokable for the independent judge seats are
`mistral.mistral-large-3-675b-instruct`, `us.meta.llama4-maverick-17b-instruct-v1:0`,
`deepseek.v3.2` and the `openai.gpt-oss-*` family — which is what the judge preference
list now contains, in that order, as a hypothesis for calibration to settle.

**Cross-region token ceiling: resolved by test.** The 4096 figure in the code comments
is thinking-specific, not a general per-invocation cap. A real non-thinking
`invoke-model` against a `us.` cross-region profile with `max_tokens: 8000` returned
exactly 8000 output tokens (`stop_reason: max_tokens`, ~5,700 words of coherent prose),
1.95x the supposed cap, stopping only at the requested ceiling. The 16000-token bumps
stand. Two honest limits on that result: it demonstrates >4096 and specifically 8000,
not 16000 (that remains an extrapolation supported by Draft's production record at
16000), and it says nothing about the thinking path, where the original constraint may
well still hold — `invoke_with_thinking` keeps it.

## Update 2026-09-11: what a live deploy proved, including one design that could not work

Three deploy attempts against the real account. The third succeeded. The two failures
and the fixes between them are worth recording, because a linter caught none of it.

**`SEARCH()` cannot be used in a CloudWatch metric alarm at all.** The previous entry
described replacing the per-function metric list with a single `SUM(SEARCH(...))`
expression to escape CloudWatch's 10-metric-per-alarm cap. That premise was wrong, and
not marginally: four controlled `put-metric-alarm` tests settled it.

| Shape | Result |
|---|---|
| `SUM(SEARCH(...))`, no `Period` | `Period must not be null` |
| `SUM(SEARCH(...))` + `Period` | `SEARCH is not supported on Metric Alarms.` |
| bare `SEARCH(...)` + `Period` | `SEARCH is not supported on Metric Alarms.` |
| explicit `MetricStat` + `m1+m2` | accepted |

An alarm needs one static series; SEARCH returns a dynamic set. The 10-metric cap has to
be **designed around**, not expressed away. `cfn-lint` was clean for every revision,
including the two that failed — a template linter validates structure, not service
semantics, and is not a substitute for a change set.

Worse, the SEARCH version had a second defect that would have been **invisible at
runtime**: the search term `"blog-agent-"` was quoted, which CloudWatch treats as an
exact-match token rather than a prefix. It matched zero functions (unquoted matched all
eight then deployed). With `TreatMissingData: notBreaching` the alarm would have sat in
`OK` forever, monitoring nothing. A silently-wrong metric filter is worse than a failed
deploy, and only a live `get-metric-data` check would have caught it.

**The design that works:** one single-metric alarm per function, none of them carrying
an action, OR-ed together by a composite alarm that holds the sole action to the alert
topic — with an explicit `DependsOn`, since an `AlarmRule` names its children as strings
and CloudFormation infers no ordering from that. Verified post-deploy: 11 alarms, all
`OK` (not `INSUFFICIENT_DATA`), `actions=0` on every child so only the composite
notifies, and watched-set exactly equal to deployed-set with no Lambda unwatched and no
alarm pointing outside the stack. Note that `describe-alarms` omits composite alarms
unless `--alarm-types CompositeAlarm` is passed, so the composite looks missing on a
casual spot-check.

**Entitlement, corrected and explained.** The previous entry already corrected "listed
as ACTIVE" to "not entitled." Live probing added the actual predictor, which is not what
either of us guessed from model names: **inference type**. Third-party `ON_DEMAND`
models are invokable; third-party `INFERENCE_PROFILE`-only models are uniformly denied
in this account (`grok-4.6`, every `gpt-5.6-*`, `gpt-6-astra`). Anthropic is
profile-only throughout and needs per-model entitlement, which this account has up to
the 4-6 line. "The name looks implausibly far ahead" was never a real signal; it
happened to correlate. Accordingly `zai.glm-5`, `minimax.minimax-m2.5`, `zai.glm-4.7`,
`minimax.minimax-m2` and `moonshotai.kimi-k2.5` are all genuinely accessible — an
earlier report swept them into the denied group in error.

**Cross-family judging is live.** On a seeded draft (an unsourced "60%" figure, an
"always" absolute, a FAIL citation verdict), all three `independent: True` seats ran on
`mistral.mistral-large-3-675b-instruct` — first in the preference list, no fallback —
and the two `independent: False` seats correctly stayed on Sonnet. The seats did real
work rather than boilerplate: `fact_checker` flagged the 60% figure as blocking, citing
the FAIL verdict, and `skeptical_expert` independently caught both the statistic and the
"always" absolute. This is the first end-to-end evidence that the L2 panel functions.

**Still open:** the judge preference ordering remains an unmeasured hypothesis — the
calibration pass over `agent/evals` is what should set it. And every call in these
sessions ran as account root, which is worth fixing independently of this work.

## Next (not in this change)

1. **Judge calibration run.** Score the 14 corpus cases with each L2 seat and report
   per-seat agreement with the author's fixes; flip a seat to blocking only above
   90 % on clear-cut cases. Requires Bedrock credentials; the harness shape is in
   place.
2. **Retire the citation-audit rewrite pass** once L1 has run on a few posts: it is
   the content-loss risk L1 makes redundant.
3. **Model bump** to the 5-generation Sonnet/Opus profiles via `update-models.sh`;
   the code paths that would have broken are already model-aware.
