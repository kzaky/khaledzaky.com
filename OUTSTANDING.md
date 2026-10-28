# Outstanding: needs the author

Work that is done in the repo but cannot be finished from a cloud session, or needs a
device or decision only the author has. Keep each item until it is done, then delete it.

## 1. Replace the root access keys

The Lambda deploy on 2026-10-28 ran with the account's root keys. Create an IAM user or
role limited to `lambda:UpdateFunctionCode`, `lambda:GetFunction`, `lambda:InvokeFunction`
and `lambda:GetFunctionConfiguration` on
`arn:aws:lambda:us-east-1:243130581301:function:blog-agent-*`, plus
`states:StartExecution`/`DescribeExecution` on the blog-agent state machine, then
deactivate and delete the root access keys.

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
