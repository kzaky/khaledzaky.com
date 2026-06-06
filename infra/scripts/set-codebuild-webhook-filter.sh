#!/bin/bash
# Scope the CodeBuild webhook to PUSH events on master only.
#
# Why: the khaledzaky_com CodeBuild project's webhook ships with empty
# filterGroups, so it builds *every* push and pull-request event on *any*
# branch. Any PR-branch build failure then trips the `khaledzaky-codebuild-
# failure` alarm even though production (master) deploys are fine. GitHub
# Actions (.github/workflows/ci.yml) already validates pull requests, so the
# CodeBuild project only needs to run on merges to master (the deploy).
#
# This applies the same FilterGroups documented in infra/template.yaml's
# CodeBuildProject reference block. It is idempotent — re-running just
# re-applies the same filter.
#
# Usage: ./set-codebuild-webhook-filter.sh [project-name]
set -euo pipefail

PROJECT="${1:-khaledzaky_com}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

echo ">> Scoping webhook for CodeBuild project '${PROJECT}' (region ${REGION}) to PUSH on master..."
aws codebuild update-webhook \
  --project-name "${PROJECT}" \
  --region "${REGION}" \
  --filter-groups '[[{"type":"EVENT","pattern":"PUSH"},{"type":"HEAD_REF","pattern":"^refs/heads/master$"}]]' \
  --no-cli-pager

echo ">> Done. Current filter groups:"
aws codebuild batch-get-projects \
  --names "${PROJECT}" \
  --region "${REGION}" \
  --query 'projects[0].webhook.filterGroups' \
  --output json
