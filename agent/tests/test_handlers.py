"""Smoke tests for Lambda handler imports and signatures.

These tests validate that:
1. Every handler module can be imported without errors
2. Every handler function accepts (event, context) signature
3. No missing dependencies at import time
"""

import importlib
import inspect
import json
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
LAMBDA_DIRS = ["research", "draft", "verify", "notify", "approve", "publish", "ingest", "chart", "alarm-formatter", "upload"]

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
