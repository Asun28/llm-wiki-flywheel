"""Acceptance tests 1-5 of card T1-KBEVAL-CITATIONS for `bench/knowledge/probes/citations.py`."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import sys
from pathlib import Path

import pytest
from conftest import REPO

PROBE = REPO / "bench" / "knowledge" / "probes" / "citations.py"
DATA = REPO / "bench" / "knowledge" / "data" / "citations"
CLASSES = ("in-context", "out-of-context", "nonexistent", "traversal")
# The test's own reading of a `[[...]]` citation, independent of kb and of the probe.
WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
MISSING = re.compile(r"concepts/missing-[0-9]+")


# -- helpers ---------------------------------------------------------------------


@pytest.fixture
def probe():
    name = "kbeval_probe_citations_under_test"
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


def dumps(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False)


def page(pid, topic, title, body):
    return {"id": pid, "topic": topic, "title": title, "body": body}


SMALL_PAGES = [
    page("concepts/levain", "bread", "Levain", "A levain is fed starter mixed into dough."),
    page("concepts/autolyse", "bread", "Autolyse", "Autolyse is a rest of flour and water."),
    page("concepts/banneton", "bread", "Banneton", "A banneton is a proofing basket."),
    page("concepts/neap-tide", "tides", "Neap Tide", "A neap tide has the smallest range."),
    page("concepts/tide-gauge", "tides", "Tide Gauge", "A tide gauge records sea level."),
]
SMALL_IDS = {p["id"] for p in SMALL_PAGES}
SMALL_QUESTIONS = [
    {"id": "q-one", "topic": "bread", "question": "What is a levain?", "why": "asks about levain"},
    {
        "id": "q-two",
        "topic": "tides",
        "question": "What is a neap tide?",
        "why": "asks about tides",
    },
]
# The stub's fixed context: three of the five pages stay outside it.
FIXED_CONTEXT = ["concepts/autolyse", "concepts/levain"]


def small_data(tmp_path: Path, pages=None, questions=None) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    write_lines(data / "pages.jsonl", [dumps(p) for p in (pages or SMALL_PAGES)])
    write_lines(data / "questions.jsonl", [dumps(q) for q in (questions or SMALL_QUESTIONS)])
    return data


def classify(path: str, context: list[str], page_ids: set[str]) -> str | None:
    """The class of R4 for one cited path, by the test's own rules."""
    if path.startswith("../"):
        return "traversal"
    if path in context:
        return "in-context"
    if path in page_ids:
        return "out-of-context"
    if MISSING.fullmatch(path):
        return "nonexistent"
    return None


def committed_rows(name: str) -> list[dict]:
    lines = (DATA / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


class StubWiki:
    """A stand-in for `kb.query.engine.query_wiki`.

    Each call asks the replaced model function of `kb.query.engine` for the
    answer, reads the `[[...]]` citations from it with the test's own pattern
    and returns as `citations` the first `keep[qid][class]` cited paths of each
    class. `context_for(qid, call_number)` gives the `context_pages` of a call.
    """

    def __init__(self, keep, context_for=None, extra_key_on=None):
        self.keep = keep
        self.context_for = context_for or (lambda qid, n: list(FIXED_CONTEXT))
        self.extra_key_on = extra_key_on
        self.calls: list[tuple[str, Path]] = []
        self.answers: list[tuple[str, str]] = []
        self.wiki_files: list[set[str]] = []

    def __call__(self, question, wiki_dir=None, *args, **kwargs):
        import kb.query.engine

        assert not args and not kwargs, (args, kwargs)
        qid = next(q["id"] for q in SMALL_QUESTIONS if q["question"] == question)
        call_number = sum(1 for asked, _ in self.calls if asked == question)
        self.calls.append((question, Path(wiki_dir)))
        self.wiki_files.append(
            {p.relative_to(wiki_dir).as_posix() for p in Path(wiki_dir).rglob("*.md")}
        )
        context = self.context_for(qid, call_number)
        answer = kb.query.engine.call_llm(
            f"QUESTION: {question}", tier="orchestrate", system="stub", max_tokens=100
        )
        self.answers.append((qid, answer))
        kept: dict[str, int] = {}
        citations = []
        for path in WIKILINK.findall(answer):
            cls = classify(path, context, SMALL_IDS)
            if kept.get(cls, 0) < self.keep.get(qid, {}).get(cls, 0):
                kept[cls] = kept.get(cls, 0) + 1
                citations.append({"type": "wiki", "path": path, "context": "..."})
        if self.extra_key_on == qid and citations:
            citations[0]["stale"] = False
        return {"question": question, "citations": citations, "context_pages": context}


# Per question, how many cited paths of each class the stub returns.
KEEP = {
    "q-one": {"in-context": 1, "out-of-context": 1, "traversal": 1},
    "q-two": {"out-of-context": 2, "nonexistent": 2},
}
# Hand-computed from KEEP and R4 for the two small questions.
EXPECTED_SMALL = {
    "injected_in-context": 2,
    "injected_out-of-context": 4,
    "injected_nonexistent": 4,
    "injected_traversal": 2,
    "returned_in-context": 1,
    "returned_out-of-context": 3,
    "returned_nonexistent": 2,
    "returned_traversal": 1,
}


@pytest.fixture
def stub_wiki(monkeypatch):
    import kb.query.engine

    def install(**kwargs):
        stub = StubWiki(**kwargs)
        monkeypatch.setattr(kb.query.engine, "query_wiki", stub)
        return stub

    return install


# -- acceptance 1: the committed files [R1] [R2] ----------------------------------


def test_committed_files_load_with_the_minimum_counts(probe):
    pages = probe.load_pages(DATA / "pages.jsonl")
    questions = probe.load_questions(DATA / "questions.jsonl", pages)

    raw_pages = committed_rows("pages.jsonl")
    raw_questions = committed_rows("questions.jsonl")
    assert sorted(pages) == sorted(p["id"] for p in raw_pages)
    assert [q["id"] for q in questions] == [q["id"] for q in raw_questions]
    assert len(pages) >= 12
    topics = {p["topic"] for p in raw_pages}
    assert len(topics) >= 2
    assert len(questions) >= 5
    assert all(q["topic"] in topics for q in raw_questions)
    for p in raw_pages:
        assert p["title"].strip() and p["body"].strip(), p["id"]
    for q in raw_questions:
        assert q["question"].strip() and q["why"].strip(), q["id"]


# -- acceptance 2: one ValueError per cause of R2 for each file [R2] --------------

BAD_PAGE_LINES = {
    "not JSON": "{",
    "not an object": "[1, 2]",
    "lacks a field": dumps({k: v for k, v in SMALL_PAGES[0].items() if k != "body"}),
    "repeats an id": dumps(SMALL_PAGES[0]),
    "has an id outside concepts/": dumps(page("entities/crumb", "bread", "Crumb", "Crumb text.")),
    "has an id with a capital and a space": dumps(
        page("concepts/Crumb two", "bread", "Crumb", "Crumb text.")
    ),
    "has an id of the nonexistent form": dumps(
        page("concepts/missing-3", "bread", "Missing", "Missing text.")
    ),
    "has a topic that is not a slug": dumps(
        page("concepts/crumb", "Bread Baking", "Crumb", "Crumb text.")
    ),
    "has a title that is not a string": dumps(page("concepts/crumb", "bread", 7, "Crumb text.")),
    "has a body without a word": dumps(page("concepts/crumb", "bread", "Crumb", "... 123 !!")),
    "has an empty title": dumps(page("concepts/crumb", "bread", " ", "Crumb text.")),
}

BAD_QUESTION_LINES = {
    "not JSON": "not json",
    "not an object": '"just a string"',
    "lacks a field": dumps({k: v for k, v in SMALL_QUESTIONS[0].items() if k != "why"}),
    "repeats an id": dumps(SMALL_QUESTIONS[0]),
    "has an id that is not a slug": dumps({**SMALL_QUESTIONS[0], "id": "Q 3"}),
    "has a question without a word": dumps(
        {**SMALL_QUESTIONS[0], "id": "q-three", "question": "??? 42"}
    ),
    "has a topic of no page": dumps({**SMALL_QUESTIONS[0], "id": "q-three", "topic": "cooking"}),
    "has an empty why": dumps({**SMALL_QUESTIONS[0], "id": "q-three", "why": ""}),
    "has a question that is not a string": dumps(
        {**SMALL_QUESTIONS[0], "id": "q-three", "question": ["What", "is"]}
    ),
}


@pytest.mark.parametrize("cause", sorted(BAD_PAGE_LINES))
def test_a_bad_pages_line_raises_with_file_and_line(probe, runner, tmp_path, stub_wiki, cause):
    stub_wiki(keep=KEEP)
    data = small_data(tmp_path)
    write_lines(data / "pages.jsonl", [dumps(p) for p in SMALL_PAGES] + [BAD_PAGE_LINES[cause]])

    with pytest.raises(ValueError) as raised:
        probe.run(make_ctx(runner, tmp_path, data))

    assert "pages.jsonl" in str(raised.value)
    assert "line 6" in str(raised.value)


@pytest.mark.parametrize("cause", sorted(BAD_QUESTION_LINES))
def test_a_bad_questions_line_raises_with_file_and_line(probe, runner, tmp_path, stub_wiki, cause):
    stub_wiki(keep=KEEP)
    data = small_data(tmp_path)
    lines = [dumps(q) for q in SMALL_QUESTIONS] + [BAD_QUESTION_LINES[cause]]
    write_lines(data / "questions.jsonl", lines)

    with pytest.raises(ValueError) as raised:
        probe.run(make_ctx(runner, tmp_path, data))

    assert "questions.jsonl" in str(raised.value)
    assert "line 3" in str(raised.value)


# -- acceptance 3: the scripted answers and the counts [R3] [R4] [R6] -------------


def test_counts_equal_hand_computed_values(probe, runner, tmp_path, stub_wiki):
    stub_wiki(keep=KEEP)

    result = probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    arm = result["arms"]["scripted"]
    assert arm["status"] == "measured"
    assert arm["cases"] == 2
    assert arm["metrics"] == {**EXPECTED_SMALL, "citation_keys_uniform": 1}


def test_citation_keys_uniform_is_zero_when_one_citation_has_another_key_set(
    probe, runner, tmp_path, stub_wiki
):
    stub_wiki(keep=KEEP, extra_key_on="q-two")

    result = probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    assert result["arms"]["scripted"]["metrics"].get("citation_keys_uniform") == 0


def test_the_scripted_answer_holds_the_six_citations_of_r4(probe, runner, tmp_path, stub_wiki):
    stub = stub_wiki(keep=KEEP)

    probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    # Two calls per question, in order: the first answer cites nothing.
    assert [qid for qid, _ in stub.answers] == ["q-one", "q-one", "q-two", "q-two"]
    for qid, answer in stub.answers[0::2]:
        assert WIKILINK.findall(answer) == [], qid
    for qid, answer in stub.answers[1::2]:
        cited = WIKILINK.findall(answer)
        assert len(cited) == len(set(cited)) == 6, (qid, cited)
        classes = [classify(path, FIXED_CONTEXT, SMALL_IDS) for path in cited]
        counts = {cls: classes.count(cls) for cls in CLASSES}
        assert counts == {"in-context": 1, "out-of-context": 2, "nonexistent": 2, "traversal": 1}


def test_query_wiki_is_called_twice_per_question_on_a_wiki_under_tmp(
    probe, runner, tmp_path, stub_wiki
):
    stub = stub_wiki(keep=KEEP)
    ctx = make_ctx(runner, tmp_path, small_data(tmp_path))

    probe.run(ctx)

    questions = [q["question"] for q in SMALL_QUESTIONS]
    assert [asked for asked, _ in stub.calls] == [questions[0]] * 2 + [questions[1]] * 2
    wiki = stub.calls[0][1]
    assert all(seen == wiki for _, seen in stub.calls)
    assert wiki.is_relative_to(ctx.tmp)
    expected_files = {f"{p['id']}.md" for p in SMALL_PAGES}
    assert all(files == expected_files for files in stub.wiki_files)


def test_the_model_function_is_restored_after_the_run(probe, runner, tmp_path, stub_wiki):
    import kb.query.engine

    original = kb.query.engine.call_llm
    stub_wiki(keep=KEEP)

    probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    assert kb.query.engine.call_llm is original


# -- acceptance 4: one ValueError per cause of R5 ---------------------------------

R5_CONTEXTS = {
    "empty context": lambda qid, n: [] if qid == "q-two" else list(FIXED_CONTEXT),
    "context differs between the calls": lambda qid, n: (
        ["concepts/autolyse"] if qid == "q-two" and n == 1 else list(FIXED_CONTEXT)
    ),
    "fewer than two pages outside": lambda qid, n: (
        sorted(SMALL_IDS - {"concepts/tide-gauge"}) if qid == "q-two" else list(FIXED_CONTEXT)
    ),
}


@pytest.mark.parametrize("cause", sorted(R5_CONTEXTS))
def test_a_bad_context_raises_naming_the_question(probe, runner, tmp_path, stub_wiki, cause):
    import kb.query.engine

    original = kb.query.engine.call_llm
    stub_wiki(keep=KEEP, context_for=R5_CONTEXTS[cause])

    with pytest.raises(ValueError) as raised:
        probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    assert "q-two" in str(raised.value)
    assert kb.query.engine.call_llm is original


# -- acceptance 5: the committed set through the runner [R3] [R6] [R7] ------------


class ModelCalled(Exception):
    """Raised by a spy on a model function the probe must not reach."""


@pytest.fixture(scope="module")
def committed_run(tmp_path_factory):
    """Run the runner in-process on the committed set with the real query_wiki.

    Every model entry point other than the one the probe replaces records the call
    and raises, and `extract_citations` in `kb.query.engine` records each answer
    it is given before it runs, so the test sees what the model function returned.
    """
    import kb.query.engine
    import kb.query.rewriter
    import kb.utils.cli_backend
    import kb.utils.llm

    spec = importlib.util.spec_from_file_location(
        "kbeval_run_for_citations", REPO / "bench" / "knowledge" / "run.py"
    )
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    root = tmp_path_factory.mktemp("committed")
    for name in ("wiki", "raw"):
        (root / name).mkdir()
    other_calls: list[str] = []
    answers: list[str] = []
    real_extract = kb.query.engine.extract_citations

    def spy(name):
        def called(*args, **kwargs):
            other_calls.append(name)
            raise ModelCalled(name)

        return called

    def extract(text):
        answers.append(text)
        return real_extract(text)

    real_query_wiki = kb.query.engine.query_wiki
    out, err = io.StringIO(), io.StringIO()
    try:
        spec.loader.exec_module(runner)
        with pytest.MonkeyPatch.context() as mp:
            for module, name in (
                (kb.utils.llm, "call_llm"),
                (kb.utils.llm, "call_llm_json"),
                (kb.utils.llm, "get_client"),
                (kb.utils.llm, "_make_api_call"),
                (kb.utils.cli_backend, "call_cli"),
                (kb.query.rewriter, "call_llm"),
                (kb.query.engine, "_suggest_rephrasings"),
            ):
                mp.setattr(module, name, spy(f"{module.__name__}.{name}"))
            mp.setattr(kb.query.engine, "extract_citations", extract)
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = runner.main(
                    [
                        "--probe",
                        "citations",
                        "--probes-dir",
                        str(PROBE.parent),
                        "--wiki",
                        str(root / "wiki"),
                        "--raw",
                        str(root / "raw"),
                        "--out",
                        str(root / "out"),
                    ]
                )
            query_wiki_seen = kb.query.engine.query_wiki
    finally:
        sys.modules.pop(spec.name, None)
    record_path = root / "out" / "citations.json"
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else None
    return {
        "code": code,
        "output": out.getvalue() + err.getvalue(),
        "record": record,
        "other_calls": other_calls,
        "answers": answers,
        "real_query_wiki": query_wiki_seen is real_query_wiki,
    }


def test_committed_set_runs_through_the_runner(committed_run):
    cases = len(committed_rows("questions.jsonl"))
    assert committed_run["code"] == 0, committed_run["output"]
    assert "guarded directory changed:" not in committed_run["output"]
    record = committed_run["record"]
    assert record["invariants"] == ["I1"]
    arm = record["arms"]["scripted"]
    assert arm["status"] == "measured"
    assert arm["cases"] == cases
    metrics = arm["metrics"]
    assert metrics["injected_in-context"] == cases
    assert metrics["injected_out-of-context"] == 2 * cases
    assert metrics["injected_nonexistent"] == 2 * cases
    assert metrics["returned_traversal"] == 0
    for cls in CLASSES:
        assert f"returned_{cls}" in metrics
    assert metrics["citation_keys_uniform"] in (0, 1)


def test_only_the_replaced_model_function_is_called(committed_run):
    cases = len(committed_rows("questions.jsonl"))
    assert committed_run["real_query_wiki"]
    assert committed_run["other_calls"] == []
    answers = committed_run["answers"]
    # query_wiki passes each model answer to extract_citations once: two per question,
    # the first without a citation and the second with the scripted ones.
    assert len(answers) == 2 * cases
    assert all(WIKILINK.findall(a) == [] for a in answers[0::2])
    assert all(len(WIKILINK.findall(a)) == 6 and MISSING.search(a) for a in answers[1::2])
