"""
Publish Lambda — After HITL approval, commits the draft blog post to GitHub
which triggers CodeBuild to build and deploy the site.
"""

import json
import os
import base64

import boto3
import urllib.request

ssm = boto3.client("ssm")
s3 = boto3.client("s3")

GITHUB_TOKEN_PARAM = os.environ.get("GITHUB_TOKEN_PARAM", "/blog-agent/github-token")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "kzaky/khaledzaky.com")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "master")
DRAFTS_BUCKET = os.environ.get("DRAFTS_BUCKET", "")


def get_github_token():
    """Retrieve GitHub token from SSM Parameter Store."""
    response = ssm.get_parameter(Name=GITHUB_TOKEN_PARAM, WithDecryption=True)
    return response["Parameter"]["Value"]


def github_api(method, path, data=None, token=None):
    """Make a GitHub API request."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def handler(event, context):
    """
    Input event:
    {
        "approved": true,
        "draft_key": "drafts/2024-01-15-my-post.md",
        "title": "...",
        "slug": "...",
        "charts": [{"s3_key": "...", "filename": "...", "public_path": "..."}]
    }

    Reads the draft from S3, commits it and any chart images to GitHub
    in a single atomic commit via the Git Trees API, triggering CodeBuild deploy.
    """
    approved = event.get("approved", False)
    if not approved:
        return {"published": False, "reason": "Not approved"}

    slug = event.get("slug", "")
    date = event.get("date", "")
    draft_key = event.get("draft_key", "")
    charts = event.get("charts", [])

    # Reconstruct the S3 key if not provided (matches notify Lambda pattern)
    if not draft_key and slug and date:
        draft_key = f"drafts/{date}-{slug}.md"

    if not draft_key or not DRAFTS_BUCKET:
        return {"published": False, "reason": "Missing draft_key or DRAFTS_BUCKET"}

    # Read draft from S3
    obj = s3.get_object(Bucket=DRAFTS_BUCKET, Key=draft_key)
    markdown = obj["Body"].read().decode("utf-8")

    # Remove draft: true from frontmatter before publishing
    markdown = markdown.replace("draft: true\n", "")

    # Commit all files atomically via Git Trees API
    token = get_github_token()

    # 1. Get the current commit SHA for the branch
    ref = github_api("GET", f"git/ref/heads/{GITHUB_BRANCH}", token=token)
    base_commit_sha = ref["object"]["sha"]
    base_commit = github_api("GET", f"git/commits/{base_commit_sha}", token=token)
    base_tree_sha = base_commit["tree"]["sha"]

    # 2. Build tree entries for all files
    tree_entries = []
    committed_files = []

    # Blog post markdown
    file_path = f"src/content/blog/{slug}.md"
    post_blob = github_api("POST", "git/blobs", data={
        "content": base64.b64encode(markdown.encode("utf-8")).decode("utf-8"),
        "encoding": "base64",
    }, token=token)
    tree_entries.append({
        "path": file_path,
        "mode": "100644",
        "type": "blob",
        "sha": post_blob["sha"],
    })
    committed_files.append(file_path)

    # Chart/diagram SVGs
    for chart in charts:
        chart_s3_key = chart.get("s3_key", "")
        chart_filename = chart.get("filename", "")
        if not chart_s3_key or not chart_filename:
            continue

        try:
            chart_obj = s3.get_object(Bucket=DRAFTS_BUCKET, Key=chart_s3_key)
            chart_content = chart_obj["Body"].read()
            chart_b64 = base64.b64encode(chart_content).decode("utf-8")
            chart_path = f"public/postimages/charts/{chart_filename}"

            blob = github_api("POST", "git/blobs", data={
                "content": chart_b64,
                "encoding": "base64",
            }, token=token)
            tree_entries.append({
                "path": chart_path,
                "mode": "100644",
                "type": "blob",
                "sha": blob["sha"],
            })
            committed_files.append(chart_path)
        except Exception as e:
            print(f"Failed to create blob for {chart_filename}: {e}")

    # 3. Create new tree
    new_tree = github_api("POST", "git/trees", data={
        "base_tree": base_tree_sha,
        "tree": tree_entries,
    }, token=token)

    # 4. Create commit
    title_text = event.get("title", slug)
    commit_msg = f"Add blog post: {title_text}"
    if len(committed_files) > 1:
        commit_msg += f"\n\n{len(committed_files)} files: post + {len(committed_files) - 1} chart(s)"

    new_commit = github_api("POST", "git/commits", data={
        "message": commit_msg,
        "tree": new_tree["sha"],
        "parents": [base_commit_sha],
    }, token=token)

    # 5. Update branch ref
    github_api("PATCH", f"git/refs/heads/{GITHUB_BRANCH}", data={
        "sha": new_commit["sha"],
    }, token=token)

    print(f"Atomic commit {new_commit['sha'][:8]} with {len(committed_files)} file(s)")

    return {
        "published": True,
        "commit_sha": new_commit["sha"],
        "file_path": file_path,
        "files_committed": committed_files,
    }
