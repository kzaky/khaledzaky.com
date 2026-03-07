"""
Verify Lambda — Post-draft URL verification and citation-to-content matching.
Fetches every external URL in the draft markdown, extracts page metadata,
and uses an LLM to check whether each link's surrounding claim is supported
by the actual page content. Flags mismatches for human review.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

# Max bytes to read from each URL for content extraction
_MAX_FETCH_BYTES = 8192
_FETCH_TIMEOUT = 12


def _extract_links(markdown):
    """Extract all inline markdown links [text](url) from the draft.
    Returns list of (link_text, url, surrounding_sentence)."""
    links = []
    # Match [text](url) and capture a window of surrounding text
    for m in re.finditer(r'\[([^\]]+)\]\((https?://[^)]+)\)', markdown):
        link_text = m.group(1)
        url = m.group(2)
        # Get ~200 chars of surrounding context
        start = max(0, m.start() - 100)
        end = min(len(markdown), m.end() + 100)
        context = markdown[start:end].replace("\n", " ").strip()
        links.append({"link_text": link_text, "url": url, "context": context})
    return links


def _fetch_page_meta(url):
    """Fetch a URL and extract title + first ~2000 chars of visible text.
    Returns (ok, status_code, title, excerpt)."""
    try:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "User-Agent": "BlogAgent/1.0 (citation-verifier)",
                "Accept": "text/html,application/xhtml+xml,*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            status = resp.getcode()
            if status >= 400:
                return False, status, "", ""

            content_type = resp.headers.get("Content-Type", "")
            # Skip binary content (PDFs, images, etc.)
            if "pdf" in content_type or "image" in content_type:
                # For PDFs, just confirm they resolve
                return True, status, f"[PDF document at {url}]", "[Binary content — cannot extract text]"

            raw = resp.read(_MAX_FETCH_BYTES).decode("utf-8", errors="ignore")

            # Extract title
            title = ""
            title_match = re.search(r"<title[^>]*>([^<]+)</title>", raw, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()

            # Extract visible text (strip HTML tags, collapse whitespace)
            text = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            excerpt = text[:2000]

            return True, status, title, excerpt

    except urllib.error.HTTPError as e:
        logger.warning(json.dumps({"event": "verify_fetch_failed", "url": url[:80], "method": "GET", "status": e.code}))
        return False, e.code, "", ""
    except Exception as e:
        logger.warning(json.dumps({"event": "verify_fetch_failed", "url": url[:80], "error": str(e)[:200]}))
        return False, 0, "", ""


def _verify_citations_with_llm(link_reports):
    """Use LLM to verify whether each citation's claim matches the fetched page content.
    Returns list of {url, status, verdict, issue} dicts."""
    if not link_reports:
        return []

    report_block = ""
    for i, lr in enumerate(link_reports, 1):
        report_block += f"""
--- CITATION {i} ---
Link text: {lr['link_text']}
URL: {lr['url']}
Claim context: {lr['context']}
Page title: {lr.get('title', 'N/A')}
Page excerpt: {lr.get('excerpt', 'N/A')[:1000]}
HTTP status: {lr.get('status_code', 'N/A')}
"""

    prompt = f"""You are a citation verification assistant. For each citation below, determine whether
the linked page actually supports the claim made in the blog post.

{report_block}

For EACH citation, output one line in this exact format:
CITATION [number]: [PASS|FAIL|WARN|UNREACHABLE] | [brief reason]

Verdicts:
- PASS: The page content clearly supports the claim in the blog post
- FAIL: The page content contradicts the claim, or discusses a completely different topic
- WARN: The page content is tangentially related but does not directly support the specific claim
- UNREACHABLE: The page could not be fetched (use this only if HTTP status indicates failure)

Be strict. If the claim says "Article 61 requires deployer monitoring" but the page is about
"informed consent for testing," that is a FAIL, not a WARN.

Output ONLY the verdict lines, nothing else."""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "temperature": 0.0,
        "messages": [
            {"role": "user", "content": prompt}
        ],
    })

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        verdict_text = result["content"][0]["text"].strip()

        verdicts = []
        for line in verdict_text.split("\n"):
            line = line.strip()
            match = re.match(r"CITATION\s*(\d+):\s*(PASS|FAIL|WARN|UNREACHABLE)\s*\|\s*(.+)", line)
            if match:
                idx = int(match.group(1)) - 1
                if 0 <= idx < len(link_reports):
                    verdicts.append({
                        "url": link_reports[idx]["url"],
                        "link_text": link_reports[idx]["link_text"],
                        "verdict": match.group(2),
                        "reason": match.group(3).strip(),
                    })
        return verdicts

    except Exception as e:
        logger.warning(json.dumps({"event": "verify_llm_failed", "error": str(e)[:200]}))
        return []


def handler(event, context):
    """
    Input event:
    {
        "title": "...",
        "slug": "...",
        "categories": [...],
        "description": "...",
        "markdown": "complete markdown with frontmatter",
        "date": "YYYY-MM-DD",
        "research": "research notes from Research Lambda"
    }

    Output: same fields as input, plus:
    {
        "verification": {
            "total_links": N,
            "passed": N,
            "warnings": N,
            "failures": N,
            "unreachable": N,
            "details": [...]
        }
    }
    """
    title = event.get("title", "")
    markdown = event.get("markdown", "")

    request_id = getattr(context, 'aws_request_id', 'local')
    logger.info(json.dumps({"event": "verify_start", "title": title[:100], "request_id": request_id}))

    if not markdown:
        raise ValueError("No markdown provided for verification")

    # Extract all links from the draft
    links = _extract_links(markdown)
    logger.info(json.dumps({"event": "verify_links_extracted", "count": len(links), "request_id": request_id}))

    if not links:
        return {
            **event,
            "verification": {
                "total_links": 0,
                "passed": 0,
                "warnings": 0,
                "failures": 0,
                "unreachable": 0,
                "details": [],
            },
        }

    # Fetch each URL and build link reports
    link_reports = []
    for link in links:
        ok, status_code, page_title, excerpt = _fetch_page_meta(link["url"])
        link_reports.append({
            **link,
            "reachable": ok,
            "status_code": status_code,
            "title": page_title,
            "excerpt": excerpt,
        })

    reachable_count = sum(1 for lr in link_reports if lr["reachable"])
    logger.info(json.dumps({"event": "verify_fetch_complete", "reachable": reachable_count, "total": len(link_reports), "request_id": request_id}))

    # LLM verification pass
    verdicts = _verify_citations_with_llm(link_reports)

    # Build summary
    passed = sum(1 for v in verdicts if v["verdict"] == "PASS")
    warnings = sum(1 for v in verdicts if v["verdict"] == "WARN")
    failures = sum(1 for v in verdicts if v["verdict"] == "FAIL")
    unreachable = sum(1 for v in verdicts if v["verdict"] == "UNREACHABLE")

    logger.info(json.dumps({
        "event": "verify_complete",
        "total_links": len(links),
        "passed": passed,
        "warnings": warnings,
        "failures": failures,
        "unreachable": unreachable,
        "request_id": request_id,
    }))

    # Log individual failures and warnings for visibility
    for v in verdicts:
        if v["verdict"] in ("FAIL", "WARN"):
            logger.warning(json.dumps({"event": "verify_citation_issue", "verdict": v["verdict"], "url": v["url"][:80], "reason": v["reason"], "link_text": v["link_text"][:50], "request_id": request_id}))

    # Inject verification comments into the markdown for HITL review
    annotated_markdown = markdown
    for v in verdicts:
        if v["verdict"] == "FAIL":
            # Add a visible warning comment after the failing link
            old_link = f']({v["url"]})'
            replacement = f']({v["url"]})\n<!-- ⚠️ CITATION FAIL: {v["reason"]} -->'
            annotated_markdown = annotated_markdown.replace(old_link, replacement, 1)
        elif v["verdict"] == "WARN":
            old_link = f']({v["url"]})'
            replacement = f']({v["url"]})\n<!-- ⚡ CITATION WARN: {v["reason"]} -->'
            annotated_markdown = annotated_markdown.replace(old_link, replacement, 1)

    return {
        "title": event.get("title", ""),
        "slug": event.get("slug", ""),
        "categories": event.get("categories", []),
        "description": event.get("description", ""),
        "markdown": annotated_markdown,
        "date": event.get("date", ""),
        "verification": {
            "total_links": len(links),
            "passed": passed,
            "warnings": warnings,
            "failures": failures,
            "unreachable": unreachable,
            "details": verdicts,
        },
    }
