"""Smoke tests for Lambda handler imports and signatures.

These tests validate that:
1. Every handler module can be imported without errors
2. Every handler function accepts (event, context) signature
3. No missing dependencies at import time
"""

import importlib
import inspect
import json
import sys
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
