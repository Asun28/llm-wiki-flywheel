"""Probe `citations`: which citations of a scripted answer `query_wiki` returns.

Reads `pages.jsonl` and `questions.jsonl` from `ctx.data` and writes the pages as
a wiki under `ctx.tmp`. For each question it calls
`kb.query.engine.query_wiki(question, wiki_dir)` twice, with the model call of
`kb.query.engine` (`call_llm`) replaced by a function that makes no network
request:

1. the replacement returns an answer with no citation; the result gives the
   `context_pages` of the question;
2. the replacement returns the scripted answer, which cites in the `[[page id]]`
   form one page of `context_pages` (`in-context`), two wiki pages outside it
   (`out-of-context`), `concepts/missing-1` and `concepts/missing-2`, which are
   no page (`nonexistent`), and `../` followed by the in-context page id
   (`traversal`).

The arm `scripted` reports, for each class, `injected_<class>` and
`returned_<class>` (the injected citations of that class whose path is in the
result's `citations`), and `citation_keys_uniform` (1 when every returned
citation has the same key set, else 0). It judges no count.

Spec: specs/kb-baseline.md (R6); card specs/tasks/T1-KBEVAL-CITATIONS.md.
"""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from pathlib import Path

CLASSES = ("in-context", "out-of-context", "nonexistent", "traversal")
PAGE_FIELDS = ("id", "topic", "title", "body")
QUESTION_FIELDS = ("id", "topic", "question", "why")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
PAGE_ID = re.compile(r"concepts/[a-z0-9]+(?:-[a-z0-9]+)*")
MISSING_ID = re.compile(r"concepts/missing-[0-9]+")
WORD = re.compile(r"[A-Za-z]{2,}")
NONEXISTENT = ("concepts/missing-1", "concepts/missing-2")
PLAIN_ANSWER = "The wiki pages in the context describe this."


def run(ctx) -> dict:
    pages = load_pages(Path(ctx.data) / "pages.jsonl")
    questions = load_questions(Path(ctx.data) / "questions.jsonl", pages)
    wiki = Path(ctx.tmp) / "wiki"
    write_wiki(wiki, pages)
    return {"invariants": ["I1"], "arms": {"scripted": scripted_arm(questions, pages, wiki)}}


# -- loading and checking the input files ------------------------------------------


def fail(path: Path, number: int, cause: str):
    raise ValueError(f"{path.name} line {number}: {cause}")


def read_rows(path: Path, fields: tuple[str, ...]) -> list[tuple[int, dict]]:
    """Return (line number, object) per line; each field must be a non-empty string."""
    rows = []
    seen: set[str] = set()
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                fail(path, number, f"not JSON ({exc.msg})")
            if not isinstance(row, dict):
                fail(path, number, "not a JSON object")
            missing = [f for f in fields if f not in row]
            if missing:
                fail(path, number, f"lacks field {', '.join(missing)}")
            for field in fields:
                if not isinstance(row[field], str) or not row[field].strip():
                    fail(path, number, f"field {field} is not a non-empty string")
            if row["id"] in seen:
                fail(path, number, f"repeats id {row['id']}")
            if not SLUG.fullmatch(row["topic"]):
                fail(path, number, f"topic {row['topic']!r} is not a lower-case slug")
            seen.add(row["id"])
            rows.append((number, row))
    return rows


def load_pages(path: Path) -> dict[str, dict]:
    pages: dict[str, dict] = {}
    for number, row in read_rows(path, PAGE_FIELDS):
        pid = row["id"]
        if not PAGE_ID.fullmatch(pid):
            fail(path, number, f"id {pid!r} is not concepts/<slug>")
        if MISSING_ID.fullmatch(pid):
            fail(path, number, f"id {pid!r} has the form kept for nonexistent pages")
        for field in ("title", "body"):
            if not WORD.search(row[field]):
                fail(path, number, f"field {field} holds no word")
        pages[pid] = row
    return pages


def load_questions(path: Path, pages: dict[str, dict]) -> list[dict]:
    topics = {row["topic"] for row in pages.values()}
    questions = []
    for number, row in read_rows(path, QUESTION_FIELDS):
        if not SLUG.fullmatch(row["id"]):
            fail(path, number, f"id {row['id']!r} is not a lower-case slug")
        if not WORD.search(row["question"]):
            fail(path, number, "field question holds no word")
        if row["topic"] not in topics:
            fail(path, number, f"topic {row['topic']!r} is the topic of no page")
        questions.append(row)
    return questions


# -- the temporary wiki ------------------------------------------------------------


def write_wiki(wiki: Path, pages: dict[str, dict]) -> None:
    """Write each page with the frontmatter template of CLAUDE.md and `type: concept`."""
    for pid, row in pages.items():
        slug = pid.split("/", 1)[1]
        path = wiki / f"{pid}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = (
            "---\n"
            f"title: {json.dumps(row['title'], ensure_ascii=False)}\n"
            "source:\n"
            f'  - "raw/articles/{slug}.md"\n'
            "created: 2026-01-01\n"
            "updated: 2026-01-01\n"
            "type: concept\n"
            "confidence: stated\n"
            "---\n"
            "\n"
            f"{row['body']}\n"
        )
        path.write_bytes(text.encode("utf-8"))


# -- the replaced model function -----------------------------------------------------


class ScriptedModel:
    """Stands in for `kb.query.engine.call_llm`; returns the answer set before each call."""

    def __init__(self):
        self.answer = PLAIN_ANSWER

    def __call__(self, prompt, *, tier="write", system="", max_tokens=4096):
        return self.answer


@contextmanager
def scripted_model():
    from kb.query import engine

    model = ScriptedModel()
    original = engine.call_llm
    engine.call_llm = model
    try:
        yield model
    finally:
        engine.call_llm = original


# -- the arm ---------------------------------------------------------------------------


def scripted_citations(context: list[str], pages: dict[str, dict]) -> dict[str, list[str]]:
    outside = sorted(pid for pid in pages if pid not in context)
    return {
        "in-context": [context[0]],
        "out-of-context": outside[:2],
        "nonexistent": list(NONEXISTENT),
        "traversal": [f"../{context[0]}"],
    }


def scripted_answer(cited: dict[str, list[str]]) -> str:
    inside, (out1, out2), (none1, none2), traversal = (cited[cls] for cls in CLASSES)
    return (
        f"The answer is stated in [[{inside[0]}]]. "
        f"Related pages are [[{out1}]] and [[{out2}]]. "
        f"Further detail is in [[{none1}]] and [[{none2}]]. "
        f"The source page is [[{traversal[0]}]]."
    )


def scripted_arm(questions: list[dict], pages: dict[str, dict], wiki: Path) -> dict:
    from kb.query import engine

    injected = dict.fromkeys(CLASSES, 0)
    returned = dict.fromkeys(CLASSES, 0)
    key_sets: set[frozenset] = set()
    with scripted_model() as model:
        for row in questions:
            model.answer = PLAIN_ANSWER
            first = engine.query_wiki(row["question"], wiki)
            context = list(first["context_pages"])
            if not context:
                raise ValueError(f"question {row['id']}: context_pages is empty")
            if sum(pid not in context for pid in pages) < 2:
                raise ValueError(
                    f"question {row['id']}: fewer than two pages lie outside context_pages"
                )
            cited = scripted_citations(context, pages)
            model.answer = scripted_answer(cited)
            second = engine.query_wiki(row["question"], wiki)
            if list(second["context_pages"]) != context:
                raise ValueError(f"question {row['id']}: context_pages differs between the calls")
            paths = {citation["path"] for citation in second["citations"]}
            key_sets.update(frozenset(citation) for citation in second["citations"])
            for cls in CLASSES:
                injected[cls] += len(cited[cls])
                returned[cls] += sum(path in paths for path in cited[cls])
    metrics: dict[str, float] = {}
    for cls in CLASSES:
        metrics[f"injected_{cls}"] = injected[cls]
        metrics[f"returned_{cls}"] = returned[cls]
    metrics["citation_keys_uniform"] = int(len(key_sets) <= 1)
    return {"status": "measured", "cases": len(questions), "metrics": metrics}
