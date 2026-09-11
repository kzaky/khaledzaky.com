# Blog agent evals

Ground truth for the pipeline's quality gates, built from the author's own hand fixes.

## What is in here

| Path | Purpose |
|---|---|
| `manifest.json` | One entry per post-publication fix commit: slug, defect classes, note, and the gate expectations the measurements support |
| `build_cases.py` | Materialises `cases/<commit>-<slug>.json` (shipped text = parent commit, fixed text = the commit) from git; re-run when the manifest changes. Files are committed so the harness runs on a shallow CI checkout |
| `run_gate.py` | Offline runner: oracle over every published post (zero gate errors) + corpus scoring. `--json` for machine output; exit 1 on any failure |
| `../tests/test_evals.py` | The same assertions as pytest, so CI runs them with the handler tests |
| `calibrate_judges.py` | Measures which judge model belongs first in the rubric panel's preference list, by scoring each seat's findings against what the author actually changed. Needs AWS credentials; `--estimate` prints the call count without touching Bedrock |

## Calibrating the judge ordering

The independent seats run on whichever non-Anthropic model is first in `JUDGE_MODEL_ID`
and accessible. That ordering started as a hypothesis — "bigger and newer is probably a
better judge" — which is the same kind of unmeasured claim these gates exist to catch.

`calibrate_judges.py` settles it against the corpus. The `before`/`after` pair gives
ground truth for free: the lines the author changed are the defects a good judge should
have caught, with no labelling and no model's opinion involved. A seat finding is a
`hit` when its quoted sentence is substantially inside a line the author removed.

    python3 agent/evals/calibrate_judges.py --estimate     # call count, no spend
    python3 agent/evals/calibrate_judges.py \
      --models mistral.mistral-large-3-675b-instruct,us.meta.llama4-maverick-17b-instruct-v1:0,openai.gpt-oss-120b-1:0 \
      --json /tmp/judges.json

Read `hit_rate` as a **relative** signal, not accuracy. It is a deliberate lower bound:
the author fixed what they noticed, not everything that was wrong, so a finding on
untouched text is not necessarily a false one. What makes the comparison fair is that
every model faces identical cases, seats, and scoring. `findings_per_case` is reported
alongside because flagging everything inflates the denominator without being useful —
the combination worth having is a high `hit_rate` at a non-trivial volume.

Seats are scored only on the defect classes they own (`SEAT_CLASSES`); grading a voice
seat on a citation fix measures nothing. The script never writes to SSM or Lambda —
acting on the result means reordering `JUDGE_MODEL_ID` deliberately.

## The partition that matters

Fourteen cases, six defect classes. Nine cases carry a signal the deterministic gate
(`agent/common/gate.py`) can see — a fenced body, an LLM preamble, `-ise` spellings,
formula repeats, links or sections the fix added back. The other five (a wrong but
resolving arXiv id, employer references, a lost credibility hook, overclaimed precision)
need a model: claim-level source verification (L1) or the rubric panel (L2). The
runner prints that partition every time so drift is visible; `test_detectability_partition_is_documented`
pins it.

## Rules

- **Fix the gate, not the post.** A false positive on a published post means the gate
  would have blocked real writing. Errors are calibrated on all 52 posts (zero false
  positives). Advisory prose findings are calibrated on the **18 pre-agent posts**
  (before 2026-02-21, the agent's launch): none of them contains a rule-of-three
  triplet and 17 of 18 end in plain prose, while 41% and 76% of agent-era posts do
  — so those are agent tells and are reported from the first occurrence. `behavior`
  is the author's own spelling and is never flagged.
- **New production escape → new case.** Add the fix commit to `manifest.json` with
  its classes and the expectation the gate should satisfy, rebuild, and make the
  gate pass it.
- **Human-labelled only.** Every `after` here was written or approved by the author;
  no model output is used as gold.
