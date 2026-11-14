"""Acceptance tests 1-5 of card T1-KBEVAL-PROVENANCE for `bench/knowledge/probes/provenance.py`."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import textwrap
from pathlib import Path

import pytest
from conftest import REPO

PROBE = REPO / "bench" / "knowledge" / "probes" / "provenance.py"
DEMO_WIKI = REPO / "demo" / "wiki"
DEMO_RAW = REPO / "demo" / "raw"
KS = (1, 3, 10)
RATIOS = (50, 10, 1, 0)
FRONTMATTER = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)


# -- helpers ---------------------------------------------------------------------


@pytest.fixture
def probe():
    name = "kbeval_probe_provenance_under_test"
    spec = importlib.util.spec_from_file_location(name, PROBE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(name, None)


def make_ctx(runner, tmp_path: Path, wiki: Path | None = None):
    work = tmp_path / "work"
    work.mkdir()
    if wiki is None:
        wiki = tmp_path / "corpus-wiki"
        write_page(wiki, "concepts/only.md", source=["raw/articles/only.md"])
    raw = tmp_path / "corpus-raw"
    raw.mkdir(exist_ok=True)
    return runner.Context(tmp=work, data=tmp_path / "data", wiki=wiki, raw=raw, out=tmp_path)


def page_body(text: str) -> str:
    """The text after the closing frontmatter fence, or the whole text without one."""
    match = FRONTMATTER.match(text)
    return text[match.end() :] if match else text


class FeedbackStub:
    """Stands in for `kb.feedback.store.add_feedback_entry`.

    It writes a score file at `path` whose `trust` and `wrong` values differ for
    every (k, position) pair, so a probe that reads another page's entry, another
    file or a constant reports a value the test does not expect.
    """

    def __init__(self, fail: BaseException | None = None, omit_last: bool = False):
        self.fail = fail
        self.omit_last = omit_last
        self.calls: list[dict] = []

    @staticmethod
    def chosen(k: int, position: int) -> tuple[float, int]:
        return round((k * 100 + position) / 10000, 4), k * 100 + position

    def __call__(self, question, rating, cited_pages, notes="", path=None):
        path = Path(path)
        self.calls.append(
            {
                "question": question,
                "rating": rating,
                "cited_pages": list(cited_pages),
                "notes": notes,
                "path": path,
                "existed": path.exists(),
            }
        )
        if self.fail is not None:
            raise self.fail
        k = len(cited_pages)
        scores = {}
        for position, pid in enumerate(cited_pages, start=1):
            if self.omit_last and position == k:
                continue
            trust, wrong = self.chosen(k, position)
            scores[pid] = {"useful": 0, "wrong": wrong, "incomplete": 0, "trust": trust}
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"entries": [{"rating": rating}], "page_scores": scores}
        path.write_bytes(json.dumps(data).encode("utf-8"))
        return {"rating": rating}


class RefineStub:
    """Stands in for `kb.review.refiner.refine_page`.

    `write` replaces the body after the frontmatter with the new body, the way
    `refine_page` lays it out; `error` returns `{"error": "x"}`; `raise` raises
    ValueError; `silent` reports success and leaves the page as it was.
    """

    def __init__(self, mode: str):
        self.mode = mode
        self.calls: list[dict] = []

    def __call__(
        self, page_id, updated_content, revision_notes="", wiki_dir=None, history_path=None
    ):
        page = Path(wiki_dir) / f"{page_id}.md"
        before = page.read_bytes().decode("utf-8")
        self.calls.append(
            {
                "page_id": page_id,
                "new_body": updated_content,
                "notes": revision_notes,
                "wiki_dir": Path(wiki_dir),
                "history_path": Path(history_path),
                "page_before": before,
            }
        )
        if self.mode == "write":
            head = FRONTMATTER.match(before).group(0)
            page.write_bytes((head + "\n" + updated_content + "\n").encode("utf-8"))
        elif self.mode == "error":
            return {"error": "x"}
        elif self.mode == "raise":
            raise ValueError("refused by the stub")
        return {"page_id": page_id, "updated": True, "revision_notes": revision_notes}


@pytest.fixture
def seams(monkeypatch):
    """Replace both writing kb functions; each test picks the stubs it needs."""
    import kb.feedback.store
    import kb.review.refiner

    class Seams:
        def feedback(self, **kwargs) -> FeedbackStub:
            stub = FeedbackStub(**kwargs)
            monkeypatch.setattr(kb.feedback.store, "add_feedback_entry", stub)
            return stub

        def refine(self, mode: str = "write") -> RefineStub:
            stub = RefineStub(mode)
            monkeypatch.setattr(kb.review.refiner, "refine_page", stub)
            return stub

    return Seams()


def write_page(
    wiki: Path, relative: str, *, source=None, extra: str = "", raw: bytes | None = None
):
    path = wiki / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        path.write_bytes(raw)
        return path
    lines = ["---", 'title: "A page"']
    if isinstance(source, list):
        lines.append("source:")
        lines += [f'  - "{ref}"' for ref in source]
    elif isinstance(source, str):
        lines.append(f'source: "{source}"')
    lines += ["created: 2026-01-01", "type: concept"]
    if extra:
        lines += extra.strip("\n").split("\n")
    lines += ["---", "", "Body text.", ""]
    path.write_bytes("\n".join(lines).encode("utf-8"))
    return path


def snapshot(directory: Path) -> dict[str, tuple[bytes, int]]:
    return {
        p.relative_to(directory).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


# -- acceptance 1: the trust arm [R1] ---------------------------------------------


def test_trust_reports_the_stored_values_of_each_cited_page(probe, runner, tmp_path, seams):
    stub = seams.feedback()
    seams.refine()
    ctx = make_ctx(runner, tmp_path)

    result = probe.run(ctx)

    arm = result["arms"]["trust"]
    expected = {}
    for call in stub.calls:
        k = len(call["cited_pages"])
        for position in range(1, k + 1):
            trust, wrong = FeedbackStub.chosen(k, position)
            expected[f"trust_k{k}_p{position}"] = trust
            expected[f"wrong_k{k}_p{position}"] = wrong
    assert arm == {"status": "measured", "cases": 3, "metrics": expected}
    assert sum(name.startswith("trust_") for name in arm["metrics"]) == 14
    assert sum(name.startswith("wrong_") for name in arm["metrics"]) == 14


def test_trust_calls_add_feedback_entry_once_per_k_with_a_new_file_under_tmp(
    probe, runner, tmp_path, seams
):
    stub = seams.feedback()
    seams.refine()
    ctx = make_ctx(runner, tmp_path)

    probe.run(ctx)

    assert [len(c["cited_pages"]) for c in stub.calls] == list(KS)
    for call in stub.calls:
        assert call["question"] == "bench question"
        assert call["rating"] == "wrong"
        assert call["notes"] == ""
        assert len(set(call["cited_pages"])) == len(call["cited_pages"])
        assert all(isinstance(p, str) and p for p in call["cited_pages"])
        assert call["existed"] is False
        assert call["path"].is_relative_to(ctx.tmp), call["path"]
    assert len({c["path"] for c in stub.calls}) == len(KS)


def test_a_store_without_an_entry_for_a_cited_page_raises_naming_the_page(
    probe, runner, tmp_path, seams
):
    stub = seams.feedback(omit_last=True)
    seams.refine()

    with pytest.raises(ValueError) as raised:
        probe.run(make_ctx(runner, tmp_path))

    first = stub.calls[0]
    assert first["cited_pages"][0] in str(raised.value)
    assert first["path"].name in str(raised.value)


# -- acceptance 2: the refine arm [R2] --------------------------------------------


@pytest.mark.parametrize(
    "mode, accepted, refused",
    [("write", 1, 0), ("error", 0, 1), ("raise", 0, 1), ("silent", 0, 0)],
)
def test_refine_reports_accept_and_refuse_per_ratio(
    probe, runner, tmp_path, seams, mode, accepted, refused
):
    seams.feedback()
    seams.refine(mode)

    result = probe.run(make_ctx(runner, tmp_path))

    expected = {}
    for ratio in RATIOS:
        expected[f"accepted_{ratio}"] = accepted
        expected[f"refused_{ratio}"] = refused
    assert result["arms"]["refine"] == {"status": "measured", "cases": 4, "metrics": expected}


def test_refine_passes_the_first_ratio_percent_of_a_twenty_sentence_body(
    probe, runner, tmp_path, seams
):
    seams.feedback()
    stub = seams.refine("error")
    ctx = make_ctx(runner, tmp_path)

    probe.run(ctx)

    assert len(stub.calls) == len(RATIOS)
    bodies = [page_body(c["page_before"]).strip() for c in stub.calls]
    body = bodies[0]
    assert all(b == body for b in bodies)
    sentences = re.split(r"(?<=\.)\s+", body)
    assert len(sentences) == 20 and len(set(sentences)) == 20
    assert all(s.endswith(".") for s in sentences)
    assert len(body) >= 2000
    by_ratio = dict(zip(RATIOS, (c["new_body"] for c in stub.calls), strict=True))
    assert by_ratio[50] == body[: len(body) // 2]
    assert by_ratio[10] == body[: len(body) // 10]
    assert by_ratio[1] == body[: len(body) // 100]
    assert by_ratio[0] == ""


def test_refine_uses_its_own_wiki_and_history_under_tmp_for_each_ratio(
    probe, runner, tmp_path, seams
):
    seams.feedback()
    stub = seams.refine("write")
    ctx = make_ctx(runner, tmp_path)
    corpus_before = snapshot(ctx.wiki)

    probe.run(ctx)

    assert len(stub.calls) == len(RATIOS)
    for call in stub.calls:
        assert call["notes"] == "bench"
        assert call["wiki_dir"].is_relative_to(ctx.tmp)
        assert call["history_path"].is_relative_to(ctx.tmp)
        assert (call["wiki_dir"] / f"{call['page_id']}.md").is_file()
    assert len({c["wiki_dir"] for c in stub.calls}) == len(RATIOS)
    assert len({c["history_path"] for c in stub.calls}) == len(RATIOS)
    assert snapshot(ctx.wiki) == corpus_before


def test_a_failing_page_write_reaches_the_caller(probe, runner, tmp_path, seams, monkeypatch):
    seams.feedback()
    stub = seams.refine("write")
    for method in ("write_bytes", "write_text"):
        real = getattr(Path, method)

        def failing(self, data, *args, _real=real, **kwargs):
            if self.suffix == ".md" and "bench" in self.name:
                raise PermissionError(13, "denied by the test", str(self))
            return _real(self, data, *args, **kwargs)

        monkeypatch.setattr(Path, method, failing)

    with pytest.raises(PermissionError):
        probe.run(make_ctx(runner, tmp_path))

    assert stub.calls == []


# -- acceptance 3: the captures arm [R3] [R4] -------------------------------------

STATED_CONFIRMED = "confidence: stated\nbelief_state: confirmed"


def six_page_wiki(wiki: Path) -> None:
    write_page(wiki, "concepts/no-source.md")
    write_page(wiki, "concepts/one-capture.md", source=["raw/captures/a.md"])
    write_page(wiki, "concepts/two-captures.md", source=["raw/captures/b.md", "raw/captures/c.md"])
    write_page(wiki, "entities/mixed.md", source=["raw/captures/d.md", "raw/articles/e.md"])
    write_page(wiki, "entities/article.md", source=["raw/articles/f.md"])
    write_page(
        wiki,
        "summaries/stated-confirmed.md",
        source=["raw/captures/g.md", "raw/captures/h.md"],
        extra=STATED_CONFIRMED,
    )


def test_captures_metrics_equal_hand_computed_values(probe, runner, tmp_path, seams):
    seams.feedback()
    seams.refine()
    wiki = tmp_path / "corpus-wiki"
    six_page_wiki(wiki)
    ctx = make_ctx(runner, tmp_path, wiki)
    before = snapshot(wiki)

    result = probe.run(ctx)

    # Pages with sources: all but no-source. Any capture: one-capture,
    # two-captures, mixed, stated-confirmed. All captures: those less mixed.
    # Refs 1+2+2+1+2 = 8, of them captures 1+2+1+0+2 = 6.
    assert result["arms"]["captures"] == {
        "status": "measured",
        "cases": 6,
        "metrics": {
            "pages_with_sources": 5,
            "pages_any_capture_source": 4,
            "pages_all_capture_sources": 3,
            "refs_total": 8,
            "refs_captures": 6,
            "stated_all_capture": 1,
            "confirmed_all_capture": 1,
        },
    }
    assert result["invariants"] == ["I6", "I9"]
    assert snapshot(wiki) == before


def test_captures_counts_only_files_in_subdirectories_and_only_all_capture_pages(
    probe, runner, tmp_path, seams
):
    seams.feedback()
    seams.refine()
    wiki = tmp_path / "corpus-wiki"
    # Root files are no pages; a non-markdown file is no page; a nested page is one.
    write_page(wiki, "index.md", source=["raw/captures/root.md"], extra=STATED_CONFIRMED)
    write_page(wiki, "concepts/notes.txt", source=["raw/captures/txt.md"])
    write_page(wiki, "concepts/deep/nested.md", source=["raw/captures/n.md"])
    # stated and confirmed on a page that is not all captures are not counted.
    write_page(
        wiki,
        "entities/mixed.md",
        source=["raw/captures/m.md", "raw/articles/m.md"],
        extra=STATED_CONFIRMED,
    )
    # A ref that names captures in another form does not start with raw/captures/.
    write_page(wiki, "entities/other-form.md", source=["captures/x.md", "raw/captures/y.md"])
    # Belief and confidence values are compared exactly.
    write_page(
        wiki,
        "concepts/inferred.md",
        source=["raw/captures/i.md"],
        extra="confidence: inferred\nbelief_state: uncertain",
    )

    result = probe.run(make_ctx(runner, tmp_path, wiki))

    assert result["arms"]["captures"] == {
        "status": "measured",
        "cases": 4,
        "metrics": {
            "pages_with_sources": 4,
            "pages_any_capture_source": 4,
            "pages_all_capture_sources": 2,
            "refs_total": 6,
            "refs_captures": 4,
            "stated_all_capture": 0,
            "confirmed_all_capture": 0,
        },
    }


def test_captures_reads_a_single_string_source_and_crlf_frontmatter(probe, runner, tmp_path, seams):
    seams.feedback()
    seams.refine()
    wiki = tmp_path / "corpus-wiki"
    write_page(wiki, "concepts/string-source.md", source="raw/captures/s.md")
    crlf = (
        "---\r\ntitle: CRLF\r\nsource:\r\n  - raw/captures/r.md\r\n"
        "confidence: stated\r\nbelief_state: confirmed\r\n---\r\n\r\nBody.\r\n"
    )
    write_page(wiki, "concepts/crlf.md", raw=crlf.encode("utf-8"))

    result = probe.run(make_ctx(runner, tmp_path, wiki))

    assert result["arms"]["captures"] == {
        "status": "measured",
        "cases": 2,
        "metrics": {
            "pages_with_sources": 2,
            "pages_any_capture_source": 2,
            "pages_all_capture_sources": 2,
            "refs_total": 2,
            "refs_captures": 2,
            "stated_all_capture": 1,
            "confirmed_all_capture": 1,
        },
    }


UNPARSED_PAGES = {
    "malformed YAML": b"---\ntitle: [unclosed\nsource:\n  - raw/captures/a.md\n---\n\nBody.\n",
    "an impossible date": (
        b"---\ntitle: Bad date\ncreated: 2026-02-30\nsource:\n  - raw/captures/a.md\n---\n\nB.\n"
    ),
    "bytes that are not UTF-8": b"---\ntitle: \xff\xfe\nsource:\n  - raw/captures/a.md\n---\n",
}


@pytest.mark.parametrize("cause", sorted(UNPARSED_PAGES))
def test_a_page_whose_frontmatter_fails_to_load_is_read_with_no_sources(
    probe, runner, tmp_path, seams, cause
):
    seams.feedback()
    seams.refine()
    wiki = tmp_path / "corpus-wiki"
    write_page(wiki, "concepts/bad.md", raw=UNPARSED_PAGES[cause])
    write_page(wiki, "concepts/good.md", source=["raw/captures/g.md"])

    result = probe.run(make_ctx(runner, tmp_path, wiki))

    assert result["arms"]["captures"] == {
        "status": "measured",
        "cases": 2,
        "metrics": {
            "pages_with_sources": 1,
            "pages_any_capture_source": 1,
            "pages_all_capture_sources": 1,
            "refs_total": 1,
            "refs_captures": 1,
            "stated_all_capture": 0,
            "confirmed_all_capture": 0,
        },
    }


@pytest.mark.parametrize("layout", ["empty", "root files only"])
def test_a_wiki_with_no_page_makes_captures_unmeasured(probe, runner, tmp_path, seams, layout):
    seams.feedback()
    seams.refine()
    wiki = tmp_path / "corpus-wiki"
    wiki.mkdir()
    if layout == "root files only":
        write_page(wiki, "index.md", source=["raw/captures/a.md"])
        (wiki / "concepts").mkdir()

    result = probe.run(make_ctx(runner, tmp_path, wiki))

    assert result["arms"]["captures"] == {
        "status": "unmeasured",
        "reason": "no pages",
        "cases": 0,
        "metrics": {},
    }


def fail_reading(monkeypatch, name: str, exc: OSError) -> None:
    real = Path.read_bytes

    def reading(self):
        if self.name == name:
            raise exc
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", reading)


def test_a_page_that_vanishes_before_it_is_read_is_not_counted(
    probe, runner, tmp_path, seams, monkeypatch
):
    seams.feedback()
    seams.refine()
    wiki = tmp_path / "corpus-wiki"
    six_page_wiki(wiki)
    fail_reading(monkeypatch, "mixed.md", FileNotFoundError(2, "gone", "mixed.md"))

    result = probe.run(make_ctx(runner, tmp_path, wiki))

    # The six-page values less entities/mixed.md (one capture and one article ref).
    assert result["arms"]["captures"] == {
        "status": "measured",
        "cases": 5,
        "metrics": {
            "pages_with_sources": 4,
            "pages_any_capture_source": 3,
            "pages_all_capture_sources": 3,
            "refs_total": 6,
            "refs_captures": 5,
            "stated_all_capture": 1,
            "confirmed_all_capture": 1,
        },
    }


def test_a_page_that_cannot_be_read_for_another_reason_raises(
    probe, runner, tmp_path, seams, monkeypatch
):
    seams.feedback()
    seams.refine()
    wiki = tmp_path / "corpus-wiki"
    six_page_wiki(wiki)
    fail_reading(monkeypatch, "mixed.md", PermissionError(13, "denied", "mixed.md"))

    with pytest.raises(PermissionError):
        probe.run(make_ctx(runner, tmp_path, wiki))


# -- acceptance 4 and 5: through the runner [R1] [R2] [R5] [R6] -------------------

FAILING_WRAPPER = """
import importlib.util
from pathlib import Path

REAL = Path({real!r})


def run(ctx):
    import kb.feedback.store

    def failing(*args, **kwargs):
        raise OSError("feedback store unwritable")

    original = kb.feedback.store.add_feedback_entry
    kb.feedback.store.add_feedback_entry = failing
    spec = importlib.util.spec_from_file_location("kbeval_provenance_real", REAL)
    real = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(real)
        return real.run(ctx)
    finally:
        kb.feedback.store.add_feedback_entry = original
"""


def runner_bench(tmp_path_factory, name: str):
    from conftest import Bench

    root = tmp_path_factory.mktemp(name)
    dirs = {key: root / key for key in ("probes", "wiki", "raw")}
    for path in dirs.values():
        path.mkdir()
    return Bench(root=root, out=root / "out", **dirs)


def test_a_failing_feedback_store_makes_the_runner_exit_1_with_the_probe_name(
    tmp_path_factory,
):
    bench = runner_bench(tmp_path_factory, "failing")
    write_page(bench.wiki, "concepts/only.md", source=["raw/captures/a.md"])
    bench.probe("provenance", textwrap.dedent(FAILING_WRAPPER).format(real=str(PROBE)))

    proc = bench.run()

    assert proc.returncode == 1, proc.output
    assert "provenance failed:" in proc.output
    assert "OSError" in proc.output and "feedback store unwritable" in proc.output
    assert bench.records() == []


DEMO_WRAPPER = """
import importlib
import importlib.util
import json
from pathlib import Path

REAL = Path({real!r})
TARGETS = (
    ("kb.utils.llm", "call_llm"),
    ("kb.utils.llm", "call_llm_json"),
    ("kb.utils.llm", "get_client"),
    ("kb.utils.llm", "_make_api_call"),
    ("kb.utils.cli_backend", "call_cli"),
    ("kb.query.embeddings", "rebuild_vector_index"),
)


def run(ctx):
    import kb.feedback.store
    import kb.review.refiner

    model_calls = []
    feedback = []
    refines = []
    saved = []

    def spy(name):
        def called(*args, **kwargs):
            model_calls.append(name)
            raise RuntimeError("model function called: " + name)

        return called

    real_feedback = kb.feedback.store.add_feedback_entry
    real_refine = kb.review.refiner.refine_page

    def recording_feedback(question, rating, cited_pages, notes="", path=None):
        feedback.append({{"pages": list(cited_pages), "path": str(path)}})
        return real_feedback(question, rating, cited_pages, notes=notes, path=path)

    def recording_refine(page_id, content, notes="", wiki_dir=None, history_path=None):
        refines.append({{"wiki_dir": str(wiki_dir), "history_path": str(history_path)}})
        return real_refine(page_id, content, notes, wiki_dir=wiki_dir, history_path=history_path)

    for module_name, attr in TARGETS:
        module = importlib.import_module(module_name)
        saved.append((module, attr, getattr(module, attr)))
        setattr(module, attr, spy(module_name + "." + attr))
    saved.append((kb.feedback.store, "add_feedback_entry", real_feedback))
    saved.append((kb.review.refiner, "refine_page", real_refine))
    kb.feedback.store.add_feedback_entry = recording_feedback
    kb.review.refiner.refine_page = recording_refine
    spec = importlib.util.spec_from_file_location("kbeval_provenance_real", REAL)
    real = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(real)
        return real.run(ctx)
    finally:
        for module, attr, original in saved:
            setattr(module, attr, original)
        report = {{
            "tmp": str(ctx.tmp),
            "model_calls": model_calls,
            "feedback": feedback,
            "refines": refines,
        }}
        (Path(ctx.out) / "calls.json").write_text(json.dumps(report), encoding="utf-8")
"""


@pytest.fixture(scope="module")
def demo_run(tmp_path_factory):
    """Run the runner in a subprocess on demo/wiki with the real kb functions."""
    bench = runner_bench(tmp_path_factory, "demo")
    bench.probe("provenance", textwrap.dedent(DEMO_WRAPPER).format(real=str(PROBE)))
    proc = bench.run("--wiki", str(DEMO_WIKI), "--raw", str(DEMO_RAW))
    record_path = bench.out / "provenance.json"
    calls_path = bench.out / "calls.json"
    return {
        "code": proc.returncode,
        "output": proc.output,
        "record": json.loads(record_path.read_text(encoding="utf-8"))
        if record_path.exists()
        else None,
        "calls": json.loads(calls_path.read_text(encoding="utf-8"))
        if calls_path.exists()
        else None,
    }


def test_demo_wiki_runs_through_the_runner_with_the_real_functions(demo_run):
    assert demo_run["code"] == 0, demo_run["output"]
    assert "guarded directory changed:" not in demo_run["output"]
    record = demo_run["record"]
    assert record["invariants"] == ["I6", "I9"]
    arms = record["arms"]
    assert arms["trust"]["status"] == "measured"
    assert arms["refine"]["status"] == "measured"
    trust = arms["trust"]["metrics"]
    expected_names = {
        f"{kind}_k{k}_p{i}" for kind in ("trust", "wrong") for k in KS for i in range(1, k + 1)
    }
    assert set(trust) == expected_names
    for name, value in trust.items():
        if name.startswith("trust_"):
            assert 0 <= value <= 1, (name, value)
    refine = arms["refine"]["metrics"]
    assert set(refine) == {f"{kind}_{r}" for kind in ("accepted", "refused") for r in RATIOS}
    for ratio in RATIOS:
        assert not (refine[f"accepted_{ratio}"] == 1 and refine[f"refused_{ratio}"] == 1), ratio
    pages = [p for p in DEMO_WIKI.rglob("*.md") if len(p.relative_to(DEMO_WIKI).parts) > 1]
    assert arms["captures"]["status"] == "measured"
    assert arms["captures"]["cases"] == len(pages)


def test_the_real_stores_lie_under_tmp_and_no_model_function_runs(demo_run):
    calls = demo_run["calls"]
    assert calls is not None, demo_run["output"]
    assert calls["model_calls"] == []
    tmp = Path(calls["tmp"])
    assert [len(c["pages"]) for c in calls["feedback"]] == list(KS)
    for call in calls["feedback"]:
        assert Path(call["path"]).is_relative_to(tmp), call
    assert len(calls["refines"]) == len(RATIOS)
    for call in calls["refines"]:
        assert Path(call["wiki_dir"]).is_relative_to(tmp), call
        assert Path(call["history_path"]).is_relative_to(tmp), call
