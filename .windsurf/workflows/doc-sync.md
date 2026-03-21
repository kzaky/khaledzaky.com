---
description: Audit and sync all documentation after pipeline changes
---

Run this after any change to the agent pipeline (new Lambda, new LLM pass, cost change, new feature, bug fix).

## 1. Identify what changed
Review recent git diff to understand what was modified:
// turbo
Run `cd /Users/kzaky/Documents/khaledzaky.com && git diff HEAD~1 --stat`

## 2. Check Lambda count
Verify all three locations agree on 10 Lambdas:
// turbo
Run `grep -n "Lambda\|lambda" /Users/kzaky/Documents/khaledzaky.com/README.md | grep -i "10\|nine\|eight\|seven" | head -20`
Run `grep -n "10 Lambda\|9 Lambda\|8 Lambda" /Users/kzaky/Documents/khaledzaky.com/agent/README.md | head -10`

## 3. Check LLM call count and cost in both READMEs
Read the cost sections:
- `README.md` lines ~288-301 (cost table + per-post total)
- `agent/README.md` lines ~63-73 (cost estimate section)

Correct values: **14 LLM calls/post**, **~$0.17/post**, **~$0.65/month at 4 posts**, **~$1.60/month at 10 posts**

## 4. Check module docstrings in affected Lambda files
Read the top of any modified `index.py` files and verify the docstring matches current behaviour.
Key files to check after most changes:
- `agent/research/index.py` — 8-step architecture docstring
- `agent/draft/index.py` — 7-pass enumeration docstring
- `agent/publish/index.py` — annotation stripping mention
- `agent/verify/index.py` — flow steps 1-5

## 5. Check test coverage
// turbo
Run `grep "LAMBDA_DIRS" /Users/kzaky/Documents/khaledzaky.com/agent/tests/test_handlers.py`

Verify all 10 Lambdas are present: `research`, `draft`, `verify`, `notify`, `approve`, `publish`, `ingest`, `chart`, `alarm-formatter`, `upload`

## 6. Check RECOVERY.md SSM secrets section
Read `RECOVERY.md` lines ~13-43 and verify all SSM keys are listed:
- `/blog-agent/github-token`
- `/blog-agent/tavily-api-key`
- `/blog-agent/perplexity-api-key`
- `/blog-agent/upload-passphrase`
- `cloudfront_distid`

## 7. Check deploy.sh prerequisites and reminder
// turbo
Run `grep -n "ssm put-parameter\|prerequisite\|Prerequisite\|reminder" /Users/kzaky/Documents/khaledzaky.com/agent/deploy.sh`

Verify GitHub token, Tavily key, and Perplexity key are all mentioned.

## 8. Check RECOVERY.md log retention loop
// turbo
Run `grep "blog-agent-" /Users/kzaky/Documents/khaledzaky.com/RECOVERY.md`

Verify all 10 Lambda log group names are in the loop.

## 9. Make any corrections found, then commit and push
Stage all changed doc files and commit with `docs:` prefix.
Run `/git-sync` or:
```bash
cd /Users/kzaky/Documents/khaledzaky.com && git add -A && git commit -m "docs: sync documentation after pipeline changes" && git push origin master
```
