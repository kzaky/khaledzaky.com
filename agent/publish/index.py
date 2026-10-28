"""
Publish Lambda — After HITL approval, strips all review-only annotation comments
(`<!-- ⚠️ CITATION FAIL: -->`, `<!-- 💡 CITATION NOTE: -->`, `<!-- 🔁 CITATION REPLACED: -->`, `<!-- ⚡ INSIGHT: -->`)
from the draft, then commits the clean post and any chart SVGs to GitHub,
which triggers CodeBuild to build and deploy the site.

Note: `<!-- 🎙️ VOICE: -->` stripping is retained as a safety net for any legacy
drafts that passed through before voice annotation mode was removed.
"""

import base64
import hashlib
import json
import logging
import os
import re
import time
import urllib.request

import artifacts
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_MAX_RETRIES = 4
_RETRY_BACKOFF = 3
# Per-request socket timeout. The Lambda has 120 s: a slow call fails fast and is
# retried here, and a Lambda timeout is retried by Step Functions, which is safe
# because a replay after a successful commit makes no second commit.
_GITHUB_TIMEOUT = 10
# Ref updates rebuilt on a new HEAD after a 422 (someone pushed in between).
_MAX_REF_ATTEMPTS = 3

_SAFE_SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
# Longest slug accepted. Draft's slugify truncates to the same bound (published slugs
# run to 103 characters), so a title that passes review always passes this check.
MAX_SLUG_LEN = 120
# A CHART/DIAGRAM placeholder on its own line. Prose that mentions the syntax in
# backticks is not at a line start and survives (same anchoring as gate.PLACEHOLDER_RE).
_PLACEHOLDER_LINE = re.compile(r'^[ \t]*<!--\s*(?:CHART|DIAGRAM):.*?-->[ \t]*\n?', re.MULTILINE | re.DOTALL)
_SAFE_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_SAFE_FILENAME = re.compile(r'^[a-z0-9-]+\.svg$')



class PublishRefused(RuntimeError):
    """Publishing would be wrong, not merely failed: the state machine routes it to
    PipelineFailed instead of retrying (retrying cannot fix it)."""


class ReviewedDraftMismatch(PublishRefused):
    """The stored draft is not the one the reviewer approved."""


ssm = boto3.client("ssm")
s3 = boto3.client("s3")

GITHUB_TOKEN_PARAM = os.environ.get("GITHUB_TOKEN_PARAM", "/blog-agent/github-token")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "kzaky/khaledzaky.com")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "master")
DRAFTS_BUCKET = os.environ.get("DRAFTS_BUCKET", "")
KNOWN_SLUGS_PARAM = os.environ.get("KNOWN_SLUGS_PARAM", "/blog-agent/known-post-slugs")


def get_github_token():
    """Retrieve GitHub token from SSM Parameter Store."""
    response = ssm.get_parameter(Name=GITHUB_TOKEN_PARAM, WithDecryption=True)
    return response["Parameter"]["Value"]


def github_api(method, path, data=None, token=None):
    """Make a GitHub API request with retry on transient errors (502, 503, 504)."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode("utf-8") if data else None
    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=_GITHUB_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and attempt < _MAX_RETRIES - 1:
                wait = _RETRY_BACKOFF ** attempt
                logger.warning("GitHub API %s %s returned %d — retrying in %ds (attempt %d/%d)", method, path, e.code, wait, attempt + 1, _MAX_RETRIES)
                time.sleep(wait)
                last_error = e
            else:
                raise
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < _MAX_RETRIES - 1:
                wait = _RETRY_BACKOFF ** attempt
                logger.warning("GitHub API %s %s failed: %s — retrying in %ds (attempt %d/%d)", method, path, e, wait, attempt + 1, _MAX_RETRIES)
                time.sleep(wait)
                last_error = e
            else:
                raise
    raise last_error


def _strip_review_annotations(markdown):
    """Remove the draft flag and every review-only annotation before the post is
    committed. Pure function so the strip list is unit-testable; any new annotation
    type added to draft/verify MUST be registered here or it leaks into the site."""
    # Remove draft: true from frontmatter before publishing
    markdown = re.sub(r'^draft:\s*true\s*$', '', markdown, flags=re.MULTILINE)

    # Strip review-only annotation comments before publishing. Three rules learned
    # from annotations that leaked to the live site (halt, agent-observability and
    # governance-debt posts): the emoji prefix is optional (the Draft citation audit
    # emits none; ⚠️ is two code points so a character class never matched it), the
    # comment may wrap across lines (DOTALL), and the leading newline is consumed so
    # no blank line is left behind.
    _REVIEW_ANNOTATION = (
        r'\n?<!--\s*(?:[^\w\s<>-]+\s*)?'
        r'(?:CITATION\s+(?:FAIL|WARN|NOTE|REPLACED)|INSIGHT|ENTITY\s+CHECK|STRUCTURE|CITATION_AUDIT|STRUCTURE_AUDIT)'
        r'\b.*?-->'
    )
    markdown = re.sub(_REVIEW_ANNOTATION, '', markdown, flags=re.DOTALL)
    # Strip VOICE annotations — handles both inline (<!-- 🎙️ VOICE: ... -->) and
    # multi-line block form (<!-- 🎙️ VOICE\n...\n-->) that Haiku sometimes emits.
    markdown = re.sub(r'<!-- 🎙️ VOICE.*?-->\n?', '', markdown, flags=re.DOTALL)
    # Strip VOICE_AUDIT scaffolding — the voice audit model sometimes appends an
    # "Issues fixed:" markdown block after the <!-- VOICE_AUDIT: ... --> comment.
    # The draft Lambda strips this too, but belt-and-suspenders here prevents leaks.
    markdown = re.sub(r'\n*<!--\s*VOICE_AUDIT:.*', '', markdown, flags=re.DOTALL)

    # Safety net: strip any leading unclosed HTML comment after frontmatter.
    # An unclosed <!-- wrapping the body makes the entire page invisible.
    # Catches both the old Haiku wrapper pattern and the VOICE block without -->.
    # Only an UNCLOSED comment (no --> on its line) is stripped; a closed comment right
    # after the frontmatter is legitimate content and must survive.
    markdown = re.sub(r'(---\n+)\s*<!--(?![^\n]*-->)[^\n]*\n', r'\1', markdown)
    return markdown


def _strip_unrendered_placeholders(markdown):
    """Backstop for <!-- CHART: --> / <!-- DIAGRAM: --> placeholders the Chart Lambda
    left behind. One that reaches the site fails check:render, which stops the deploy
    of every page, so Publish removes it and logs the loss. Returns (markdown, count)."""
    found = _PLACEHOLDER_LINE.findall(markdown)
    if not found:
        return markdown, 0
    logger.warning(json.dumps({"event": "publish_stripped_placeholders", "count": len(found),
                               "placeholders": [f.strip()[:120] for f in found[:5]]}))
    return _PLACEHOLDER_LINE.sub("", markdown), len(found)


def _git_blob_sha(content_bytes):
    """The SHA git (and the GitHub contents API) gives a blob with these bytes."""
    return hashlib.sha1(b"blob %d\0" % len(content_bytes) + content_bytes).hexdigest()


def _existing_post_sha(file_path, token, ref=None):
    """Blob SHA of file_path at `ref` (default: the branch HEAD), or None when it does not exist."""
    try:
        meta = github_api("GET", f"contents/{file_path}?ref={ref or GITHUB_BRANCH}", token=token)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    if not isinstance(meta, dict) or not meta.get("sha"):
        raise RuntimeError(f"Publish aborted: cannot tell whether {file_path} already exists on {GITHUB_BRANCH}")
    return meta["sha"]


def _guard_overwrite(slug, file_path, markdown, event, token, existing_sha=False):
    """Refuse to replace an existing post unless the event says this is a revision of
    that same post.

    The pipeline only writes new posts: the Revise loop revises the draft before
    approval, and nothing in the state machine marks a run as an edit of a published
    post. So a slug that already exists on the branch means a new title slugified to the
    name of an old post, and committing would silently replace that post. A run that is
    meant to replace it must say so with `"revision_of": "<slug>"`. A retry that would
    write byte-identical content is allowed (the commit changes nothing).
    """
    if existing_sha is False:
        existing_sha = _existing_post_sha(file_path, token)
    if existing_sha is None:
        return
    if event.get("revision_of") == slug:
        logger.info(json.dumps({"event": "publish_revision", "slug": slug}))
        return
    if existing_sha == _git_blob_sha(markdown.encode("utf-8")):
        logger.info(json.dumps({"event": "publish_identical_retry", "slug": slug}))
        return
    raise PublishRefused(
        f"Publish aborted: {file_path} already exists on {GITHUB_BRANCH} and this run is not marked "
        f"as a revision of it, so committing would replace the published post. Give the new post a "
        f"different slug, or rerun Publish with \"revision_of\": \"{slug}\" if replacing it is intended."
    )


def _load_reviewed_draft(event):
    """Return (markdown, key) for the draft the reviewer approved.

    The artifact-based definition passes review_key and review_sha256 (recorded by the
    Chart stage, stored by Notify before the email went out). Publish reads exactly that
    object and refuses anything whose hash differs, so a later write to S3 cannot change
    what goes live. A run on the previous definition has neither and falls back to the
    old drafts/<date>-<slug>.md key, unverified, as before.
    """
    review_key = event.get("review_key", "")
    if review_key:
        expected = event.get("review_sha256", "")
        rid = artifacts.run_id(event)
        if not expected:
            raise ReviewedDraftMismatch(f"{review_key}: no review_sha256 in the Publish input")
        if not rid or not review_key.startswith(artifacts.run_prefix(rid)):
            raise ReviewedDraftMismatch(f"review_key {review_key!r} is not under this run's prefix")
        body = s3.get_object(Bucket=DRAFTS_BUCKET, Key=review_key)["Body"].read()
        actual = artifacts.sha256_hex(body)
        if actual != expected:
            raise ReviewedDraftMismatch(
                f"{review_key}: sha256 {actual[:12]} is not the reviewed draft's {expected[:12]}; refusing to publish")
        return body.decode("utf-8"), review_key

    draft_key = event.get("draft_key", "")
    slug, date = event.get("slug", ""), event.get("date", "")
    if not draft_key and slug and date:
        draft_key = f"drafts/{date}-{slug}.md"
    if not draft_key or not DRAFTS_BUCKET:
        raise RuntimeError(f"Missing draft_key ({draft_key!r}) or DRAFTS_BUCKET ({DRAFTS_BUCKET!r})")
    logger.warning(json.dumps({"event": "publish_unverified_legacy_draft", "key": draft_key}))
    obj = s3.get_object(Bucket=DRAFTS_BUCKET, Key=draft_key)
    return obj["Body"].read().decode("utf-8"), draft_key


def _commit_message(title_text, committed_files, execution):
    msg = f"Add blog post: {title_text}"
    if len(committed_files) > 1:
        msg += f"\n\n{len(committed_files)} files: post + {len(committed_files) - 1} chart(s)"
    if execution:
        # A trailer, so `git log --grep "Execution: <name>"` finds the run's commit.
        msg += f"\n\nExecution: {execution}"
    return msg


def handler(event, context):
    """
    Input event (artifact-based definition):
    {
        "approved": true,
        "title": "...", "slug": "...", "date": "YYYY-MM-DD",
        "charts": [{"s3_key": "...", "filename": "...", "public_path": "..."}],
        "run_id": "<execution name>",
        "review_key": "runs/<execution name>/review-<sha256>.md",
        "review_sha256": "<sha256 of the reviewed draft>"
    }
    A run on the previous definition sends neither run_id nor the review fields.

    Commits the post and its charts in one commit via the Git Trees API, which triggers
    the CodeBuild deploy. Safe to retry or redrive: if the post at HEAD already has the
    blob this run would write, it returns success without a second commit, and a ref
    update that loses a race (422) is rebuilt on the new HEAD.
    """
    approved = event.get("approved", False)
    if not approved:
        raise ValueError("Draft was not approved")

    slug = event.get("slug", "")
    date = event.get("date", "")
    charts = event.get("charts", [])
    execution = event.get("run_id", "")

    # Validate slug and date to prevent path traversal
    if slug and not _SAFE_SLUG.match(slug):
        raise ValueError(f"Invalid slug: {slug!r} contains disallowed characters")
    if len(slug) > MAX_SLUG_LEN:
        raise ValueError(f"Invalid slug: {len(slug)} characters, longer than {MAX_SLUG_LEN}")
    if date and not _SAFE_DATE.match(date):
        raise ValueError(f"Invalid date format: {date!r} — expected YYYY-MM-DD")
    if not DRAFTS_BUCKET:
        raise RuntimeError("DRAFTS_BUCKET not configured")

    markdown, draft_key = _load_reviewed_draft(event)

    markdown = _strip_review_annotations(markdown)
    markdown, _ = _strip_unrendered_placeholders(markdown)
    markdown = re.sub(r'\n-->\s*$', '', markdown)

    # Deduplicate image tags — Chart Lambda runs twice (pre-Verify and post-Revise);
    # if a revision preserves an existing image while also generating a new placeholder,
    # the same filename can appear twice. Keep the first occurrence, remove subsequent ones.
    seen_images = set()
    deduped_lines = []
    for line in markdown.splitlines():
        img_match = re.match(r'!\[.*?\]\((/postimages/[^\)]+)\)', line.strip())
        if img_match:
            img_path = img_match.group(1)
            if img_path in seen_images:
                logger.warning("Removing duplicate image tag: %s", img_path)
                continue
            seen_images.add(img_path)
        deduped_lines.append(line)
    markdown = "\n".join(deduped_lines)

    # Cross-check: every /postimages/charts/ image referenced in the markdown must have
    # a corresponding entry in the charts list. Missing charts → broken images in production.
    committed_chart_filenames = {c.get("filename", "") for c in charts if c.get("filename")}
    referenced_chart_images = re.findall(r'!\[.*?\]\(/postimages/charts/([^)]+)\)', markdown)
    missing_charts = [img for img in referenced_chart_images if img not in committed_chart_filenames]
    if missing_charts:
        logger.error(json.dumps({
            "event": "publish_missing_charts",
            "missing": missing_charts,
            "committed": sorted(committed_chart_filenames),
            "slug": slug,
        }))
        raise PublishRefused(
            f"Publish aborted: markdown references {len(missing_charts)} chart file(s) not in "
            f"the charts list: {', '.join(missing_charts)}"
        )

    token = get_github_token()
    file_path = f"src/content/blog/{slug}.md"
    markdown_bytes = markdown.encode("utf-8")
    post_sha = _git_blob_sha(markdown_bytes)

    def _already_published(existing_sha):
        if existing_sha != post_sha:
            return None
        # A replay after a successful commit (Lambda timeout, Step Functions retry,
        # redrive): the post at HEAD is byte-identical, so a second commit would only
        # re-trigger the deploy. Charts went in the same commit as the post.
        logger.info(json.dumps({"event": "publish_already_committed", "slug": slug, "execution": execution}))
        if slug:
            _update_known_slugs(slug)
        return {"published": True, "already_published": True, "commit_sha": None,
                "file_path": file_path, "files_committed": [], "draft_key": draft_key}

    # Idempotency first (no blob uploads on a replay), then the overwrite guard.
    existing_sha = _existing_post_sha(file_path, token)
    done = _already_published(existing_sha)
    if done:
        return done
    _guard_overwrite(slug, file_path, markdown, event, token, existing_sha=existing_sha)

    # Blobs are content-addressed, so they are uploaded once and reused if the ref
    # update below has to be rebuilt on a newer HEAD.
    tree_entries = []
    committed_files = []
    post_blob = github_api("POST", "git/blobs", data={
        "content": base64.b64encode(markdown_bytes).decode("utf-8"),
        "encoding": "base64",
    }, token=token)
    tree_entries.append({"path": file_path, "mode": "100644", "type": "blob", "sha": post_blob["sha"]})
    committed_files.append(file_path)

    # Chart/diagram SVGs
    for chart in charts:
        chart_s3_key = chart.get("s3_key", "")
        chart_filename = chart.get("filename", "")
        if not chart_s3_key or not chart_filename:
            continue

        # Validate chart filename to prevent path traversal
        if not _SAFE_FILENAME.match(chart_filename):
            if chart_filename in referenced_chart_images:
                raise PublishRefused(f"Publish aborted: the post references chart {chart_filename!r}, whose filename is unsafe")
            logger.warning("Skipping chart with unsafe filename: %s", chart_filename)
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
            # The post references this file: committing without it ships a broken image.
            logger.error("Failed to create blob for %s: %s", chart_filename, e)
            raise RuntimeError(f"Publish aborted: could not upload chart {chart_filename}: {e}") from e

    commit_msg = _commit_message(event.get("title", slug), committed_files, execution)

    for attempt in range(1, _MAX_REF_ATTEMPTS + 1):
        ref = github_api("GET", f"git/ref/heads/{GITHUB_BRANCH}", token=token)
        base_commit_sha = ref["object"]["sha"]
        if attempt > 1:
            # HEAD moved under us. It may now hold this very post (an earlier attempt
            # whose response was lost) or another post at the same path.
            existing_sha = _existing_post_sha(file_path, token, ref=base_commit_sha)
            done = _already_published(existing_sha)
            if done:
                return done
            _guard_overwrite(slug, file_path, markdown, event, token, existing_sha=existing_sha)
        base_commit = github_api("GET", f"git/commits/{base_commit_sha}", token=token)
        new_tree = github_api("POST", "git/trees", data={
            "base_tree": base_commit["tree"]["sha"],
            "tree": tree_entries,
        }, token=token)
        new_commit = github_api("POST", "git/commits", data={
            "message": commit_msg,
            "tree": new_tree["sha"],
            "parents": [base_commit_sha],
        }, token=token)
        try:
            github_api("PATCH", f"git/refs/heads/{GITHUB_BRANCH}", data={"sha": new_commit["sha"]}, token=token)
            break
        except urllib.error.HTTPError as e:
            # 422: not a fast-forward, someone pushed between the GET and the PATCH.
            if e.code != 422 or attempt == _MAX_REF_ATTEMPTS:
                raise
            logger.warning(json.dumps({"event": "publish_ref_moved", "attempt": attempt, "slug": slug}))

    logger.info(json.dumps({"event": "published", "commit": new_commit['sha'][:8], "files": len(committed_files),
                            "slug": slug, "execution": execution}))

    # Update the known slugs list in SSM so the Draft Lambda always has current internal link targets
    if slug:
        _update_known_slugs(slug)

    return {
        "published": True,
        "already_published": False,
        "commit_sha": new_commit["sha"],
        "file_path": file_path,
        "files_committed": committed_files,
        "draft_key": draft_key,
    }


def _update_known_slugs(new_slug):
    """Append new_slug to the /blog-agent/known-post-slugs SSM parameter.
    Draft Lambda reads this at startup to avoid fabricating internal links."""
    try:
        try:
            resp = ssm.get_parameter(Name=KNOWN_SLUGS_PARAM)
            existing = resp["Parameter"]["Value"]
            slugs = [s.strip() for s in existing.split(",") if s.strip()]
        except ssm.exceptions.ParameterNotFound:
            slugs = []

        if new_slug not in slugs:
            slugs.append(new_slug)
            ssm.put_parameter(
                Name=KNOWN_SLUGS_PARAM,
                Value=",".join(slugs),
                Type="String",
                Overwrite=True,
            )
            logger.info(json.dumps({"event": "known_slugs_updated", "slug": new_slug, "total": len(slugs)}))
        else:
            logger.info(json.dumps({"event": "known_slugs_unchanged", "slug": new_slug}))
    except Exception as e:
        logger.warning(json.dumps({"event": "known_slugs_update_failed", "error": str(e)[:200]}))
