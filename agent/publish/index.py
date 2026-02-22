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
        "slug": "..."
    }

    Reads the draft from S3, commits it to GitHub, triggering CodeBuild deploy.
    """
    approved = event.get("approved", False)
    if not approved:
        return {"published": False, "reason": "Not approved"}

    slug = event.get("slug", "")
    date = event.get("date", "")
    draft_key = event.get("draft_key", "")

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

    # Commit to GitHub
    token = get_github_token()
    file_path = f"src/content/blog/{slug}.md"

    # Encode content as base64
    content_b64 = base64.b64encode(markdown.encode("utf-8")).decode("utf-8")

    # Check if file already exists (to get SHA for update)
    sha = None
    try:
        existing = github_api("GET", f"contents/{file_path}?ref={GITHUB_BRANCH}", token=token)
        sha = existing.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise

    # Create or update file
    commit_data = {
        "message": f"Add blog post: {event.get('title', slug)}",
        "content": content_b64,
        "branch": GITHUB_BRANCH,
    }
    if sha:
        commit_data["sha"] = sha

    result = github_api("PUT", f"contents/{file_path}", data=commit_data, token=token)

    return {
        "published": True,
        "commit_sha": result.get("commit", {}).get("sha", ""),
        "file_path": file_path,
        "html_url": result.get("content", {}).get("html_url", ""),
    }
