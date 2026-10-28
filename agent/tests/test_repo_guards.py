"""Repo-level privacy guards (source side; scripts/check-leaks.mjs checks dist/).

- The author's real voice profile (agent/voice-profile.md) is private and gitignored;
  it was once committed to this public repo. No tracked path may look like one,
  except the published template voice-profile.sample.md.
- src/pages/drop.astro is a private upload page. Nothing else in src/ may link to it,
  or it becomes discoverable from the public site.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

DROP_LINK = re.compile(
    r"""(?:(?:https?:)?//(?:www\.)?khaledzaky\.com/drop(?=[/?#"'<\s]|$))"""
    r"""|(?:\b(?:href|src|action|formaction)\s*=\s*\{?\s*["'`]?/drop(?=[/?#"'`\s>}]|$))""",
    re.IGNORECASE | re.MULTILINE,
)


def _tracked_paths():
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=REPO,
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [p for p in out.split("\0") if p]


def test_no_private_voice_profile_is_tracked():
    bad = [
        p
        for p in _tracked_paths()
        if "voice-profile" in Path(p).name.lower()
        and Path(p).name.lower() != "voice-profile.sample.md"
    ]
    assert not bad, f"private voice profile tracked in git: {bad} (git rm --cached it)"


def test_voice_profile_is_gitignored():
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "agent/voice-profile.md" in [line.strip() for line in gitignore]


def test_drop_page_is_not_linked_from_other_sources():
    src = REPO / "src"
    offenders = []
    for path in src.rglob("*"):
        if not path.is_file() or path.suffix not in {
            ".astro", ".md", ".mdx", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".html",
        }:
            continue
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith("src/pages/drop"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in DROP_LINK.finditer(text):
            offenders.append(f"{rel}:{text[: match.start()].count(chr(10)) + 1}")
    assert not offenders, f"links to the private /drop page: {offenders}"


def test_drop_page_is_noindex_and_excluded_from_sitemap():
    drop = (REPO / "src/pages/drop.astro").read_text(encoding="utf-8")
    assert re.search(r"<BaseLayout\b[^>]*\bnoindex\b", drop), "drop.astro must pass noindex"
    layout = (REPO / "src/layouts/BaseLayout.astro").read_text(encoding="utf-8")
    assert 'content="noindex, nofollow"' in layout
    config = (REPO / "astro.config.mjs").read_text(encoding="utf-8")
    assert re.search(r"filter:.*drop", config), "sitemap filter must exclude /drop"
    robots = (REPO / "public/robots.txt").read_text(encoding="utf-8")
    assert re.search(r"^Disallow:\s*/drop\s*$", robots, re.MULTILINE)


def test_drop_link_pattern_catches_links():
    assert DROP_LINK.search('<a href="/drop">x</a>')
    assert DROP_LINK.search("<a href='/drop/'>x</a>")
    assert DROP_LINK.search("https://khaledzaky.com/drop/")
    assert not DROP_LINK.search('<a href="/dropbox-notes">x</a>')
    assert not DROP_LINK.search("drop the ball")
