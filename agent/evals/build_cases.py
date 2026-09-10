#!/usr/bin/env python3
"""Materialise the eval corpus from git history.

For every entry in manifest.json, writes cases/<commit>-<slug>.json holding the post
as the pipeline shipped it (parent commit) and as the author fixed it (the commit).
Run from anywhere inside the repo whenever manifest.json changes; the generated
files are committed so the harness works on CI's shallow checkout.

    python3 agent/evals/build_cases.py
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def _show(rev, path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{rev}:{path}"], text=True)


def main():
    manifest = json.loads((HERE / "manifest.json").read_text())
    out_dir = HERE / "cases"
    out_dir.mkdir(exist_ok=True)
    written = 0
    for case in manifest["cases"]:
        path = f"src/content/blog/{case['slug']}.md"
        sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", case["commit"]], text=True).strip()
        subject = subprocess.check_output(["git", "-C", str(ROOT), "show", "-s", "--format=%s", sha], text=True).strip()
        record = {
            "commit": sha,
            "subject": subject,
            "slug": case["slug"],
            "classes": case["classes"],
            "note": case["note"],
            "before": _show(f"{sha}^", path),
            "after": _show(sha, path),
        }
        (out_dir / f"{sha}-{case['slug'][:40]}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
        written += 1
    print(f"wrote {written} cases to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
