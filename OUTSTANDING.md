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

## 4. Get Claude 5.5 opened for this AWS account

The code is 5.5-ready and the Bedrock Marketplace agreements for Opus, Sonnet and Haiku
5.5 were accepted on 2026-10-28 (status AVAILABLE, account AUTHORIZED, entitlement
AVAILABLE), but every call still returns `AccessDeniedException: ... not available for
this account ... contact AWS Sales`. AWS gates these models per account. Ask AWS
(Support case under Bedrock, or the sales contact in the error) to enable
`anthropic.claude-{opus,sonnet,haiku}-5-5` for account 243130581301 in us-east-1. Once a
`converse` call succeeds: `agent/scripts/update-models.sh --preset 5.5`, `check-models.sh`,
`agent/deploy.sh`, then one end-to-end test. Rollback: `update-models.sh --preset 4.6`.

## 5. Redeploy the draft Lambda for the TL;DR blockquote

b901635 makes generated posts open with a `> **TL;DR:**` blockquote instead of a bold
line. It reaches the pipeline only after `agent/scripts/deploy-lambda.sh draft`.

## 6. Deploy the stage-artifact and Publish-retry change (code first, then the stack)

Running executions stay on the definition they started on, and the new code still
serves that definition's inline shapes, so an in-flight post is safe. Order matters:

1. `cd agent && for fn in research draft verify evaluate chart notify publish; do scripts/deploy-lambda.sh "$fn"; done`
2. `./deploy.sh --review <email>` and check the change set: 12 Modify, 0 Replace (state
   machine definition; research, draft, verify, evaluate, chart, notify and publish
   roles; DraftsBucket lifecycle; research and verify environment; publish timeout).
   Then `./deploy.sh <email>`.
3. On the next run, confirm `runs/<execution name>/` fills in the drafts bucket and the
   review email shows a `Draft sha256` line. See agent/README.md, "Deploy the
   stage-artifact change".
