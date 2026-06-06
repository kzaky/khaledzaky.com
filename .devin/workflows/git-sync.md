---
description: Commit all staged/unstaged changes and push to master
---

## 1. Check current status
// turbo
Run `cd /Users/kzaky/Documents/khaledzaky.com && git status`

## 2. Review what changed
// turbo
Run `cd /Users/kzaky/Documents/khaledzaky.com && git diff --stat`

## 3. Stage all changes
// turbo
Run `cd /Users/kzaky/Documents/khaledzaky.com && git add -A`

## 4. Commit with conventional message
Use the appropriate prefix based on what changed:
- `feat:` — new feature or Lambda
- `fix:` — bug fix
- `docs:` — documentation only
- `refine:` — editorial/tone change to a blog post
- `infra:` — CloudFormation / infrastructure change
- `chore:` — maintenance, deps, cleanup

Run `cd /Users/kzaky/Documents/khaledzaky.com && git commit -m "<type>: <short summary>"`

## 5. Push to master
// turbo
Run `cd /Users/kzaky/Documents/khaledzaky.com && git push origin master`
