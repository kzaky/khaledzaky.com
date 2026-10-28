---
description: Audit and sync all documentation after pipeline changes
---

Run this after any change to the agent pipeline (new Lambda, new LLM pass, cost change, new feature, bug fix).

## 1. Identify what changed
Review recent git diff to understand what was modified:
// turbo
Run `cd /Users/kzaky/Documents/khaledzaky.com && git diff HEAD~1 --stat`

## 2. Check Lambda count
Verify the READMEs agree with the 11 functions in `agent/template.yaml`:
// turbo
Run `grep -c "Type: AWS::Lambda::Function" /Users/kzaky/Documents/khaledzaky.com/agent/template.yaml`
Run `grep -n "Lambda function\|Lambdas" /Users/kzaky/Documents/khaledzaky.com/README.md /Users/kzaky/Documents/khaledzaky.com/agent/README.md | head -20`

## 3. Check pass order, budgets and cost in both READMEs
Read the Draft pass list, the Draft flowchart and the "Cost Estimate" section in
`README.md` and `agent/README.md`.

Current values: Draft runs thinking plan → Opus draft (16000) → structure (16000) →
placeholders → citation review (4000, read-only) → voice (16000) → lint → insight +
named-entity (16000, concurrent, skipped on revise). Cost, measured from Bedrock metrics
(Oct 2026): ~$1.32 single-pass post, ~$2.26 with one revise. Re-measure from the Bedrock
token metrics after a pipeline change that adds or removes LLM calls; do not estimate.

## 4. Check module docstrings in affected Lambda files
Read the top of any modified `index.py` files and verify the docstring matches current behaviour.
Key files to check after most changes:
- `agent/research/index.py` — architecture docstring
- `agent/draft/index.py` — pass enumeration (order and token budgets as in step 3)
- `agent/verify/index.py` — flow steps; suggest-only unless `VERIFY_AUTO_REPAIR=1`
- `agent/evaluate/index.py` — seats and repair loop
- `agent/publish/index.py` — annotation stripping mention

## 5. Check test coverage
// turbo
Run `grep "LAMBDA_DIRS =" /Users/kzaky/Documents/khaledzaky.com/agent/tests/test_handlers.py`

Verify all 11 Lambdas are present: `research`, `draft`, `verify`, `evaluate`, `notify`, `approve`, `publish`, `ingest`, `chart`, `alarm-formatter`, `upload`

Run the eval runner and update any counts the docs quote (published posts, corpus cases):
Run `python3 /Users/kzaky/Documents/khaledzaky.com/agent/evals/run_gate.py | head -3`

## 6. Check RECOVERY.md SSM secrets section (kept privately, gitignored)
Read `RECOVERY.md` and verify every SSM key the agent reads is listed (see the SSM Parameter
Keys section of `.devin/rules`, plus any private ones).

## 7. Check deploy.sh prerequisites and reminder
// turbo
Run `grep -n "ssm put-parameter\|prerequisite\|Prerequisite\|reminder" /Users/kzaky/Documents/khaledzaky.com/agent/deploy.sh`

Verify GitHub token, Tavily key, and Perplexity key are all mentioned.

## 8. Check RECOVERY.md log retention loop
// turbo
Run `grep "blog-agent-" /Users/kzaky/Documents/khaledzaky.com/RECOVERY.md`

Verify all 11 Lambda log group names are in the loop.

## 9. Make any corrections found, then commit and push
Stage all changed doc files and commit with `docs:` prefix.
Run `/git-sync` or:
```bash
cd /Users/kzaky/Documents/khaledzaky.com && git add -A && git commit -m "docs: sync documentation after pipeline changes" && git push origin master
```
