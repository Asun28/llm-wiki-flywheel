"""Probe `rebuild`: what a second ingest, the ingest order and the changed-source scan do.

Reads `sources.jsonl` (one `{"path": "articles/<name>.md", "text": ...}` per line)
and `extractions.json` (each `path` mapped to a finished extraction) from
`ctx.data`. Each case below gets its own directory under `ctx.tmp` holding
`raw/articles/` with the sources, `wiki/` and `.data/hashes.json`. Every source
is ingested with
`kb.ingest.pipeline.ingest_source(path, "article", extraction, wiki_dir=...,
raw_dir=..., _skip_vector_rebuild=True)`, so no model is called; the vector
index rebuild is skipped because it loads an embedding model and writes outside
the wiki. While the probe runs, `kb.compile.compiler.HASH_MANIFEST` points at
the case's manifest, so the manifest writes of ingest stay under `ctx.tmp`.

Arms:

- `idempotence`: ingest in `path` order, hash every file under the wiki,
  ingest again in the same order and count the files added, removed or with
  another sha256 (`files_changed_by_second`), and those of them in a
  subdirectory of the wiki (`page_files_changed_by_second`).
- `order`: three wikis, ingested in `path` order, in reverse `path` order and
  in ascending order of the sha256 of `path`. For `reverse` and `hashed`
  against `path` order: `page_set_equal_<pair>` over the files in
  subdirectories, and of the pages in both, those whose bytes differ and those
  whose non-empty lines differ as multisets.
- `scan`: after one ingest, `find_changed_sources(raw_dir, manifest,
  save_hashes=False)` with nothing changed (`listed_clean`), then with other
  model ids in the three `CLAUDE_*_MODEL` variables, with a line appended to
  `article.yaml` in the temporary project root, and with a line appended to one
  source. Each `sees_*` metric is 1 when the call lists a source. Each change
  is undone before the next. Unmeasured when the clean call lists a source.

It judges no count.

Spec: specs/kb-baseline.md (R8); card specs/tasks/T1-KBEVAL-REBUILD.md.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple

CHECKOUT = Path(__file__).resolve().parents[3]
SOURCE_FIELDS = ("path", "text")
SOURCE_PATH = re.compile(r"articles/[a-z0-9]+(?:-[a-z0-9]+)*\.md")
# The string fields `ingest_source` renders into the summary page.
STRING_FIELDS = (
    "author",
    "speaker",
    "core_argument",
    "abstract",
    "description",
    "problem_solved",
    "name",
)
LIST_FIELDS = ("entities_mentioned", "concepts_mentioned")
OPTIONAL_LIST_FIELDS = ("key_claims",)
MODEL_VARS = ("CLAUDE_SCAN_MODEL", "CLAUDE_WRITE_MODEL", "CLAUDE_ORCHESTRATE_MODEL")
APPENDED_LINE = b"# line appended by the kbeval rebuild probe\n"


def run(ctx) -> dict:
    data = Path(ctx.data)
    sources = load_sources(data / "sources.jsonl")
    extractions = load_extractions(data / "extractions.json", sources)
    tmp = Path(ctx.tmp)
    return {
        "invariants": ["I3", "I4"],
        "arms": {
            "idempotence": idempotence_arm(tmp, sources, extractions),
            "order": order_arm(tmp, sources, extractions),
            "scan": scan_arm(ctx, tmp, sources, extractions),
        },
    }


# -- loading and checking the input files ------------------------------------------


def fail(path: Path, where: str, cause: str):
    raise ValueError(f"{path.name} {where}: {cause}")


def load_sources(path: Path) -> dict[str, str]:
    """Return {path: text} in file order; raise ValueError naming the file and line."""
    sources: dict[str, str] = {}
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            where = f"line {number}"
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                fail(path, where, f"not JSON ({exc.msg})")
            if not isinstance(row, dict):
                fail(path, where, "not a JSON object")
            missing = [f for f in SOURCE_FIELDS if f not in row]
            if missing:
                fail(path, where, f"lacks field {', '.join(missing)}")
            for field in SOURCE_FIELDS:
                if not isinstance(row[field], str) or not row[field].strip():
                    fail(path, where, f"field {field} is not a non-empty string")
            if not SOURCE_PATH.fullmatch(row["path"]):
                fail(path, where, f"path {row['path']!r} is not articles/<name>.md")
            if row["path"] in sources:
                fail(path, where, f"repeats path {row['path']}")
            sources[row["path"]] = row["text"]
    return sources


def load_extractions(path: Path, sources: dict[str, str]) -> dict[str, dict]:
    """Return {path: extraction}; raise ValueError naming the file and the line or path."""
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except json.JSONDecodeError as exc:
        fail(path, f"line {exc.lineno}", f"not JSON ({exc.msg})")
    if not isinstance(raw, dict):
        fail(path, "top level", "not a JSON object")
    for source in sources:
        if source not in raw:
            fail(path, f"path {source}", "no extraction for this source")
    for key, value in raw.items():
        where = f"path {key}"
        if key not in sources:
            fail(path, where, "the extraction names no source in sources.jsonl")
        if not isinstance(value, dict):
            fail(path, where, "the extraction is not a JSON object")
        title = value.get("title")
        if not isinstance(title, str) or not title.strip():
            fail(path, where, "title is not a non-empty string")
        for field in STRING_FIELDS:
            if field in value and not isinstance(value[field], str):
                fail(path, where, f"{field} is not a string")
        for field in LIST_FIELDS + OPTIONAL_LIST_FIELDS:
            if field not in value:
                if field in LIST_FIELDS:
                    fail(path, where, f"lacks {field}")
                continue
            items = value[field]
            if not isinstance(items, list) or not all(
                isinstance(item, str) and item.strip() for item in items
            ):
                fail(path, where, f"{field} is not a list of non-empty strings")
    return raw


# -- cases and ingest ----------------------------------------------------------------


class Case(NamedTuple):
    raw: Path
    wiki: Path
    manifest: Path


def make_case(tmp: Path, name: str, sources: dict[str, str]) -> Case:
    """Write the sources and an empty wiki with the page subdirectories ingest expects."""
    from kb.config import WIKI_SUBDIR_TO_TYPE

    base = tmp / name
    raw = base / "raw"
    for path, text in sources.items():
        target = raw / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    wiki = base / "wiki"
    for subdir in WIKI_SUBDIR_TO_TYPE:
        (wiki / subdir).mkdir(parents=True)
    return Case(raw=raw, wiki=wiki, manifest=base / ".data" / "hashes.json")


@contextmanager
def manifest_at(path: Path):
    """Point the manifest `ingest_source` reads and writes at `path`."""
    from kb.compile import compiler

    original = compiler.HASH_MANIFEST
    compiler.HASH_MANIFEST = path
    try:
        yield
    finally:
        compiler.HASH_MANIFEST = original


def ingest(case: Case, order: list[str], extractions: dict[str, dict]) -> None:
    from kb.ingest import pipeline

    with manifest_at(case.manifest):
        for path in order:
            pipeline.ingest_source(
                case.raw / path,
                "article",
                copy.deepcopy(extractions[path]),
                wiki_dir=case.wiki,
                raw_dir=case.raw,
                _skip_vector_rebuild=True,
            )


def file_hashes(wiki: Path) -> dict[str, str]:
    """Map each file under the wiki (relative POSIX path) to the sha256 of its bytes."""
    return {
        p.relative_to(wiki).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in wiki.rglob("*")
        if p.is_file()
    }


def is_page(relative: str) -> bool:
    return "/" in relative


# -- the arms ------------------------------------------------------------------------


def idempotence_arm(tmp: Path, sources: dict[str, str], extractions: dict[str, dict]) -> dict:
    order = sorted(sources)
    case = make_case(tmp, "idempotence", sources)
    ingest(case, order, extractions)
    first = file_hashes(case.wiki)
    ingest(case, order, extractions)
    second = file_hashes(case.wiki)
    changed = [p for p in sorted(set(first) | set(second)) if first.get(p) != second.get(p)]
    return {
        "status": "measured",
        "cases": len(sources),
        "metrics": {
            "files_after_first": len(first),
            "files_changed_by_second": len(changed),
            "page_files_changed_by_second": sum(is_page(p) for p in changed),
        },
    }


def pages(wiki: Path) -> dict[str, bytes]:
    return {
        p.relative_to(wiki).as_posix(): p.read_bytes()
        for p in wiki.rglob("*")
        if p.is_file() and is_page(p.relative_to(wiki).as_posix())
    }


def non_empty_lines(data: bytes) -> Counter:
    return Counter(line for line in data.decode("utf-8").splitlines() if line.strip())


def order_arm(tmp: Path, sources: dict[str, str], extractions: dict[str, dict]) -> dict:
    orders = {
        "path": sorted(sources),
        "reverse": sorted(sources, reverse=True),
        "hashed": sorted(sources, key=lambda p: hashlib.sha256(p.encode("utf-8")).hexdigest()),
    }
    built: dict[str, dict[str, bytes]] = {}
    for name, order in orders.items():
        case = make_case(tmp, f"order-{name}", sources)
        ingest(case, order, extractions)
        built[name] = pages(case.wiki)
    base = built["path"]
    metrics: dict[str, int] = {}
    for pair in ("reverse", "hashed"):
        other = built[pair]
        both = sorted(set(base) & set(other))
        metrics[f"page_set_equal_{pair}"] = int(set(base) == set(other))
        metrics[f"pages_differing_bytes_{pair}"] = sum(base[p] != other[p] for p in both)
        metrics[f"pages_differing_lines_{pair}"] = sum(
            non_empty_lines(base[p]) != non_empty_lines(other[p]) for p in both
        )
    return {"status": "measured", "cases": len(sources), "metrics": metrics}


@contextmanager
def environment(values: dict[str, str]):
    earlier = {name: os.environ.get(name) for name in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for name, value in earlier.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@contextmanager
def appended_line(path: Path):
    original = path.read_bytes()
    try:
        path.write_bytes(original + APPENDED_LINE)
        yield
    finally:
        path.write_bytes(original)


def template_to_edit() -> Path:
    """Return `article.yaml` of the temporary project root; refuse any other copy."""
    from kb.compile import compiler

    template = (Path(compiler.TEMPLATES_DIR) / "article.yaml").resolve()
    root = os.environ.get("KB_PROJECT_ROOT")
    inside_root = root is not None and template.is_relative_to(Path(root).resolve())
    if not inside_root or template.is_relative_to(CHECKOUT):
        raise ValueError(
            f"{template} (article.yaml) is not in the temporary project root "
            f"KB_PROJECT_ROOT={root!r}; the probe edits only that copy"
        )
    return template


def other_model_ids() -> dict[str, str]:
    ids = {}
    for name in MODEL_VARS:
        value = f"kbeval-other-{name.lower()}"
        if os.environ.get(name) == value:
            value += "-2"
        ids[name] = value
    return ids


def scan_arm(ctx, tmp: Path, sources: dict[str, str], extractions: dict[str, dict]) -> dict:
    from kb.compile import compiler

    order = sorted(sources)
    case = make_case(tmp, "scan", sources)
    ingest(case, order, extractions)

    def listed() -> int:
        new, changed = compiler.find_changed_sources(case.raw, case.manifest, save_hashes=False)
        return len({Path(p) for p in new} | {Path(p) for p in changed})

    clean = listed()
    if clean:
        return ctx.unmeasured(
            f"listed_clean={clean}: find_changed_sources listed {clean} source(s) "
            "with nothing changed since the ingest"
        )
    template = template_to_edit()
    with environment(other_model_ids()):
        model = listed()
    with appended_line(template):
        template_seen = listed()
    with appended_line(case.raw / order[0]):
        source_seen = listed()
    return {
        "status": "measured",
        "cases": len(sources),
        "metrics": {
            "listed_clean": clean,
            "sees_model_change": int(model > 0),
            "sees_template_change": int(template_seen > 0),
            "sees_source_change": int(source_seen > 0),
        },
    }
