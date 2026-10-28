"""Stage artifacts keep Step Functions state small, and Publish is safe to retry.

Runs ab924859 and 4e0f28a4 died with States.DataLimitExceeded (256 KB), which skips
Catch; run 19fc39e3 reached 243,119 bytes. These tests chain the real handlers through
a small interpreter of the state machine definition in template.yaml, with S3, GitHub
and the model calls mocked, and measure the state after every transition.

The previous definition is kept as a fixture: an execution started before a deploy
keeps running on it, so the new handler code must still work when that definition
invokes it with the old inline shapes.
"""

import base64
import copy
import hashlib
import importlib.util
import io
import json
import re
import sys
import textwrap
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_cfg = MagicMock()
_cfg.Config = MagicMock(return_value=MagicMock())
_botocore = MagicMock()
_botocore.config = _cfg
sys.modules.setdefault("boto3", MagicMock())
sys.modules.setdefault("botocore", _botocore)
sys.modules.setdefault("botocore.config", _cfg)
sys.modules.setdefault("botocore.exceptions", MagicMock())

AGENT_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = AGENT_DIR.parent
for _d in ("common", "chart"):
    if str(AGENT_DIR / _d) not in sys.path:
        sys.path.insert(0, str(AGENT_DIR / _d))

import artifacts  # noqa: E402

STATE_BUDGET = 40 * 1024      # per transition, three revisions
HARD_CEILING = 128 * 1024     # half the Step Functions limit
RUN_ID = "4f1c2d3e-test-run"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"artifact_test_{name}", AGENT_DIR / name / "index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Ctx:
    aws_request_id = "req"
    function_name = "fn"

    def get_remaining_time_in_millis(self):
        return 900_000


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeS3:
    def __init__(self):
        self.store = {}

    def put_object(self, Bucket, Key, Body, **kw):
        self.store[Key] = Body if isinstance(Body, bytes) else Body.encode("utf-8")

    def get_object(self, Bucket, Key):
        if Key not in self.store:
            raise KeyError(f"NoSuchKey: {Key}")
        return {"Body": io.BytesIO(self.store[Key])}

    def generate_presigned_url(self, *a, **kw):
        return "https://example.invalid/presigned"


def _blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


class FakeGitHub:
    """A branch with real fast-forward semantics: PATCH to a commit whose parent is not
    HEAD is a 422, and `push_before_patch` simulates someone pushing in between."""

    def __init__(self, files=None, push_before_patch=0):
        self.files = dict(files or {})       # path -> bytes at HEAD
        self.head = "c0"
        self.blobs = {}
        self.trees = {}
        self.commits = {"c0": {"tree": "t0", "parents": [], "message": "init"}}
        self.trees["t0"] = dict(self.files)
        self.push_before_patch = push_before_patch
        self.calls = []
        self.patches = 0

    def __call__(self, method, path, data=None, token=None):
        self.calls.append((method, path))
        if path.startswith("contents/"):
            fp, _, ref = path[len("contents/"):].partition("?ref=")
            tree = self.trees[self.commits[ref]["tree"]] if ref in self.commits else self.files
            if fp not in tree:
                raise urllib.error.HTTPError(path, 404, "Not Found", {}, io.BytesIO(b""))
            return {"type": "file", "sha": _blob_sha(tree[fp])}
        if path.startswith("git/ref/heads/"):
            return {"object": {"sha": self.head}}
        if path.startswith("git/commits/"):
            return {"tree": {"sha": self.commits[path.rsplit("/", 1)[1]]["tree"]}}
        if path == "git/blobs":
            content = base64.b64decode(data["content"])
            sha = _blob_sha(content)
            self.blobs[sha] = content
            return {"sha": sha}
        if path == "git/trees":
            tree = dict(self.trees[data["base_tree"]])
            for e in data["tree"]:
                tree[e["path"]] = self.blobs[e["sha"]]
            tid = f"t{len(self.trees)}"
            self.trees[tid] = tree
            return {"sha": tid}
        if path == "git/commits":
            cid = f"c{len(self.commits)}"
            self.commits[cid] = {"tree": data["tree"], "parents": data["parents"], "message": data["message"]}
            return {"sha": cid}
        if path.startswith("git/refs/heads/"):
            if self.push_before_patch:
                self.push_before_patch -= 1
                self._push_unrelated()
            commit = self.commits[data["sha"]]
            if commit["parents"] != [self.head]:
                raise urllib.error.HTTPError(path, 422, "Update is not a fast forward", {}, io.BytesIO(b""))
            self.head = data["sha"]
            self.files = dict(self.trees[commit["tree"]])
            self.patches += 1
            return {}
        raise AssertionError(f"unexpected call {method} {path}")

    def _push_unrelated(self):
        tree = dict(self.files)
        tree[f"src/content/blog/other-{len(self.commits)}.md"] = b"other"
        tid = f"t{len(self.trees)}"
        self.trees[tid] = tree
        cid = f"c{len(self.commits)}"
        self.commits[cid] = {"tree": tid, "parents": [self.head], "message": "someone else"}
        self.head = cid
        self.files = tree

    def our_commits(self):
        return [c for c in self.commits.values() if c["message"].startswith("Add blog post")]


# ---------------------------------------------------------------------------
# A small interpreter of the subset of ASL the pipeline uses
# ---------------------------------------------------------------------------

def _current_definition():
    text = (AGENT_DIR / "template.yaml").read_text()
    start = text.index("DefinitionString: !Sub |") + len("DefinitionString: !Sub |")
    lines = []
    for line in text[start:].splitlines()[1:]:
        if line.strip() and not line.startswith(" " * 8):
            break
        lines.append(line)
    return json.loads(textwrap.dedent("\n".join(lines)))


def _previous_definition():
    return json.loads((Path(__file__).parent / "fixtures" / "state_machine_previous.json").read_text())


class StatesRuntime(Exception):
    """A missing JSONPath: Step Functions fails the execution, Catch cannot help."""


def _get(path, state, ctx):
    if path == "$":
        return state
    root, rest = (ctx, path[3:]) if path.startswith("$$.") else (state, path[2:])
    node = root
    for part in rest.split("."):
        if not isinstance(node, dict) or part not in node:
            raise StatesRuntime(f"path {path} not found")
        node = node[part]
    return node


def _params(tmpl, state, ctx):
    if isinstance(tmpl, dict):
        out = {}
        for k, v in tmpl.items():
            if k.endswith(".$"):
                out[k[:-2]] = copy.deepcopy(_get(v, state, ctx))
            else:
                out[k] = _params(v, state, ctx)
        return out
    return tmpl


def _set_result(state, result_path, result):
    if result_path is None or result_path == "$":
        return result
    state = copy.deepcopy(state)
    node = state
    parts = result_path[2:].split(".")
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    node[parts[-1]] = result
    return state


def _function_of(st):
    target = st["Resource"]
    if "waitForTaskToken" in target:
        target = st["Parameters"]["FunctionName"]
    return re.search(r"\$\{(\w+)Function\.Arn\}", target).group(1)


def run_definition(definition, execution_input, invoke):
    """invoke(function, payload) -> result. Returns (final_state, trace) where trace is
    [(state name, input bytes, output bytes)]."""
    states = definition["States"]
    name, state = definition["StartAt"], execution_input
    trace = []
    for _ in range(200):
        st = states[name]
        ctx = {"Execution": {"Name": RUN_ID}, "Task": {"Token": f"token-{len(trace)}"}}
        typ = st["Type"]
        if typ in ("Succeed", "Fail"):
            return name, state, trace
        if typ == "Choice":
            nxt = st.get("Default")
            for c in st["Choices"]:
                try:
                    if _get(c["Variable"], state, ctx) is c["BooleanEquals"]:
                        nxt = c["Next"]
                        break
                except StatesRuntime:
                    continue
            name = nxt
            continue
        if typ == "Pass":
            out = _params(st["Parameters"], state, ctx) if "Parameters" in st else state
        else:
            tmpl = st.get("Parameters")
            payload = _params(tmpl, state, ctx) if tmpl is not None else copy.deepcopy(state)
            if "waitForTaskToken" in st["Resource"]:
                payload = payload["Payload"]
            task_input = len(json.dumps(payload).encode())
            result = invoke(_function_of(st), payload)
            json.dumps(result)  # must be JSON
            if "ResultSelector" in st:
                result = _params(st["ResultSelector"], result, ctx)
            out = _set_result(state, st.get("ResultPath", "$"), result)
        size = len(json.dumps(out).encode())
        trace.append((name, task_input if typ == "Task" else 0, size))
        state = out
        if st.get("End"):
            return name, state, trace
        name = st["Next"]
    raise AssertionError("state machine did not terminate")


# ---------------------------------------------------------------------------
# The chained pipeline: real handler I/O, fake model work
# ---------------------------------------------------------------------------

def _pick_post():
    gate = importlib.import_module("gate")
    for path in sorted((REPO_DIR / "src" / "content" / "blog").glob("*.md"), key=lambda p: -p.stat().st_size):
        text = path.read_text()
        if "/postimages/" in text or "<!--" in text or len(re.findall(r"\]\(https?://", text)) < 4:
            continue
        _, body = gate.split_frontmatter(text)
        md = ('---\ntitle: "Artifacts"\ndate: 2026-10-27\nauthor: "Khaled Zaky"\ncategories: ["ai"]\n'
              'description: "A post"\ndraft: true\n---\n\n' + body.strip() + "\n")
        if not gate.errors(gate.analyze(md)):
            return md
    raise AssertionError("no published post usable as a fixture")


class Pipeline:
    """Holds the loaded handlers and fakes for one simulated execution."""

    def __init__(self, revisions=3, research_kb=49, author_kb=29):
        self.s3 = FakeS3()
        self.gh = FakeGitHub()
        self.post = _pick_post()
        self.revisions_left = revisions
        self.research = "R" * (research_kb * 1024)
        self.author = "A" * (author_kb * 1024)
        self.mods = {n: _load(n) for n in ("research", "draft", "verify", "evaluate", "chart", "notify", "publish")}
        self.draft_calls = []
        self.notified = []
        self.callbacks = []
        for m in ("chart", "notify", "publish"):
            self.mods[m].DRAFTS_BUCKET = "bucket"

    # fake stage bodies ------------------------------------------------------
    def _research_core(self, event, context):
        return {"topic": event["topic"], "categories": event.get("categories", []), "research": self.research,
                "suggested_title": "Artifacts", "suggested_description": "A post",
                "author_content": event.get("author_content", ""), "tone": "", "goal": "", "avoid": "",
                "analogies": "", "generate_hero": False, "verified_source_count": 9, "preserve_source": ""}

    def _draft_core(self, event, context):
        assert event["research"] == self.research and event["author_content"] == self.author
        self.draft_calls.append({"previous_draft": event.get("previous_draft", ""), "feedback": event.get("feedback", "")})
        n = len(self.draft_calls)
        markdown = self.post + f"\nRevision {n} of the post.\n"
        return {"title": "Artifacts", "slug": "artifacts-test", "categories": ["ai"], "description": "A post",
                "markdown": markdown, "date": "2026-10-27",
                "validation_report": {"preserve_source": False, "review_findings": ["[voice/NOTE] x" * 40] * 30,
                                      "blockers": [], "source_differences": [], "passed": True}}

    def _invoke(self, fn, payload):
        mods = self.mods
        if fn == "Research":
            return mods["research"].handler(payload, _Ctx())
        if fn == "Draft":
            mods["draft"].handler(payload, _Ctx())
            return self.callbacks.pop()
        if fn == "Verify":
            return mods["verify"].handler(payload, _Ctx())
        if fn == "Evaluate":
            return mods["evaluate"].handler(payload, _Ctx())
        if fn == "Chart":
            return mods["chart"].handler(payload, _Ctx())
        if fn == "Notify":
            mods["notify"].handler(payload, _Ctx())
            self.notified.append(payload)
            if self.revisions_left:
                self.revisions_left -= 1
                return {"approved": False, "revise": True, "feedback": "F" * 5000}
            return {"approved": True}
        if fn == "Publish":
            self.publish_input = copy.deepcopy(payload)
            return mods["publish"].handler(payload, _Ctx())
        raise AssertionError(fn)

    def run(self, definition):
        m = self.mods
        sfn = MagicMock()
        sfn.send_task_success.side_effect = lambda taskToken, output: self.callbacks.append(json.loads(output))
        verdict = lambda lr: {"url": lr["url"], "link_text": lr["link_text"], "context": lr["context"],  # noqa: E731
                              "verdict": "PASS", "reason": "supported " * 20, "quote": "q" * 400,
                              "precision": False, "published_at": "2026-01-01"}
        seats = {"fact_checker": {"score": 4, "model": "m", "findings": [
            {"quote": "x" * 200, "issue": "i" * 300, "fix": "f" * 200, "blocking": False}] * 20}}
        with patch.object(artifacts, "s3", self.s3), patch.object(artifacts, "DRAFTS_BUCKET", "bucket"), \
             patch.object(m["research"].handler, "core", self._research_core), \
             patch.object(m["draft"].handler, "core", self._draft_core), \
             patch.object(m["draft"], "_get_sfn", return_value=sfn), \
             patch.object(m["verify"], "_fetch_page_meta", return_value=(True, 200, "t", "page text", "2026-01-01")), \
             patch.object(m["verify"], "_verify_one_link", side_effect=verdict), \
             patch.object(m["evaluate"], "evaluate_once", return_value=([], seats)), \
             patch.object(m["evaluate"], "_load_voice_references", return_value=[]), \
             patch.object(m["chart"], "s3", self.s3), \
             patch.object(m["notify"], "s3", self.s3), patch.object(m["notify"], "sns", MagicMock()), \
             patch.object(m["notify"], "cloudwatch", MagicMock()), \
             patch.object(m["notify"], "invoke_model", return_value='{"score": 9, "preserved": [], "drifted": []}'), \
             patch.object(m["notify"], "SNS_TOPIC_ARN", "arn:topic"), \
             patch.object(m["publish"], "s3", self.s3), patch.object(m["publish"], "github_api", self.gh), \
             patch.object(m["publish"], "get_github_token", return_value="t"), \
             patch.object(m["publish"], "_update_known_slugs"):
            execution_input = {"topic": "Artifacts", "categories": ["ai"], "author_content": self.author}
            return run_definition(definition, execution_input, self._invoke)

    def replay_publish(self):
        m = self.mods["publish"]
        with patch.object(m, "s3", self.s3), patch.object(m, "github_api", self.gh), \
             patch.object(m, "get_github_token", return_value="t"), patch.object(m, "_update_known_slugs"):
            return m.handler(copy.deepcopy(self.publish_input), _Ctx())


@pytest.fixture(scope="module")
def three_revision_run():
    p = Pipeline(revisions=3)
    end, state, trace = p.run(_current_definition())
    return p, end, state, trace


class TestChainedStateSize:
    def test_three_revisions_reach_publish(self, three_revision_run):
        p, end, state, trace = three_revision_run
        assert end == "Publish" and state["published"] and not state["already_published"]
        assert [t[0] for t in trace].count("Revise") == 3
        assert len(p.gh.our_commits()) == 1
        assert f"Execution: {RUN_ID}" in p.gh.our_commits()[0]["message"]

    def test_state_stays_under_40kb_per_transition(self, three_revision_run):
        _, _, _, trace = three_revision_run
        worst = max(trace, key=lambda t: t[2])
        assert worst[2] < STATE_BUDGET, f"{worst[0]} produced {worst[2]} bytes of state"
        worst_in = max(trace, key=lambda t: t[1])
        assert worst_in[1] < STATE_BUDGET, f"{worst_in[0]} was sent {worst_in[1]} bytes"

    def test_no_state_output_exceeds_128kb(self, three_revision_run):
        _, _, _, trace = three_revision_run
        assert all(size <= HARD_CEILING for _, _, size in trace), trace

    def test_state_does_not_grow_with_revisions(self, three_revision_run):
        _, _, _, trace = three_revision_run
        notify_sizes = [size for name, _, size in trace if name == "NotifyForReview"]
        assert len(notify_sizes) == 4
        # The only difference is the 5,000-character revise feedback in $.approval.
        assert max(notify_sizes) - min(notify_sizes) < 5000 + 1024, notify_sizes

    def test_revise_gets_the_reviewed_draft_and_feedback_by_ref(self, three_revision_run):
        p, _, _, _ = three_revision_run
        assert p.draft_calls[0] == {"previous_draft": "", "feedback": ""}
        for n, call in enumerate(p.draft_calls[1:], start=1):
            assert call["previous_draft"].endswith(f"Revision {n} of the post.\n")
            assert call["feedback"] == "F" * 5000

    def test_published_post_is_the_last_reviewed_draft(self, three_revision_run):
        p, _, _, _ = three_revision_run
        reviewed = p.s3.store[p.publish_input["review_key"]]
        assert hashlib.sha256(reviewed).hexdigest() == p.publish_input["review_sha256"]
        assert b"Revision 4 of the post." in reviewed
        assert b"Revision 4 of the post." in p.gh.files["src/content/blog/artifacts-test.md"]
        assert p.publish_input["review_key"].startswith(f"runs/{RUN_ID}/review-")

    def test_large_fields_are_in_s3_under_the_run_prefix(self, three_revision_run):
        p, _, _, _ = three_revision_run
        keys = [k for k in p.s3.store if k.startswith(f"runs/{RUN_ID}/")]
        stages = {re.match(rf"runs/{RUN_ID}/([a-z]+)-", k).group(1) for k in keys}
        assert {"research", "draft", "verify", "evaluate", "chart", "review"} <= stages
        research = json.loads(next(p.s3.store[k] for k in keys if "/research-" in k))
        assert len(research["research"]) == 49 * 1024

    def test_replaying_publish_makes_no_second_commit(self, three_revision_run):
        p, _, _, _ = three_revision_run
        patches = p.gh.patches
        out = p.replay_publish()
        assert out["published"] and out["already_published"]
        assert p.gh.patches == patches and len(p.gh.our_commits()) == 1


class TestPreviousDefinitionStillWorks:
    """An execution started before the deploy runs on the previous definition with the
    new Lambda code: no run_id, inline shapes, the old drafts/<date>-<slug>.md key."""

    def test_old_definition_completes_with_new_code(self):
        p = Pipeline(revisions=1)
        end, state, trace = p.run(_previous_definition())
        assert end == "Publish" and state["published"]
        assert "drafts/2026-10-27-artifacts-test.md" in p.s3.store
        assert not [k for k in p.s3.store if k.startswith("runs/")]
        assert all(size < 256 * 1024 for _, _, size in trace)


class TestArtifactsHelper:
    def test_hydrate_prefers_inline_fields(self):
        event = {"markdown": "inline", "markdown_ref": {"key": "runs/x/a.json"}}
        assert artifacts.hydrate(event, {"markdown_ref": {"markdown": "markdown"}}) == event

    def test_tampered_artifact_is_refused(self):
        s3 = FakeS3()
        with patch.object(artifacts, "s3", s3), patch.object(artifacts, "DRAFTS_BUCKET", "b"):
            ref = artifacts.put("run", "draft", {"markdown": "x"})
            s3.store[ref["key"]] = b'{"markdown": "y"}'
            with pytest.raises(artifacts.ArtifactIntegrityError):
                artifacts.get(ref)

    def test_offload_is_a_no_op_without_run_id(self):
        result = {"markdown": "m", "title": "t"}
        assert artifacts.offload({}, "draft", result, ("markdown",)) is result

    def test_run_id_is_made_key_safe(self):
        assert artifacts.run_id({"run_id": "a/b c"}) == "a_b_c"


# ---------------------------------------------------------------------------
# Publish: bound to the reviewed draft, idempotent, 422-tolerant
# ---------------------------------------------------------------------------

class TestPublishRetry:
    POST = b"---\ntitle: T\n---\n\nBody.\n"

    def setup_method(self):
        self.mod = _load("publish")
        self.mod.DRAFTS_BUCKET = "bucket"
        self.s3 = FakeS3()
        self.digest = hashlib.sha256(self.POST).hexdigest()
        self.key = f"runs/{RUN_ID}/review-{self.digest}.md"
        self.s3.store[self.key] = self.POST

    def _event(self, **extra):
        return {"approved": True, "slug": "s", "date": "2026-01-01", "title": "T", "charts": [],
                "run_id": RUN_ID, "review_key": self.key, "review_sha256": self.digest, **extra}

    def _run(self, gh, event=None):
        with patch.object(self.mod, "github_api", gh), patch.object(self.mod, "get_github_token", return_value="t"), \
             patch.object(self.mod, "_update_known_slugs"), patch.object(self.mod, "s3", self.s3), \
             patch.object(artifacts, "s3", self.s3):
            return self.mod.handler(event or self._event(), _Ctx())

    def test_replay_after_success_makes_no_second_commit(self):
        gh = FakeGitHub()
        first = self._run(gh)
        assert first["published"] and not first["already_published"] and gh.patches == 1
        again = self._run(gh)
        assert again["published"] and again["already_published"]
        assert gh.patches == 1 and len(gh.our_commits()) == 1
        assert ("POST", "git/blobs") not in gh.calls[len(gh.calls) - 1:]

    def test_hash_mismatch_refuses(self):
        gh = FakeGitHub()
        self.s3.store[self.key] = self.POST + b"\nEdited after review.\n"
        with pytest.raises(self.mod.ReviewedDraftMismatch):
            self._run(gh)
        assert gh.calls == [] and gh.patches == 0

    def test_review_key_outside_the_run_is_refused(self):
        with pytest.raises(self.mod.ReviewedDraftMismatch):
            self._run(FakeGitHub(), self._event(review_key=f"runs/other/review-{self.digest}.md"))

    def test_ref_moved_422_then_success_retries_on_new_head(self):
        gh = FakeGitHub(push_before_patch=2)
        out = self._run(gh)
        assert out["published"] and gh.patches == 1
        ours = gh.our_commits()
        assert len(ours) == 3                       # two lost the race, the third landed
        landed = gh.commits[gh.head]
        assert landed["message"].startswith("Add blog post") and landed["parents"] != ["c0"]
        assert len([f for f in gh.files if "/other-" in f]) == 2  # the concurrent pushes survived
        assert gh.files["src/content/blog/s.md"] == self.POST.rstrip(b"\n")

    def test_ref_moved_every_time_gives_up_after_three(self):
        gh = FakeGitHub(push_before_patch=5)
        with pytest.raises(urllib.error.HTTPError):
            self._run(gh)
        assert gh.patches == 0

    def test_commit_carries_the_execution_trailer(self):
        gh = FakeGitHub()
        self._run(gh)
        assert gh.our_commits()[0]["message"].rstrip().endswith(f"Execution: {RUN_ID}")

    def test_existing_different_post_still_refused(self):
        gh = FakeGitHub(files={"src/content/blog/s.md": b"an older post"})
        with pytest.raises(self.mod.PublishRefused, match="already exists"):
            self._run(gh)
        assert gh.patches == 0

    def test_legacy_event_without_review_key_still_publishes(self):
        self.s3.store["drafts/2026-01-01-s.md"] = self.POST
        event = {"approved": True, "slug": "s", "date": "2026-01-01", "charts": []}
        gh = FakeGitHub()
        assert self._run(gh, event)["published"] and gh.patches == 1
