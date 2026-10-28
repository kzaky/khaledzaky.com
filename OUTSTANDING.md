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

## 2. Check stacked tables with VoiceOver on an iPhone

On phones, tables of three or more columns stack into labelled rows, and the HTML
carries explicit ARIA table roles so Safari keeps announcing them as tables. Chromium's
accessibility tree confirms the roles; Safari itself cannot be run in the cloud session.
Open a post with a table (e.g. /blog/the-agent-has-an-identity-who-gave-it-authority/)
on an iPhone with VoiceOver and confirm it reads "table, N rows, N columns".

## 3. Ask GitHub to purge the old voice-profile commits

History was rewritten on 2026-10-28 to remove `agent/voice-profile.md`, but GitHub keeps
the old commits reachable by SHA (for example via `refs/pull/*` and cached views) until
support runs a garbage collection. Open a request at https://support.github.com/request
(category: "Removing sensitive data") for `kzaky/khaledzaky.com`: say history was rewritten
with git-filter-repo to remove `agent/voice-profile.md`, and ask them to remove cached views
and dereference the orphaned commits, including old commit 1c1a15c. Then confirm
`https://raw.githubusercontent.com/kzaky/khaledzaky.com/1c1a15c/agent/voice-profile.md` 404s.
