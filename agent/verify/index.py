"""
Verify Lambda — Post-draft URL verification, citation-to-content matching, and auto-repair.

Flow:
1. Extract all [text](url) links from the draft
2. Fetch each URL in parallel, extract page title + text excerpt
3. LLM (Haiku) checks claim↔content match: PASS / FAIL / WARN / UNREACHABLE
4. Auto-repair: for each FAIL/WARN, Tavily searches for a better source and
   Haiku selects the best replacement URL. Swaps it silently in the markdown.
5. Remaining unrepaired FAIL/WARN are annotated with HTML comments for human review.
   Publish Lambda strips those comments before committing to GitHub.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
HAIKU_MODEL_ID = os.environ.get("HAIKU_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
TAVILY_API_KEY_PARAM = os.environ.get("TAVILY_API_KEY_PARAM", "/blog-agent/tavily-api-key")
_tavily_key_cache = [None]

# Max bytes to read from each URL for content extraction
_MAX_FETCH_BYTES = 8192
_FETCH_TIMEOUT = 12


def _get_tavily_key():
    """Retrieve Tavily API key from SSM, cached after first call."""
    if _tavily_key_cache[0] is not None:
        return _tavily_key_cache[0]
    try:
        resp = ssm.get_parameter(Name=TAVILY_API_KEY_PARAM, WithDecryption=True)
        _tavily_key_cache[0] = resp["Parameter"]["Value"]
        return _tavily_key_cache[0]
    except Exception as e:
        logger.warning(json.dumps({"event": "tavily_key_unavailable", "error": str(e)[:100]}))
        return None


def _tavily_search_for_claim(query):
    """Search Tavily for sources relevant to a specific claim.
    Returns list of {url, title, content} dicts."""
    api_key = _get_tavily_key()
    if not api_key:
        return []
    try:
        payload = json.dumps({
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": 5,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("results", [])
    except Exception as e:
        logger.warning(json.dumps({"event": "repair_search_failed", "error": str(e)[:200]}))
        return []


def _find_replacement_url(claim_context, failed_url, search_results):
    """Use Haiku to select the best replacement URL for a failing citation.
    Returns a URL string, or None if no good replacement found."""
    if not search_results:
        return None
    candidates = "\n".join(
        f"{i+1}. URL: {r.get('url', '')}\n   Title: {r.get('title', '')}\n   Snippet: {r.get('content', '')[:300]}"
        for i, r in enumerate(search_results[:5])
    )
    prompt = f"""You are a citation repair assistant. A blog post citation was flagged as not supporting its claim.

CLAIM (what the blog post says):
{claim_context[:500]}

ORIGINAL URL (flagged):
{failed_url}

CANDIDATE REPLACEMENT SOURCES:
{candidates}

Choose the candidate that BEST supports the specific claim.
- Output ONLY the URL of the best match, nothing else.
- If none clearly support the claim, output: NONE"""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": prompt}],
    })
    try:
        response = bedrock.invoke_model(
            modelId=HAIKU_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        chosen = json.loads(response["body"].read())["content"][0]["text"].strip()
        if chosen == "NONE" or not chosen.startswith("http"):
            return None
        candidate_urls = [r.get("url", "") for r in search_results[:5]]
        return chosen if chosen in candidate_urls else None
    except Exception as e:
        logger.warning(json.dumps({"event": "repair_llm_failed", "error": str(e)[:200]}))
        return None


def _repair_citations(verdicts, markdown, request_id):
    """For each FAIL/WARN verdict, search Tavily for a better source and swap the URL.
    Repaired citations are marked with verdict=REPAIRED. Unrepaired keep FAIL/WARN
    for human annotation. Returns (updated_markdown, updated_verdicts)."""
    issues = [(i, v) for i, v in enumerate(verdicts) if v["verdict"] in ("FAIL", "WARN")]
    if not issues:
        return markdown, verdicts

    logger.info(json.dumps({"event": "repair_start", "count": len(issues), "request_id": request_id}))
    updated_verdicts = list(verdicts)
    updated_markdown = markdown

    def _repair_one(idx_verdict):
        i, v = idx_verdict
        query = v.get("context", v["link_text"])[:200]
        results = _tavily_search_for_claim(query)
        replacement = _find_replacement_url(v.get("context", ""), v["url"], results)
        return i, v, replacement

    with ThreadPoolExecutor(max_workers=min(len(issues), 4)) as executor:
        futures = [executor.submit(_repair_one, iv) for iv in issues]
        for future in as_completed(futures):
            try:
                i, v, replacement_url = future.result()
                if replacement_url and replacement_url != v["url"]:
                    old_link = f']({v["url"]})'
                    new_link = f']({replacement_url})'
                    if old_link in updated_markdown:
                        updated_markdown = updated_markdown.replace(old_link, new_link, 1)
                        updated_verdicts[i] = {**v, "verdict": "REPAIRED", "replacement_url": replacement_url}
                        logger.info(json.dumps({
                            "event": "citation_repaired",
                            "original_url": v["url"][:80],
                            "replacement_url": replacement_url[:80],
                            "request_id": request_id,
                        }))
                else:
                    logger.info(json.dumps({"event": "repair_no_replacement", "url": v["url"][:80], "request_id": request_id}))
            except Exception as e:
                logger.warning(json.dumps({"event": "repair_error", "error": str(e)[:200], "request_id": request_id}))

    repaired = sum(1 for v in updated_verdicts if v.get("verdict") == "REPAIRED")
    logger.info(json.dumps({"event": "repair_complete", "repaired": repaired, "remaining_issues": len(issues) - repaired, "request_id": request_id}))
    return updated_markdown, updated_verdicts


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
                        "context": link_reports[idx].get("context", ""),
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

    # Fetch each URL in parallel and build link reports
    link_reports = [None] * len(links)
    with ThreadPoolExecutor(max_workers=min(len(links), 8)) as executor:
        future_to_idx = {
            executor.submit(_fetch_page_meta, link["url"]): i
            for i, link in enumerate(links)
        }
        for future in as_completed(future_to_idx):
            i = future_to_idx[future]
            try:
                ok, status_code, page_title, excerpt = future.result()
            except Exception as e:
                logger.warning("URL fetch raised in thread: %s", e)
                ok, status_code, page_title, excerpt = False, 0, "", ""
            link_reports[i] = {
                **links[i],
                "reachable": ok,
                "status_code": status_code,
                "title": page_title,
                "excerpt": excerpt,
            }

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

    # Auto-repair: attempt to find better sources for FAIL/WARN citations
    markdown, verdicts = _repair_citations(verdicts, markdown, request_id)

    # Recompute summary after repairs
    passed = sum(1 for v in verdicts if v["verdict"] == "PASS")
    warnings = sum(1 for v in verdicts if v["verdict"] == "WARN")
    failures = sum(1 for v in verdicts if v["verdict"] == "FAIL")
    unreachable = sum(1 for v in verdicts if v["verdict"] == "UNREACHABLE")
    repaired = sum(1 for v in verdicts if v["verdict"] == "REPAIRED")

    # Annotate remaining unrepaired FAIL/WARN for human review
    # (Publish Lambda strips these before committing to GitHub)
    annotated_markdown = markdown
    for v in verdicts:
        if v["verdict"] == "FAIL":
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
            "repaired": repaired,
            "details": verdicts,
        },
    }
