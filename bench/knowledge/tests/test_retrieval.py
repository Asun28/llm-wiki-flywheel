"""Acceptance tests 1-7 of card T1-KBEVAL-RETRIEVAL for `bench/knowledge/probes/retrieval.py`."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

import pytest
from conftest import REPO, Bench

PROBE = REPO / "bench" / "knowledge" / "probes" / "retrieval.py"
DATA = REPO / "bench" / "knowledge" / "data" / "retrieval"
GROUPS = ("en", "zh", "zh-to-en")
HAN = re.compile(r"^[㐀-䶿一-鿿]+$")
ASCII_LETTER = re.compile(r"[A-Za-z]")


# -- helpers ---------------------------------------------------------------------


@pytest.fixture
def probe():
    name = "kbeval_probe_retrieval_under_test"
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


def page(pid, lang, role, title, body):
    return {"id": pid, "title": title, "lang": lang, "role": role, "body": body}


SMALL_PAGES = [
    page("concepts/alpha", "en", "target", "Alpha", "Alpha beta gamma."),
    page("concepts/jia", "zh", "target", "甲", "甲乙丙丁。"),
    page("concepts/yi", "zh", "target", "乙", "乙丙戊己。"),
    page("concepts/noise", "en", "distractor", "Noise", "Unrelated text."),
]
SMALL_QUERIES = [
    {
        "id": "q-en",
        "group": "en",
        "query": "alpha beta",
        "relevant": ["concepts/alpha"],
        "why": "concepts/alpha body says 'Alpha beta gamma'",
    },
    {
        "id": "q-zh",
        "group": "zh",
        "query": "乙丙",
        "relevant": ["concepts/jia", "concepts/yi"],
        "why": "both bodies hold '乙丙'",
    },
    {
        "id": "q-x",
        "group": "zh-to-en",
        "query": "阿尔法贝塔",
        "relevant": ["concepts/alpha"],
        "translates": "q-en",
        "why": "translates q-en",
    },
]
# Fixed result lists the stub returns, keyed by query.
SMALL_RESULTS = {
    "alpha beta": ["concepts/noise", "concepts/alpha"],
    "乙丙": [
        "concepts/jia",
        "concepts/f1",
        "concepts/f2",
        "concepts/f3",
        "concepts/f4",
        "concepts/yi",
    ],
    "阿尔法贝塔": [],
}


def small_data(tmp_path: Path, pages=None, queries=None) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    write_lines(data / "pages.jsonl", [dumps(p) for p in (pages or SMALL_PAGES)])
    write_lines(data / "queries.jsonl", [dumps(q) for q in (queries or SMALL_QUERIES)])
    return data


class Calls:
    """What the stubs saw: one entry per call with the environment at that moment."""

    def __init__(self):
        self.search: list[dict] = []
        self.load: list[dict] = []
        self.build: list[dict] = []


def env_now() -> dict:
    from huggingface_hub import constants

    seen = {k: os.environ.get(k) for k in ("KB_DISABLE_VECTORS", "HF_HUB_OFFLINE")}
    seen["hub_offline"] = constants.HF_HUB_OFFLINE
    return seen


@pytest.fixture
def calls():
    return Calls()


@pytest.fixture
def fake_search(monkeypatch, calls):
    """Replace search_pages with fixed result lists; the vector branch reports one hit."""
    import kb.query.engine

    def install(results: dict[str, list[str]], vector_hits: int = 1):
        def search_pages(question, wiki_dir=None, max_results=10, *, search_telemetry=None):
            calls.search.append(
                {"query": question, "wiki_dir": wiki_dir, "max": max_results, **env_now()}
            )
            search_telemetry["vector_hits"] = search_telemetry.get("vector_hits", 0) + vector_hits
            return [{"id": pid, "score": 1.0} for pid in results[question]]

        monkeypatch.setattr(kb.query.engine, "search_pages", search_pages)

    return install


@pytest.fixture
def fake_vectors(monkeypatch, calls):
    """Replace the model load and the index build; each succeeds unless told to raise."""
    import kb.query.embeddings

    def install(load_error=None, build_error=None, built=True):
        def embed_texts(texts):
            calls.load.append(env_now())
            if load_error:
                raise load_error
            return [[0.0, 1.0] for _ in texts]

        def rebuild_vector_index(wiki_dir, force=False):
            calls.build.append(env_now())
            if build_error:
                raise build_error
            return built

        monkeypatch.setattr(kb.query.embeddings, "embed_texts", embed_texts)
        monkeypatch.setattr(kb.query.embeddings, "rebuild_vector_index", rebuild_vector_index)

    return install


def committed_rows(name: str) -> list[dict]:
    lines = (DATA / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


# -- acceptance 1: the committed files [R1] [R2] ----------------------------------


def test_committed_pages_meet_the_minimum_counts_and_language_rules():
    pages = committed_rows("pages.jsonl")
    ids = [p["id"] for p in pages]
    assert len(ids) == len(set(ids))
    for p in pages:
        assert set(p) >= {"id", "title", "lang", "role", "body"}
        assert re.fullmatch(r"concepts/[a-z0-9-]+", p["id"])
        if p["lang"] == "zh":
            text = p["title"] + p["body"]
            assert re.search(r"[一-鿿]", text) and not ASCII_LETTER.search(text), p["id"]
    en_targets = [p for p in pages if p["lang"] == "en" and p["role"] == "target"]
    zh_targets = [p for p in pages if p["lang"] == "zh" and p["role"] == "target"]
    distractors = [p for p in pages if p["role"] == "distractor"]
    assert len(en_targets) >= 8
    assert len(zh_targets) >= 8
    assert len(distractors) >= 8
    assert sum(p["lang"] == "zh" for p in distractors) * 2 >= len(distractors)


def test_committed_queries_meet_the_minimum_counts_and_group_rules():
    pages = {p["id"]: p for p in committed_rows("pages.jsonl")}
    queries = committed_rows("queries.jsonl")
    by_id = {q["id"]: q for q in queries}
    assert len(by_id) == len(queries)
    for group in GROUPS:
        assert sum(q["group"] == group for q in queries) >= 8, group
    for q in queries:
        assert q["why"].strip() and q["relevant"], q["id"]
        assert all(pages[r]["role"] == "target" for r in q["relevant"]), q["id"]
        if q["group"] == "en":
            words = q["query"].split()
            assert 2 <= len(words) <= 6, q["id"]
            for r in q["relevant"]:
                body = pages[r]["body"].lower()
                assert all(re.search(rf"\b{re.escape(w.lower())}\b", body) for w in words), q["id"]
        elif q["group"] == "zh":
            assert HAN.match(q["query"]) and 2 <= len(q["query"]) <= 8, q["id"]
        else:
            assert HAN.match(q["query"]), q["id"]
            source = by_id[q["translates"]]
            assert source["group"] == "en" and source["relevant"] == q["relevant"], q["id"]


def test_each_zh_query_is_a_substring_of_its_relevant_page_body():
    pages = {p["id"]: p for p in committed_rows("pages.jsonl")}
    for q in committed_rows("queries.jsonl"):
        if q["group"] == "zh":
            for r in q["relevant"]:
                assert pages[r]["lang"] == "zh"
                assert q["query"] in pages[r]["body"], q["id"]


# -- acceptance 2: one ValueError per cause of R3 [R3] -----------------------------

BAD_PAGE_LINES = {
    "not an object": "[1, 2]",
    "lacks a field": dumps({k: v for k, v in SMALL_PAGES[0].items() if k != "body"}),
    "repeats an id": dumps(SMALL_PAGES[0]),
    "breaks the lang rule": dumps(
        page("concepts/kai", "zh", "target", "开", "Plain English text.")
    ),
    "breaks the role rule": dumps(page("concepts/beta", "en", "background", "Beta", "Beta text.")),
    "has an unknown lang": dumps(page("concepts/beta", "fr", "target", "Beta", "Beta text.")),
    "has an id outside concepts/": dumps(
        page("entities/beta", "en", "target", "Beta", "Beta text.")
    ),
    "has an id with a capital and a space": dumps(
        page("concepts/Beta two", "en", "target", "Beta", "Beta text.")
    ),
}

BAD_QUERY_LINES = {
    "not an object": '"just a string"',
    "lacks a field": dumps({k: v for k, v in SMALL_QUERIES[0].items() if k != "why"}),
    "repeats an id": dumps(SMALL_QUERIES[0]),
    "names a relevant id that is not a target": dumps(
        {**SMALL_QUERIES[0], "id": "q-bad", "relevant": ["concepts/noise"]}
    ),
    "names a relevant id that is no page": dumps(
        {**SMALL_QUERIES[0], "id": "q-bad", "relevant": ["concepts/missing"]}
    ),
    "has an unknown group": dumps({**SMALL_QUERIES[0], "id": "q-bad", "group": "fr"}),
    "en word missing from the body": dumps(
        {**SMALL_QUERIES[0], "id": "q-bad", "query": "alpha delta"}
    ),
    "en query of seven words": dumps(
        {**SMALL_QUERIES[0], "id": "q-bad", "query": "alpha beta gamma alpha beta gamma alpha"}
    ),
    "zh query not in the body": dumps({**SMALL_QUERIES[1], "id": "q-bad", "query": "庚辛"}),
    "zh query not in Chinese": dumps({**SMALL_QUERIES[1], "id": "q-bad", "query": "alpha"}),
    "zh-to-en query not in Chinese": dumps(
        {**SMALL_QUERIES[2], "id": "q-bad", "query": "alpha beta"}
    ),
    "zh-to-en relevant differs from its en row": dumps(
        {**SMALL_QUERIES[2], "id": "q-bad", "relevant": ["concepts/jia"]}
    ),
}


@pytest.mark.parametrize("cause", sorted(BAD_PAGE_LINES))
def test_a_bad_pages_line_raises_with_file_and_line(probe, runner, tmp_path, cause):
    data = small_data(tmp_path)
    lines = [dumps(p) for p in SMALL_PAGES] + [BAD_PAGE_LINES[cause]]
    write_lines(data / "pages.jsonl", lines)

    with pytest.raises(ValueError) as raised:
        probe.run(make_ctx(runner, tmp_path, data))

    assert "pages.jsonl" in str(raised.value)
    assert "line 5" in str(raised.value)


@pytest.mark.parametrize("cause", sorted(BAD_QUERY_LINES))
def test_a_bad_queries_line_raises_with_file_and_line(probe, runner, tmp_path, cause):
    data = small_data(tmp_path)
    lines = [dumps(q) for q in SMALL_QUERIES] + [BAD_QUERY_LINES[cause]]
    write_lines(data / "queries.jsonl", lines)

    with pytest.raises(ValueError) as raised:
        probe.run(make_ctx(runner, tmp_path, data))

    assert "queries.jsonl" in str(raised.value)
    assert "line 4" in str(raised.value)


def test_a_line_that_is_not_utf8_raises_with_file_and_line(probe, runner, tmp_path):
    data = small_data(tmp_path)
    good = "\n".join(dumps(p) for p in SMALL_PAGES).encode("utf-8")
    (data / "pages.jsonl").write_bytes(good + b'\n{"id": "\xff"}\n')

    with pytest.raises(ValueError, match=r"pages\.jsonl.*line 5"):
        probe.run(make_ctx(runner, tmp_path, data))


# Extra target pages for the rules that compare a query with every relevant body.
# concepts/delta also holds a number run and a punctuation run, so a query made of
# them would pass a body check and must be stopped by the English word-form check.
EXTRA_PAGES = [
    page("concepts/delta", "en", "target", "Delta", "Gamma delta 123 456 ... --- !!"),
    page("concepts/bing", "zh", "target", "丙", "丙丁。"),
]

BAD_QUERY_LINES_EXTRA = {
    "en query whose words are split across relevant bodies": {
        **SMALL_QUERIES[0],
        "id": "q-bad",
        "query": "alpha delta",
        "relevant": ["concepts/alpha", "concepts/delta"],
    },
    "zh query missing from one relevant body": {
        **SMALL_QUERIES[1],
        "id": "q-bad",
        "query": "甲乙",
        "relevant": ["concepts/jia", "concepts/bing"],
    },
    "en query of numbers only": {
        **SMALL_QUERIES[0],
        "id": "q-bad",
        "query": "123 456",
        "relevant": ["concepts/delta"],
    },
    "en query of punctuation only": {
        **SMALL_QUERIES[0],
        "id": "q-bad",
        "query": "... ---",
        "relevant": ["concepts/delta"],
    },
    "en query with a number word": {
        **SMALL_QUERIES[0],
        "id": "q-bad",
        "query": "delta 123",
        "relevant": ["concepts/delta"],
    },
}


@pytest.mark.parametrize("cause", sorted(BAD_QUERY_LINES_EXTRA))
def test_a_query_that_breaks_its_group_rule_raises_with_file_and_line(
    probe, runner, tmp_path, cause
):
    data = small_data(tmp_path, pages=SMALL_PAGES + EXTRA_PAGES)
    lines = [dumps(q) for q in SMALL_QUERIES] + [dumps(BAD_QUERY_LINES_EXTRA[cause])]
    write_lines(data / "queries.jsonl", lines)

    with pytest.raises(ValueError) as raised:
        probe.run(make_ctx(runner, tmp_path, data))

    assert "queries.jsonl" in str(raised.value)
    assert "line 4" in str(raised.value)


# -- acceptance 3: metrics against hand-computed values [R7] ----------------------

# en: one relevant page at rank 2 -> recall@5 1, nDCG@10 = 1/log2(3).
# zh: two relevant pages at ranks 1 and 6 -> recall@5 1/2,
#     nDCG@10 = (1 + 1/log2(7)) / (1 + 1/log2(3)).
# zh-to-en: empty result list -> recall@5 0, nDCG@10 0, one zero-result query.
EXPECTED_SMALL = {
    "queries_en": 1,
    "recall5_en": 1.0,
    "ndcg10_en": 0.6309297535714575,
    "zero_result_en": 0,
    "queries_zh": 1,
    "recall5_zh": 0.5,
    "ndcg10_zh": 0.8315546295836225,
    "zero_result_zh": 0,
    "queries_zh-to-en": 1,
    "recall5_zh-to-en": 0.0,
    "ndcg10_zh-to-en": 0.0,
    "zero_result_zh-to-en": 1,
}


def test_search_arms_report_recall_ndcg_and_zero_results(
    probe, runner, tmp_path, fake_search, fake_vectors
):
    fake_search(SMALL_RESULTS)
    fake_vectors()

    result = probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    for arm in ("bm25", "hybrid"):
        assert result["arms"][arm]["status"] == "measured"
        assert result["arms"][arm]["cases"] == 3
        assert result["arms"][arm]["metrics"] == pytest.approx(EXPECTED_SMALL), arm


def test_each_query_is_searched_once_per_arm_in_a_wiki_under_tmp(
    probe, runner, tmp_path, calls, fake_search, fake_vectors
):
    fake_search(SMALL_RESULTS)
    fake_vectors()
    ctx = make_ctx(runner, tmp_path, small_data(tmp_path))

    probe.run(ctx)

    seen = sorted((c["query"], c["max"]) for c in calls.search)
    assert seen == sorted([(q, 10) for q in SMALL_RESULTS] * 2)
    wiki = Path(calls.search[0]["wiki_dir"])
    assert wiki.is_relative_to(ctx.tmp)


def test_pages_are_written_as_concept_pages_under_tmp(probe, runner, tmp_path, fake_vectors):
    fake_vectors()
    seen = {}

    import kb.query.engine

    def search_pages(question, wiki_dir=None, max_results=10, *, search_telemetry=None):
        path = Path(wiki_dir) / "concepts" / "jia.md"
        seen.setdefault("text", path.read_text(encoding="utf-8"))
        search_telemetry["vector_hits"] = 1
        return []

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(kb.query.engine, "search_pages", search_pages)
        probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    text = seen.get("text", "")
    assert text.startswith("---\n")
    assert 'title: "甲"' in text
    assert "type: concept" in text
    assert text.rstrip().endswith("甲乙丙丁。")


# -- acceptance 4: KB_DISABLE_VECTORS during and after the bm25 arm [R5] ----------


@pytest.mark.parametrize("earlier", ["0", None])
def test_bm25_arm_sets_disable_vectors_and_restores_it(
    probe, runner, tmp_path, monkeypatch, calls, fake_search, fake_vectors, earlier
):
    if earlier is None:
        monkeypatch.delenv("KB_DISABLE_VECTORS", raising=False)
    else:
        monkeypatch.setenv("KB_DISABLE_VECTORS", earlier)
    fake_search(SMALL_RESULTS)
    # The hybrid arm stops at the model load, so every search call is the bm25 arm's.
    fake_vectors(load_error=OSError("no model files"))

    probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    assert calls.search
    assert {c["KB_DISABLE_VECTORS"] for c in calls.search} == {"1"}
    assert os.environ.get("KB_DISABLE_VECTORS") == earlier


# -- acceptance 5: the hybrid arm is unmeasured with the cause [R6] ---------------

HYBRID_FAILURES = {
    "model load raises": (
        {"load_error": OSError("no model files")},
        1,
        ("embedding model", "no model files"),
    ),
    "index build raises": (
        {"build_error": sqlite3.OperationalError("disk full")},
        1,
        ("vector index", "disk full"),
    ),
    "index build skipped": ({"built": False}, 1, ("vector index",)),
    "vector branch returns no hit": ({}, 0, ("no hit",)),
}


@pytest.mark.parametrize("cause", sorted(HYBRID_FAILURES))
def test_hybrid_arm_is_unmeasured_with_the_cause(
    probe, runner, tmp_path, monkeypatch, calls, fake_search, fake_vectors, cause
):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.setenv("KB_DISABLE_VECTORS", "1")
    vectors, hits, words = HYBRID_FAILURES[cause]
    fake_search(SMALL_RESULTS, vector_hits=hits)
    fake_vectors(**vectors)

    result = probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    hybrid = result["arms"]["hybrid"]
    assert hybrid["status"] == "unmeasured"
    for word in words:
        assert word in hybrid["reason"]
    during = calls.load + calls.build + calls.search[len(SMALL_RESULTS) :]
    assert during and all(c["HF_HUB_OFFLINE"] == "1" for c in during)
    assert all(c["KB_DISABLE_VECTORS"] is None for c in during)
    assert os.environ.get("HF_HUB_OFFLINE") is None
    assert os.environ.get("KB_DISABLE_VECTORS") == "1"


class ArmStopped(BaseException):
    """Raised by a stub to stop the hybrid arm with an exception the probe does not catch."""


@pytest.mark.parametrize("ending", ["returns", "raises"])
def test_hybrid_arm_makes_imported_hub_offline_and_restores_it(
    probe, runner, tmp_path, monkeypatch, calls, fake_search, fake_vectors, ending
):
    from huggingface_hub import constants

    # huggingface_hub reads HF_HUB_OFFLINE at import, so this is the value it acts on.
    monkeypatch.setattr(constants, "HF_HUB_OFFLINE", False)
    fake_search(SMALL_RESULTS)
    if ending == "raises":
        fake_vectors(load_error=ArmStopped())
        with pytest.raises(ArmStopped):
            probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))
    else:
        fake_vectors()
        probe.run(make_ctx(runner, tmp_path, small_data(tmp_path)))

    assert [c["hub_offline"] for c in calls.load] == [True]
    assert constants.HF_HUB_OFFLINE is False


# -- acceptance 6 and 7: the committed set through the runner [R4] [R8] [R9] ------


@pytest.fixture(scope="module")
def committed_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("committed")
    dirs = {name: root / name for name in ("wiki", "raw")}
    for path in dirs.values():
        path.mkdir()
    bench = Bench(root=root, probes=PROBE.parent, out=root / "out", **dirs)
    proc = bench.run("--probe", "retrieval")
    record_path = bench.out / "retrieval.json"
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else None
    return proc, record


def expected_token_metrics(rows: list[dict]) -> dict:
    """The tokenize arm as R8 defines it, computed here from kb.query.bm25.tokenize."""
    from kb.query.bm25 import tokenize

    counts = {q["id"]: len(tokenize(q["query"])) for q in rows if q["group"] != "en"}
    metrics = {f"tokens_{qid}": n for qid, n in counts.items()}
    metrics["zh_queries"] = len(counts)
    metrics["zh_zero_token"] = sum(n == 0 for n in counts.values())
    metrics["zh_single_token"] = sum(n == 1 for n in counts.values())
    metrics["zh_mean_tokens"] = sum(counts.values()) / len(counts)
    return metrics


def test_tokenize_arm_counts_tokens_per_chinese_row(committed_run):
    _, record = committed_run
    arm = record["arms"]["tokenize"]
    assert arm["status"] == "measured"
    assert arm["metrics"] == pytest.approx(expected_token_metrics(committed_rows("queries.jsonl")))


def test_tokenize_arm_counts_a_one_character_query_as_zero_tokens(
    probe, runner, tmp_path, fake_search, fake_vectors
):
    # tokenize keeps runs of two or more word characters, so one Chinese
    # character gives 0 tokens and the committed rows (all 1 token) do not
    # tell a real count from a constant.
    single = {**SMALL_QUERIES[2], "id": "q-one", "query": "阿"}
    queries = SMALL_QUERIES + [single]
    fake_search({**SMALL_RESULTS, "阿": []})
    fake_vectors()

    result = probe.run(make_ctx(runner, tmp_path, small_data(tmp_path, queries=queries)))

    assert result["arms"]["tokenize"]["metrics"] == pytest.approx(expected_token_metrics(queries))


def test_committed_set_runs_through_the_runner(committed_run):
    proc, record = committed_run
    queries = committed_rows("queries.jsonl")
    assert proc.returncode == 0, proc.output
    assert "guarded directory changed:" not in proc.output
    assert record["invariants"] == ["I8"]
    bm25 = record["arms"]["bm25"]
    assert bm25["status"] == "measured"
    assert bm25["cases"] == len(queries)
    for group in GROUPS:
        assert {f"recall5_{group}", f"ndcg10_{group}"} <= set(bm25["metrics"])
    hybrid = record["arms"]["hybrid"]
    if hybrid["status"] == "measured":
        assert hybrid["cases"] == len(queries)
    else:
        assert hybrid["status"] == "unmeasured" and hybrid["reason"].strip()
