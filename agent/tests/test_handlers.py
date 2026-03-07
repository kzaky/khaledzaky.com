"""Smoke tests for Lambda handler imports and signatures.

These tests validate that:
1. Every handler module can be imported without errors
2. Every handler function accepts (event, context) signature
3. No missing dependencies at import time
"""

import importlib
import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Inject a mock boto3 into sys.modules before any Lambda code imports it
_mock_boto3 = MagicMock()
sys.modules.setdefault("boto3", _mock_boto3)
sys.modules.setdefault("botocore", MagicMock())
sys.modules.setdefault("botocore.exceptions", MagicMock())

# Add each Lambda function directory to sys.path so imports resolve
AGENT_DIR = Path(__file__).parent.parent
LAMBDA_DIRS = ["research", "draft", "notify", "approve", "publish", "ingest", "chart"]

for d in LAMBDA_DIRS:
    path = str(AGENT_DIR / d)
    if path not in sys.path:
        sys.path.insert(0, path)

# Chart renderers need their parent on the path too
chart_dir = str(AGENT_DIR / "chart")
if chart_dir not in sys.path:
    sys.path.insert(0, chart_dir)


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
        render_bar_chart,
        render_comparison_diagram,
        render_convergence_diagram,
        render_pie_chart,
        render_progression_diagram,
        render_stack_diagram,
        render_venn_diagram,
    )
    assert callable(render_bar_chart)
    assert callable(render_pie_chart)
    assert callable(render_comparison_diagram)
    assert callable(render_progression_diagram)
    assert callable(render_stack_diagram)
    assert callable(render_convergence_diagram)
    assert callable(render_venn_diagram)


def test_chart_theme_constants():
    """Theme module exports expected constants."""
    from renderers.theme import COLORS, COLORS_DARK, FONT_FAMILY
    assert len(COLORS) >= 6, "Expected at least 6 chart colors"
    assert len(COLORS_DARK) >= 6, "Expected at least 6 dark mode colors"
    assert isinstance(FONT_FAMILY, str)
