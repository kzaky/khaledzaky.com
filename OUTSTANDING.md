# Outstanding: needs the author

Work that is done in the repo but cannot be finished from a cloud session, or needs a
device or decision only the author has. Keep each item until it is done, then delete it.

## 1. Deploy the blog-agent Lambdas

The pipeline code on `master` is ahead of what runs in AWS. Until these are deployed, the
live agent still swaps citations on unreadable pages, appends change logs, renders the
old chart palette and runs the older gate.

- **Blocked by:** the AWS keys in the cloud environment are rejected
  (`InvalidClientTokenId`, 2026-10-25). Put working keys in the environment settings as
  `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (plus `AWS_SESSION_TOKEN` if temporary)
  and start a new session. The role needs `lambda:UpdateFunctionCode`,
  `lambda:GetFunction`, `lambda:InvokeFunction` on `blog-agent-*`.
- **Then:** one at a time, smoke-tested by the script, in this order:
  ```bash
  agent/scripts/deploy-lambda.sh verify
  agent/scripts/deploy-lambda.sh evaluate
  agent/scripts/deploy-lambda.sh draft
  agent/scripts/deploy-lambda.sh notify
  agent/scripts/deploy-lambda.sh chart
  ```
  Then send one test topic end to end and check the review email (chart findings,
  citation suggestions, gate warnings).
- **Optional:** `VERIFY_AUTO_REPAIR=1` on the verify function restores automatic
  citation replacement (default is suggest-only). `CHART_STYLE=classic` on chart brings
  back the old palette (default is brand).

## 2. Delete merged and superseded branches

- **Blocked by:** the session's git proxy refuses ref deletes and tag pushes (HTTP 403).
- Every branch below was checked on 2026-10-25: merged into `master`, or its change is
  already in `master` (the five with rewritten history hold July drafts master has since
  revised; the Dependabot bumps are in master at equal or newer versions). Keep
  `master` and `archive/jekyll`.
  ```bash
  git push origin --delete claude/blog-post-edits-model-decision-sq0zhs claude/code-infra-critique-efkbk6 claude/edit-judge-post-revision-9y1pqe claude/fix-coverage-article-rendering-0tw2uk claude/halt-article-corrections-4dky92 claude/jev-blog-surgical-edits-khdexq claude/verification-budget-revision-us3f0r dependabot/npm_and_yarn/fontsource-variable/inter-5.3.0 dependabot/npm_and_yarn/fontsource-variable/lora-5.3.0 dependabot/npm_and_yarn/npm_and_yarn-5f7cea1f02 dependabot/npm_and_yarn/sanitize-html-2.17.6 dependabot/npm_and_yarn/tailwindcss/vite-4.3.3 edit/agent-antislop-guardrails edit/break-antithesis-cadence edit/citation-accuracy-fixes edit/judge-post-final fix/agent-authority-corrections fix/agent-authority-final-pass pipeline/hardening
  ```

## 3. Check stacked tables with VoiceOver on an iPhone

On phones, tables of three or more columns stack into labelled rows, and the HTML
carries explicit ARIA table roles so Safari keeps announcing them as tables. Chromium's
accessibility tree confirms the roles; Safari itself cannot be run in the cloud session.
Open a post with a table (e.g. /blog/the-agent-has-an-identity-who-gave-it-authority/)
on an iPhone with VoiceOver and confirm it reads "table, N rows, N columns".
