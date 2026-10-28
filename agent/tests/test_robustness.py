"""Robustness fixes for failures seen in live pipeline runs.

1. A comparison diagram written one cell per field ('MAP: ... | Shadow: ...') drew each
   cell as its own row, scrambling the two columns.
2. A chart or diagram that could not be drawn left its <!-- CHART/DIAGRAM --> comment in
   the post, which fails check:render and with it the whole site deploy.
3. Publish swallowed a failed chart upload (broken image) and would overwrite an
   existing post with the same slug.
4. Draft's slug cleanup let '&', '/', curly apostrophes and accents through; Publish
   rejected the slug after approval.
5. Draft continued with an empty voice profile.
6. Verify's precision backstop counted digits in URLs, treated 1,000 and 1000 as
   different figures, and compared quotes without normalizing whitespace.
"""

import base64
import importlib.util
import io
import json
import re
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_mock_botocore_config = MagicMock()
_mock_botocore_config.Config = MagicMock(return_value=MagicMock())
_mock_botocore = MagicMock()
_mock_botocore.config = _mock_botocore_config
sys.modules.setdefault("boto3", MagicMock())
sys.modules.setdefault("botocore", _mock_botocore)
sys.modules.setdefault("botocore.config", _mock_botocore_config)
sys.modules.setdefault("botocore.exceptions", MagicMock())

AGENT_DIR = Path(__file__).resolve().parent.parent
for _d in ("common", "chart"):
    if str(AGENT_DIR / _d) not in sys.path:
        sys.path.insert(0, str(AGENT_DIR / _d))


def _load(lambda_dir):
    spec = importlib.util.spec_from_file_location(
        f"robust_{lambda_dir}_index", str(AGENT_DIR / lambda_dir / "index.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Ctx:
    aws_request_id = "test"
    function_name = "test"
    memory_limit_in_mb = 128

    def get_remaining_time_in_millis(self):
        return 900_000


def _texts(svg):
    return re.findall(r">([^<>]+)</text>", svg)


# ---------------------------------------------------------------------------
# 1. Comparison diagram: one 'Label: text' cell per field
# ---------------------------------------------------------------------------

LIVE_SPEC = ("comparison | NIST AI RMF Function | Rollout Stage | MAP: identify risks and context | "
             "Shadow: observe real data, no actions | GOVERN: define and exercise human authority | "
             "Suggest: human approves every output")


def _rows(spec):
    from renderers import comparison
    return comparison.parse_comparison_rows([p.strip() for p in spec.split("|")][1:])


def test_live_one_cell_per_field_spec_pairs_left_and_right_cells():
    assert _rows(LIVE_SPEC) == [
        ("MAP: identify risks and context", "Shadow: observe real data, no actions"),
        ("GOVERN: define and exercise human authority", "Suggest: human approves every output"),
    ]


def test_live_spec_renders_each_function_against_its_stage():
    from renderers import comparison
    fields = [p.strip() for p in LIVE_SPEC.split("|")][1:]
    svg = comparison.render_comparison_diagram(fields)
    texts = _texts(svg)
    # Two rows, not four, and no cell is the bare label or the bare description.
    assert svg.count('fill="var(--card)"') == 4
    assert "MAP" not in texts and "Shadow" not in texts
    assert not any(t.startswith(("identify risks", "observe real data")) for t in texts)
    joined = " ".join(texts)
    assert "MAP: identify" in joined and "Shadow: observe" in joined
    # MAP's cell sits in the left column, Shadow's in the right, on the same row.
    xs = {t: int(x) for x, t in re.findall(r'<text x="(\d+)"[^>]*>([^<>]+)</text>', svg)}
    map_cell = next(t for t in xs if t.startswith("MAP:"))
    shadow_cell = next(t for t in xs if t.startswith("Shadow:"))
    assert xs[map_cell] < 350 < xs[shadow_cell]


def test_repeated_column_labels_pair_up():
    assert _rows("comparison | A | B | Before: manual review | After: automated check | "
                 "Before: weekly | After: on every commit") == [
        ("Before: manual review", "After: automated check"), ("Before: weekly", "After: on every commit")]


def test_odd_alternating_cells_are_rejected_not_drawn():
    from renderers import comparison
    with pytest.raises(comparison.ComparisonSpecError, match="odd count"):
        _rows(LIVE_SPEC + " | MEASURE: track drift")


def test_documented_row_formats_are_unchanged():
    # The prompt's own example, colon with no space.
    assert _rows("comparison | Traditional Software | AI Agents | Deterministic:Probabilistic | "
                 "Request/Response:Autonomous Action") == [
        ("Deterministic", "Probabilistic"), ("Request/Response", "Autonomous Action")]
    # One row per field with a spaced colon: uniform labels stay label/description rows.
    assert _rows("comparison | Function | What it does | Govern: sets policy | Map: finds risks") == [
        ("Govern", "sets policy"), ("Map", "finds risks")]
    assert _rows("comparison | A | B | Deterministic: Probabilistic | Static: Dynamic") == [
        ("Deterministic", "Probabilistic"), ("Static", "Dynamic")]
    # The documented fix for the live spec: both labelled cells in one field.
    assert _rows("comparison | F | S | MAP: identify risks and context:Shadow: observe real data") == [
        ("MAP: identify risks and context", "Shadow: observe real data")]


def test_draft_prompt_documents_one_row_per_field():
    src = (AGENT_DIR / "draft" / "index.py").read_text()
    assert "each pipe-delimited field after the two headers is ONE ROW" in src
    example = re.search(r"Example: <!-- DIAGRAM: (comparison \| NIST[^>]*?) -->", src).group(1)
    assert _rows(example) == [
        ("MAP: identify risks and context", "Shadow: observe real data, no actions"),
        ("GOVERN: define and exercise human authority", "Suggest: human approves every output"),
    ]


# ---------------------------------------------------------------------------
# 2. Chart Lambda never leaves a placeholder behind
# ---------------------------------------------------------------------------

class TestChartRemovesUnrenderedPlaceholders:
    def setup_method(self):
        self.mod = _load("chart")

    def _run(self, markdown, research=""):
        event = {"markdown": markdown, "research": research, "slug": "s", "date": "2026-01-01"}
        with patch.object(self.mod.s3, "put_object"):
            return self.mod.handler(event, _Ctx())

    def _assert_clean(self, result):
        assert not re.search(r"<!--\s*(?:CHART|DIAGRAM):", result["markdown"])

    def test_chart_without_matching_data_is_removed_and_noted(self):
        md = "---\ntitle: T\n---\n\nPara one.\n\n<!-- CHART: quarterly revenue growth -->\n\nPara two.\n"
        result = self._run(md)
        self._assert_clean(result)
        assert result["charts"] == []
        assert "Para one." in result["markdown"] and "Para two." in result["markdown"]
        assert re.search(r"<!-- ⚠️ STRUCTURE: s-chart-1: chart not drawn: no matching data point", result["markdown"])
        assert result["chart_warnings"] and "s-chart-1" in result["chart_warnings"][0]
        assert result["chart_validation"]["passed"]

    def test_unparseable_diagram_is_removed_and_noted(self):
        md = "Intro.\n\n<!-- DIAGRAM: hexagon | nothing here -->\n\nOutro.\n"
        result = self._run(md)
        self._assert_clean(result)
        assert "unknown diagram type 'hexagon'" in result["chart_warnings"][0]

    def test_ambiguous_comparison_is_rejected_with_its_reason(self):
        md = f"Intro.\n\n<!-- DIAGRAM: {LIVE_SPEC} | MEASURE: track drift -->\n\nOutro.\n"
        result = self._run(md)
        self._assert_clean(result)
        assert result["charts"] == []
        assert "odd count" in result["chart_warnings"][0]

    def test_live_comparison_spec_renders(self):
        result = self._run(f"Intro.\n\n<!-- DIAGRAM: {LIVE_SPEC} -->\n\nOutro.\n")
        self._assert_clean(result)
        assert "/postimages/charts/s-diagram-1.svg" in result["markdown"]
        assert result["chart_warnings"] == []

    def test_renderer_failure_is_removed_and_noted(self):
        md = "Intro.\n\n<!-- CHART: agent failure rates -->\n"
        research = "- Data point: agent failure rates\n- Values: A: 1, B: 2\n- Source: Gartner 2024\n"
        with patch.object(self.mod, "_render_chart", side_effect=RuntimeError("boom")):
            result = self._run(md, research)
        self._assert_clean(result)
        assert "rendering failed (boom)" in result["chart_warnings"][0]

    def test_notify_shows_the_note_to_the_reviewer(self):
        """The note uses the STRUCTURE annotation Notify already lists in the email."""
        result = self._run("Intro.\n\n<!-- CHART: quarterly revenue growth -->\n")
        notes = re.findall(r"<!--\s*⚠️\s*STRUCTURE:(.*?)-->", result["markdown"], re.DOTALL)
        assert len(notes) == 1 and "chart not drawn" in notes[0]

    def test_publish_strips_the_note(self):
        result = self._run("Intro.\n\n<!-- CHART: quarterly revenue growth -->\n\nOutro.\n")
        out = _load("publish")._strip_review_annotations(result["markdown"])
        assert "<!--" not in out and "Intro." in out and "Outro." in out


# ---------------------------------------------------------------------------
# 3. Publish: placeholder backstop, failed uploads, overwrite guard
# ---------------------------------------------------------------------------

def test_publish_backstop_strips_placeholder_lines_but_not_prose_mentions():
    publish = _load("publish")
    md = ("---\ntitle: x\n---\n\nPara.\n\n<!-- CHART: Title | a: 1 -->\n\n<!-- DIAGRAM: comparison | A | B\n| x:y -->\n"
          "Use `<!-- DIAGRAM: type | ... -->` placeholders.\n")
    out, n = publish._strip_unrendered_placeholders(md)
    assert n == 2
    assert "<!-- CHART" not in out and "\n<!-- DIAGRAM" not in out
    assert "Use `<!-- DIAGRAM: type | ... -->` placeholders." in out


class _GitHub:
    """Records GitHub API calls; `existing` is the content of the post on the branch."""

    def __init__(self, existing=None, blob_fails_for=None):
        self.existing = existing
        self.blob_fails_for = blob_fails_for
        self.calls = []
        self.blobs = []

    def __call__(self, method, path, data=None, token=None):
        self.calls.append((method, path))
        if path.startswith("contents/"):
            if self.existing is None:
                raise urllib.error.HTTPError(path, 404, "Not Found", {}, io.BytesIO(b""))
            return {"type": "file", "sha": _load_publish_sha(self.existing)}
        if path.startswith("git/ref/"):
            return {"object": {"sha": "base"}}
        if path.startswith("git/commits/"):
            return {"tree": {"sha": "tree"}}
        if path == "git/blobs":
            content = base64.b64decode(data["content"])
            self.blobs.append(content)
            if self.blob_fails_for and self.blob_fails_for in content:
                raise urllib.error.HTTPError(path, 422, "Unprocessable", {}, io.BytesIO(b""))
            return {"sha": "blob"}
        if path in ("git/trees", "git/commits"):
            return {"sha": "new"}
        if path.startswith("git/refs/"):
            return {}
        raise AssertionError(f"unexpected call {method} {path}")

    @property
    def committed(self):
        return ("PATCH", f"git/refs/heads/{_load('publish').GITHUB_BRANCH}") in self.calls


def _load_publish_sha(text):
    return _load("publish")._git_blob_sha(text.encode("utf-8"))


class TestPublishGuards:
    POST = "---\ntitle: T\n---\n\nBody.\n\n![Fig](/postimages/charts/s-chart-1.svg)\n"

    def setup_method(self):
        self.mod = _load("publish")
        self.mod.DRAFTS_BUCKET = "bucket"

    def _s3(self, chart_body=b"<svg>chart</svg>"):
        def get_object(Bucket, Key):
            body = self.POST.encode() if Key.startswith("drafts/") else chart_body
            return {"Body": io.BytesIO(body)}
        return get_object

    def _event(self, **extra):
        return {"approved": True, "slug": "s", "date": "2026-01-01",
                "charts": [{"filename": "s-chart-1.svg", "s3_key": "charts/2026-01-01-s-chart-1.svg"}], **extra}

    def _run(self, gh, event=None):
        with patch.object(self.mod, "github_api", gh), \
             patch.object(self.mod, "get_github_token", return_value="t"), \
             patch.object(self.mod, "_update_known_slugs"), \
             patch.object(self.mod.s3, "get_object", side_effect=self._s3()):
            return self.mod.handler(event or self._event(), _Ctx())

    def test_new_post_publishes(self):
        gh = _GitHub()
        result = self._run(gh)
        assert result["published"] and gh.committed
        assert "public/postimages/charts/s-chart-1.svg" in result["files_committed"]

    def test_failed_chart_upload_aborts_before_commit(self):
        gh = _GitHub(blob_fails_for=b"<svg>chart</svg>")
        with pytest.raises(RuntimeError, match="could not upload chart s-chart-1.svg"):
            self._run(gh)
        assert not gh.committed

    def test_failed_chart_read_from_s3_aborts(self):
        gh = _GitHub()
        def get_object(Bucket, Key):
            if Key.startswith("charts/"):
                raise RuntimeError("NoSuchKey")
            return {"Body": io.BytesIO(self.POST.encode())}
        with patch.object(self.mod, "github_api", gh), patch.object(self.mod, "get_github_token", return_value="t"), \
             patch.object(self.mod.s3, "get_object", side_effect=get_object), \
             pytest.raises(RuntimeError, match="could not upload chart"):
            self.mod.handler(self._event(), _Ctx())
        assert not gh.committed

    def test_existing_post_is_not_overwritten(self):
        gh = _GitHub(existing="---\ntitle: An older post\n---\n\nDifferent body.\n")
        with pytest.raises(RuntimeError, match=r"already exists.*revision_of"):
            self._run(gh)
        assert not gh.committed
        assert ("GET", f"contents/src/content/blog/s.md?ref={self.mod.GITHUB_BRANCH}") in gh.calls

    def test_marked_revision_may_overwrite_the_same_post(self):
        gh = _GitHub(existing="old body")
        assert self._run(gh, self._event(revision_of="s"))["published"] and gh.committed

    def test_revision_of_a_different_post_does_not_count(self):
        gh = _GitHub(existing="old body")
        with pytest.raises(RuntimeError, match="already exists"):
            self._run(gh, self._event(revision_of="another-post"))

    def test_identical_retry_is_allowed(self):
        first = _GitHub()
        self._run(first)
        gh = _GitHub(existing=first.blobs[0].decode("utf-8"))
        assert self._run(gh)["published"]

    def test_unclear_existence_check_fails_closed(self):
        def gh(method, path, data=None, token=None):
            if path.startswith("contents/"):
                raise urllib.error.HTTPError(path, 403, "Forbidden", {}, io.BytesIO(b""))
            return _GitHub()(method, path, data, token)
        with pytest.raises(urllib.error.HTTPError):
            self._run(gh)

    def test_git_blob_sha_matches_git(self):
        # `printf 'hello\n' | git hash-object --stdin`
        assert self.mod._git_blob_sha(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"


# ---------------------------------------------------------------------------
# 4. Draft slug always passes Publish's _SAFE_SLUG
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,slug", [
    ("Identity & Authority: Who Decides?", "identity-authority-who-decides"),
    ("Build/Buy for AI Platforms", "build-buy-for-ai-platforms"),
    ("The Agent’s Identity", "the-agents-identity"),
    ("Don't Ship It", "dont-ship-it"),
    ("Café Résumé Naïve", "cafe-resume-naive"),
    ("  --Leading and trailing--  ", "leading-and-trailing"),
    ("NIST AI RMF (2024): MAP, GOVERN — v1.0", "nist-ai-rmf-2024-map-govern-v1-0"),
    ("The Agent Has an Identity. Who Gave It Authority?", "the-agent-has-an-identity-who-gave-it-authority"),
])
def test_slugify(title, slug):
    draft = _load("draft")
    publish = _load("publish")
    assert draft.slugify(title) == slug
    assert publish._SAFE_SLUG.match(slug)


def test_slugify_bounds_length_at_a_word_and_never_returns_empty():
    draft = _load("draft")
    publish = _load("publish")
    assert draft.MAX_SLUG_LEN == publish.MAX_SLUG_LEN
    long = draft.slugify("word " * 60)
    assert len(long) <= publish.MAX_SLUG_LEN and publish._SAFE_SLUG.match(long) and long.endswith("word")
    for title in ("日本語", "???", ""):
        s = draft.slugify(title)
        assert s and publish._SAFE_SLUG.match(s)


def test_published_slugs_are_unchanged_by_slugify():
    """Every existing post's slug is already a fixed point, so no URL would move."""
    draft = _load("draft")
    slugs = [p.stem for p in (AGENT_DIR.parent / "src" / "content" / "blog").glob("*.md")]
    assert slugs
    assert [s for s in slugs if draft.slugify(s) != s] == []


def test_handler_uses_slugify():
    src = (AGENT_DIR / "draft" / "index.py").read_text()
    assert "slug = slugify(suggested_title)" in src


# ---------------------------------------------------------------------------
# 5. Draft fails loudly without a voice profile
# ---------------------------------------------------------------------------

class TestVoiceProfileRequired:
    def setup_method(self):
        self.mod = _load("draft")

    def test_missing_profile_raises(self, monkeypatch):
        monkeypatch.delenv("VOICE_PROFILE_OPTIONAL", raising=False)
        with patch.object(self.mod, "_load_voice_profile", return_value=""), \
             pytest.raises(RuntimeError, match="Voice profile missing"):
            self.mod.handler({"topic": "t", "research": "notes"}, _Ctx())

    def test_whitespace_profile_raises(self, monkeypatch):
        monkeypatch.delenv("VOICE_PROFILE_OPTIONAL", raising=False)
        with patch.object(self.mod, "_load_voice_profile", return_value="  \n"), \
             pytest.raises(RuntimeError, match="VOICE_PROFILE_OPTIONAL=1"):
            self.mod.handler({"topic": "t", "research": "notes"}, _Ctx())

    def test_opt_out_continues_past_the_check(self, monkeypatch):
        monkeypatch.setenv("VOICE_PROFILE_OPTIONAL", "1")

        class _Reached(Exception):
            pass

        # The next step after the voice check reads the author content; stop there.
        with patch.object(self.mod, "_load_voice_profile", return_value=""), \
             patch.object(self.mod, "_detect_finished_source", side_effect=_Reached), \
             pytest.raises(_Reached):
            self.mod.handler({"topic": "t", "research": "notes", "author_content": "x"}, _Ctx())

    def test_loaded_profile_passes_the_check(self, monkeypatch):
        monkeypatch.delenv("VOICE_PROFILE_OPTIONAL", raising=False)

        class _Reached(Exception):
            pass

        with patch.object(self.mod, "_load_voice_profile", return_value="# Voice\nPlain."), \
             patch.object(self.mod, "_detect_finished_source", side_effect=_Reached), \
             pytest.raises(_Reached):
            self.mod.handler({"topic": "t", "research": "notes", "author_content": "x"}, _Ctx())


# ---------------------------------------------------------------------------
# 6. Verify precision backstop false positives
# ---------------------------------------------------------------------------

_FILLER = " Background section with no figures in it, describing context for the reader." * 8


def _llm(payload):
    # verify calls llm.invoke_model (imported by name), which returns the text block.
    return MagicMock(return_value=json.dumps(payload))


class TestVerifyPrecisionBackstop:
    def setup_method(self):
        self.mod = _load("verify")

    def _verify(self, context, excerpt, quote):
        lr = {"url": "https://src.example/p", "link_text": "source", "context": context, "reachable": True,
              "status_code": 200, "title": "Source", "excerpt": excerpt + _FILLER, "published_at": ""}
        with patch.object(self.mod, "invoke_model",
                          _llm({"verdict": "PASS", "quote": quote, "reason": "stated"})):
            return self.mod._verify_one_link(lr)

    def test_digits_in_the_url_are_not_a_precision_claim(self):
        v = self._verify("Agents need scoped authority, per [the paper](https://arxiv.org/abs/2401.12345).",
                         "Agents need scoped authority over the tools they call.", "Agents need scoped authority")
        assert v["precision"] is False and v["verdict"] == "PASS"

    def test_digits_in_the_url_do_not_have_to_appear_on_the_page(self):
        v = self._verify("Testing is 30 percent of cost, per [the 2025 model](https://ex.com/2025/07/23/cost).",
                         "In the 2025 model, testing is 30 percent of cost.", "testing is 30 percent of cost")
        assert v["precision"] is True and v["verdict"] == "PASS"

    def test_real_figure_absent_from_page_still_fails(self):
        v = self._verify("Testing is 45 percent of cost, per [the model](https://ex.com/a).",
                         "Testing is a large share of cost.", "Testing is a large share of cost")
        assert v["verdict"] == "FAIL" and "figure not found" in v["reason"]

    def test_thousands_separator_does_not_change_the_figure(self):
        assert self.mod._digits("more than 100,000 trials") == self.mod._digits("more than 100000 trials")
        v = self._verify("They ran more than 100,000 trials across 13 models [source].",
                         "We ran 100000 trials over 13 models.", "We ran 100000 trials over 13 models")
        assert v["verdict"] == "PASS"

    def test_decimals_stay_distinct(self):
        assert self.mod._digits("2.5x") != self.mod._digits("25x")

    def test_quote_matches_across_line_breaks_and_curly_quotes(self):
        v = self._verify("AWS reports up to 99% accuracy [source].",
                         "AWS\nreports  up to 99% accuracy on the “benchmark”.",
                         'AWS reports up to 99% accuracy on the "benchmark"')
        assert v["verdict"] == "PASS"

    def test_fabricated_quote_still_fails(self):
        v = self._verify("AWS reports up to 99% accuracy [source].", "AWS reports 99% uptime.",
                         "AWS reports up to 99% accuracy")
        assert v["verdict"] == "FAIL" and "quote not found" in v["reason"]

    def test_claim_text_keeps_link_text(self):
        assert self.mod._claim_text("See [the 2024 report](https://a.example/2024/x) now.") == "See the 2024 report now."


# ---------------------------------------------------------------------------
# 7. Chart captions and alt text carry no em or en dashes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Fiddler AI — AI Agent Failure Rate", "Fiddler AI, AI Agent Failure Rate"),   # e2e-test-20261028-3
    ("Anthropic – Measuring Agent Autonomy", "Anthropic, Measuring Agent Autonomy"),
    ("Agents fail 70–90% of the time", "Agents fail 70 to 90% of the time"),
    ("No dashes here", "No dashes here"),
    (None, ""),
])
def test_chart_dedash(text, expected):
    assert _load("chart")._dedash(text) == expected


# The full spec from the run that shipped the scrambled figure, including the
# 'MANAGE (residual risk)' row that defeated whole-label style detection.
_NIST_LIVE = ["NIST AI RMF Function", "Rollout Stage", "MAP: identify risks and context", "Shadow: observe real data, no actions",
              "GOVERN: define and exercise human authority", "Suggest: human approves every output",
              "MANAGE: concrete risk treatment controls", "Bounded: dollar limits, scope constraints",
              "MEASURE: post-hoc assessment and metrics", "Supervised: sampling, exception rates",
              "MANAGE (residual risk): monitor drift", "Autonomous: anomaly and threshold triggers"]


def test_full_live_nist_spec_pairs_every_row():
    from renderers import comparison as cmp
    rows = cmp.parse_comparison_rows(_NIST_LIVE)
    assert rows[0] == ("MAP: identify risks and context", "Shadow: observe real data, no actions")
    assert rows[-1] == ("MANAGE (residual risk): monitor drift", "Autonomous: anomaly and threshold triggers")
    assert len(rows) == 5


_LABELLED_LIVE = ["Chatbot Pilot", "Production Agent",
                  "Who reviews output:Every response, or none, stakes are low:Graduated from 100% review down to sample-based",
                  "Failure detection:User reports it, or nobody notices:Requires observability and attribution infrastructure"]


def test_labelled_rows_split_into_label_left_right():
    from renderers import comparison as cmp
    rows = cmp.parse_comparison_rows(_LABELLED_LIVE)
    assert rows == [("Who reviews output", "Every response, or none, stakes are low", "Graduated from 100% review down to sample-based"),
                    ("Failure detection", "User reports it, or nobody notices", "Requires observability and attribution infrastructure")]
    svg = cmp.render_comparison_diagram(_LABELLED_LIVE)
    assert "Who reviews output" in svg and ":Graduated" not in svg


def test_a_ratio_in_one_row_does_not_switch_on_labelled_rows():
    from renderers import comparison as cmp
    rows = cmp.parse_comparison_rows(["Before", "After", "Defect cost:1:10:100 ratio", "Review:none"])
    assert all(len(r) == 2 for r in rows)

