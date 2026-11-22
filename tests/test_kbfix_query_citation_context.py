"""T0-KBFIX-CITECTX (#189): `query_wiki` returns only citations that were in the prompt.

`query_wiki` returned every `[[page]]` the answer named after a path-shape filter, so a
page outside the prompt context, or one that does not exist, came back in `citations`.
Now a citation is returned only when its id is in `context_pages` (wiki) or entered the
prompt through the raw-source fallback (raw). Every other citation is returned in
`rejected_citations` with a reason. These tests stub only the model call
(`kb.query.engine.call_llm`); search, context building and citation extraction run for real.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _page(title: str, body: str, page_type: str = "concept") -> bytes:
    return (
        "---\n"
        f'title: "{title}"\n'
        "source:\n"
        '  - "raw/articles/source.md"\n'
        "created: 2026-11-23\n"
        "updated: 2026-11-23\n"
        f"type: {page_type}\n"
        "confidence: stated\n"
        "---\n"
        "\n"
        f"{body}\n"
    ).encode()


class _Model:
    """Stands in for `kb.query.engine.call_llm`; records prompts, returns `answer`."""

    def __init__(self) -> None:
        self.answer = ""
        self.prompts: list[str] = []

    def __call__(self, prompt, *args, **kwargs):
        self.prompts.append(prompt)
        return self.answer


@pytest.fixture
def model(tmp_kb_env: Path, monkeypatch: pytest.MonkeyPatch) -> _Model:
    monkeypatch.setenv("KB_DISABLE_VECTORS", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    stub = _Model()
    monkeypatch.setattr("kb.query.engine.call_llm", stub)
    return stub


@pytest.fixture
def concept_wiki(tmp_kb_env: Path) -> Path:
    wiki = tmp_kb_env / "wiki"
    (wiki / "concepts").mkdir(parents=True, exist_ok=True)
    (wiki / "concepts" / "hydration.md").write_bytes(
        _page("Hydration", "Hydration attaches state to server-rendered HTML.")
    )
    (wiki / "concepts" / "tokenizer.md").write_bytes(
        _page("Tokenizer", "A tokenizer splits text into subword units.")
    )
    (wiki / "concepts" / "quantization.md").write_bytes(
        _page("Quantization", "Quantization stores weights with fewer bits.")
    )
    return wiki


def _paths(entries: list[dict]) -> list[str]:
    return [entry["path"] for entry in entries]


def test_only_in_context_citations_are_returned(model, concept_wiki):
    from kb.query.engine import query_wiki

    model.answer = (
        "Hydration attaches state [[concepts/hydration]]. "
        "See also [[concepts/tokenizer]] and [[concepts/missing-page]]."
    )
    result = query_wiki("What is hydration?")

    assert result["context_pages"] == ["concepts/hydration"]
    assert result["answer"] == model.answer
    assert _paths(result["citations"]) == ["concepts/hydration"]
    assert set(result["citations"][0]) == {"type", "path", "context"}
    rejected = {entry["path"]: entry["reason"] for entry in result["rejected_citations"]}
    assert rejected == {
        "concepts/tokenizer": "out_of_context",
        "concepts/missing-page": "nonexistent",
    }
    for entry in result["rejected_citations"]:
        assert entry["type"] == "wiki"
        assert entry["context"]


def test_citation_id_comparison_ignores_case(model, concept_wiki):
    from kb.query.engine import query_wiki

    model.answer = "Hydration attaches state [[Concepts/Hydration]]."
    result = query_wiki("What is hydration?")

    assert result["context_pages"] == ["concepts/hydration"]
    assert _paths(result["citations"]) == ["Concepts/Hydration"]
    assert result["rejected_citations"] == []


def test_raw_citation_accepted_only_when_it_entered_the_prompt(model, tmp_kb_env):
    from kb.query.engine import query_wiki

    wiki = tmp_kb_env / "wiki"
    (wiki / "summaries").mkdir(parents=True, exist_ok=True)
    (wiki / "summaries" / "hydration-summary.md").write_bytes(
        _page("Hydration summary", "Summary of hydration in rendering.", page_type="summary")
    )
    articles = tmp_kb_env / "raw" / "articles"
    articles.mkdir(parents=True, exist_ok=True)
    (articles / "hydration.md").write_bytes(b"# Hydration\nHydration attaches state to HTML.\n")
    (articles / "tokenizer.md").write_bytes(b"# Tokenizer\nA tokenizer splits text.\n")

    model.answer = (
        "Hydration attaches state [ref: raw/articles/hydration.md]. "
        "Unrelated [ref: raw/articles/tokenizer.md]."
    )
    result = query_wiki("What is hydration?")

    assert result["context_pages"] == ["summaries/hydration-summary"]
    prompt = model.prompts[0]
    assert "--- Raw Source: raw/articles/hydration.md (verbatim) ---" in prompt
    assert "raw/articles/tokenizer.md" not in prompt
    assert "raw/articles/hydration.md" in _paths(result["citations"])
    rejected = {entry["path"]: entry["reason"] for entry in result["rejected_citations"]}
    assert rejected == {"raw/articles/tokenizer.md": "out_of_context"}
    assert result["rejected_citations"][0]["type"] == "raw"


def test_no_match_path_has_empty_rejected_citations(model, tmp_kb_env):
    from kb.query.engine import query_wiki

    result = query_wiki("What is hydration?")

    assert result["citations"] == []
    assert result["rejected_citations"] == []
    assert model.prompts == []


# -- R3 decision 1 regressions --------------------------------------------------------


@pytest.fixture
def summary_wiki_with_raw(tmp_kb_env: Path) -> Path:
    """A summary-only wiki, so the raw fallback fires, and two raw articles."""
    wiki = tmp_kb_env / "wiki"
    (wiki / "summaries").mkdir(parents=True, exist_ok=True)
    (wiki / "summaries" / "hydration-summary.md").write_bytes(
        _page("Hydration summary", "Summary of hydration in rendering.", page_type="summary")
    )
    articles = tmp_kb_env / "raw" / "articles"
    articles.mkdir(parents=True, exist_ok=True)
    (articles / "hydration.md").write_bytes(b"# Hydration\nHydration attaches state to HTML.\n")
    (articles / "tokenizer.md").write_bytes(b"# Tokenizer\nA tokenizer splits text.\n")
    return wiki


def test_raw_form_citation_of_a_wiki_page_is_not_accepted(model, concept_wiki):
    """R3 F1: `[ref: <wiki id>]` is a raw citation and must not pass on the wiki allowance."""
    from kb.query.engine import query_wiki

    model.answer = "Hydration [[concepts/hydration]] and [ref: concepts/hydration]."
    result = query_wiki("What is hydration?")

    assert result["context_pages"] == ["concepts/hydration"]
    assert [(c["type"], c["path"]) for c in result["citations"]] == [("wiki", "concepts/hydration")]
    assert [(c["type"], c["path"], c["reason"]) for c in result["rejected_citations"]] == [
        ("raw", "concepts/hydration", "nonexistent")
    ]


@pytest.mark.parametrize(
    ("extra", "accepted"),
    [
        pytest.param(
            1 - len("--- Raw Source: raw/articles/hydration.md (verbatim) ---\n"),
            False,
            id="one-char",
        ),
        pytest.param(0, False, id="header-only"),
        pytest.param(10, True, id="header-plus-content"),
    ],
)
def test_truncated_raw_section_counts_only_with_header_and_content(
    model, summary_wiki_with_raw, monkeypatch, extra, accepted
):
    """R3 F2: a raw id counts as in the prompt only when its header and some content fit."""
    from kb.query import engine

    header_len = len("--- Raw Source: raw/articles/hydration.md (verbatim) ---\n")
    budget = header_len + extra
    real_build = engine._build_query_context

    def _padded(pages, max_chars=engine.QUERY_CONTEXT_MAX_CHARS):
        ctx = real_build(pages, max_chars=max_chars)
        fill = (
            engine.QUERY_CONTEXT_MAX_CHARS - engine._FENCE_OVERHEAD - budget - len(ctx["context"])
        )
        ctx["context"] += "x" * fill
        return ctx

    monkeypatch.setattr(engine, "_build_query_context", _padded)
    model.answer = "Hydration attaches state [ref: raw/articles/hydration.md]."
    result = engine.query_wiki("What is hydration?")

    assert result["context_pages"] == ["summaries/hydration-summary"]
    if accepted:
        assert _paths(result["citations"]) == ["raw/articles/hydration.md"]
        assert result["rejected_citations"] == []
    else:
        assert result["citations"] == []
        assert [(c["path"], c["reason"]) for c in result["rejected_citations"]] == [
            ("raw/articles/hydration.md", "out_of_context")
        ]


def test_upper_case_raw_prefix_is_probed_under_the_raw_dir(model, summary_wiki_with_raw):
    """R3 F3: `RAW/...` names an existing raw file, so the reason is out_of_context."""
    from kb.query.engine import query_wiki

    model.answer = "Unrelated [ref: RAW/articles/tokenizer.md]."
    result = query_wiki("What is hydration?")

    assert result["citations"] == []
    assert [(c["type"], c["path"], c["reason"]) for c in result["rejected_citations"]] == [
        ("raw", "RAW/articles/tokenizer.md", "out_of_context")
    ]


# -- R3 decision 2 regressions --------------------------------------------------------


@pytest.fixture
def case_sensitive_stat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make `Path.stat` case-sensitive under `tmp_path`, as on Linux.

    `exists`, `is_file` and `is_dir` all call `Path.stat`, so on Windows a name that
    differs from the file on disk only in case is not found, as on a case-sensitive
    filesystem.
    """
    import os

    real_stat = Path.stat
    root = tmp_path.resolve()

    def _stat(self, *args, **kwargs):
        resolved = Path(os.path.abspath(self))
        if resolved != root and resolved.is_relative_to(root):
            current = root
            for part in resolved.relative_to(root).parts:
                if part not in os.listdir(current):
                    raise FileNotFoundError(2, "No such file or directory", str(self))
                current = current / part
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _stat)


def test_case_sensitive_stat_fixture_hides_a_case_variant(tmp_path, case_sensitive_stat):
    (tmp_path / "Hydration.md").write_bytes(b"x\n")

    assert (tmp_path / "Hydration.md").is_file()
    assert not (tmp_path / "hydration.md").is_file()


def test_wiki_reason_finds_a_mixed_case_file_name(tmp_path, case_sensitive_stat):
    """R3 F1: id `concepts/hydration` names `concepts/Hydration.md` (`page_id` lower-cases)."""
    from kb.query.citations import partition_citations

    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "wiki" / "concepts" / "Hydration.md").write_bytes(b"# Hydration\n")
    (tmp_path / "raw").mkdir()
    cite = {"type": "wiki", "path": "concepts/hydration", "context": "x"}

    accepted, rejected = partition_citations(
        [cite], wiki_ids=[], raw_ids=[], wiki_dir=tmp_path / "wiki", raw_dir=tmp_path / "raw"
    )

    assert accepted == []
    assert rejected == [{**cite, "reason": "out_of_context"}]


def test_raw_reason_ignores_case_beyond_the_prefix(tmp_path, case_sensitive_stat):
    """R3 F2: `raw/articles/HYDRATION.md` names the existing `raw/articles/hydration.md`."""
    from kb.query.citations import partition_citations

    (tmp_path / "raw" / "articles").mkdir(parents=True)
    (tmp_path / "raw" / "articles" / "hydration.md").write_bytes(b"# Hydration\n")
    (tmp_path / "wiki").mkdir()
    found = {"type": "raw", "path": "raw/Articles/HYDRATION.md", "context": "x"}
    missing = {"type": "raw", "path": "raw/articles/absent.md", "context": "y"}

    accepted, rejected = partition_citations(
        [found, missing],
        wiki_ids=[],
        raw_ids=[],
        wiki_dir=tmp_path / "wiki",
        raw_dir=tmp_path / "raw",
    )

    assert accepted == []
    assert [(c["path"], c["reason"]) for c in rejected] == [
        ("raw/Articles/HYDRATION.md", "out_of_context"),
        ("raw/articles/absent.md", "nonexistent"),
    ]


def test_stat_error_on_a_cited_name_rejects_it_and_keeps_the_answer(
    model, concept_wiki, monkeypatch
):
    """R3 F3: an OSError from the existence probe (ENAMETOOLONG) must not abort the query."""
    import errno

    from kb.query.engine import query_wiki

    long_name = "a" * 300
    real_stat = Path.stat

    def _stat(self, *args, **kwargs):
        # What Linux raises for a 300-byte file name component.
        if long_name in self.name:
            raise OSError(errno.ENAMETOOLONG, "File name too long", str(self))
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _stat)
    model.answer = f"Hydration [[concepts/hydration]] and [[concepts/{long_name}]]."
    result = query_wiki("What is hydration?")

    assert result["answer"] == model.answer
    assert _paths(result["citations"]) == ["concepts/hydration"]
    assert [(c["path"], c["reason"]) for c in result["rejected_citations"]] == [
        (f"concepts/{long_name}", "nonexistent")
    ]


# -- R3 decision 3 regression ---------------------------------------------------------


def _filesystem_is_case_sensitive(directory: Path) -> bool:
    probe = directory / "case_probe"
    probe.write_bytes(b"")
    try:
        return not (directory / "CASE_PROBE").exists()
    finally:
        probe.unlink()


def test_raw_reason_checks_every_case_variant_directory(tmp_path):
    """R3 decision 3: `raw/articles/` (exact case, empty) and `raw/ARTICLES/` (empty) must
    not hide `raw/Articles/hydration.md` from the citation `raw/articles/hydration.md`."""
    if not _filesystem_is_case_sensitive(tmp_path):
        pytest.skip("needs a case-sensitive filesystem to hold directories differing in case")
    from kb.query.citations import partition_citations

    for name in ("articles", "ARTICLES", "Articles"):
        (tmp_path / "raw" / name).mkdir(parents=True)
    (tmp_path / "raw" / "Articles" / "hydration.md").write_bytes(b"# Hydration\n")
    (tmp_path / "wiki").mkdir()
    cite = {"type": "raw", "path": "raw/articles/hydration.md", "context": "x"}

    accepted, rejected = partition_citations(
        [cite], wiki_ids=[], raw_ids=[], wiki_dir=tmp_path / "wiki", raw_dir=tmp_path / "raw"
    )

    assert accepted == []
    assert rejected == [{**cite, "reason": "out_of_context"}]
