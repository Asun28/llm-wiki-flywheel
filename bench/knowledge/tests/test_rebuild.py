"""Acceptance tests 1-6 of card T1-KBEVAL-REBUILD for `bench/knowledge/probes/rebuild.py`."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
import textwrap
from pathlib import Path

import pytest
from conftest import REPO

PROBE = REPO / "bench" / "knowledge" / "probes" / "rebuild.py"
DATA = REPO / "bench" / "knowledge" / "data" / "rebuild"
MODEL_VARS = ("CLAUDE_SCAN_MODEL", "CLAUDE_WRITE_MODEL", "CLAUDE_ORCHESTRATE_MODEL")
TEMPLATE_TEXT = b"# Extraction template: Web article\nname: article\nextract:\n  - title\n"

# Four small sources. Their sha256 order, worked out once and checked by
# test_the_hashed_order_literal_matches_sha256, keeps the first and the last
# source of path order and swaps the middle two.
STEMS = ["alder", "ash", "ginkgo", "hazel"]
PATH_ORDER = STEMS
REVERSE_ORDER = ["hazel", "ginkgo", "ash", "alder"]
HASHED_ORDER = ["alder", "ginkgo", "ash", "hazel"]


# -- helpers ---------------------------------------------------------------------


@pytest.fixture
def probe():
    name = "kbeval_probe_rebuild_under_test"
    spec = importlib.util.spec_from_file_location(name, PROBE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(name, None)


def make_ctx(runner, tmp_path: Path, data: Path):
    work = tmp_path / "work"
    work.mkdir()
    return runner.Context(tmp=work, data=data, wiki=tmp_path, raw=tmp_path, out=tmp_path)


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def dumps(row) -> str:
    return json.dumps(row, ensure_ascii=False)


def source_row(stem: str) -> dict:
    return {"path": f"articles/{stem}.md", "text": f"# {stem.title()}\n\nNotes on {stem} wood.\n"}


def extraction(stem: str) -> dict:
    return {
        "title": f"{stem.title()} Wood",
        "entities_mentioned": [f"{stem.title()} Mill"],
        "concepts_mentioned": ["Grain"],
    }


SMALL_SOURCES = [source_row(stem) for stem in STEMS]
SMALL_EXTRACTIONS = {row["path"]: extraction(row["path"][9:-3]) for row in SMALL_SOURCES}


def small_data(tmp_path: Path, sources=None, extractions=None, raw_extractions=None) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    write_lines(data / "sources.jsonl", [dumps(r) for r in (sources or SMALL_SOURCES)])
    text = raw_extractions or dumps(extractions or SMALL_EXTRACTIONS)
    (data / "extractions.json").write_bytes(text.encode("utf-8"))
    return data


class StubIngest:
    """A stand-in for `kb.ingest.pipeline.ingest_source` that writes chosen files.

    `writer(wiki, stem, number, seen)` writes the files of one call: `number` is the
    index of the call among the calls on that wiki and `seen` the stems ingested
    into that wiki so far, this one included. Each call is recorded with what the
    test needs to check it.
    """

    def __init__(self, writer):
        self.writer = writer
        self.calls: list[dict] = []

    def __call__(self, source_path, source_type=None, extraction=None, **kwargs):
        import kb.compile.compiler

        wiki = Path(kwargs["wiki_dir"])
        stem = Path(source_path).stem
        earlier = [c for c in self.calls if c["wiki"] == wiki]
        self.calls.append(
            {
                "wiki": wiki,
                "stem": stem,
                "source_path": Path(source_path),
                "source_bytes": Path(source_path).read_bytes(),
                "source_type": source_type,
                "extraction": extraction,
                "kwargs": dict(kwargs),
                "manifest": Path(kb.compile.compiler.HASH_MANIFEST),
            }
        )
        seen = [c["stem"] for c in earlier] + [stem]
        self.writer(wiki, stem, len(earlier), seen)
        return {"source_path": str(source_path), "pages_created": [], "pages_updated": []}

    def wikis(self) -> list[Path]:
        found: list[Path] = []
        for call in self.calls:
            if call["wiki"] not in found:
                found.append(call["wiki"])
        return found

    def stems_by_wiki(self) -> list[list[str]]:
        return [[c["stem"] for c in self.calls if c["wiki"] == w] for w in self.wikis()]


def put(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def append(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "ab") as handle:
        handle.write(data)


def plain_writer(wiki: Path, stem: str, number: int, seen: list[str]) -> None:
    put(wiki / "summaries" / f"{stem}.md", f"# {stem}\n".encode())


class StubScan:
    """A stand-in for `kb.compile.compiler.find_changed_sources`.

    Each call notes what differs from the first call: the three model variables,
    the bytes of `article.yaml` and the bytes of each raw source. The answer of a
    call is `answers[step]`, where the step is named by what differs.
    """

    def __init__(self, template: Path, answers: dict[str, list[str]] | None = None, fail_on=None):
        self.template = template
        self.answers = answers or {}
        self.fail_on = fail_on
        self.calls: list[dict] = []

    def state(self, raw_dir: Path) -> dict:
        return {
            "env": {var: os.environ.get(var) for var in MODEL_VARS},
            "template": self.template.read_bytes(),
            "sources": {
                p.name: p.read_bytes() for p in sorted((Path(raw_dir) / "articles").glob("*.md"))
            },
        }

    def __call__(self, raw_dir=None, manifest_path=None, *args, **kwargs):
        state = self.state(raw_dir)
        base = self.calls[0]["state"] if self.calls else state
        changed = []
        if state["env"] != base["env"]:
            changed.append("model")
        if state["template"] != base["template"]:
            changed.append("template")
        if state["sources"] != base["sources"]:
            changed.append("source")
        step = changed[0] if len(changed) == 1 else ("clean" if not changed else "mixed")
        self.calls.append(
            {
                "raw_dir": Path(raw_dir),
                "manifest_path": manifest_path,
                "args": args,
                "kwargs": dict(kwargs),
                "state": state,
                "step": step,
            }
        )
        if step == self.fail_on:
            raise RuntimeError(f"scan failed on the {step} step")
        listed = [Path(raw_dir) / "articles" / name for name in self.answers.get(step, [])]
        # Half of the listed sources come back as new and half as changed, so a
        # probe that reads only one of the two lists undercounts.
        return listed[::2], listed[1::2]


@pytest.fixture
def seams(monkeypatch, tmp_path):
    """Stub ingest and scan, a temporary project root and its `article.yaml`."""
    import kb.compile.compiler
    import kb.ingest.pipeline

    root = tmp_path / "root"
    templates = root / "templates"
    templates.mkdir(parents=True)
    (templates / "article.yaml").write_bytes(TEMPLATE_TEXT)
    monkeypatch.setenv("KB_PROJECT_ROOT", str(root))
    monkeypatch.setattr(kb.compile.compiler, "TEMPLATES_DIR", templates)

    class Seams:
        template = templates / "article.yaml"

        def ingest(self, writer=plain_writer) -> StubIngest:
            stub = StubIngest(writer)
            monkeypatch.setattr(kb.ingest.pipeline, "ingest_source", stub)
            return stub

        def scan(self, **kwargs) -> StubScan:
            stub = StubScan(self.template, **kwargs)
            monkeypatch.setattr(kb.compile.compiler, "find_changed_sources", stub)
            return stub

    return Seams()


def committed_sources() -> list[dict]:
    lines = (DATA / "sources.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def committed_extractions() -> dict:
    return json.loads((DATA / "extractions.json").read_text(encoding="utf-8"))


# -- acceptance 1: the committed files [R1] [R2] ---------------------------------


def test_committed_files_load_with_the_minimum_counts(probe, runner, tmp_path, seams):
    sources = committed_sources()
    extractions = committed_extractions()
    paths = [row["path"] for row in sources]
    assert len(sources) >= 6
    assert len(set(paths)) == len(paths)
    assert all(re.fullmatch(r"articles/[a-z0-9]+(?:-[a-z0-9]+)*\.md", p) for p in paths)
    assert sorted(extractions) == sorted(paths)
    for kind, minimum in (("entities_mentioned", 3), ("concepts_mentioned", 3)):
        counts: dict[str, int] = {}
        for value in extractions.values():
            for name in set(value[kind]):
                counts[name] = counts.get(name, 0) + 1
        assert sum(n >= 2 for n in counts.values()) >= minimum, (kind, counts)

    stub = seams.ingest()
    seams.scan()
    probe.run(make_ctx(runner, tmp_path, DATA))

    by_path = {row["path"]: row for row in sources}
    first_pass = stub.calls[: len(sources)]
    assert [c["stem"] for c in first_pass] == [Path(p).stem for p in sorted(paths)]
    for call in first_pass:
        path = f"articles/{call['stem']}.md"
        assert call["source_bytes"] == by_path[path]["text"].encode("utf-8")
        assert call["extraction"] == extractions[path]


# -- acceptance 2: one ValueError per cause of R2 --------------------------------

BAD_SOURCE_LINES = {
    "not JSON": "{",
    "not an object": '["articles/oak.md", "text"]',
    "lacks path": dumps({"text": "Oak."}),
    "lacks text": dumps({"path": "articles/oak.md"}),
    "repeats a path": dumps(source_row("alder")),
    "has a path outside articles/": dumps({"path": "notes/oak.md", "text": "Oak."}),
    "has a path with a capital and a space": dumps({"path": "articles/Oak tree.md", "text": "O"}),
    "has a path that is not .md": dumps({"path": "articles/oak.txt", "text": "Oak."}),
    "has a path with a parent step": dumps({"path": "articles/../oak.md", "text": "Oak."}),
    "has a path that is not a string": dumps({"path": 7, "text": "Oak."}),
    "has a text that is not a string": dumps({"path": "articles/oak.md", "text": ["Oak."]}),
    "has an empty text": dumps({"path": "articles/oak.md", "text": "  "}),
}


@pytest.mark.parametrize("cause", sorted(BAD_SOURCE_LINES))
def test_a_bad_sources_line_raises_with_file_and_line(probe, runner, tmp_path, seams, cause):
    stub = seams.ingest()
    seams.scan()
    data = small_data(tmp_path)
    write_lines(
        data / "sources.jsonl", [dumps(r) for r in SMALL_SOURCES] + [BAD_SOURCE_LINES[cause]]
    )

    with pytest.raises(ValueError) as raised:
        probe.run(make_ctx(runner, tmp_path, data))

    assert "sources.jsonl" in str(raised.value)
    assert "line 5" in str(raised.value)
    assert stub.calls == []


def with_extraction(path: str, value) -> dict:
    return {**SMALL_EXTRACTIONS, path: value}


ALDER = "articles/alder.md"
BAD_EXTRACTIONS = {
    "a path with no extraction": (
        {k: v for k, v in SMALL_EXTRACTIONS.items() if k != "articles/ginkgo.md"},
        "articles/ginkgo.md",
    ),
    "an extraction that names no source": (
        with_extraction("articles/oak.md", extraction("oak")),
        "articles/oak.md",
    ),
    "an extraction that is not an object": (with_extraction(ALDER, ["Alder Wood"]), ALDER),
    "an extraction without a title": (
        with_extraction(ALDER, {k: v for k, v in extraction("alder").items() if k != "title"}),
        ALDER,
    ),
    "a title that is not a string": (
        with_extraction(ALDER, {**extraction("alder"), "title": 3}),
        ALDER,
    ),
    "an empty title": (with_extraction(ALDER, {**extraction("alder"), "title": " "}), ALDER),
    "an author that is not a string": (
        with_extraction(ALDER, {**extraction("alder"), "author": ["A", "B"]}),
        ALDER,
    ),
    "entities that are not a list": (
        with_extraction(ALDER, {**extraction("alder"), "entities_mentioned": "Alder Mill"}),
        ALDER,
    ),
    "entities with one item that is not a string": (
        with_extraction(ALDER, {**extraction("alder"), "entities_mentioned": ["Alder Mill", 4]}),
        ALDER,
    ),
    "concepts missing": (
        with_extraction(
            ALDER,
            {k: v for k, v in extraction("alder").items() if k != "concepts_mentioned"},
        ),
        ALDER,
    ),
    "concepts with one empty item": (
        with_extraction(ALDER, {**extraction("alder"), "concepts_mentioned": ["Grain", ""]}),
        ALDER,
    ),
    "key claims with one item that is not a string": (
        with_extraction(ALDER, {**extraction("alder"), "key_claims": ["Alder is soft.", None]}),
        ALDER,
    ),
}


@pytest.mark.parametrize("cause", sorted(BAD_EXTRACTIONS))
def test_a_bad_extraction_raises_with_file_and_path(probe, runner, tmp_path, seams, cause):
    stub = seams.ingest()
    seams.scan()
    extractions, path = BAD_EXTRACTIONS[cause]
    data = small_data(tmp_path, extractions=extractions)

    with pytest.raises(ValueError) as raised:
        probe.run(make_ctx(runner, tmp_path, data))

    assert "extractions.json" in str(raised.value)
    assert path in str(raised.value)
    assert stub.calls == []


def test_an_extractions_file_that_is_not_json_raises_with_file_and_line(
    probe, runner, tmp_path, seams
):
    stub = seams.ingest()
    seams.scan()
    data = small_data(tmp_path, raw_extractions='{\n  "articles/alder.md": {\n    "title": ,\n')

    with pytest.raises(ValueError) as raised:
        probe.run(make_ctx(runner, tmp_path, data))

    assert "extractions.json" in str(raised.value)
    assert "line 3" in str(raised.value)
    assert stub.calls == []


def test_an_extractions_file_that_is_not_an_object_raises_with_file(probe, runner, tmp_path, seams):
    stub = seams.ingest()
    seams.scan()
    data = small_data(tmp_path, raw_extractions=dumps([SMALL_EXTRACTIONS]))

    with pytest.raises(ValueError) as raised:
        probe.run(make_ctx(runner, tmp_path, data))

    assert "extractions.json" in str(raised.value)
    assert "not a JSON object" in str(raised.value)
    assert stub.calls == []


# -- acceptance 3: the idempotence arm [R3] [R4] ---------------------------------


def second_pass_writer(wiki: Path, stem: str, number: int, seen: list[str]) -> None:
    """Pass 1 writes 7 files; pass 2 adds one page and rewrites one page and log.md.

    Every other file of pass 2 is written again with the bytes it already holds.
    Only the wiki that sees a second pass (calls 4 to 7) gets the pass-2 writes.
    """
    second = number >= len(STEMS)
    put(wiki / "summaries" / f"{stem}.md", f"# {stem}\n".encode())
    if stem == "alder":
        put(
            wiki / "entities" / "shared.md",
            b"# Shared\n\nversion two\n" if second else b"# Shared\n\nversion one\n",
        )
        put(wiki / "index.md", b"# Index\n")
    if stem == "ash" and second:
        put(wiki / "concepts" / "added.md", b"# Added\n")
    if stem == "hazel":
        put(wiki / "log.md", b"second\n" if second else b"first\n")


def removing_writer(wiki: Path, stem: str, number: int, seen: list[str]) -> None:
    """Pass 1 as above; pass 2 removes summaries/ash.md and changes nothing else."""
    second = number >= len(STEMS)
    if second and stem == "ash":
        (wiki / "summaries" / "ash.md").unlink()
        return
    put(wiki / "summaries" / f"{stem}.md", f"# {stem}\n".encode())
    if stem == "alder":
        put(wiki / "entities" / "shared.md", b"# Shared\n\nversion one\n")
        put(wiki / "index.md", b"# Index\n")
    if stem == "hazel":
        put(wiki / "log.md", b"first\n")


def test_idempotence_counts_equal_hand_computed_values(probe, runner, tmp_path, seams):
    seams.ingest(second_pass_writer)
    seams.scan()

    result = probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    # After pass 1: four summaries, entities/shared.md, index.md and log.md.
    # Pass 2 changes entities/shared.md and log.md and adds concepts/added.md.
    assert result["arms"]["idempotence"] == {
        "status": "measured",
        "cases": 4,
        "metrics": {
            "files_after_first": 7,
            "files_changed_by_second": 3,
            "page_files_changed_by_second": 2,
        },
    }


def test_a_file_removed_by_the_second_pass_counts_as_changed(probe, runner, tmp_path, seams):
    seams.ingest(removing_writer)
    seams.scan()

    result = probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    assert result["arms"]["idempotence"]["metrics"] == {
        "files_after_first": 7,
        "files_changed_by_second": 1,
        "page_files_changed_by_second": 1,
    }


def test_ingest_is_called_once_per_source_per_pass_on_wikis_under_tmp(
    probe, runner, tmp_path, seams
):
    import kb.compile.compiler

    manifest_before = kb.compile.compiler.HASH_MANIFEST
    stub = seams.ingest()
    seams.scan()
    ctx = make_ctx(runner, tmp_path, small_data(tmp_path))

    probe.run(ctx)

    # Idempotence: path order twice. Order: path, reverse, sha256. Scan: path order.
    assert stub.stems_by_wiki() == [
        PATH_ORDER + PATH_ORDER,
        PATH_ORDER,
        REVERSE_ORDER,
        HASHED_ORDER,
        PATH_ORDER,
    ]
    assert len(stub.calls) == 6 * len(STEMS)
    by_path = {row["path"]: row for row in SMALL_SOURCES}
    for call in stub.calls:
        path = f"articles/{call['stem']}.md"
        raw_dir = Path(call["kwargs"]["raw_dir"])
        assert call["kwargs"] == {
            "wiki_dir": call["wiki"],
            "raw_dir": raw_dir,
            "_skip_vector_rebuild": True,
        }
        assert call["source_type"] == "article"
        assert call["extraction"] == SMALL_EXTRACTIONS[path]
        assert raw_dir.name == "raw"
        assert call["source_path"] == raw_dir / "articles" / f"{call['stem']}.md"
        assert call["source_bytes"] == by_path[path]["text"].encode("utf-8")
        for where in (call["wiki"], raw_dir, call["manifest"]):
            assert where.is_relative_to(ctx.tmp), where
    # Each wiki has a raw directory and a manifest of its own.
    assert len({c["kwargs"]["raw_dir"] for c in stub.calls}) == 5
    assert len({c["manifest"] for c in stub.calls}) == 5
    assert kb.compile.compiler.HASH_MANIFEST == manifest_before


def test_the_hashed_order_literal_matches_sha256():
    def digest(stem):
        return hashlib.sha256(f"articles/{stem}.md".encode()).hexdigest()

    assert sorted(STEMS, key=digest) == HASHED_ORDER


# -- acceptance 4: the order arm [R5] --------------------------------------------


def order_writer(wiki: Path, stem: str, number: int, seen: list[str]) -> None:
    """Write pages that depend on the order of the calls on one wiki.

    - summaries/<stem>.md: the same in every order;
    - entities/shared.md: one line per source in call order, so another order
      gives other bytes and the same lines;
    - concepts/latest.md: names the last source, so its lines depend on it;
    - concepts/opener-<stem>.md: written by the first source only, so the page
      set depends on which source comes first;
    - log.md: order-dependent but at the wiki root, so it is no page.
    """
    put(wiki / "summaries" / f"{stem}.md", f"# {stem}\n\nSummary of {stem}.\n".encode())
    shared = wiki / "entities" / "shared.md"
    if not shared.exists():
        put(shared, b"# Shared\n\n")
    append(shared, f"- {stem}\n".encode())
    put(wiki / "concepts" / "latest.md", f"# Latest\n\nlast: {stem}\n".encode())
    if len(seen) == 1:
        put(wiki / "concepts" / f"opener-{stem}.md", b"# Opener\n")
    append(wiki / "log.md", f"{stem}\n".encode())


def test_order_counts_equal_hand_computed_values(probe, runner, tmp_path, seams):
    seams.ingest(order_writer)
    seams.scan()

    result = probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    # reverse: opener-hazel against opener-alder; of the six shared pages,
    #   shared.md differs in bytes only and latest.md (alder against hazel) in lines.
    # hashed: alder first and hazel last, so only shared.md differs, in bytes only.
    assert result["arms"]["order"] == {
        "status": "measured",
        "cases": 4,
        "metrics": {
            "page_set_equal_reverse": 0,
            "pages_differing_bytes_reverse": 2,
            "pages_differing_lines_reverse": 1,
            "page_set_equal_hashed": 1,
            "pages_differing_bytes_hashed": 1,
            "pages_differing_lines_hashed": 0,
        },
    }


def blank_line_writer(wiki: Path, stem: str, number: int, seen: list[str]) -> None:
    """A page that gains a blank line in reverse order only, and nothing else differs."""
    put(wiki / "summaries" / f"{stem}.md", f"# {stem}\n".encode())
    blank = b"\n\n" if seen[0] == "hazel" else b"\n"
    put(wiki / "concepts" / "spaced.md", b"# Spaced\n" + blank + b"text\n")


def test_a_page_that_differs_by_a_blank_line_counts_in_bytes_not_in_lines(
    probe, runner, tmp_path, seams
):
    seams.ingest(blank_line_writer)
    seams.scan()

    result = probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    assert result["arms"]["order"]["metrics"] == {
        "page_set_equal_reverse": 1,
        "pages_differing_bytes_reverse": 1,
        "pages_differing_lines_reverse": 0,
        "page_set_equal_hashed": 1,
        "pages_differing_bytes_hashed": 0,
        "pages_differing_lines_hashed": 0,
    }


# -- acceptance 5: the scan arm [R6] [R7] [R8] -----------------------------------


@pytest.fixture
def model_env(monkeypatch):
    """Known earlier values: two variables set and one unset."""
    monkeypatch.setenv("CLAUDE_SCAN_MODEL", "scan-before")
    monkeypatch.delenv("CLAUDE_WRITE_MODEL", raising=False)
    monkeypatch.setenv("CLAUDE_ORCHESTRATE_MODEL", "orchestrate-before")
    return {
        "CLAUDE_SCAN_MODEL": "scan-before",
        "CLAUDE_WRITE_MODEL": None,
        "CLAUDE_ORCHESTRATE_MODEL": "orchestrate-before",
    }


@pytest.mark.parametrize(
    "answers, expected",
    [
        (
            {"template": ["alder.md"], "source": ["alder.md", "ash.md"]},
            {
                "listed_clean": 0,
                "sees_model_change": 0,
                "sees_template_change": 1,
                "sees_source_change": 1,
            },
        ),
        (
            {"model": ["hazel.md", "ash.md"]},
            {
                "listed_clean": 0,
                "sees_model_change": 1,
                "sees_template_change": 0,
                "sees_source_change": 0,
            },
        ),
    ],
)
def test_scan_metrics_follow_the_answers_of_each_step(
    probe, runner, tmp_path, seams, model_env, answers, expected
):
    seams.ingest()
    scan = seams.scan(answers=answers)
    ctx = make_ctx(runner, tmp_path, small_data(tmp_path))

    result = probe.run(ctx)

    assert result["arms"]["scan"] == {"status": "measured", "cases": 4, "metrics": expected}
    assert [c["step"] for c in scan.calls] == ["clean", "model", "template", "source"]
    for call in scan.calls:
        assert call["args"] == ()
        assert call["kwargs"] == {"save_hashes": False}
        assert call["raw_dir"] == scan.calls[0]["raw_dir"]
        assert call["raw_dir"].is_relative_to(ctx.tmp)
        assert Path(call["manifest_path"]).is_relative_to(ctx.tmp)


def test_each_scan_step_changes_one_input_and_undoes_it(probe, runner, tmp_path, seams, model_env):
    seams.ingest()
    scan = seams.scan()
    ctx = make_ctx(runner, tmp_path, small_data(tmp_path))

    probe.run(ctx)

    assert [c["step"] for c in scan.calls] == ["clean", "model", "template", "source"]
    clean, model, template, source = (c["state"] for c in scan.calls)
    assert clean["env"] == model_env
    for var in MODEL_VARS:
        assert model["env"][var] not in (None, "", model_env[var]), var
    assert template["env"] == model_env
    assert source["env"] == model_env
    # The template step appends one line to article.yaml and nothing else.
    assert template["template"].startswith(TEMPLATE_TEXT)
    added = template["template"][len(TEMPLATE_TEXT) :]
    assert added.strip() and added.endswith(b"\n") and added.count(b"\n") == 1
    assert source["template"] == TEMPLATE_TEXT
    # The source step appends one line to one source.
    changed = [n for n in source["sources"] if source["sources"][n] != clean["sources"][n]]
    assert len(changed) == 1
    before, after = clean["sources"][changed[0]], source["sources"][changed[0]]
    assert after.startswith(before) and after[len(before) :].count(b"\n") == 1
    # Everything is back as it was after the run.
    assert {var: os.environ.get(var) for var in MODEL_VARS} == model_env
    assert seams.template.read_bytes() == TEMPLATE_TEXT
    raw = scan.calls[0]["raw_dir"] / "articles"
    assert {p.name: p.read_bytes() for p in raw.glob("*.md")} == clean["sources"]


def test_a_source_listed_on_the_clean_call_makes_the_arm_unmeasured(
    probe, runner, tmp_path, seams, model_env
):
    seams.ingest()
    scan = seams.scan(answers={"clean": ["alder.md", "ash.md", "hazel.md"]})

    result = probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    arm = result["arms"]["scan"]
    assert arm["status"] == "unmeasured"
    assert re.search(r"\b3\b", arm["reason"]), arm["reason"]
    assert [c["step"] for c in scan.calls] == ["clean"]
    assert {var: os.environ.get(var) for var in MODEL_VARS} == model_env
    assert seams.template.read_bytes() == TEMPLATE_TEXT


@pytest.mark.parametrize("step", ["model", "template", "source"])
def test_a_scan_that_raises_leaves_every_input_as_it_was(
    probe, runner, tmp_path, seams, model_env, step
):
    seams.ingest()
    scan = seams.scan(fail_on=step)
    ctx = make_ctx(runner, tmp_path, small_data(tmp_path))

    with pytest.raises(RuntimeError):
        probe.run(ctx)

    assert scan.calls[-1]["step"] == step
    assert {var: os.environ.get(var) for var in MODEL_VARS} == model_env
    assert seams.template.read_bytes() == TEMPLATE_TEXT
    raw = scan.calls[0]["raw_dir"] / "articles"
    assert {p.name: p.read_bytes() for p in raw.glob("*.md")} == scan.calls[0]["state"]["sources"]


def test_a_template_outside_the_project_root_is_not_edited(
    probe, runner, tmp_path, seams, monkeypatch
):
    seams.ingest()
    scan = seams.scan()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setenv("KB_PROJECT_ROOT", str(elsewhere))

    with pytest.raises(ValueError) as raised:
        probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    assert "article.yaml" in str(raised.value)
    assert seams.template.read_bytes() == TEMPLATE_TEXT
    assert "template" not in [c["step"] for c in scan.calls]


# -- acceptance 6: the committed set through the runner [R3] [R8] [R9] ----------

WRAPPER = """
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
    ("kb.ingest.extractors", "call_llm_json"),
    ("kb.ingest.extractors", "extract_from_source"),
    ("kb.ingest.pipeline", "extract_from_source"),
    ("kb.query.embeddings", "rebuild_vector_index"),
)


def run(ctx):
    import importlib

    import kb.ingest.pipeline

    calls = []
    ingested = []
    saved = []

    def spy(name):
        def called(*args, **kwargs):
            calls.append(name)
            raise RuntimeError("model function called: " + name)

        return called

    real_ingest = kb.ingest.pipeline.ingest_source

    def recording_ingest(source_path, *args, **kwargs):
        ingested.append(Path(source_path).name)
        return real_ingest(source_path, *args, **kwargs)

    for module_name, attr in TARGETS:
        module = importlib.import_module(module_name)
        saved.append((module, attr, getattr(module, attr)))
        setattr(module, attr, spy(module_name + "." + attr))
    saved.append((kb.ingest.pipeline, "ingest_source", real_ingest))
    kb.ingest.pipeline.ingest_source = recording_ingest
    spec = importlib.util.spec_from_file_location("kbeval_rebuild_real", REAL)
    real = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(real)
        return real.run(ctx)
    finally:
        for module, attr, original in saved:
            setattr(module, attr, original)
        report = {{"model_calls": calls, "ingested": ingested}}
        (Path(ctx.out) / "calls.json").write_text(json.dumps(report), encoding="utf-8")
"""


@pytest.fixture(scope="module")
def committed_run(tmp_path_factory):
    """Run the runner in a subprocess on the committed set with the real kb functions.

    The probe file in the temporary probes directory is named `rebuild.py`, so the
    runner gives it the committed data directory. It replaces every model entry
    point with a function that records the call and raises, then runs the real
    probe.
    """
    from conftest import Bench

    root = tmp_path_factory.mktemp("committed")
    dirs = {name: root / name for name in ("probes", "wiki", "raw")}
    for path in dirs.values():
        path.mkdir()
    bench = Bench(root=root, out=root / "out", **dirs)
    bench.probe("rebuild", textwrap.dedent(WRAPPER).format(real=str(PROBE)))
    proc = bench.run()
    record_path = bench.out / "rebuild.json"
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


def test_committed_set_runs_through_the_runner(committed_run):
    cases = len(committed_sources())
    assert committed_run["code"] == 0, committed_run["output"]
    assert "guarded directory changed:" not in committed_run["output"]
    record = committed_run["record"]
    assert record["invariants"] == ["I3", "I4"]
    assert set(record["arms"]) == {"idempotence", "order", "scan"}
    for name in ("idempotence", "order"):
        assert record["arms"][name]["status"] == "measured", name
        assert record["arms"][name]["cases"] == cases, name
    idempotence = record["arms"]["idempotence"]["metrics"]
    assert set(idempotence) == {
        "files_after_first",
        "files_changed_by_second",
        "page_files_changed_by_second",
    }
    assert idempotence["files_after_first"] > cases
    order = record["arms"]["order"]["metrics"]
    assert set(order) == {
        f"{metric}_{pair}"
        for metric in ("page_set_equal", "pages_differing_bytes", "pages_differing_lines")
        for pair in ("reverse", "hashed")
    }
    scan = record["arms"]["scan"]
    if scan["status"] == "unmeasured":
        assert re.search(r"\d", scan["reason"]), scan["reason"]
    else:
        assert scan["cases"] == cases
        assert scan["metrics"]["listed_clean"] == 0


def test_the_real_ingest_runs_once_per_source_per_pass_and_no_model_function_runs(
    committed_run,
):
    names = sorted(Path(row["path"]).name for row in committed_sources())
    by_hash = sorted(names, key=lambda n: hashlib.sha256(f"articles/{n}".encode()).hexdigest())
    calls = committed_run["calls"]
    assert calls is not None, committed_run["output"]
    assert calls["model_calls"] == []
    # Idempotence twice in path order; order in path, reverse and sha256 order;
    # scan once in path order.
    assert calls["ingested"] == names + names + names + names[::-1] + by_hash + names
