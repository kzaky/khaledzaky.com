"""Pytest configuration for the blog-agent test suite.

Fails fast with an actionable message when run on a Python older than the Lambda
runtime. Without this, an older interpreter produces 16 failures all reading
`ImportError: cannot import name 'UTC' from 'datetime'`, which looks like a code
defect rather than a local-environment mismatch — it cost a real deploy session the
time to work that out. macOS still ships 3.9 as the default `python3`.
"""

import sys

# datetime.UTC (used by the Draft handler) landed in 3.11; the Lambda runtime is 3.12.
MIN_PYTHON = (3, 11)

if sys.version_info < MIN_PYTHON:
    raise RuntimeError(
        f"The blog-agent test suite needs Python >= {'.'.join(map(str, MIN_PYTHON))}, "
        f"but this is {sys.version.split()[0]} ({sys.executable}).\n"
        "The Lambda runtime is python3.12; handler code uses datetime.UTC, which does "
        "not exist before 3.11.\n"
        "Run with a newer interpreter, e.g.:\n"
        "    python3.12 -m venv /tmp/agentvenv && /tmp/agentvenv/bin/pip install -q pytest ruff\n"
        "    /tmp/agentvenv/bin/python -m pytest tests/ -q"
    )
