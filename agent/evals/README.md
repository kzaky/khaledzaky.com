# Blog agent evals

Ground truth for the pipeline's quality gates, built from the author's own hand fixes.

## What is in here

| Path | Purpose |
|---|---|
| `manifest.json` | One entry per post-publication fix commit: slug, defect classes, note, and the gate expectations the measurements support |
| `build_cases.py` | Materialises `cases/<commit>-<slug>.json` (shipped text = parent commit, fixed text = the commit) from git; re-run when the manifest changes. Files are committed so the harness runs on a shallow CI checkout |
| `run_gate.py` | Offline runner: oracle over every published post (zero gate errors) + corpus scoring. `--json` for machine output; exit 1 on any failure |
| `../tests/test_evals.py` | The same assertions as pytest, so CI runs them with the handler tests |

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
  would have blocked real writing. Thresholds were calibrated on all 52 posts
  (e.g. one terse triplet is the author's style; the cadence is flagged only when it
  repeats; `behavior` is the author's spelling and is never flagged).
- **New production escape → new case.** Add the fix commit to `manifest.json` with
  its classes and the expectation the gate should satisfy, rebuild, and make the
  gate pass it.
- **Human-labelled only.** Every `after` here was written or approved by the author;
  no model output is used as gold.
