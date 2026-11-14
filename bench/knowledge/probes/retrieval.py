"""Probe `retrieval`: recall@5 and nDCG@10 of `kb.query.engine.search_pages`.

Reads `pages.jsonl` and `queries.jsonl` from `ctx.data`, writes the pages as a
wiki under `ctx.tmp` and reports three arms:

- `bm25`: every query with `KB_DISABLE_VECTORS=1`, before any vector index exists.
- `tokenize`: the token count of `kb.query.bm25.tokenize` for each Chinese query.
- `hybrid`: every query with `KB_DISABLE_VECTORS` unset and `HF_HUB_OFFLINE=1`,
  after building the vector index of the temporary wiki. Unmeasured when the
  embedding model cannot be loaded, the index cannot be built, or the vector
  branch returns no hit for any query.

Spec: specs/kb-baseline.md (R4, recall@5 and nDCG@10 definitions); card
specs/tasks/T1-KBEVAL-RETRIEVAL.md.
"""

from __future__ import annotations

import json
import math
import os
import re
from contextlib import contextmanager
from pathlib import Path

GROUPS = ("en", "zh", "zh-to-en")
PAGE_FIELDS = ("id", "title", "lang", "role", "body")
QUERY_FIELDS = ("id", "group", "query", "relevant", "why")
PAGE_ID = re.compile(r"concepts/[a-z0-9]+(?:-[a-z0-9]+)*")
HAN = re.compile(r"[㐀-䶿一-鿿]")
ONLY_HAN = re.compile(r"[㐀-䶿一-鿿]+")
ASCII_LETTER = re.compile(r"[A-Za-z]")
# An English query word: Latin letters, with an inner hyphen or apostrophe.
EN_WORD = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
MAX_RESULTS = 10


def run(ctx) -> dict:
    pages = load_pages(Path(ctx.data) / "pages.jsonl")
    queries = load_queries(Path(ctx.data) / "queries.jsonl", pages)
    wiki = Path(ctx.tmp) / "wiki"
    write_wiki(wiki, pages)

    # search_pages runs its vector branch whenever the index file exists and does
    # not read KB_DISABLE_VECTORS, so the bm25 arm runs before the index is built.
    with environment({"KB_DISABLE_VECTORS": "1"}):
        bm25_arm = search_arm(queries, wiki)[0]
    arms = {"bm25": bm25_arm, "tokenize": tokenize_arm(queries)}
    with environment({"KB_DISABLE_VECTORS": None, "HF_HUB_OFFLINE": "1"}), hub_offline():
        arms["hybrid"] = hybrid_arm(ctx, queries, wiki)
    return {"invariants": ["I8"], "arms": arms}


# -- loading and checking the case set -------------------------------------------


def read_rows(path: Path) -> list[tuple[int, dict]]:
    """Return (line number, object) for each line; raise ValueError naming file and line."""
    rows = []
    for number, raw in enumerate(path.read_bytes().split(b"\n"), start=1):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path.name} line {number}: not UTF-8 ({exc.reason})") from None
        rows.append((number, text))
    # A final newline leaves one empty piece after the last line; it is not a line.
    if rows and rows[-1][1] == "":
        rows.pop()
    parsed = []
    for number, text in rows:
        try:
            row = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name} line {number}: not JSON ({exc.msg})") from None
        if not isinstance(row, dict):
            raise ValueError(f"{path.name} line {number}: not a JSON object")
        parsed.append((number, row))
    return parsed


def fail(path: Path, number: int, cause: str):
    raise ValueError(f"{path.name} line {number}: {cause}")


def require(path: Path, number: int, row: dict, fields: tuple[str, ...]) -> None:
    missing = [f for f in fields if f not in row]
    if missing:
        fail(path, number, f"lacks field {', '.join(missing)}")
    for field in fields:
        if field != "relevant" and (not isinstance(row[field], str) or not row[field].strip()):
            fail(path, number, f"field {field} is not a non-empty string")


def load_pages(path: Path) -> dict[str, dict]:
    pages: dict[str, dict] = {}
    for number, row in read_rows(path):
        require(path, number, row, PAGE_FIELDS)
        pid = row["id"]
        if not PAGE_ID.fullmatch(pid):
            fail(path, number, f"id {pid!r} is not concepts/<slug>")
        if pid in pages:
            fail(path, number, f"repeats id {pid}")
        if row["role"] not in ("target", "distractor"):
            fail(path, number, f"role {row['role']!r} is not target or distractor")
        text = row["title"] + "\n" + row["body"]
        if row["lang"] == "zh":
            if not HAN.search(row["title"]) or not HAN.search(row["body"]):
                fail(path, number, "lang zh page without Chinese characters in title and body")
            if ASCII_LETTER.search(text):
                fail(path, number, "lang zh page holds Latin letters")
        elif row["lang"] == "en":
            if HAN.search(text):
                fail(path, number, "lang en page holds Chinese characters")
        else:
            fail(path, number, f"lang {row['lang']!r} is not en or zh")
        pages[pid] = row
    return pages


def has_word(word: str, body: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", body) is not None


def load_queries(path: Path, pages: dict[str, dict]) -> list[dict]:
    rows = read_rows(path)
    queries: dict[str, tuple[int, dict]] = {}
    for number, row in rows:
        require(path, number, row, QUERY_FIELDS)
        qid, query, relevant = row["id"], row["query"], row["relevant"]
        if qid in queries:
            fail(path, number, f"repeats id {qid}")
        if not isinstance(relevant, list) or not relevant:
            fail(path, number, "relevant is not a non-empty list")
        for pid in relevant:
            if not isinstance(pid, str) or pages.get(pid, {}).get("role") != "target":
                fail(path, number, f"relevant id {pid!r} is not a target page")
        if len(set(relevant)) != len(relevant):
            fail(path, number, "relevant repeats a page id")
        group = row["group"]
        bodies = [pages[pid]["body"] for pid in relevant]
        langs = {pages[pid]["lang"] for pid in relevant}
        if group == "en":
            words = query.split(" ")
            if not all(EN_WORD.fullmatch(word) for word in words):
                fail(path, number, "en query is not English words separated by single spaces")
            if not 2 <= len(words) <= 6:
                fail(path, number, f"en query has {len(words)} words, not 2 to 6")
            if langs != {"en"}:
                fail(path, number, "en query names a relevant page that is not English")
            for word in words:
                if not all(has_word(word.lower(), body.lower()) for body in bodies):
                    fail(path, number, f"en query word {word!r} is not in every relevant body")
        elif group == "zh":
            if not ONLY_HAN.fullmatch(query) or not 2 <= len(query) <= 8:
                fail(path, number, "zh query is not 2 to 8 Chinese characters")
            if langs != {"zh"}:
                fail(path, number, "zh query names a relevant page that is not Chinese")
            if not all(query in body for body in bodies):
                fail(path, number, "zh query does not occur in every relevant body")
        elif group == "zh-to-en":
            if not ONLY_HAN.fullmatch(query):
                fail(path, number, "zh-to-en query is not in Chinese characters")
            if not isinstance(row.get("translates"), str):
                fail(path, number, "zh-to-en row lacks field translates")
        else:
            fail(path, number, f"group {group!r} is not one of {', '.join(GROUPS)}")
        queries[qid] = (number, row)
    # A zh-to-en row may name an en row that comes later in the file.
    for qid, (number, row) in queries.items():
        if row["group"] != "zh-to-en":
            continue
        source = queries.get(row["translates"], (0, {}))[1]
        if source.get("group") != "en":
            fail(path, number, f"translates {row['translates']!r}, which is not an en row")
        if source["relevant"] != row["relevant"]:
            fail(path, number, "relevant differs from the relevant of the en row it translates")
    return [row for _, row in queries.values()]


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


# -- environment ---------------------------------------------------------------------


@contextmanager
def environment(values: dict[str, str | None]):
    """Set (or, for None, unset) environment variables and restore the earlier values."""
    earlier = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in earlier.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@contextmanager
def hub_offline():
    """Make an already imported huggingface_hub offline too.

    huggingface_hub reads HF_HUB_OFFLINE once, when it is imported, and kb imports
    it through model2vec; setting the variable later changes nothing on its own.
    """
    try:
        from huggingface_hub import constants
    except ImportError:
        yield
        return
    earlier = constants.HF_HUB_OFFLINE
    constants.HF_HUB_OFFLINE = True
    try:
        yield
    finally:
        constants.HF_HUB_OFFLINE = earlier


# -- arms ------------------------------------------------------------------------------


def search_arm(queries: list[dict], wiki: Path) -> tuple[dict, int]:
    """Return the measured arm and the number of vector-branch hits over all queries."""
    from kb.query import engine

    per_group: dict[str, list[tuple[float, float, bool]]] = {g: [] for g in GROUPS}
    vector_hits = 0
    for row in queries:
        telemetry: dict = {}
        results = engine.search_pages(row["query"], wiki, MAX_RESULTS, search_telemetry=telemetry)
        vector_hits += int(telemetry.get("vector_hits", 0))
        ranked = [r["id"] for r in results]
        relevant = set(row["relevant"])
        per_group[row["group"]].append(
            (recall_at(ranked, relevant, 5), ndcg_at(ranked, relevant, 10), not ranked)
        )
    metrics: dict[str, float] = {}
    for group, scores in per_group.items():
        metrics[f"queries_{group}"] = len(scores)
        if scores:
            metrics[f"recall5_{group}"] = sum(s[0] for s in scores) / len(scores)
            metrics[f"ndcg10_{group}"] = sum(s[1] for s in scores) / len(scores)
            metrics[f"zero_result_{group}"] = sum(s[2] for s in scores)
    arm = {"status": "measured", "cases": len(queries), "metrics": metrics}
    return arm, vector_hits


def recall_at(ranked: list[str], relevant: set[str], k: int) -> float:
    return len(relevant & set(ranked[:k])) / len(relevant)


def ndcg_at(ranked: list[str], relevant: set[str], k: int) -> float:
    """Binary gain, log2 discount; a page id counts once at its first rank."""
    seen: set[str] = set()
    dcg = 0.0
    for rank, pid in enumerate(ranked[:k], start=1):
        if pid in relevant and pid not in seen:
            seen.add(pid)
            dcg += 1 / math.log2(rank + 1)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(len(relevant), k) + 1))
    return dcg / ideal


def tokenize_arm(queries: list[dict]) -> dict:
    from kb.query import bm25

    counts = {
        row["id"]: len(bm25.tokenize(row["query"]))
        for row in queries
        if row["group"] in ("zh", "zh-to-en")
    }
    metrics: dict[str, float] = {f"tokens_{qid}": n for qid, n in counts.items()}
    metrics["zh_queries"] = len(counts)
    metrics["zh_zero_token"] = sum(n == 0 for n in counts.values())
    metrics["zh_single_token"] = sum(n == 1 for n in counts.values())
    if counts:
        metrics["zh_mean_tokens"] = sum(counts.values()) / len(counts)
    return {"status": "measured", "cases": len(counts), "metrics": metrics}


def hybrid_arm(ctx, queries: list[dict], wiki: Path) -> dict:
    from kb.query import embeddings

    try:
        embeddings.embed_texts(["probe"])
    except Exception as exc:  # any load failure means the arm cannot run
        return ctx.unmeasured(f"embedding model could not be loaded: {describe(exc)}")
    try:
        built = embeddings.rebuild_vector_index(wiki, force=True)
    except Exception as exc:
        return ctx.unmeasured(f"vector index could not be built: {describe(exc)}")
    if not built:
        return ctx.unmeasured("vector index was not built: model2vec or sqlite-vec unavailable")
    try:
        arm, vector_hits = search_arm(queries, wiki)
    finally:
        close_index(embeddings, wiki)
    if vector_hits == 0:
        return ctx.unmeasured("vector branch returned no hit for any query")
    return arm


def close_index(embeddings, wiki: Path) -> None:
    """Close the cached index connection so the temporary directory can be removed."""
    evict = getattr(embeddings, "_evict_vector_index_cache_entry", None)
    vec_path = getattr(embeddings, "_vec_db_path", None)
    if evict and vec_path:
        evict(vec_path(wiki))


def describe(exc: BaseException) -> str:
    text = str(exc).strip().splitlines()
    return f"{type(exc).__name__}: {text[0]}" if text else type(exc).__name__
