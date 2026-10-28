---
description: Checklist for adding a new Lambda function to the blog-agent pipeline
---

Run this whenever a new Lambda is added to the agent. Replace `{name}` with the new Lambda's name (e.g., `summarize`).

## 1. Create the Lambda directory and index.py
Create `agent/{name}/index.py` with:
- Module docstring describing what the Lambda does
- `handler(event, context)` function
- Structured JSON logging with `aws_request_id` correlation

## 2. Add to deploy.sh — packaging loop
Read `agent/deploy.sh` and add `{name}` to both `for fn in ...` loops (packaging and deploy) and to both cleanup `rm -f ... .zip` lines. If it needs shared code, add a `.common-deps` file listing the `agent/common/` modules (e.g. `llm.py`, `gate.py`) so `scripts/package-lambda.sh` vendors them.

## 3. Add to CloudFormation template
Read `agent/template.yaml` and add:
- `{Name}Function` Lambda resource
- `{Name}LambdaRole` IAM role scoped to minimum permissions
- `{Name}ErrorAlarm` (`errors-{name}`, no action) and add it to `LambdaErrorCompositeAlarm`'s `DependsOn` and `AlarmRule`
- Step Functions state if it's part of the pipeline flow
- Environment variables needed

## 4. Add to test_handlers.py LAMBDA_DIRS
Read `agent/tests/test_handlers.py` (`LAMBDA_DIRS =`, ~line 38) and add `"{name}"` to `LAMBDA_DIRS`.
This is the most commonly missed step — it ensures CI smoke-tests the handler import and signature.

## 5. Add to RECOVERY.md log retention loop
Read `RECOVERY.md` (gitignored, kept privately) and add `/aws/lambda/blog-agent-{name}` to the `for lg in ...` loop in the log retention section.

## 6. Update Lambda count in all READMEs
Search for the current Lambda count (e.g., "11 Lambda") in:
- `README.md` — update count in Tech Stack table, blog-agent stack row, monitoring table
- `agent/README.md` — update `### Components (N Lambda functions)` heading, the setup step, and the Ops table alerting, logging and tracing rows
- `.devin/rules` — Lambda list and count
- Both cost sections if the new Lambda adds LLM calls

## 7. Update cost estimate if the Lambda makes LLM calls
If the new Lambda invokes Bedrock:
- Add the call to the LLM call list in both READMEs
- Re-measure per-post cost from the Bedrock token metrics after a real run; do not estimate

## 8. Update module docstrings of affected Lambdas
If this Lambda is inserted into the pipeline flow, update the docstring of any Lambda that now precedes or follows it.

## 9. Run smoke tests locally
// turbo
Run `cd /Users/kzaky/Documents/khaledzaky.com && python3 -m pytest agent/tests/test_handlers.py -v 2>&1 | tail -30` (Python 3.11+; `pip install ruff pytest pyyaml cfn-lint`)

## 10. Commit and push
Run `/git-sync` or:
```bash
cd /Users/kzaky/Documents/khaledzaky.com && git add -A && git commit -m "feat: add {name} Lambda to blog-agent pipeline" && git push origin master
```
