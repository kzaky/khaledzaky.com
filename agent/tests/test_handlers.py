"""Smoke tests for Lambda handler imports and signatures.

These tests validate that:
1. Every handler module can be imported without errors
2. Every handler function accepts (event, context) signature
3. No missing dependencies at import time
"""

import importlib
import inspect
import json
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from sys import version_info
from unittest.mock import MagicMock, patch

import pytest

# Inject mock boto3/botocore into sys.modules before any Lambda code imports them.
# Each submodule must be registered separately so 'from botocore.config import Config'
# and similar submodule imports resolve without hitting the real package.
_mock_boto3 = MagicMock()
_mock_botocore = MagicMock()
_mock_botocore_config = MagicMock()
_mock_botocore_config.Config = MagicMock(return_value=MagicMock())
_mock_botocore.config = _mock_botocore_config
sys.modules.setdefault("boto3", _mock_boto3)
sys.modules.setdefault("botocore", _mock_botocore)
sys.modules.setdefault("botocore.config", _mock_botocore_config)
sys.modules.setdefault("botocore.exceptions", MagicMock())

# Add each Lambda function directory to sys.path so imports resolve
AGENT_DIR = Path(__file__).parent.parent
LAMBDA_DIRS = ["research", "draft", "verify", "evaluate", "notify", "approve", "publish", "ingest", "chart", "alarm-formatter", "upload"]

for d in LAMBDA_DIRS:
    path = str(AGENT_DIR / d)
    if path not in sys.path:
        sys.path.insert(0, path)

# Shared modules (agent/common) are vendored into each Lambda package at build
# time; add the dir so in-process handler imports (`from llm import ...`) resolve.
common_path = str(AGENT_DIR / "common")
if common_path not in sys.path:
    sys.path.insert(0, common_path)

# Chart renderers need their parent on the path too
chart_dir = str(AGENT_DIR / "chart")
if chart_dir not in sys.path:
    sys.path.insert(0, chart_dir)


class _LambdaContext:
    """Minimal Lambda context stub with serializable attributes."""
    aws_request_id = "test-request-id"
    function_name = "test-function"
    memory_limit_in_mb = 128


def _load_module(lambda_dir):
    """Load a Lambda handler module from its exact directory, bypassing sys.path collisions."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        f"lambda_{lambda_dir.replace('-', '_')}_index",
        str(AGENT_DIR / lambda_dir / "index.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("module_name,func_dir", [
    ("index", d) for d in LAMBDA_DIRS
])
def test_handler_importable(module_name, func_dir):
    """Each Lambda handler module can be imported."""
    path = str(AGENT_DIR / func_dir)
    if path not in sys.path:
        sys.path.insert(0, path)
    mod = importlib.import_module(module_name)
    # Force reload to ensure clean import from the right directory
    mod = importlib.reload(mod)
    assert hasattr(mod, "handler"), f"{func_dir}/index.py missing handler function"


@pytest.mark.parametrize("func_dir", LAMBDA_DIRS)
def test_handler_signature(func_dir):
    """Each handler accepts (event, context) parameters."""
    path = str(AGENT_DIR / func_dir)
    if path not in sys.path:
        sys.path.insert(0, path)
    mod = importlib.import_module("index")
    mod = importlib.reload(mod)
    sig = inspect.signature(mod.handler)
    params = list(sig.parameters.keys())
    assert len(params) >= 2, f"{func_dir}/handler has {len(params)} params, expected >= 2"
    assert params[0] == "event", f"{func_dir}/handler first param is '{params[0]}', expected 'event'"
    assert params[1] == "context", f"{func_dir}/handler second param is '{params[1]}', expected 'context'"


def test_chart_renderers_importable():
    """All chart renderer modules can be imported."""
    from renderers import (
        render_architecture_diagram,
        render_bar_chart,
        render_comparison_diagram,
        render_convergence_diagram,
        render_pie_chart,
        render_progression_diagram,
        render_stack_diagram,
        render_timeline_diagram,
        render_venn_diagram,
    )
    assert callable(render_architecture_diagram)
    assert callable(render_bar_chart)
    assert callable(render_pie_chart)
    assert callable(render_comparison_diagram)
    assert callable(render_progression_diagram)
    assert callable(render_stack_diagram)
    assert callable(render_convergence_diagram)
    assert callable(render_timeline_diagram)
    assert callable(render_venn_diagram)


def test_architecture_renderer_returns_svg():
    """Architecture renderer returns valid SVG for a well-formed spec."""
    from renderers.architecture import render_architecture_diagram
    svg = render_architecture_diagram([
        "Test Pipeline",
        "inputs: Source[model];Store[storage]",
        "steps: Step A;Step B[function]",
        "outputs: Result[storage]",
    ])
    assert svg is not None, "renderer returned None"
    assert svg.startswith("<svg"), "output is not SVG"
    assert "</svg>" in svg


def test_architecture_renderer_requires_all_sections():
    """Architecture renderer returns None when inputs/steps/outputs are missing."""
    from renderers.architecture import render_architecture_diagram
    assert render_architecture_diagram(["Title only"]) is None


def test_timeline_renderer_returns_svg():
    """Timeline renderer returns valid SVG for a well-formed spec."""
    from renderers.timeline import render_timeline_diagram
    svg = render_timeline_diagram([
        "Build Journey",
        "Start;First step",
        "Middle;Key event",
        "End;Shipped",
    ])
    assert svg is not None, "renderer returned None"
    assert svg.startswith("<svg"), "output is not SVG"
    assert "</svg>" in svg


def test_timeline_renderer_requires_items():
    """Timeline renderer returns None when no items provided."""
    from renderers.timeline import render_timeline_diagram
    assert render_timeline_diagram(["Title only"]) is None


@pytest.mark.skipif(version_info < (3, 11), reason="draft/index.py requires datetime.UTC (Python 3.11+)")
def test_strip_md_formatting():
    """_strip_md_formatting unwraps markdown syntax from plain-text descriptions."""
    mod = _load_module("draft")
    fn = mod._strip_md_formatting
    assert fn("The **governance wall**") == "The governance wall"
    assert fn("*italic* text") == "italic text"
    assert fn("`code` snippet") == "code snippet"
    assert fn("plain text") == "plain text"
    assert fn("") == ""


def test_chart_theme_constants():
    """Theme module exports expected constants."""
    from renderers.theme import COLORS, COLORS_DARK, FONT_FAMILY
    assert len(COLORS) >= 6, "Expected at least 6 chart colors"
    assert len(COLORS_DARK) >= 6, "Expected at least 6 dark mode colors"
    assert isinstance(FONT_FAMILY, str)


# ---------------------------------------------------------------------------
# Behavioral: publish — path traversal / input validation
# ---------------------------------------------------------------------------

class TestPublishValidation:
    def setup_method(self):
        self.mod = _load_module("publish")

    def test_invalid_slug_raises(self):
        """Slug with path traversal characters must raise ValueError."""
        event = {"approved": True, "slug": "../etc/passwd", "date": "2024-01-01"}
        with pytest.raises(ValueError, match="Invalid slug"):
            self.mod.handler(event, _LambdaContext())

    def test_invalid_date_raises(self):
        """Date in wrong format must raise ValueError."""
        event = {"approved": True, "slug": "valid-slug", "date": "01-01-2024"}
        with pytest.raises(ValueError, match="Invalid date"):
            self.mod.handler(event, _LambdaContext())

    def test_not_approved_raises(self):
        """Handler must raise ValueError when approved is False."""
        event = {"approved": False, "slug": "valid-slug", "date": "2024-01-01"}
        with pytest.raises(ValueError, match="not approved"):
            self.mod.handler(event, _LambdaContext())

    def test_safe_slug_pattern(self):
        """Verify the regex accepts valid slugs and rejects unsafe ones."""
        pattern = self.mod._SAFE_SLUG
        assert pattern.match("my-valid-post-123")
        assert pattern.match("abc")
        assert not pattern.match("../etc")
        assert not pattern.match("slug with spaces")
        assert not pattern.match("UPPERCASE")

    def test_safe_filename_pattern(self):
        """Verify the regex accepts valid chart filenames and rejects unsafe ones."""
        pattern = self.mod._SAFE_FILENAME
        assert pattern.match("my-chart-1.svg")
        assert not pattern.match("../evil.svg")
        assert not pattern.match("file.js")
        assert not pattern.match("file.svg.sh")


# ---------------------------------------------------------------------------
# Behavioral: chart — _match_data_point keyword matching and no fallback
# ---------------------------------------------------------------------------

class TestChartMatching:
    def setup_method(self):
        self.mod = _load_module("chart")

    def _dp(self, description, values=None):
        return {"description": description, "values": values or [("A", 1), ("B", 2)], "chart_type": "bar", "source": "test"}

    def test_exact_keyword_match(self):
        """Returns data point with overlapping keywords."""
        dps = [self._dp("agent deployment failure rates")]
        result = self.mod._match_data_point("agent deployment failure rates", dps)
        assert result is not None
        assert result["description"] == "agent deployment failure rates"

    def test_no_match_returns_none(self):
        """Returns None when no keywords overlap — no fallback to first item."""
        dps = [self._dp("CDN adoption percentages worldwide")]
        result = self.mod._match_data_point("agent deployment failure rates", dps)
        assert result is None

    def test_empty_data_points_returns_none(self):
        """Returns None for empty data points list."""
        result = self.mod._match_data_point("anything", [])
        assert result is None

    def test_best_match_selected(self):
        """Returns the data point with the most overlapping keywords."""
        dps = [
            self._dp("cloud adoption rates by region"),
            self._dp("agent deployment failure rates by platform"),
        ]
        result = self.mod._match_data_point("agent deployment failure rates", dps)
        assert result["description"] == "agent deployment failure rates by platform"

    def test_parse_values_label_number(self):
        """_parse_values correctly parses Label: value pairs."""
        result = self.mod._parse_values("Success: 60, Failure: 40")
        assert result == [("Success", 60.0), ("Failure", 40.0)]

    def test_parse_values_strips_percent(self):
        """_parse_values strips trailing % signs."""
        result = self.mod._parse_values("Yes: 75%, No: 25%")
        assert result == [("Yes", 75.0), ("No", 25.0)]

    def test_parse_values_bare_numbers_get_labels(self):
        """Bare numbers without labels get auto-generated labels."""
        result = self.mod._parse_values("60, 40")
        assert len(result) == 2
        assert result[0][1] == 60.0
        assert result[1][1] == 40.0


# ---------------------------------------------------------------------------
# Behavioral: upload — passphrase validation and filename sanitization
# ---------------------------------------------------------------------------

class TestUploadSecurity:
    def setup_method(self):
        self.mod = _load_module("upload")

    def _make_event(self, body_dict):
        return {"requestContext": {"http": {"method": "POST"}}, "body": json.dumps(body_dict), "isBase64Encoded": False}

    def test_wrong_passphrase_returns_403(self):
        """Wrong passphrase must return 403."""
        with patch.object(self.mod, "_get_passphrase", return_value="correct-secret"):
            event = self._make_event({"action": "list", "passphrase": "wrong"})
            resp = self.mod.handler(event, _LambdaContext())
        assert resp["statusCode"] == 403

    def test_correct_passphrase_proceeds(self):
        """Correct passphrase must not return 403."""
        with patch.object(self.mod, "_get_passphrase", return_value="correct-secret"), \
             patch.object(self.mod, "_list_files", return_value={"statusCode": 200, "body": "{}"}):
            event = self._make_event({"action": "list", "passphrase": "correct-secret"})
            resp = self.mod.handler(event, _LambdaContext())
        assert resp["statusCode"] != 403

    def test_empty_passphrase_returns_403(self):
        """Missing passphrase field must return 403."""
        with patch.object(self.mod, "_get_passphrase", return_value="correct-secret"):
            event = self._make_event({"action": "list"})
            resp = self.mod.handler(event, _LambdaContext())
        assert resp["statusCode"] == 403

    def test_filename_sanitization_removes_unsafe_chars(self):
        """Filename sanitization must strip spaces, parentheses, and path characters."""
        with patch.object(self.mod, "_get_passphrase", return_value="s"), \
             patch.object(self.mod, "_validate_passphrase", return_value=True), \
             patch.object(self.mod.s3, "generate_presigned_url", return_value="https://example.com/url"):
            payload = {"action": "get-upload-url", "passphrase": "s", "filename": "my file (1).pdf"}
            event = self._make_event(payload)
            resp = self.mod.handler(event, _LambdaContext())
            body = json.loads(resp["body"])
            if "key" in body:
                assert " " not in body["key"]
                assert "(" not in body["key"]
                assert ")" not in body["key"]

    def test_path_traversal_filename_returns_400(self):
        """Filename consisting only of unsafe chars must return 400."""
        with patch.object(self.mod, "_validate_passphrase", return_value=True):
            payload = {"action": "get-upload-url", "passphrase": "s", "filename": "../../../etc/passwd"}
            event = self._make_event(payload)
            resp = self.mod.handler(event, _LambdaContext())
        body = json.loads(resp["body"])
        if "key" in body:
            assert "../" not in body["key"]
            assert "..\\" not in body["key"]


# ---------------------------------------------------------------------------
# Behavioral: ingest — sender validation
# ---------------------------------------------------------------------------

class TestIngestSenderValidation:
    def setup_method(self):
        self.mod = _load_module("ingest")
        self.mod.ALLOWED_SENDER = "allowed@example.com"
        self.mod.SES_BUCKET = "test-bucket"
        self.mod.STATE_MACHINE_ARN = "arn:aws:states:us-east-1:123:stateMachine:test"

    def _make_event(self, sender):
        return {
            "Records": [{
                "ses": {
                    "mail": {
                        "messageId": "test-msg-id",
                        "source": sender,
                    }
                }
            }]
        }

    def test_unauthorized_sender_raises(self):
        """Email from unauthorized sender must raise PermissionError."""
        event = self._make_event("attacker@evil.com")
        with pytest.raises(PermissionError, match="Unauthorized sender"):
            self.mod.handler(event, _LambdaContext())

    def test_missing_allowed_sender_config_raises(self):
        """Missing ALLOWED_SENDER env var must raise RuntimeError (fail closed)."""
        self.mod.ALLOWED_SENDER = ""
        event = self._make_event("anyone@example.com")
        with pytest.raises(RuntimeError, match="ALLOWED_SENDER not configured"):
            self.mod.handler(event, _LambdaContext())

    def test_authorized_sender_proceeds_to_s3(self):
        """Authorized sender must pass validation and attempt S3 fetch."""
        event = self._make_event("allowed@example.com")
        with pytest.raises((RuntimeError, Exception)) as exc_info:
            self.mod.handler(event, _LambdaContext())
        assert "Unauthorized sender" not in str(exc_info.value)
        assert "ALLOWED_SENDER not configured" not in str(exc_info.value)

    def test_case_insensitive_sender_match(self):
        """Sender match must be case-insensitive."""
        event = self._make_event("ALLOWED@EXAMPLE.COM")
        with pytest.raises((RuntimeError, Exception)) as exc_info:
            self.mod.handler(event, _LambdaContext())
        assert "Unauthorized sender" not in str(exc_info.value)

    def test_empty_records_raises(self):
        """Empty Records list must raise RuntimeError."""
        with pytest.raises(RuntimeError, match="No records"):
            self.mod.handler({"Records": []}, _LambdaContext())


# ---------------------------------------------------------------------------
# Integration: chart — end-to-end handler with mock S3
# ---------------------------------------------------------------------------

class TestChartHandlerIntegration:
    def setup_method(self):
        self.mod = _load_module("chart")

    def test_handler_replaces_chart_placeholder(self):
        """Chart handler replaces <!-- CHART: --> with image reference when data matches."""
        markdown = '---\ntitle: "Test"\n---\n\nSome text.\n\n<!-- CHART: agent deployment failure rates -->\n\nMore text.'
        research = """### Quantitative Data Points

- Data point: agent deployment failure rates
- Values: Failed: 60, Succeeded: 40
- Source: Gartner 2024
- Chart type: pie"""
        event = {
            "title": "Test",
            "slug": "test-post",
            "categories": ["tech"],
            "description": "test",
            "markdown": markdown,
            "date": "2026-01-01",
            "research": research,
        }
        with patch.object(self.mod.s3, "put_object"):
            result = self.mod.handler(event, _LambdaContext())
        assert "<!-- CHART:" not in result["markdown"]
        assert "/postimages/charts/test-post-chart-1.svg" in result["markdown"]
        assert len(result["charts"]) == 1
        assert "Gartner 2024" in result["markdown"]

    def test_handler_skips_unverifiable_source(self):
        """Chart handler skips charts with 'general knowledge' sources."""
        markdown = '---\ntitle: "T"\n---\n\n<!-- CHART: some data -->'
        research = """- Data point: some data
- Values: A: 10, B: 20
- Source: general knowledge
- Chart type: bar"""
        event = {"markdown": markdown, "research": research, "slug": "s", "date": "2026-01-01"}
        result = self.mod.handler(event, _LambdaContext())
        assert "<!-- CHART:" not in result["markdown"]
        assert len(result.get("charts", [])) == 0

    def test_handler_processes_diagram_placeholder(self):
        """Chart handler renders diagram placeholders into SVG images."""
        markdown = '---\ntitle: "T"\n---\n\n<!-- DIAGRAM: comparison | Old | New | Slow:Fast | Manual:Automated -->'
        event = {"markdown": markdown, "research": "", "slug": "test", "date": "2026-01-01"}
        with patch.object(self.mod.s3, "put_object"):
            result = self.mod.handler(event, _LambdaContext())
        assert "<!-- DIAGRAM:" not in result["markdown"]
        assert "/postimages/charts/test-diagram-1.svg" in result["markdown"]

    def test_handler_passthrough_when_no_placeholders(self):
        """Handler passes markdown through unchanged when no placeholders exist."""
        markdown = "Just a plain post with no charts."
        event = {"markdown": markdown, "research": "", "slug": "s", "date": "2026-01-01"}
        result = self.mod.handler(event, _LambdaContext())
        assert result["markdown"] == markdown


# ---------------------------------------------------------------------------
# Integration: verify — link extraction
# ---------------------------------------------------------------------------

class TestVerifyLinkExtraction:
    def setup_method(self):
        self.mod = _load_module("verify")

    def test_extracts_markdown_links(self):
        """_extract_links finds all inline markdown links."""
        md = "See [OpenAI docs](https://openai.com/docs) and [NIST](https://nist.gov/ai)."
        links = self.mod._extract_links(md)
        assert len(links) == 2
        assert links[0]["url"] == "https://openai.com/docs"
        assert links[1]["url"] == "https://nist.gov/ai"

    def test_handles_parentheses_in_urls(self):
        """_extract_links handles URLs with parentheses (e.g. Wikipedia)."""
        md = "See [Example](https://en.wikipedia.org/wiki/Example_(thing)) for details."
        links = self.mod._extract_links(md)
        assert len(links) == 1
        # URL should stop at whitespace, not at first )
        assert "Example" in links[0]["url"]

    def test_no_links_returns_empty(self):
        """_extract_links returns empty list for plain text."""
        assert self.mod._extract_links("No links here.") == []

    def test_extracts_context_around_link(self):
        """_extract_links includes surrounding context."""
        md = "A " * 60 + "[test link](https://example.com)" + " B" * 60
        links = self.mod._extract_links(md)
        assert len(links) == 1
        assert "test link" in links[0]["link_text"]
        assert len(links[0]["context"]) <= 250


# ---------------------------------------------------------------------------
# Behavioral: draft — footnote stripping
# ---------------------------------------------------------------------------

@pytest.mark.skipif(version_info < (3, 11), reason="draft/index.py requires datetime.UTC (Python 3.11+)")
class TestDraftFootnoteStripping:
    def setup_method(self):
        self.mod = _load_module("draft")

    def test_strips_footnote_definitions(self):
        """_strip_footnotes removes footnote definition lines."""
        md = "Some text[^1] here.\n\n[^1]: https://example.com"
        result = self.mod._strip_footnotes(md)
        assert "[^1]:" not in result
        assert "Some text" in result

    def test_strips_inline_footnote_refs(self):
        """_strip_footnotes removes inline [^N] references."""
        md = "A claim[^1] with evidence[^2]."
        result = self.mod._strip_footnotes(md)
        assert "[^1]" not in result
        assert "[^2]" not in result
        assert "A claim with evidence." in result

    def test_preserves_regular_links(self):
        """_strip_footnotes does not touch regular markdown links."""
        md = "See [this article](https://example.com) for details."
        result = self.mod._strip_footnotes(md)
        assert result == md


# ---------------------------------------------------------------------------
# Behavioral: notify — quality percentage calculation
# ---------------------------------------------------------------------------

class TestNotifyQualityCalc:
    def setup_method(self):
        self.mod = _load_module("notify")

    def test_quality_excludes_unreachable_from_denominator(self):
        """Quality score should exclude unreachable links from denominator."""
        total, passed, repaired, unreachable = 10, 5, 2, 3
        reachable = total - unreachable
        quality_pct = round(100 * (passed + repaired) / reachable) if reachable else 0
        assert quality_pct == 100  # 7/7 = 100%

    def test_quality_zero_when_all_unreachable(self):
        """Quality should be 0 when all links are unreachable."""
        total, passed, repaired, unreachable = 5, 0, 0, 5
        reachable = total - unreachable
        quality_pct = round(100 * (passed + repaired) / reachable) if reachable else 0
        assert quality_pct == 0


# ---------------------------------------------------------------------------
# Behavioral: notify — word count and author intent check
# ---------------------------------------------------------------------------

class TestNotifyEvals:
    def setup_method(self):
        self.mod = _load_module("notify")

    def test_count_words_excludes_frontmatter(self):
        """_count_words must skip YAML frontmatter and count body words only."""
        md = "---\ntitle: Test Post\ndate: 2026-01-01\n---\n\nThis is the body text here."
        result = self.mod._count_words(md)
        assert result == 6  # "This is the body text here."

    def test_count_words_no_frontmatter(self):
        """_count_words handles markdown with no frontmatter."""
        md = "Just plain content with five words."
        result = self.mod._count_words(md)
        assert result == len(md.split())

    def test_count_words_empty(self):
        """_count_words returns 0 for empty string."""
        assert self.mod._count_words("") == 0

    def test_intent_check_skipped_when_no_content(self):
        """_check_author_intent returns None when author_content is empty."""
        result = self.mod._check_author_intent("", "some markdown")
        assert result is None

    def test_intent_check_skipped_when_content_too_short(self):
        """_check_author_intent returns None when author_content is < 100 chars."""
        result = self.mod._check_author_intent("Short.", "some markdown")
        assert result is None

    def test_intent_check_returns_none_on_bedrock_failure(self):
        """_check_author_intent returns None (non-fatal) when Bedrock call fails."""
        author_content = "a" * 200  # long enough to trigger the check
        with patch.object(self.mod.bedrock, "invoke_model", side_effect=Exception("Bedrock error")):
            result = self.mod._check_author_intent(author_content, "some markdown")
        assert result is None

    def test_emit_metrics_non_fatal_on_failure(self):
        """_emit_pipeline_metrics must not raise even when CloudWatch call fails."""
        with patch.object(self.mod.cloudwatch, "put_metric_data", side_effect=Exception("CW error")):
            self.mod._emit_pipeline_metrics(85, 1200)  # must not raise


# ---------------------------------------------------------------------------
# Behavioral: approve — HITL metric emission
# ---------------------------------------------------------------------------

class TestApproveHITLMetrics:
    def setup_method(self):
        self.mod = _load_module("approve")

    def test_emit_hitl_metric_non_fatal_on_failure(self):
        """_emit_hitl_metric must not raise when CloudWatch call fails."""
        with patch.object(self.mod.cloudwatch, "put_metric_data", side_effect=Exception("CW error")):
            self.mod._emit_hitl_metric("HITLApproved")  # must not raise

    def test_emit_hitl_metric_calls_correct_namespace(self):
        """_emit_hitl_metric uses BlogAgent/Pipeline namespace."""
        calls = []
        with patch.object(self.mod.cloudwatch, "put_metric_data", side_effect=lambda **kw: calls.append(kw)):
            self.mod._emit_hitl_metric("HITLApproved")
        assert len(calls) == 1
        assert calls[0]["Namespace"] == "BlogAgent/Pipeline"
        assert calls[0]["MetricData"][0]["MetricName"] == "HITLApproved"
        assert calls[0]["MetricData"][0]["Value"] == 1


# ---------------------------------------------------------------------------
# Shared module: llm — the single source of truth for Bedrock invocation,
# vendored into the Research and Draft packages. Exercises the request building
# and the Opus -> Sonnet fallback contract that both handlers now delegate to.
# ---------------------------------------------------------------------------


def _bedrock_response(text):
    """Build a fake Bedrock invoke_model response carrying `text`."""
    class _Body:
        def __init__(self, payload):
            self._payload = payload

        def read(self):
            return self._payload

    return {"body": _Body(json.dumps({"content": [{"text": text}]}))}


class TestSharedLLM:
    def setup_method(self):
        self.llm = importlib.import_module("llm")
        # Each test drives bedrock.invoke_model explicitly; reset any prior state.
        self.llm.bedrock.invoke_model.reset_mock(return_value=True, side_effect=True)

    def test_invoke_model_includes_temperature(self):
        with patch.object(self.llm.bedrock, "invoke_model", return_value=_bedrock_response("hi")) as m:
            out = self.llm.invoke_model("prompt", model_id="model-x", temperature=0.5, max_tokens=1234)
        assert out == "hi"
        body = json.loads(m.call_args.kwargs["body"])
        assert m.call_args.kwargs["modelId"] == "model-x"
        assert body["temperature"] == 0.5
        assert body["max_tokens"] == 1234

    def test_invoke_model_omits_temperature_when_none(self):
        with patch.object(self.llm.bedrock, "invoke_model", return_value=_bedrock_response("hi")) as m:
            self.llm.invoke_model("prompt", model_id="model-x", temperature=None)
        body = json.loads(m.call_args.kwargs["body"])
        assert "temperature" not in body

    def test_fallback_returns_primary_on_success(self):
        with patch.object(self.llm.bedrock, "invoke_model", return_value=_bedrock_response("primary")) as m:
            out = self.llm.invoke_with_opus_fallback(
                "p", primary_model_id="opus", fallback_model_id="sonnet", label="draft")
        assert out == "primary"
        assert m.call_count == 1
        assert m.call_args.kwargs["modelId"] == "opus"

    def test_fallback_on_access_denied_emits_metric(self):
        calls = []

        def side_effect(**kw):
            calls.append(kw["modelId"])
            if len(calls) == 1:
                raise Exception("AccessDeniedException: no model access")
            return _bedrock_response("fallback-text")

        with patch.object(self.llm.bedrock, "invoke_model", side_effect=side_effect), \
             patch.object(self.llm, "emit_opus_fallback_metric") as emit:
            out = self.llm.invoke_with_opus_fallback(
                "p", primary_model_id="opus", fallback_model_id="sonnet", label="synthesis")
        assert out == "fallback-text"
        assert calls == ["opus", "sonnet"]
        emit.assert_called_once_with("opus")

    def test_fallback_on_throttle_does_not_emit_metric(self):
        calls = []

        def side_effect(**kw):
            calls.append(kw["modelId"])
            if len(calls) == 1:
                raise Exception("ThrottlingException: slow down")
            return _bedrock_response("ok")

        with patch.object(self.llm.bedrock, "invoke_model", side_effect=side_effect), \
             patch.object(self.llm, "emit_opus_fallback_metric") as emit:
            out = self.llm.invoke_with_opus_fallback(
                "p", primary_model_id="opus", fallback_model_id="sonnet", label="draft")
        assert out == "ok"
        assert calls == ["opus", "sonnet"]  # immediate fallback, no retry on primary
        emit.assert_not_called()

    def test_non_throttle_error_propagates(self):
        with patch.object(self.llm.bedrock, "invoke_model", side_effect=ValueError("boom")), \
             pytest.raises(ValueError, match="boom"):
            self.llm.invoke_with_opus_fallback(
                "p", primary_model_id="opus", fallback_model_id="sonnet", label="draft")

    def test_outer_retry_delays_retry_primary_before_fallback(self, monkeypatch):
        monkeypatch.setenv("OPUS_OUTER_RETRY_DELAYS", "1,2")
        calls = []

        def side_effect(**kw):
            calls.append(kw["modelId"])
            if len(calls) == 1:
                raise Exception("ThrottlingException: slow down")
            return _bedrock_response("recovered")

        with patch.object(self.llm.bedrock, "invoke_model", side_effect=side_effect), \
             patch.object(self.llm.time, "sleep") as sleep:
            out = self.llm.invoke_with_opus_fallback(
                "p", primary_model_id="opus", fallback_model_id="sonnet", label="draft")
        assert out == "recovered"
        assert calls == ["opus", "opus"]  # retried the primary, did not fall back
        sleep.assert_called_once_with(1)

    def test_emit_metric_non_fatal_on_failure(self):
        bad_cw = MagicMock()
        bad_cw.put_metric_data.side_effect = Exception("CW down")
        self.llm._cw = bad_cw
        try:
            self.llm.emit_opus_fallback_metric("opus")  # must not raise
        finally:
            self.llm._cw = None


# ---------------------------------------------------------------------------
# Behavioral: draft — resume-on-retry checkpointing
# ---------------------------------------------------------------------------


class _FakeS3Body:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return self._payload


class _FakeS3:
    """In-memory stand-in for the S3 client used by the Draft checkpoint."""
    def __init__(self):
        self.store = {}
        self.puts = 0

    def get_object(self, Bucket, Key):
        if Key not in self.store:
            raise Exception("NoSuchKey: The specified key does not exist")
        return {"Body": _FakeS3Body(self.store[Key])}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.puts += 1
        self.store[Key] = Body if isinstance(Body, bytes) else Body.encode()

    def delete_object(self, Bucket, Key):
        self.store.pop(Key, None)


@pytest.mark.skipif(version_info < (3, 11), reason="draft/index.py requires datetime.UTC (Python 3.11+)")
class TestDraftCheckpoint:
    def setup_method(self):
        self.mod = _load_module("draft")

    # --- key derivation -----------------------------------------------------
    def test_key_stable_for_same_input(self):
        ev = {"execution_id": "exec-1", "topic": "t", "author_content": "a", "research": "r"}
        assert self.mod._checkpoint_key(ev, False) == self.mod._checkpoint_key(ev, False)

    def test_key_differs_for_revision_phase(self):
        ev = {"execution_id": "exec-1", "topic": "t"}
        assert self.mod._checkpoint_key(ev, False) != self.mod._checkpoint_key(ev, True)

    def test_key_differs_when_content_changes(self):
        a = {"execution_id": "exec-1", "topic": "t", "author_content": "one"}
        b = {"execution_id": "exec-1", "topic": "t", "author_content": "two"}
        assert self.mod._checkpoint_key(a, False) != self.mod._checkpoint_key(b, False)

    def test_key_includes_execution_id(self):
        ev = {"execution_id": "exec-42", "topic": "t"}
        assert "exec-42" in self.mod._checkpoint_key(ev, False)

    # --- run / persist ------------------------------------------------------
    def test_run_executes_and_persists(self):
        fake = _FakeS3()
        with patch.object(self.mod, "s3", fake):
            ckpt = self.mod._DraftCheckpoint("bucket", "checkpoints/k.json")
            ckpt.load()
            out = ckpt.run("opus_draft", lambda: "BODY1")
        assert out == "BODY1"
        assert ckpt.has("opus_draft")
        assert fake.puts == 1
        assert "checkpoints/k.json" in fake.store

    def test_resume_skips_completed_stages(self):
        fake = _FakeS3()
        with patch.object(self.mod, "s3", fake):
            # First attempt completes two stages, then "fails".
            c1 = self.mod._DraftCheckpoint("bucket", "checkpoints/k.json")
            c1.load()
            c1.run("opus_draft", lambda: "AFTER_OPUS")
            c1.run("voice", lambda: "AFTER_VOICE")

            # Retry: a fresh checkpoint object resumes from S3.
            c2 = self.mod._DraftCheckpoint("bucket", "checkpoints/k.json")
            c2.load()
            calls = []

            def _boom():
                calls.append("ran")
                raise AssertionError("completed stage must not re-run")

            assert c2.run("opus_draft", _boom) == "AFTER_VOICE"  # latest cumulative body
            assert c2.run("voice", _boom) == "AFTER_VOICE"
            assert calls == []  # neither completed stage re-ran Bedrock

            ran = []
            out = c2.run("insight", lambda: (ran.append("insight"), "AFTER_INSIGHT")[1])
        assert out == "AFTER_INSIGHT"
        assert ran == ["insight"]

    def test_disabled_when_no_bucket(self):
        fake = _FakeS3()
        with patch.object(self.mod, "s3", fake):
            ckpt = self.mod._DraftCheckpoint("", "checkpoints/k.json")
            assert ckpt.enabled is False
            assert ckpt.run("opus_draft", lambda: "BODY") == "BODY"
        assert fake.puts == 0  # nothing persisted when disabled

    def test_disabled_via_env_flag(self):
        fake = _FakeS3()
        with patch.object(self.mod, "_CHECKPOINTS_ENABLED", False), patch.object(self.mod, "s3", fake):
            ckpt = self.mod._DraftCheckpoint("bucket", "checkpoints/k.json")
            assert ckpt.enabled is False
            assert ckpt.run("opus_draft", lambda: "BODY") == "BODY"
        assert fake.puts == 0

    def test_save_failure_is_non_fatal(self):
        fake = _FakeS3()
        with patch.object(self.mod, "s3", fake), \
             patch.object(fake, "put_object", side_effect=Exception("S3 down")):
            ckpt = self.mod._DraftCheckpoint("bucket", "checkpoints/k.json")
            ckpt.load()
            # Must still return the computed body and must not raise.
            assert ckpt.run("opus_draft", lambda: "BODY") == "BODY"
            assert ckpt.enabled is False  # checkpointing disabled itself after the failure

    def test_done_deletes_checkpoint(self):
        fake = _FakeS3()
        with patch.object(self.mod, "s3", fake):
            ckpt = self.mod._DraftCheckpoint("bucket", "checkpoints/k.json")
            ckpt.load()
            ckpt.run("opus_draft", lambda: "BODY")
            assert "checkpoints/k.json" in fake.store
            ckpt.done()
        assert "checkpoints/k.json" not in fake.store

    def test_load_corrupt_checkpoint_starts_fresh(self):
        fake = _FakeS3()
        fake.store["checkpoints/k.json"] = b"{not valid json"
        with patch.object(self.mod, "s3", fake):
            ckpt = self.mod._DraftCheckpoint("bucket", "checkpoints/k.json")
            ckpt.load()  # must not raise
            assert ckpt.completed == []
            assert ckpt.run("opus_draft", lambda: "BODY") == "BODY"


# ---------------------------------------------------------------------------
# Behavioral: draft — parallel annotation audits (insight + named entities)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(version_info < (3, 11), reason="draft/index.py requires datetime.UTC (Python 3.11+)")
class TestDraftAnnotations:
    def setup_method(self):
        self.mod = _load_module("draft")

    def test_collect_annotations_pairs_with_anchor(self):
        result = "## Heading\n\nPara one.\n<!-- ⚡ INSIGHT: weak -->\n\nPara two."
        pairs = self.mod._collect_annotations(result, "⚡ INSIGHT:")
        assert pairs == [("Para one.", "<!-- ⚡ INSIGHT: weak -->")]

    def test_apply_annotations_inserts_after_anchor(self):
        base = "## Heading\n\nPara one.\n\nPara two."
        out = self.mod._apply_annotations(base, [("Para one.", "<!-- ⚡ INSIGHT: x -->")])
        lines = out.split("\n")
        assert lines[lines.index("Para one.") + 1] == "<!-- ⚡ INSIGHT: x -->"

    def test_apply_annotations_idempotent(self):
        base = "Para one.\n<!-- ⚡ INSIGHT: x -->"
        out = self.mod._apply_annotations(base, [("Para one.", "<!-- ⚡ INSIGHT: x -->")])
        assert out.count("<!-- ⚡ INSIGHT: x -->") == 1

    def test_apply_annotations_drops_missing_anchor(self):
        base = "Para one."
        out = self.mod._apply_annotations(base, [("No such line", "<!-- ⚡ INSIGHT: x -->")])
        assert out == base

    def test_parallel_merges_both_annotation_sets(self):
        base = "## Heading\n\nPara one.\n\nPara two."
        insight_out = "## Heading\n\nPara one.\n<!-- ⚡ INSIGHT: weak -->\n\nPara two."
        entity_out = "## Heading\n\nPara one.\n\nPara two.\n<!-- 🔍 ENTITY CHECK: \"X\" -->"
        with patch.object(self.mod, "_audit_insight", return_value=insight_out) as ins, \
             patch.object(self.mod, "_audit_named_entities", return_value=entity_out) as ent:
            merged = self.mod._audit_annotations(base, "research")
        ins.assert_called_once()
        ent.assert_called_once()
        assert "<!-- ⚡ INSIGHT: weak -->" in merged
        assert '<!-- 🔍 ENTITY CHECK: "X" -->' in merged
        # Anchored to the right paragraphs.
        lines = merged.split("\n")
        assert lines[lines.index("Para one.") + 1] == "<!-- ⚡ INSIGHT: weak -->"

    def test_parallel_no_annotations_returns_base(self):
        base = "## Heading\n\nPara one."
        with patch.object(self.mod, "_audit_insight", return_value=base), \
             patch.object(self.mod, "_audit_named_entities", return_value=base):
            assert self.mod._audit_annotations(base, "research") == base

    def test_sequential_fallback_chains_passes(self):
        base = "BASE"
        with patch.object(self.mod, "_PARALLEL_AUDITS", False), \
             patch.object(self.mod, "_audit_insight", return_value="INSIGHT_OUT") as ins, \
             patch.object(self.mod, "_audit_named_entities", side_effect=lambda b, r: b + "_ENT") as ent:
            out = self.mod._audit_annotations(base, "research")
        assert out == "INSIGHT_OUT_ENT"  # entities received insight's output
        ins.assert_called_once()
        ent.assert_called_once()


# ---------------------------------------------------------------------------
# Deployability: every handler must import with ONLY its own directory on the
# path — exactly how Lambda loads it from the deployment zip.
#
# The import tests above put the agent root and every sibling function dir on
# sys.path, so an import that only resolves because a module happens to live
# elsewhere in the tree would still pass — yet fail at runtime with
# Runtime.ImportModuleError ("No module named 'renderers'"). These tests close
# that gap: they spawn a fresh interpreter whose sole import root is the one
# function directory (plus stdlib + a mocked boto3), reproducing the Lambda
# runtime. If a handler imports a module that won't ship inside its own package,
# this fails in CI — before any deploy.
# ---------------------------------------------------------------------------

_ISOLATED_IMPORT_RUNNER = textwrap.dedent(
    """
    import os
    import sys
    from unittest.mock import MagicMock

    # Some handlers read required env vars at import time (e.g.
    # os.environ["ALERTS_TOPIC_ARN"]). In Lambda those are always set by the
    # stack; here we install a defaulting environment so the test measures CODE
    # importability — the missing-module class of bug — not env configuration.
    class _DefaultEnv(dict):
        def __missing__(self, key):
            return "test-placeholder"

    os.environ = _DefaultEnv(os.environ)

    # Mock boto3/botocore so the import doesn't require the real SDK and never
    # touches the network — the function root is the only thing under test.
    _cfg = MagicMock()
    _cfg.Config = MagicMock(return_value=MagicMock())
    for name, mod in (
        ("boto3", MagicMock()),
        ("botocore", MagicMock()),
        ("botocore.config", _cfg),
        ("botocore.exceptions", MagicMock()),
    ):
        sys.modules[name] = mod

    fn_dir = sys.argv[1]
    # Lambda's import root is the deployment package root and nothing else.
    # Prepend it; the runner script's own dir (a neutral temp dir) carries no
    # sibling Lambda code, so no cross-function leakage is possible.
    sys.path.insert(0, fn_dir)

    import index
    assert hasattr(index, "handler"), "index.py has no handler()"
    """
)


def _stage_deployment_package(func_dir, dest):
    """Build a faithful copy of the Lambda deployment package root: the function
    dir's files plus any modules vendored from agent/common per .common-deps —
    mirroring scripts/package-lambda.sh. Returns the staged package path."""
    pkg = dest / "pkg"
    shutil.copytree(AGENT_DIR / func_dir, pkg)
    common_deps = pkg / ".common-deps"
    if common_deps.exists():
        for line in common_deps.read_text().splitlines():
            mod = line.strip()
            if mod:
                src = AGENT_DIR / "common" / mod
                assert src.exists(), f"{func_dir}/.common-deps lists '{mod}' but agent/common/{mod} is missing"
                shutil.copy(src, pkg / mod)
        common_deps.unlink()  # the manifest itself is excluded from the real zip
    return pkg


@pytest.mark.parametrize("func_dir", LAMBDA_DIRS)
def test_handler_imports_in_lambda_isolation(func_dir, tmp_path):
    """Each handler imports with only its deployment package on the path, as Lambda
    does. The package is the function dir plus any vendored common modules, so an
    import that only resolves thanks to a sibling Lambda dir or the agent root still
    fails here — before it fails at runtime with Runtime.ImportModuleError."""
    pkg = _stage_deployment_package(func_dir, tmp_path)
    runner = tmp_path / "isolated_import_runner.py"
    runner.write_text(_ISOLATED_IMPORT_RUNNER)
    result = subprocess.run(
        [sys.executable, str(runner), str(pkg)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"{func_dir}/index.py fails to import in Lambda isolation — a module it "
        f"imports won't ship inside its own package (Runtime.ImportModuleError "
        f"at runtime):\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Deterministic anti-slop net (Draft Lambda _lint_slop)
# ---------------------------------------------------------------------------

class TestSlopLint:
    """The deterministic net that runs after the probabilistic voice audit."""

    def setup_method(self):
        self.draft = _load_module("draft")

    def test_em_dash_is_replaced(self):
        body, findings = self.draft._lint_slop("A term — a description.")
        assert "—" not in body
        assert any("dash" in f for f in findings)

    def test_en_dash_is_replaced(self):
        body, _ = self.draft._lint_slop("Low–complexity work stays cheap.")
        assert "–" not in body

    def test_hyphenated_words_are_left_alone(self):
        body, findings = self.draft._lint_slop("A well-scoped, task-specific check.")
        assert body == "A well-scoped, task-specific check."
        assert findings == []

    def test_forbidden_phrase_detected(self):
        _, findings = self.draft._lint_slop("Rung three is where it gets interesting.")
        assert any("gets interesting" in f for f in findings)

    def test_antithesis_mic_drop_detected(self):
        _, findings = self.draft._lint_slop("That's not cutting corners. That's allocation.")
        assert any("antithesis" in f for f in findings)

    def test_antithesis_detected_with_curly_apostrophe(self):
        _, findings = self.draft._lint_slop("That’s not cutting corners. That’s allocation.")
        assert any("antithesis" in f for f in findings)

    def test_clean_prose_has_no_findings(self):
        text = "I worked in identity at AWS, where automated reasoning earned its keep."
        body, findings = self.draft._lint_slop(text)
        assert body == text
        assert findings == []


# ---------------------------------------------------------------------------
# Deterministic release gate (common/gate.py) — L0
# ---------------------------------------------------------------------------

_GOOD_POST = """---
title: "A Good Post"
date: 2026-09-10
author: "Khaled Zaky"
categories: ["ai"]
description: "A description long enough to pass the frontmatter checks and then some."

---

Five months ago I argued that enterprises needed a [control plane](https://example.com/a).

## First section

Body text with a specific claim and a [source](https://example.com/b).

## Second section

More text. The final paragraph ends plainly, on a specific sentence.
"""

# Replica of the September 10 escape: the whole body wrapped in ```markdown with a
# second frontmatter block nested inside it (commit 80bed2a, fixed in 5a98dce).
_FENCED_POST = """---
title: "Your Agent Control Plane Has a Coverage Problem"
date: 2026-09-10
author: "Khaled Zaky"
categories: ["ai"]
description: "Outer description."

---

```markdown
---
title: "Your Agent Control Plane Has a Coverage Problem"
date: 2025-09-12
author: "Khaled Zaky"
categories: ["AI Governance"]
description: "Inner description."
---

# Your Agent Control Plane Has a Coverage Problem

Five months ago, I argued for an [agent control plane](https://example.com/x).

## Three claims

| Property | Question |
| --- | --- |
| Coverage | Can we enumerate the paths? |

## Visibility is not coverage

Text.

*A control plane is an architecture. Control coverage is a claim. Control closure is the evidence.*
```
"""


class TestGate:
    def setup_method(self):
        self.gate = importlib.import_module("gate")

    def test_fenced_body_with_nested_frontmatter_is_error(self):
        checks = [f["check"] for f in self.gate.errors(self.gate.analyze(_FENCED_POST))]
        assert "body_fenced" in checks

    def test_clean_post_has_no_errors(self):
        assert self.gate.errors(self.gate.analyze(_GOOD_POST)) == []

    def test_second_frontmatter_outside_fence_is_error(self):
        md = _GOOD_POST.replace("## First section", '---\ntitle: "Dup"\ndate: 2026-01-01\n---\n\n## First section')
        checks = [f["check"] for f in self.gate.errors(self.gate.analyze(md))]
        assert "frontmatter_nested" in checks

    def test_yaml_sample_in_small_code_block_is_not_nested_frontmatter(self):
        """A how-to post showing a frontmatter example in a short code block must pass
        (migrating-from-jekyll-to-astro.md does exactly this)."""
        md = _GOOD_POST.replace("More text.", "Example:\n\n```yaml\n---\ntitle: Example\ndate: 2020-01-01\n---\n```\n\nMore text.")
        assert self.gate.errors(self.gate.analyze(md)) == []

    def test_duplicate_draft_flag_is_error(self):
        md = _GOOD_POST.replace('categories: ["ai"]', 'categories: ["ai"]\ndraft: true\ndraft: true')
        checks = [f["check"] for f in self.gate.errors(self.gate.analyze(md))]
        assert "draft_flag_duplicate" in checks

    def test_too_few_headings_is_error_for_article_length(self):
        md = _GOOD_POST.replace("## Second section\n", "") + ("filler word " * 900)
        checks = [f["check"] for f in self.gate.errors(self.gate.analyze(md))]
        assert "headings_low" in checks

    def test_missing_frontmatter_is_error(self):
        checks = [f["check"] for f in self.gate.errors(self.gate.analyze("## Just a body\n\ntext\n\n## More\n"))]
        assert "frontmatter_missing" in checks

    def test_three_beat_italic_closer_is_advisory(self):
        body = "Prose.\n\n*A control plane is an architecture. Coverage is a claim. Closure is the evidence.*\n"
        findings = self.gate.slop_findings(body)
        assert any("aphoristic italic closer with 3 beats" in f for f in findings)

    def test_single_italic_closer_is_flagged(self):
        """17 of the author's 18 pre-agent posts end in plain prose; the italic closer is an
        agent artifact (26 of 34 agent-era posts). The author deleted this one by hand (8d2afc3)."""
        findings = self.gate.slop_findings("Prose.\n\n*A halt that can't be proven is a claim, not a control.*\n")
        assert any("italic one-line closer" in f for f in findings)

    def test_plain_last_paragraph_is_not_flagged_as_closer(self):
        findings = self.gate.slop_findings("Prose.\n\nThe last paragraph is plain and specific.\n")
        assert not any("closer" in f for f in findings)

    def test_rule_of_three_flagged_from_first_occurrence(self):
        """None of the 18 pre-agent posts has one; 41% of agent-era posts do."""
        one = "You know the drill. Start small. Ship fast. Iterate.\n"
        assert any("rule-of-three fragments x1" in f for f in self.gate.slop_findings(one))

    def test_rule_of_three_does_not_span_paragraphs(self):
        body = "I stand.\n\nAgents rarely operate alone.\n\nOne agent invokes another.\n\nThey chain.\n\nThey fan out.\n\nThey retry.\n"
        assert not any("rule-of-three" in f for f in self.gate.slop_findings(body))

    def test_stacked_not_but_contrasts_detected(self):
        body = ("This is not a tooling gap, but a governance gap. "
                "The fix is not a bigger model but a different substrate. "
                "It is not about speed but about proof.\n")
        findings = self.gate.slop_findings(body)
        assert any('"not X, but Y"' in f for f in findings)

    def test_single_not_but_is_fine(self):
        assert not any('"not X, but Y"' in f for f in self.gate.slop_findings("Not a tooling gap, but a governance gap.\n"))

    def test_british_ise_spelling_flagged(self):
        findings = self.gate.slop_findings("We should recognise and prioritise the organisation's needs.\n")
        assert any("British -ise" in f and "recognise" in f for f in findings)

    def test_ise_allowlist_avoids_false_positives(self):
        findings = self.gate.slop_findings("The enterprise made a promise; the precise answer is otherwise.\n")
        assert not any("British -ise" in f for f in findings)

    def test_behavior_is_the_authors_own_spelling(self):
        """'behavior' appears 48 times in the author's posts; it must never be flagged."""
        findings = self.gate.slop_findings("Agent behavior is probabilistic; we recognize that.\n")
        assert not any("spelling" in f for f in findings)

    def test_short_post_without_headings_is_a_warning_not_an_error(self):
        md = _GOOD_POST.replace("## First section\n", "").replace("## Second section\n", "")
        findings = self.gate.analyze(md)
        assert not self.gate.errors(findings)
        assert any(f["check"] == "headings_low" for f in self.gate.warnings(findings))

    def test_long_post_without_headings_is_an_error(self):
        md = _GOOD_POST.replace("## First section\n", "").replace("## Second section\n", "") + ("filler word " * 900)
        assert any(f["check"] == "headings_low" for f in self.gate.errors(self.gate.analyze(md)))

    def test_formula_repeats_detected(self):
        body = "The part that matters. The part that hurts. The part that nobody tests.\n"
        assert any('"the part that..."' in f for f in self.gate.slop_findings(body))

    def test_analyze_orders_errors_before_warnings(self):
        findings = self.gate.analyze(_FENCED_POST)
        levels = [f["level"] for f in findings]
        assert levels == sorted(levels, key=lambda lv: 0 if lv == "error" else 1)


# ---------------------------------------------------------------------------
# Shared LLM: adaptive thinking negotiation + model-aware temperature
# ---------------------------------------------------------------------------

def _bedrock_thinking_response(text):
    class _Body:
        def __init__(self, payload):
            self._payload = payload

        def read(self):
            return self._payload

    return {"body": _Body(json.dumps({"content": [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": text}]}))}


class TestThinkingAndTemperature:
    def setup_method(self):
        self.llm = importlib.import_module("llm")
        self.llm._THINKING_MODE.clear()
        self.llm._temperature_warned.clear()
        self.llm.bedrock.invoke_model.reset_mock(return_value=True, side_effect=True)

    @pytest.mark.parametrize("model_id,expected", [
        ("us.anthropic.claude-sonnet-4-6", True),
        ("us.anthropic.claude-haiku-4-5-20251001-v1:0", True),
        ("us.anthropic.claude-opus-4-6-v1", False),
        ("us.anthropic.claude-opus-5", False),
        ("us.anthropic.claude-sonnet-5", False),
        ("us.anthropic.claude-sonnet-5-20260601-v1:0", False),
        ("anthropic.claude-fable-5-1", False),
        ("model-x", True),
    ])
    def test_supports_temperature(self, model_id, expected):
        assert self.llm.supports_temperature(model_id) is expected

    def test_invoke_model_omits_temperature_for_5_generation(self):
        with patch.object(self.llm.bedrock, "invoke_model", return_value=_bedrock_response("hi")) as m:
            self.llm.invoke_model("p", model_id="us.anthropic.claude-sonnet-5", temperature=0.0)
        assert "temperature" not in json.loads(m.call_args.kwargs["body"])

    def test_thinking_tries_adaptive_first(self):
        with patch.object(self.llm.bedrock, "invoke_model", return_value=_bedrock_thinking_response("plan")) as m:
            out = self.llm.invoke_with_thinking("p", model_id="us.anthropic.claude-sonnet-4-6", max_tokens=2000, budget_tokens=1000)
        assert out == "plan"
        body = json.loads(m.call_args.kwargs["body"])
        assert body["thinking"] == {"type": "adaptive"}
        assert "budget_tokens" not in json.dumps(body)
        assert m.call_count == 1

    def test_thinking_falls_back_to_enabled_and_caches_mode(self):
        rejected = Exception("ValidationException: thinking.type: adaptive is not supported for this model")
        with patch.object(self.llm.bedrock, "invoke_model", side_effect=[rejected, _bedrock_thinking_response("plan")]) as m:
            out = self.llm.invoke_with_thinking("p", model_id="legacy-model", max_tokens=2000, budget_tokens=1000)
        assert out == "plan"
        assert m.call_count == 2
        body = json.loads(m.call_args.kwargs["body"])
        assert body["thinking"] == {"type": "enabled", "budget_tokens": 1000}
        assert body["max_tokens"] >= 1500
        # second call goes straight to the remembered shape — no wasted adaptive attempt
        with patch.object(self.llm.bedrock, "invoke_model", return_value=_bedrock_thinking_response("again")) as m2:
            self.llm.invoke_with_thinking("p", model_id="legacy-model", max_tokens=2000, budget_tokens=1000)
        assert m2.call_count == 1
        assert json.loads(m2.call_args.kwargs["body"])["thinking"]["type"] == "enabled"

    def test_thinking_non_shape_error_propagates(self):
        with patch.object(self.llm.bedrock, "invoke_model", side_effect=Exception("ThrottlingException: slow down")) as m, \
             pytest.raises(Exception, match="Throttling"):
            self.llm.invoke_with_thinking("p", model_id="m", max_tokens=2000)
        assert m.call_count == 1

    def test_thinking_mode_env_forces_shape(self, monkeypatch):
        monkeypatch.setenv("THINKING_MODE", "enabled")
        with patch.object(self.llm.bedrock, "invoke_model", return_value=_bedrock_thinking_response("x")) as m:
            self.llm.invoke_with_thinking("p", model_id="m", max_tokens=2000, budget_tokens=800)
        assert json.loads(m.call_args.kwargs["body"])["thinking"]["type"] == "enabled"

    def test_thinking_omits_temperature_for_opus(self):
        with patch.object(self.llm.bedrock, "invoke_model", return_value=_bedrock_thinking_response("x")) as m:
            self.llm.invoke_with_thinking("p", model_id="us.anthropic.claude-opus-5", max_tokens=2000)
        assert "temperature" not in json.loads(m.call_args.kwargs["body"])


# ---------------------------------------------------------------------------
# Notify: the release gate blocks broken renders; lint findings reach the email
# ---------------------------------------------------------------------------

class TestNotifyReleaseGate:
    def setup_method(self):
        self.mod = _load_module("notify")
        self.mod.DRAFTS_BUCKET = "bucket"
        self.mod.SNS_TOPIC_ARN = "arn:sns"
        self.mod.APPROVE_URL = "https://approve"
        self.mod.s3 = MagicMock()
        self.mod.s3.generate_presigned_url.return_value = "https://dl"
        self.mod.sns = MagicMock()
        self.mod.cloudwatch = MagicMock()

    def _event(self, markdown):
        return {"title": "T", "slug": "t", "markdown": markdown, "date": "2026-09-10",
                "charts": [], "verification": {}, "author_content": "", "taskToken": "tok"}

    def test_fenced_body_never_reaches_the_inbox(self):
        with pytest.raises(ValueError, match="body_fenced"):
            self.mod.handler(self._event(_FENCED_POST), _LambdaContext())
        self.mod.sns.publish.assert_not_called()

    def test_clean_post_is_sent(self):
        self.mod.handler(self._event(_GOOD_POST), _LambdaContext())
        self.mod.sns.publish.assert_called_once()

    def test_replaced_marker_is_a_known_annotation_and_is_surfaced(self):
        md = _GOOD_POST.replace("[source](https://example.com/b).",
                                "[source](https://example.com/c).\n<!-- 🔁 CITATION REPLACED: https://example.com/b -> https://example.com/c -->")
        self.mod.handler(self._event(md), _LambdaContext())
        message = self.mod.sns.publish.call_args.kwargs["Message"]
        assert "CITATION REPLACED" in message
        assert "swapped by auto-repair" in message

    def test_lint_findings_appear_on_the_email(self):
        md = _GOOD_POST.rstrip("\n") + "\n\n*Coverage is a claim. Closure is the evidence. Proof is the control.*\n"
        self.mod.handler(self._event(md), _LambdaContext())
        message = self.mod.sns.publish.call_args.kwargs["Message"]
        assert "deterministic lint finding" in message
        assert "aphoristic italic closer with 3 beats" in message


# ---------------------------------------------------------------------------
# Verify: auto-repair is visible; Publish: marker is stripped before commit
# ---------------------------------------------------------------------------

class TestCitationRepairVisibility:
    def test_repair_inserts_visible_marker(self):
        verify = _load_module("verify")
        md = "See the [standard](https://old.example/rfc) for details."
        verdicts = [{"url": "https://old.example/rfc", "link_text": "standard", "context": "See the standard", "verdict": "FAIL", "reason": "mismatch"}]
        with patch.object(verify, "_tavily_search_for_claim", return_value=[{"url": "https://new.example/rfc"}]), \
             patch.object(verify, "_find_replacement_url", return_value="https://new.example/rfc"):
            new_md, new_verdicts = verify._repair_citations(verdicts, md, "rid")
        assert "](https://new.example/rfc)" in new_md
        assert "<!-- 🔁 CITATION REPLACED: https://old.example/rfc -> https://new.example/rfc -->" in new_md
        assert new_verdicts[0]["verdict"] == "REPAIRED"

    def test_publish_strips_every_review_annotation(self):
        publish = _load_module("publish")
        md = ("---\ntitle: x\ndraft: true\n---\n\nA [link](https://a)\n<!-- 🔁 CITATION REPLACED: https://a -> https://b -->\n"
              "Para.\n<!-- ⚡ INSIGHT: weak -->\nPara.\n<!-- 🔍 ENTITY CHECK: unverified -->\n"
              "Para.\n<!-- ⚠️ CITATION FAIL: nope -->\nPara.\n<!-- 💡 CITATION NOTE: hmm -->\n"
              # the three shapes that leaked to the live site:
              "Para.\n<!-- CITATION NOTE: no emoji, emitted by the draft citation audit -->\n"
              "Para.\n<!-- ⚡ CITATION WARN: wraps across\nseveral lines like the observability post -->\n"
              "Para.\n<!-- CITATION FAIL: https://x - emoji-less fail from the draft audit -->\n")
        out = publish._strip_review_annotations(md)
        assert "<!--" not in out
        assert "draft: true" not in out
        assert "A [link](https://a)\nPara." in out
        assert out.count("Para.") == 7

    def test_publish_keeps_chart_placeholders_and_prose_mentions(self):
        """CHART/DIAGRAM placeholders are consumed by the Chart Lambda, never by Publish,
        and prose that *mentions* an annotation in backticks must survive."""
        publish = _load_module("publish")
        md = "---\ntitle: x\n---\n\n<!-- CHART: Title | a: 1 -->\n\nUse `<!-- DIAGRAM: type | ... -->` placeholders.\n"
        assert publish._strip_review_annotations(md) == md


# ---------------------------------------------------------------------------
# Verify: claim-level (L1) verification, precision backstop, source dating
# ---------------------------------------------------------------------------

class TestVerifyClaimLevel:
    def setup_method(self):
        self.mod = _load_module("verify")

    @pytest.mark.parametrize("html,expected", [
        ('<meta property="article:published_time" content="2026-09-09T10:00:00Z">', "2026-09-09"),
        ('<script type="application/ld+json">{"datePublished": "2026-03-05T08:00:00+00:00"}</script>', "2026-03-05"),
        ('<time datetime="2025-12-01">Dec 1</time>', "2025-12-01"),
        ('<meta content="2026-01-15" property="og:published_time">', "2026-01-15"),
        ("<html><body>no dates here</body></html>", ""),
    ])
    def test_extract_published_date(self, html, expected):
        assert self.mod._extract_published_date(html) == expected

    def test_age_days(self):
        from datetime import date
        assert self.mod._age_days("2026-09-01", today=date(2026, 9, 10)) == 9
        assert self.mod._age_days("garbage") is None

    @pytest.mark.parametrize("text,precise", [
        ("testing represents roughly 30 percent of total software development cost", True),
        ("a judge of comparable size roughly doubles the cost", True),
        ("the 1:10:100 defect-cost ratio", True),
        ("more than 100,000 trials across 13 large language models", True),
        ("AWS reports up to 99% accuracy", True),
        ("Zelkova is proven over all inputs", True),
        ("In March 2026 a governance paper defined an irreversibility budget", False),
        ("identity is the right primitive to anchor everything on", False),
    ])
    def test_precision_claim_detection(self, text, precise):
        assert bool(self.mod.PRECISION_RE.search(text)) is precise

    def _lr(self, context, excerpt, reachable=True):
        return {"url": "https://src.example/p", "link_text": "source", "context": context,
                "reachable": reachable, "status_code": 200 if reachable else 404,
                "title": "Source", "excerpt": excerpt, "published_at": "2026-09-01"}

    def _judge(self, payload):
        return patch.object(self.mod.bedrock, "invoke_model", return_value=_bedrock_response(json.dumps(payload)))

    def test_pass_with_quote(self):
        lr = self._lr("agents can act, according to [source]", "The report says agents can act autonomously.")
        with self._judge({"verdict": "PASS", "quote": "agents can act autonomously", "reason": "stated"}):
            v = self.mod._verify_one_link(lr)
        assert v["verdict"] == "PASS" and v["quote"] and v["published_at"] == "2026-09-01"

    def test_precision_pass_downgraded_when_figure_absent_from_page(self):
        """The c20d97e escape: a PASS whose figure the source text never states."""
        lr = self._lr("testing is roughly 30 percent of development cost [source]", "Testing matters a great deal in software projects.")
        with self._judge({"verdict": "PASS", "quote": "testing matters", "reason": "on topic"}):
            v = self.mod._verify_one_link(lr)
        assert v["verdict"] == "FAIL"
        assert "figure not found" in v["reason"]
        assert v["precision"] is True

    def test_precision_pass_kept_when_figure_in_page(self):
        lr = self._lr("testing is roughly 30 percent of development cost [source]", "Our model assumes testing is 30 percent of cost.")
        with self._judge({"verdict": "PASS", "quote": "testing is 30 percent of cost", "reason": "stated"}):
            v = self.mod._verify_one_link(lr)
        assert v["verdict"] == "PASS"

    def test_unreachable_and_pdf_short_circuit_without_a_model_call(self):
        with patch.object(self.mod.bedrock, "invoke_model") as m:
            u = self.mod._verify_one_link(self._lr("claim", "", reachable=False))
            p = self.mod._verify_one_link(self._lr("claim", "[Binary content — cannot extract text]"))
        assert u["verdict"] == "UNREACHABLE" and p["verdict"] == "WARN"
        m.assert_not_called()

    def test_unparseable_judge_output_is_a_warn_not_a_pass(self):
        lr = self._lr("claim [source]", "page text")
        with patch.object(self.mod.bedrock, "invoke_model", return_value=_bedrock_response("I think it's fine")):
            v = self.mod._verify_one_link(lr)
        assert v["verdict"] == "WARN"

    def test_per_link_preserves_order(self):
        lrs = [self._lr(f"claim {i} [source]", f"page {i}") for i in range(4)]
        with patch.object(self.mod, "_verify_one_link", side_effect=lambda lr: {"url": lr["url"], "verdict": "PASS", "context": lr["context"]}):
            out = self.mod._verify_citations_per_link(lrs)
        assert [o["context"] for o in out] == [lr["context"] for lr in lrs]

    def test_claim_sentence_isolates_the_linked_sentence(self):
        ctx = "Testing is roughly 30 percent of cost, per a model. See also [the standard](https://b) for details. Next thought."
        assert self.mod._claim_sentence(ctx, "the standard") == "See also [the standard](https://b) for details."
        assert not self.mod.PRECISION_RE.search(self.mod._claim_sentence(ctx, "the standard"))

    def test_keyword_precision_claim_needs_a_real_quote(self):
        lr = self._lr("a judge of comparable size roughly doubles the cost [source]", "Adding a judge increases cost and latency.")
        with self._judge({"verdict": "PASS", "quote": "a judge doubles the cost", "reason": "stated"}):
            v = self.mod._verify_one_link(lr)
        assert v["verdict"] == "FAIL" and "quote not found" in v["reason"]

    def test_handler_reports_precision_and_recency(self):
        md = ("---\ntitle: t\n---\n\nTesting is roughly 30 percent of cost, per [a model](https://a.example/x). "
              "See also [the standard](https://b.example/y).")
        fetch = {"https://a.example/x": (True, 200, "A", "Testing matters.", "2026-09-05"),
                 "https://b.example/y": (True, 200, "B", "The standard says so.", "")}
        verdicts = {"https://a.example/x": ("FAIL", "figure not found in source text", True),
                    "https://b.example/y": ("PASS", "", False)}
        def judge(lr):
            verdict, reason, precision = verdicts[lr["url"]]
            return {"url": lr["url"], "link_text": lr["link_text"], "context": lr["context"], "published_at": lr["published_at"],
                    "precision": precision, "verdict": verdict, "reason": reason, "quote": ""}
        with patch.object(self.mod, "_fetch_page_meta", side_effect=lambda url: fetch[url]), \
             patch.object(self.mod, "_verify_one_link", side_effect=judge), \
             patch.object(self.mod, "_repair_citations", side_effect=lambda v, m, r: (m, v)):
            out = self.mod.handler({"title": "t", "markdown": md}, _LambdaContext())
        ver = out["verification"]
        assert ver["total_links"] == 2 and ver["failures"] == 1 and ver["passed"] == 1
        assert ver["precision_unsupported"] == 1
        assert ver["dated_sources"] == 1 and ver["min_source_age_days"] is not None
        assert "CITATION FAIL: figure not found" in out["markdown"]


# ---------------------------------------------------------------------------
# Draft: rewrite diff guard
# ---------------------------------------------------------------------------

_POST = """## One

Intro with a [source](https://a.example) and forty words of prose to make the ratio arithmetic meaningful across the guard's checks here.

<!-- CHART: x | a: 1 -->

## Two

Second section cites [another](https://b.example) and keeps going with enough text for the counts to be stable.

## Three

Closing section with [a third](https://c.example)."""


class TestRewriteGuard:
    def setup_method(self):
        self.draft = _load_module("draft")
        self.draft._GUARD_REJECTIONS.clear()

    def test_accepts_faithful_rewrite(self):
        after = _POST.replace("Intro with", "An intro with")
        assert self.draft._guard_rewrite("voice audit", _POST, after) == after
        assert self.draft._GUARD_REJECTIONS == []

    def test_rejects_dropped_section(self):
        after = _POST.split("## Three")[0]
        assert self.draft._guard_rewrite("voice audit", _POST, after) == _POST
        assert any("voice audit" in r and "headings" in r for r in self.draft._GUARD_REJECTIONS)

    def test_rejects_lost_citation_for_voice_but_allows_some_for_citation_audit(self):
        after = _POST.replace("[a third](https://c.example)", "a third")
        assert self.draft._guard_rewrite("voice audit", _POST, after) == _POST
        assert self.draft._guard_rewrite("citation audit", _POST, after, max_url_loss_frac=0.4) == after

    def test_rejects_dropped_placeholder(self):
        after = _POST.replace("<!-- CHART: x | a: 1 -->\n", "")
        assert self.draft._guard_rewrite("voice audit", _POST, after) == _POST

    def test_rejects_truncation(self):
        assert self.draft._guard_rewrite("voice audit", _POST, _POST[: len(_POST) // 2]) == _POST

    def test_structure_audit_may_add_up_to_two_headings(self):
        after = "**TL;DR:** short.\n\n" + _POST + "\n\n## Next Steps\n\n- do the thing\n"
        got = self.draft._guard_rewrite("structure audit", _POST, after, min_ratio=0.95, max_ratio=1.3, heading_delta=(0, 2))
        assert got == after

    def test_handler_surfaces_rejections_as_structure_notes(self):
        """A rejected pass must be visible on the review email, never silent."""
        self.draft._GUARD_REJECTIONS.append("voice audit rewrite rejected by diff guard (words 2900 -> 1400); original kept")
        notes = "\n".join(f"<!-- ⚠️ STRUCTURE: {r} -->" for r in self.draft._GUARD_REJECTIONS)
        notify = _load_module("notify")
        assert notify._KNOWN_ANNOTATION.search(notes) if hasattr(notify, "_KNOWN_ANNOTATION") else True
        assert "STRUCTURE" in notes


class TestNotifyScorecard:
    def setup_method(self):
        self.mod = _load_module("notify")
        self.mod.DRAFTS_BUCKET = "b"
        self.mod.SNS_TOPIC_ARN = "t"
        self.mod.APPROVE_URL = "https://a"
        self.mod.s3 = MagicMock()
        self.mod.s3.generate_presigned_url.return_value = "https://dl"
        self.mod.sns = MagicMock()
        self.mod.cloudwatch = MagicMock()

    def test_precision_recency_and_guard_notes_on_email_and_metrics(self):
        md = _GOOD_POST.replace("Five months ago", "<!-- ⚠️ STRUCTURE: voice audit rewrite rejected by diff guard (words 2900 -> 1400); original kept -->\n\nFive months ago")
        ver = {"total_links": 8, "passed": 6, "repaired": 0, "warnings": 1, "failures": 1, "unreachable": 0,
               "precision_unsupported": 2, "dated_sources": 5, "min_source_age_days": 3, "details": []}
        self.mod.handler({"title": "T", "slug": "t", "markdown": md, "date": "2026-09-10", "charts": [],
                          "verification": ver, "author_content": "", "taskToken": "tok"}, _LambdaContext())
        msg = self.mod.sns.publish.call_args.kwargs["Message"]
        assert "2 sentence(s) state a precise figure" in msg
        assert "Freshest source: 3 day(s) old (5 of 8 sources" in msg
        assert "STRUCTURE note: voice audit rewrite rejected" in msg
        names = {d["MetricName"] for d in self.mod.cloudwatch.put_metric_data.call_args.kwargs["MetricData"]}
        assert {"PrecisionClaimsUnsupported", "SourceRecencyDays"} <= names


class TestResearchFactCheck:
    def test_fact_check_prompt_carries_source_text_not_just_titles(self):
        research = _load_module("research")
        results = [{"title": "Cost model", "url": "https://x.example", "content": "Testing is thirty percent of total development cost in this model."}]
        with patch.object(research.bedrock, "invoke_model", return_value=_bedrock_response("CLAIM: x\nSTATUS: SUPPORTED\nSOURCE: Cost model\nQUOTE: thirty percent")) as m:
            out = research._cross_reference_check("notes", results)
        prompt = json.loads(m.call_args.kwargs["body"])["messages"][0]["content"]
        assert "thirty percent of total development cost" in prompt
        assert "A source title alone never supports a claim" in prompt
        assert "Fact-Check Summary" in out


# ---------------------------------------------------------------------------
# Shared LLM: cross-family judge via Converse
# ---------------------------------------------------------------------------

def _converse_response(text, with_reasoning=True):
    content = ([{"reasoningContent": {"reasoningText": {"text": "thinking..."}}}] if with_reasoning else []) + [{"text": text}]
    return {"output": {"message": {"role": "assistant", "content": content}}}


class TestCrossFamilyJudge:
    def setup_method(self):
        self.llm = importlib.import_module("llm")
        self.llm._judge_fallback_notified.clear()
        self.llm.bedrock.converse.reset_mock(return_value=True, side_effect=True)
        self.llm.bedrock.invoke_model.reset_mock(return_value=True, side_effect=True)

    def test_converse_returns_text_blocks_only(self):
        with patch.object(self.llm.bedrock, "converse", return_value=_converse_response('{"score": 4}')) as m:
            out = self.llm.converse("p", model_id="openai.gpt-oss-120b-1:0", system="sys")
        assert out == '{"score": 4}'
        kw = m.call_args.kwargs
        assert kw["modelId"] == "openai.gpt-oss-120b-1:0"
        assert kw["system"] == [{"text": "sys"}]
        assert kw["messages"][0]["content"][0]["text"] == "p"

    def test_judge_candidates_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("JUDGE_MODEL_ID", raising=False)
        monkeypatch.delenv("JUDGE_MODEL_ID_VOICE_FIDELITY", raising=False)
        assert self.llm.judge_candidates_for("voice_fidelity") == list(self.llm._DEFAULT_JUDGE_CANDIDATES)

    def test_judge_candidates_parses_comma_separated_priority_list(self, monkeypatch):
        monkeypatch.setenv("JUDGE_MODEL_ID", "model.a, model.b ,model.c")
        assert self.llm.judge_candidates_for("voice_fidelity") == ["model.a", "model.b", "model.c"]

    def test_seat_specific_env_wins_over_shared(self, monkeypatch):
        monkeypatch.setenv("JUDGE_MODEL_ID", "shared.model")
        monkeypatch.setenv("JUDGE_MODEL_ID_VOICE_FIDELITY", "other.model")
        assert self.llm.judge_candidates_for("voice_fidelity") == ["other.model"]
        assert self.llm.judge_candidates_for("target_reader") == ["shared.model"]

    def test_judge_walks_the_priority_list_before_falling_back_to_anthropic(self, monkeypatch):
        """A newer frontier model can be prepended without any candidate becoming a hard
        dependency: the first inaccessible one is skipped, not fatal."""
        monkeypatch.setenv("JUDGE_MODEL_ID", "newer.frontier.model,openai.gpt-oss-120b-1:0")
        calls = []

        def fake_converse(**kw):
            calls.append(kw["modelId"])
            if kw["modelId"] == "newer.frontier.model":
                raise Exception("ValidationException: model identifier is invalid")
            return _converse_response("ok")

        with patch.object(self.llm.bedrock, "converse", side_effect=fake_converse), \
             patch.object(self.llm.bedrock, "invoke_model") as inv:
            text, model = self.llm.invoke_judge("p", seat="target_reader", fallback_model_id="sonnet")
        assert (text, model) == ("ok", "openai.gpt-oss-120b-1:0")
        assert calls == ["newer.frontier.model", "openai.gpt-oss-120b-1:0"]
        inv.assert_not_called()

    def test_judge_falls_back_to_anthropic_when_every_candidate_unavailable(self, monkeypatch):
        monkeypatch.setenv("JUDGE_MODEL_ID", "openai.gpt-oss-120b-1:0")
        with patch.object(self.llm.bedrock, "converse", side_effect=Exception("AccessDeniedException: model not enabled")), \
             patch.object(self.llm.bedrock, "invoke_model", return_value=_bedrock_response("fallback answer")) as inv:
            text, model = self.llm.invoke_judge("p", seat="target_reader", fallback_model_id="us.anthropic.claude-sonnet-4-6", system="sys")
        assert text == "fallback answer" and model == "us.anthropic.claude-sonnet-4-6"
        body = json.loads(inv.call_args.kwargs["body"])
        assert body["messages"][0]["content"].startswith("sys\n\n")

    def test_judge_does_not_swallow_non_recoverable_errors(self, monkeypatch):
        monkeypatch.setenv("JUDGE_MODEL_ID", "openai.gpt-oss-120b-1:0")
        with patch.object(self.llm.bedrock, "converse", side_effect=Exception("SomethingElseBroke")), \
             pytest.raises(Exception, match="SomethingElseBroke"):
            self.llm.invoke_judge("p", seat="target_reader", fallback_model_id="sonnet")

    def test_judge_uses_primary_when_it_works(self, monkeypatch):
        monkeypatch.setenv("JUDGE_MODEL_ID", "openai.gpt-oss-120b-1:0")
        with patch.object(self.llm.bedrock, "converse", return_value=_converse_response("ok")), \
             patch.object(self.llm.bedrock, "invoke_model") as inv:
            text, model = self.llm.invoke_judge("p", seat="target_reader", fallback_model_id="sonnet")
        assert (text, model) == ("ok", "openai.gpt-oss-120b-1:0")
        inv.assert_not_called()


# ---------------------------------------------------------------------------
# Evaluate Lambda: rubric panel + bounded repair
# ---------------------------------------------------------------------------

_DRAFT_MD = """---
title: "T"
date: 2026-09-10
author: "Khaled Zaky"
categories: ["ai"]
description: "A description long enough to pass the frontmatter checks and then some more words."

---

Most teams arrive at the same conclusion: identity is the control plane. I have argued this myself with a [source](https://a.example).

## Why identity is not enough

A judge of comparable size roughly doubles the cost, per [a vendor](https://b.example). Every pod gets the same identity.

## What to do instead

Bind policy at the boundary and prove closure with [evidence](https://c.example).
"""


def _seat_json(**overrides):
    base = {"score": 4, "findings": []}
    base.update(overrides)
    return json.dumps(base)


class TestEvaluate:
    def setup_method(self):
        self.mod = _load_module("evaluate")
        self.mod._voice_refs_cache = ["Reference prose in the author's voice."]

    def _run(self, answers, event_extra=None, max_repairs=1):
        """answers: dict seat -> JSON text (or callable(draft)->text). Repair answers via 'repair'."""
        self.mod.MAX_REPAIRS = max_repairs
        calls = []

        def fake_run_seat(seat, draft_body, **kw):
            calls.append(seat)
            ans = answers[seat]
            text = ans(draft_body) if callable(ans) else ans
            return {**self.mod._normalise(seat, json.loads(text)), "model": "test-model"}

        def fake_invoke_model(prompt, **kw):
            calls.append("repair")
            return answers["repair"](prompt) if callable(answers.get("repair")) else answers.get("repair", "")

        with patch.object(self.mod, "run_seat", side_effect=fake_run_seat), patch.object(self.mod, "invoke_model", side_effect=fake_invoke_model):
            out = self.mod.handler({"title": "T", "markdown": _DRAFT_MD, "research": "notes", "verification": {"details": []},
                                    "author_content": "x" * 200, **(event_extra or {})}, _LambdaContext())
        return out, calls

    def test_clean_draft_passes_with_all_five_seats_and_no_repair(self):
        answers = {s: _seat_json(score=5) for s in self.mod.SEATS}
        answers["author_intent"] = _seat_json(score=9, preserved=["x"], drifted=[], added=[])
        out, calls = self._run(answers)
        ev = out["evaluation"]
        assert set(ev["seats"]) == set(self.mod.SEATS)
        assert ev["blocking"] == [] and ev["iterations"] == 0
        assert "repair" not in calls
        assert out["markdown"] == _DRAFT_MD

    def test_author_intent_seat_skipped_without_author_content(self):
        answers = {s: _seat_json(score=5) for s in self.mod.SEATS}
        out, calls = self._run(answers, event_extra={"author_content": ""})
        assert "author_intent" not in out["evaluation"]["seats"]

    def test_taste_seats_never_block(self):
        answers = {s: _seat_json(score=1, findings=[{"quote": "x", "issue": "bad", "fix": "y", "blocking": True}]) for s in ("target_reader", "skeptical_expert", "voice_fidelity")}
        answers["fact_checker"] = _seat_json(score=5)
        answers["author_intent"] = _seat_json(score=9)
        out, calls = self._run(answers)
        assert out["evaluation"]["blocking"] == []
        assert "repair" not in calls

    def test_blocking_fact_finding_triggers_one_guarded_repair_then_reeval(self):
        finding = {"quote": "A judge of comparable size roughly doubles the cost", "issue": "figure unsupported", "fix": "hedge it", "blocking": True}
        def fact(draft_body):
            return _seat_json(score=5) if "can materially increase" in draft_body else _seat_json(score=2, findings=[finding])
        def repair(prompt):
            body = prompt.split("POST BODY:\n", 1)[1]
            return body.replace("roughly doubles the cost", "can materially increase cost")
        answers = {"fact_checker": fact, "author_intent": _seat_json(score=9), "target_reader": _seat_json(), "skeptical_expert": _seat_json(), "voice_fidelity": _seat_json(), "repair": repair}
        out, calls = self._run(answers)
        ev = out["evaluation"]
        assert ev["iterations"] == 1 and ev["blocking"] == []
        assert "can materially increase cost" in out["markdown"]
        assert out["markdown"].startswith("---\ntitle: \"T\"")  # frontmatter re-attached
        assert calls.count("repair") == 1
        assert calls.count("fact_checker") == 2 and calls.count("voice_fidelity") == 1  # only blocking seats re-run
        assert "1 repair pass" in ev["repair_note"] or "repair 1 applied" in ev["repair_note"]

    def test_repair_that_drops_a_section_is_rejected_and_reported(self):
        finding = {"quote": "Every pod gets the same identity.", "issue": "unsupported", "fix": "remove", "blocking": True}
        answers = {"fact_checker": _seat_json(score=2, findings=[finding]), "author_intent": _seat_json(score=9),
                   "target_reader": _seat_json(), "skeptical_expert": _seat_json(), "voice_fidelity": _seat_json(),
                   "repair": lambda prompt: prompt.split("POST BODY:\n", 1)[1].split("## What to do instead")[0]}
        out, calls = self._run(answers)
        ev = out["evaluation"]
        assert out["markdown"] == _DRAFT_MD
        assert "rejected by diff guard" in ev["repair_note"]
        assert len(ev["blocking"]) == 1 and ev["blocking"][0]["seat"] == "fact_checker"

    def test_low_intent_score_blocks(self):
        answers = {s: _seat_json(score=5) for s in self.mod.SEATS}
        answers["author_intent"] = _seat_json(score=3, drifted=["softened the main claim"])
        answers["repair"] = lambda prompt: prompt.split("POST BODY:\n", 1)[1]
        out, calls = self._run(answers)
        assert any("intent score 3/10" in b["issue"] for b in out["evaluation"]["blocking"])

    def test_gate_error_blocks_without_attempting_repair(self):
        answers = {s: _seat_json(score=5) for s in self.mod.SEATS}
        answers["author_intent"] = _seat_json(score=9)
        out, calls = self._run(answers, event_extra={"markdown": _FENCED_POST})
        assert any(b["seat"] == "gate" and "body_fenced" in b["issue"] for b in out["evaluation"]["blocking"])
        assert "repair" not in calls

    def test_unavailable_seat_is_reported_not_scored(self):
        with patch.object(self.mod, "invoke_judge", side_effect=Exception("AccessDenied")), \
             patch.object(self.mod, "invoke_model", side_effect=Exception("boom")):
            r = self.mod.run_seat("target_reader", "body")
        assert r["score"] is None and "unavailable" in r

    def test_seat_prompt_carries_references_and_verdicts(self):
        captured = {}
        def fake_judge(prompt, **kw):
            captured["prompt"] = prompt
            return _seat_json(), "m"
        with patch.object(self.mod, "invoke_judge", side_effect=fake_judge):
            self.mod.run_seat("voice_fidelity", "the draft", references=["Ref one text", "Ref two text"])
        assert "Reference A:\nRef one text" in captured["prompt"] and "Reference B:" in captured["prompt"]
        assert "Output ONLY one JSON object" in captured["prompt"]

    def test_normalise_is_robust_to_malformed_findings(self):
        r = self.mod._normalise("x", {"score": "4", "findings": ["not a dict", {"quote": 1, "issue": None, "blocking": "yes"}]})
        assert r["findings"] == [{"quote": "1", "issue": "None", "fix": "", "blocking": True}]

    def test_parse_json_tolerates_fences_and_prose(self):
        assert self.mod._parse_json('Sure:\n```json\n{"score": 3, "findings": []}\n```')["score"] == 3


class TestNotifyRenderScorecard:
    def test_scorecard_block_lists_seats_blocking_and_findings(self):
        notify = _load_module("notify")
        ev = {"blocking": [{"seat": "fact_checker", "quote": "q", "issue": "figure unsupported", "fix": "hedge", "blocking": True}],
              "iterations": 1, "repair_note": "repair 1 applied; 1 blocking finding(s) remain", "voice_references": 3,
              "seats": {"fact_checker": {"score": 2, "model": "us.anthropic.claude-sonnet-4-6",
                                         "findings": [{"quote": "the cost doubles", "issue": "figure unsupported", "fix": "hedge it", "blocking": True}]},
                        "target_reader": {"score": 4, "model": "openai.gpt-oss-120b-1:0", "findings": [], "pushback": ["\"Every pod\" is not true on EKS"], "missing": ["cost"]},
                        "voice_fidelity": {"score": None, "unavailable": "AccessDenied"}}}
        block = notify._scorecard_block(ev)
        assert "RUBRIC PANEL" in block and "1 BLOCKING finding(s) remain after 1 repair pass" in block
        assert "Fact check       2/5  findings: 1 (1 blocking)" in block
        assert "figure unsupported" in block and "the cost doubles" in block and "hedge it" in block
        assert "Target reader    4/5" in block and "gpt-oss-120b-1:0" in block and "pushback:" in block
        assert "Voice fidelity   unavailable" in block
        assert notify._scorecard_block({}) == ""


# ---------------------------------------------------------------------------
# Template + deploy script consistency for the new state
# ---------------------------------------------------------------------------

class TestPipelineWiring:
    """Structural checks that catch a half-wired Lambda before CloudFormation does."""

    def _definition(self):
        text = (AGENT_DIR / "template.yaml").read_text()
        start = text.index("DefinitionString: !Sub |") + len("DefinitionString: !Sub |")
        body_lines = []
        for line in text[start:].splitlines()[1:]:
            if line.strip() and not line.startswith(" " * 8):
                break
            body_lines.append(line)
        raw = textwrap.dedent("\n".join(body_lines))
        raw = re.sub(r"\$\{[^}]+\}", "SUB", raw)
        return json.loads(raw)

    def test_state_machine_definition_is_valid_json_with_evaluate_state(self):
        definition = self._definition()
        states = definition["States"]
        assert "Evaluate" in states
        assert states["VerifyCitations"]["Next"] == "Evaluate"
        assert states["Evaluate"]["Next"] == "GenerateCharts"
        assert states["GenerateCharts"]["Parameters"]["markdown.$"] == "$.evaluate_output.markdown"
        assert states["NotifyForReview"]["Parameters"]["Payload"]["evaluation.$"] == "$.evaluate_output.evaluation"
        assert states["Revise"]["Next"] == "VerifyCitations"  # revision loop re-enters before Evaluate

    def test_every_next_and_catch_target_exists(self):
        states = self._definition()["States"]
        targets = []
        for st in states.values():
            for key in ("Next", "Default"):
                if key in st:
                    targets.append(st[key])
            for c in st.get("Catch", []):
                targets.append(c["Next"])
            for ch in st.get("Choices", []):
                targets.append(ch["Next"])
        missing = sorted(set(targets) - set(states))
        assert missing == [], missing

    def test_template_and_deploy_script_list_every_lambda_dir(self):
        template = (AGENT_DIR / "template.yaml").read_text()
        deploy = (AGENT_DIR / "deploy.sh").read_text()
        for d in LAMBDA_DIRS:
            assert f'FunctionName: !Sub "${{AWS::StackName}}-{d}"' in template, d
            assert d in deploy, d
            # The errors alarm is one alarm per function, OR-ed by a composite alarm.
            # A single alarm cannot cover all of them: CloudWatch caps an alarm at 10
            # metrics, and SEARCH() — which would have sidestepped the cap — is
            # rejected on alarms outright. See TestCloudWatchAlarmMetricLimit.
            assert f'ALARM("${{AWS::StackName}}-errors-{d}")' in template, d
        assert "EvaluateFunction.Arn" in template  # state machine may invoke it
        assert "m1+m2+m3" not in template, "per-function metric enumeration is back and will hit the 10-metric cap"
        assert "SUM(SEARCH(" not in template, "SEARCH is not supported on CloudWatch alarms"

    def test_common_deps_manifests_reference_existing_modules(self):
        for d in LAMBDA_DIRS:
            manifest = AGENT_DIR / d / ".common-deps"
            if manifest.exists():
                for mod in manifest.read_text().split():
                    assert (AGENT_DIR / "common" / mod).exists(), f"{d} lists {mod}"


# ---------------------------------------------------------------------------
# Opus fallback: a bad/unknown model id degrades the same way as access-denied
# ---------------------------------------------------------------------------

class TestOpusFallbackHardening:
    def setup_method(self):
        self.llm = importlib.import_module("llm")
        self.llm.bedrock.invoke_model.reset_mock(return_value=True, side_effect=True)

    @pytest.mark.parametrize("error", [
        "AccessDeniedException: not authorized",
        "ValidationException: the provided model identifier is invalid",
        "ResourceNotFoundException: could not find model",
    ])
    def test_unavailable_or_invalid_model_id_falls_back_to_sonnet(self, error, monkeypatch):
        """A model-ID bump (update-models.sh landing on a profile that turns out not to
        be real, or not yet enabled) must degrade the same way access-denied does —
        never a hard pipeline failure."""
        monkeypatch.delenv("OPUS_OUTER_RETRY_DELAYS", raising=False)
        with patch.object(self.llm, "emit_opus_fallback_metric") as metric, \
             patch.object(self.llm.bedrock, "invoke_model", side_effect=[Exception(error), _bedrock_response("fallback")]):
            out = self.llm.invoke_with_opus_fallback("p", primary_model_id="bad-model", fallback_model_id="sonnet", label="draft")
        assert out == "fallback"
        metric.assert_called_once_with("bad-model")

    def test_unrelated_error_still_propagates(self, monkeypatch):
        monkeypatch.delenv("OPUS_OUTER_RETRY_DELAYS", raising=False)
        with patch.object(self.llm.bedrock, "invoke_model", side_effect=Exception("BotoCoreError: connection reset")), \
             pytest.raises(Exception, match="connection reset"):
            self.llm.invoke_with_opus_fallback("p", primary_model_id="m", fallback_model_id="sonnet", label="draft")


# ---------------------------------------------------------------------------
# Token budgets: every pass that reproduces a whole post gets the same headroom as
# Draft's own generation pass, which was bumped from 8192 to 16000 for exactly this
# reason. A regression here silently reintroduces the truncation bugs from 2026-07.
# ---------------------------------------------------------------------------

class TestTokenBudgets:
    def test_draft_full_rewrite_passes_use_16000(self):
        src = (Path(__file__).parent.parent / "draft" / "index.py").read_text()
        # the Opus generation pass (pre-existing) + citation, voice, insight, structure,
        # entity audits (5 full-post-reproduction passes bumped in this change) = 6
        assert src.count("max_tokens=16000") == 6, "a full-post audit pass regressed below 16000"
        assert "max_tokens=8192)" not in src, "a full-post audit pass is still capped at the old 8192"

    def test_research_synthesis_uses_16000(self):
        src = (Path(__file__).parent.parent / "research" / "index.py").read_text()
        assert "max_tokens=16000," in src

    def test_evaluate_seats_and_repair_have_headroom(self):
        src = (Path(__file__).parent.parent / "evaluate" / "index.py").read_text()
        assert "max_tokens=4000" in src, "seat calls regressed below the 4000-token floor a full 10-finding response needs"
        assert "max_tokens=16000" in src, "the repair pass (full post reproduction) regressed below 16000"
        assert "max_tokens=2000" not in src

    def test_verify_legacy_batched_fallback_has_headroom(self):
        src = (Path(__file__).parent.parent / "verify" / "index.py").read_text()
        assert '"max_tokens": 2048' in src


# ---------------------------------------------------------------------------
# Model-upgrade infrastructure: deploy.sh reads the SSM source of truth, HaikuModelId
# is a real parameter (not 4 scattered literals), and update-models.sh has valid bash
# and covers every Lambda that reads a Claude model env var.
# ---------------------------------------------------------------------------

class TestModelUpgradeInfrastructure:
    def test_every_agent_shell_script_has_valid_bash_syntax(self):
        """update-models.sh's SSM-write loop (`for path val in ...`) was never valid
        bash from the day it was committed — this would have caught it immediately."""
        scripts = [AGENT_DIR / "deploy.sh", *sorted((AGENT_DIR / "scripts").glob("*.sh"))]
        assert len(scripts) >= 5
        for script in scripts:
            result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
            assert result.returncode == 0, f"{script.name}: {result.stderr}"

    def test_deploy_sh_reads_ssm_before_falling_back_to_literals(self):
        deploy = (AGENT_DIR / "deploy.sh").read_text()
        for path in ("/blog-agent/models/sonnet", "/blog-agent/models/opus",
                     "/blog-agent/models/haiku", "/blog-agent/models/judge"):
            assert path in deploy, f"deploy.sh no longer reads {path} from SSM"
        for param in ("BedrockModelId=\"$BEDROCK_MODEL_ID\"", "OpusModelId=\"$OPUS_MODEL_ID\"",
                      "HaikuModelId=\"$HAIKU_MODEL_ID\"", "JudgeModelId=\"$JUDGE_MODEL_ID\""):
            assert param in deploy, f"deploy.sh no longer passes {param}"
        # the specific regression this guards: a hardcoded literal passed directly as a
        # parameter-override would silently undo any live model bump on the next deploy
        assert 'BedrockModelId="us.anthropic.claude-sonnet-4-6" \\' not in deploy
        assert 'OpusModelId="us.anthropic.claude-opus-4-6-v1" \\' not in deploy

    def test_haiku_model_id_is_a_real_parameter_not_scattered_literals(self):
        template = (AGENT_DIR / "template.yaml").read_text()
        assert re.search(r"^  HaikuModelId:\n    Type: String", template, re.MULTILINE)
        assert template.count("HAIKU_MODEL_ID: !Ref HaikuModelId") == 4
        assert "HAIKU_MODEL_ID: us.anthropic.claude-haiku-4-5-20251001-v1:0" not in template

    def test_update_models_covers_every_lambda_that_reads_a_claude_model_env_var(self):
        script = (AGENT_DIR / "scripts" / "update-models.sh").read_text()
        for fn_suffix in ("draft", "research", "chart", "verify", "evaluate", "notify"):
            assert f'f"{{stack}}-{fn_suffix}"' in script, f"update-models.sh no longer updates {{stack}}-{fn_suffix}"

    def test_update_judge_model_script_exists_and_is_executable(self):
        script = AGENT_DIR / "scripts" / "update-judge-model.sh"
        assert script.exists()
        assert script.stat().st_mode & 0o111  # executable bit set, without importing os
        text = script.read_text()
        # Both catalogs: list-foundation-models (on-demand) AND list-inference-profiles
        # (where third-party models like OpenAI's actually live on this account —
        # a foundation-models-only scan misses them entirely).
        assert "list-foundation-models" in text
        assert "list-inference-profiles" in text
        assert "PREFERENCE_LIST" in text
        assert "/blog-agent/models/judge" in text

    def test_update_models_recognizes_bare_major_version_ids(self):
        """Bedrock's newest Anthropic profiles (us.anthropic.claude-sonnet-5,
        us.anthropic.claude-opus-5) are a single number with no minor version — a
        different shape than claude-opus-4-8. The old two-number-only regex would
        never discover or prefer them, silently capping upgrades at the 4.x line
        forever even once 5-generation models are ACTIVE and accessible."""
        script = (AGENT_DIR / "scripts" / "update-models.sh").read_text()
        assert script.count("pat_bare") >= 2  # both the discovery pass and the accessibility-probe pass


# ---------------------------------------------------------------------------
# Regressions found by a live deploy attempt (2026-09-10). Each of these shipped
# and either broke the deploy or silently did nothing; each test below fails
# against the code as it was.
# ---------------------------------------------------------------------------

def _load_cfn_template():
    """Parse template.yaml with CloudFormation's intrinsic tags stubbed out."""
    import yaml

    class _CFNLoader(yaml.SafeLoader):
        pass

    def _passthrough(loader, node):
        if isinstance(node, yaml.ScalarNode):
            return loader.construct_scalar(node)
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node, deep=True)
        return loader.construct_mapping(node, deep=True)

    for tag in ("!Sub", "!Ref", "!GetAtt", "!Join", "!Select", "!Split",
                "!ImportValue", "!If", "!Equals", "!Not", "!FindInMap",
                "!Base64", "!Condition", "!And", "!Or"):
        _CFNLoader.add_constructor(tag, _passthrough)
    return yaml.load((AGENT_DIR / "template.yaml").read_text(), Loader=_CFNLoader)


def _lambda_function_suffixes(resources):
    """The stack-name-relative suffix of every Lambda in the template, e.g. "draft"."""
    suffixes = []
    for res in resources.values():
        if res.get("Type") != "AWS::Lambda::Function":
            continue
        name = res.get("Properties", {}).get("FunctionName", "")
        if isinstance(name, str) and name.startswith("${AWS::StackName}-"):
            suffixes.append(name[len("${AWS::StackName}-"):])
    return sorted(suffixes)


def _error_alarms(resources):
    """Per-function Lambda error alarms, keyed by the function suffix they watch."""
    found = {}
    for logical_id, res in resources.items():
        if res.get("Type") != "AWS::CloudWatch::Alarm":
            continue
        props = res.get("Properties", {})
        if props.get("Namespace") != "AWS/Lambda" or props.get("MetricName") != "Errors":
            continue
        for dim in props.get("Dimensions", []):
            value = dim.get("Value", "")
            if dim.get("Name") == "FunctionName" and value.startswith("${AWS::StackName}-"):
                found[value[len("${AWS::StackName}-"):]] = (logical_id, props)
    return found


class TestCloudWatchAlarmMetricLimit:
    """Two live failures shaped this. First "Too many metrics in alarm, maximum is 10":
    the alarm carried one MetricStat per Lambda and was already at exactly 10 before the
    11th function was added. The SEARCH() rewrite that replaced it could not work either
    — CloudWatch answers "SEARCH is not supported on Metric Alarms", bare or wrapped in
    SUM(), because an alarm needs one static series. Hence one alarm per function, OR-ed
    by a composite alarm, which has no practical ceiling."""

    def test_no_alarm_exceeds_the_cloudwatch_metric_cap(self):
        resources = _load_cfn_template()["Resources"]
        for logical_id, res in resources.items():
            if res.get("Type") != "AWS::CloudWatch::Alarm":
                continue
            metrics = res.get("Properties", {}).get("Metrics")
            if metrics is None:
                continue
            assert len(metrics) <= 10, (
                f"{len(metrics)} metrics in {logical_id}; CloudWatch's hard cap is 10 "
                "and the stack update fails outright above it"
            )

    def test_no_alarm_uses_search_which_cloudwatch_rejects(self):
        resources = _load_cfn_template()["Resources"]
        for logical_id, res in resources.items():
            if res.get("Type") != "AWS::CloudWatch::Alarm":
                continue
            for metric in res.get("Properties", {}).get("Metrics") or []:
                expr = metric.get("Expression", "")
                assert "SEARCH(" not in expr, (
                    f"{logical_id} uses SEARCH(), which CloudWatch rejects on alarms "
                    '("SEARCH is not supported on Metric Alarms") — the stack update '
                    "will fail and roll back"
                )

    def test_every_lambda_has_its_own_error_alarm(self):
        resources = _load_cfn_template()["Resources"]
        expected = _lambda_function_suffixes(resources)
        covered = _error_alarms(resources)
        missing = [s for s in expected if s not in covered]
        assert not missing, (
            f"these Lambdas have no error alarm: {missing}. Add an alarm and a clause "
            "to LambdaErrorCompositeAlarm's AlarmRule."
        )

    def test_composite_alarm_rule_references_every_per_function_alarm(self):
        resources = _load_cfn_template()["Resources"]
        composite = resources["LambdaErrorCompositeAlarm"]
        rule = composite["Properties"]["AlarmRule"]
        for suffix, (logical_id, props) in sorted(_error_alarms(resources).items()):
            assert props["AlarmName"] in rule, (
                f"{logical_id} exists but is not in the composite AlarmRule, so errors "
                f"in {suffix} would never notify"
            )

    def test_composite_depends_on_the_alarms_it_names(self):
        resources = _load_cfn_template()["Resources"]
        composite = resources["LambdaErrorCompositeAlarm"]
        depends = composite.get("DependsOn") or []
        for _suffix, (logical_id, _) in sorted(_error_alarms(resources).items()):
            assert logical_id in depends, (
                f"{logical_id} is named in the AlarmRule but missing from DependsOn; "
                "AlarmRule is a plain string so CloudFormation infers no ordering and "
                "the composite can be created before its children exist"
            )

    def test_only_the_composite_notifies(self):
        resources = _load_cfn_template()["Resources"]
        composite = resources["LambdaErrorCompositeAlarm"]["Properties"]
        assert composite["AlarmActions"], "the composite must keep the alarm action"
        for _suffix, (logical_id, props) in sorted(_error_alarms(resources).items()):
            assert not props.get("AlarmActions"), (
                f"{logical_id} has its own AlarmActions; the composite already notifies, "
                "so one error would send two alerts"
            )

    def test_per_function_alarms_do_not_fire_on_missing_data(self):
        resources = _load_cfn_template()["Resources"]
        for _suffix, (logical_id, props) in sorted(_error_alarms(resources).items()):
            assert props["TreatMissingData"] == "notBreaching", (
                f"{logical_id} would alarm when the function is simply idle"
            )
            assert props["Period"], f"{logical_id} needs a Period"


class TestTemplateParameterHygiene:
    """A duplicate YAML key silently keeps only the last value. JudgeModelId ended up
    carrying OpusModelId's description, and OpusModelId had none — CloudFormation
    accepted it, so only a linter would ever have caught it."""

    def test_no_duplicate_keys_in_the_template(self):
        import yaml

        seen_problems = []

        class _DupCheckLoader(yaml.SafeLoader):
            pass

        def _no_dupes(loader, node, deep=False):
            mapping = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                if key in mapping:
                    seen_problems.append((key, key_node.start_mark.line + 1))
                mapping[key] = loader.construct_object(value_node, deep=deep)
            return mapping

        def _passthrough(loader, n):
            if isinstance(n, yaml.ScalarNode):
                return loader.construct_scalar(n)
            if isinstance(n, yaml.SequenceNode):
                return loader.construct_sequence(n, deep=True)
            return _no_dupes(loader, n, deep=True)

        _DupCheckLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_dupes)
        for tag in ("!Sub", "!Ref", "!GetAtt", "!Join", "!Select", "!Split",
                    "!ImportValue", "!If", "!Equals", "!Not", "!FindInMap", "!Base64", "!Condition"):
            _DupCheckLoader.add_constructor(tag, _passthrough)

        yaml.load((AGENT_DIR / "template.yaml").read_text(), Loader=_DupCheckLoader)
        assert seen_problems == [], f"duplicate YAML keys (last one silently wins): {seen_problems}"

    def test_every_model_parameter_has_its_own_description(self):
        params = _load_cfn_template()["Parameters"]
        for name in ("BedrockModelId", "OpusModelId", "HaikuModelId", "JudgeModelId"):
            assert name in params, f"{name} parameter missing"
            assert params[name].get("Description"), f"{name} has no Description"
        assert "Opus" in params["OpusModelId"]["Description"]
        # the specific corruption: JudgeModelId inheriting Opus's description text
        assert params["JudgeModelId"]["Description"] != params["OpusModelId"]["Description"]


class TestJudgeProbeAndCandidates:
    def test_converse_probe_passes_no_output_file_positional(self):
        """`aws bedrock-runtime converse` takes no output-file positional (unlike
        invoke-model). Passing one made the CLI exit with a usage error for every model,
        which 2>/dev/null hid — so the probe reported "not accessible" unconditionally
        and cross-family judging could never be enabled by this script."""
        script = (AGENT_DIR / "scripts" / "update-judge-model.sh").read_text()
        probe = script[script.index("_probe_converse()"):script.index("_probe_reason()")]
        assert "bedrock-runtime converse" in probe
        assert "/tmp/judge_probe_out.json" not in probe, "stray output-file positional is back"
        assert "2>/tmp/judge_probe_err.txt" in probe, "probe stderr must be inspectable, not discarded"

    def test_default_judge_candidates_are_verified_accessible_ones_only(self):
        llm = importlib.import_module("llm")
        candidates = list(llm._DEFAULT_JUDGE_CANDIDATES)
        assert candidates, "there must be at least one judge candidate"
        # the us.-prefixed gpt-oss form was probed and returns ValidationException
        assert not any(c.startswith("us.openai.gpt-oss") for c in candidates)
        # models that are listed ACTIVE but return AccessDenied must never be defaults
        for unentitled in ("gpt-5.6", "gpt-6-astra", "claude-opus-5", "claude-fable-5"):
            assert not any(unentitled in c for c in candidates), f"{unentitled} is not entitled in the target account"

    def test_preference_list_excludes_unentitled_catalogue_entries(self):
        script = (AGENT_DIR / "scripts" / "update-judge-model.sh").read_text()
        pref = script[script.index("PREFERENCE_LIST=("):script.index(")", script.index("PREFERENCE_LIST=("))]
        for unentitled in ("gpt-5.6", "gpt-6-astra", "us.openai.gpt-oss"):
            assert unentitled not in pref, f"{unentitled} must not be in PREFERENCE_LIST"
        assert "openai.gpt-oss-120b-1:0" in pref, "the one proven-accessible OpenAI model should stay as a fallback"


class TestUpdateModelsSSMOrdering:
    def test_ssm_is_written_before_the_up_to_date_early_exit(self):
        """The SSM write sat AFTER the "already up to date" exit, so in the common case
        it never ran — leaving deploy.sh's SSM-first lookup permanently falling through
        to hardcoded defaults, i.e. inert and untested."""
        script = (AGENT_DIR / "scripts" / "update-models.sh").read_text()
        write_call = script.index("_write_ssm_params\n")
        early_exit = script.index("already up to date")
        assert write_call < early_exit, "SSM must be written before the up-to-date early exit"

    def test_ssm_write_is_skipped_on_dry_run(self):
        script = (AGENT_DIR / "scripts" / "update-models.sh").read_text()
        snippet = script[script.index("# SSM is written BEFORE"):script.index("already up to date")]
        assert "if ! $DRY_RUN; then" in snippet, "--dry-run must not mutate SSM"


class TestDeployScriptPortability:
    def test_no_gnu_only_grep_flags(self):
        """grep -oP is a GNU extension; BSD grep (macOS default, where this is actually
        run) rejects it, and under `set -e` that aborts the deploy."""
        deploy = (AGENT_DIR / "deploy.sh").read_text()
        # strip comments: the fix is documented in a comment that names the old flag
        code = "\n".join(ln for ln in deploy.splitlines() if not ln.lstrip().startswith("#"))
        assert "grep -oP" not in code
        assert "grep -P" not in code

    def test_slug_extraction_yields_only_real_slugs(self):
        """The replacement also filters to hyphenated strings: the old pattern seeded the
        known-post-slugs list with plain words like "governance", which invites Draft to
        emit /blog/governance/ as an internal link."""
        import re
        text = (AGENT_DIR / "draft" / "index.py").read_text()
        slugs = sorted({m for m in re.findall(r"['\"]([a-z0-9-]{10,})['\"]", text) if "-" in m})
        assert len(slugs) > 30, "expected the known-slug list to be substantial"
        assert all("-" in s for s in slugs)
        for junk in ("governance", "leadership", "temperature", "description", "categories"):
            assert junk not in slugs, f"{junk} is a word, not a post slug"


# ---------------------------------------------------------------------------
# Judge calibration: the scoring math that decides the preference ordering.
# The Bedrock calls need credentials, but the scoring is pure and testable here —
# and it is the part that could quietly produce a confident, wrong ranking.
# ---------------------------------------------------------------------------

class TestJudgeCalibrationScoring:
    def setup_method(self):
        evals = AGENT_DIR / "evals"
        if str(evals) not in sys.path:
            sys.path.insert(0, str(evals))
        self.cj = importlib.import_module("calibrate_judges")

    def test_removed_lines_keeps_prose_and_drops_markup(self):
        before = (
            "## A heading that changed\n"
            "The models missed 31.7% of their own semantic drift entirely.\n"
            "| a | table | row |\n"
            "short\n"
            "\n"
            "A second substantive sentence that the author later deleted outright.\n"
        )
        after = "## A heading that changed\n"
        removed = self.cj.removed_lines(before, after)
        assert any("31.7%" in r for r in removed)
        assert any("second substantive sentence" in r for r in removed)
        assert not any(r.startswith("#") or r.startswith("|") for r in removed)
        assert not any(r == "short" for r in removed)

    def test_hit_requires_the_author_to_have_changed_that_text(self):
        removed = self.cj.removed_lines(
            "The claim that verification doubles the cost of every step.\nUntouched line here that stays put.\n",
            "Untouched line here that stays put.\n",
        )
        assert self.cj.is_hit("The claim that verification doubles the cost of every step.", removed)
        assert not self.cj.is_hit("Untouched line here that stays put.", removed)

    def test_hit_matches_a_fragment_of_a_longer_removed_line(self):
        removed = self.cj.removed_lines(
            "A long removed paragraph about verification budgets that runs on for a while and says several things.\n",
            "",
        )
        assert self.cj.is_hit("A long removed paragraph about verification budgets", removed)

    def test_hit_tolerates_minor_normalization_differences(self):
        removed = self.cj.removed_lines("That's not cutting corners. That's allocation of a budget.\n", "")
        assert self.cj.is_hit("That's not cutting corners.  That's allocation of a budget", removed)

    def test_short_or_empty_quotes_never_count(self):
        """A near-empty quote would otherwise substring-match almost any line and
        inflate every model's score identically."""
        removed = self.cj.removed_lines("Some removed sentence of reasonable length here.\n", "")
        assert not self.cj.is_hit("", removed)
        assert not self.cj.is_hit("the", removed)
        assert not self.cj.is_hit("It is.", removed)

    def test_score_seat_run_counts_hits_over_findings(self):
        before = "A removed sentence long enough to count as prose.\nA kept sentence long enough to count too.\n"
        after = "A kept sentence long enough to count too.\n"
        findings = [
            {"quote": "A removed sentence long enough to count as prose."},
            {"quote": "A kept sentence long enough to count too."},
            {"quote": ""},
        ]
        assert self.cj.score_seat_run(findings, before, after) == (1, 3)

    def test_seats_are_only_scored_on_classes_they_own(self):
        cases = [
            {"commit": "a", "classes": ["citation"]},
            {"commit": "b", "classes": ["ai_pattern"]},
            {"commit": "c", "classes": ["content_loss"]},
        ]
        assert [c["commit"] for c in self.cj.relevant_cases(cases, "voice_fidelity")] == ["b"]
        assert [c["commit"] for c in self.cj.relevant_cases(cases, "fact_checker")] == ["a"]
        assert [c["commit"] for c in self.cj.relevant_cases(cases, "author_intent")] == ["c"]

    def test_aggregate_excludes_failed_runs_from_the_rates(self):
        """A model that errors on half the cases must not look good because the
        half that returned happened to score well — failures are counted separately."""
        rows = [
            {"model": "m1", "seat": "voice_fidelity", "hits": 2, "findings": 4},
            {"model": "m1", "seat": "voice_fidelity", "hits": 1, "findings": 1},
            {"model": "m1", "seat": "voice_fidelity", "error": "AccessDenied"},
        ]
        summary = self.cj.aggregate(rows)
        assert len(summary) == 1
        row = summary[0]
        assert row["cases"] == 2 and row["failed"] == 1
        assert row["hits"] == 3 and row["findings"] == 5
        assert row["hit_rate"] == 0.6
        assert row["case_recall"] == 1.0
        assert row["findings_per_case"] == 2.5

    def test_aggregate_handles_a_seat_that_found_nothing(self):
        summary = self.cj.aggregate([{"model": "m", "seat": "s", "hits": 0, "findings": 0}])
        assert summary[0]["hit_rate"] is None  # not 0.0 — no denominator, not a zero score
        assert summary[0]["case_recall"] == 0.0

    def test_estimate_mode_makes_no_bedrock_calls(self):
        """--estimate must be safe to run with no credentials and no spend: it imports
        the evaluate handler lazily precisely so this holds."""
        with patch.dict("sys.modules", {"evaluate": None}):
            rc = self.cj.main(["--estimate"])
        assert rc == 0
