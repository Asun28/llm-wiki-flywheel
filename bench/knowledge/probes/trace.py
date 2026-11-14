"""Probe `trace`: lexical containment of wiki sentences in their listed sources.

Arm `containment` reads every `*.md` file in a subdirectory of `ctx.wiki` as a page
(id `<subdirectory>/<stem>`), resolves each `source:` ref `raw/<rest>` to
`ctx.raw/<rest>`, splits the page body into sentences and reports, per sentence,
the share of its word 5-grams (character 8-grams when it holds no ASCII letter)
that occur in one of the page's text sources, in three bands: high (at least 0.8),
mid (at least 0.2) and low. It also writes `trace-sample.jsonl` under `ctx.out`:
two sentences from each of up to 30 pages, chosen by sha256, for labelling.

Arm `templates` counts the `*.yaml` files under the checkout's `templates/` (or
`ctx.templates` when the context has one) and those whose `extract` field names
hold `quote`, `span`, `offset` or `char_`.

The probe only reads `ctx.wiki`, `ctx.raw` and the templates; it writes only
`ctx.out / "trace-sample.jsonl"`. It calls no `kb` function. A ref that is a URL or
that does not resolve inside `ctx.raw` by its path alone gets no file-system call.

Two readings of the card fixed here:
- A sentence includes its end mark.
- Removed text (a fenced block, a heading, a table row, the Evidence Trail) ends
  the piece before it, so every sentence is one contiguous span of the page file
  and `start`/`end` in the sample cut it out exactly.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
import stat
from pathlib import Path

import yaml

CHECKOUT = Path(__file__).resolve().parents[3]
SAMPLE = "trace-sample.jsonl"
SAMPLE_PAGES = 30
SAMPLE_PER_PAGE = 2
TEXT_SUFFIXES = (".md", ".txt", ".vtt")
REF_KINDS = ("text", "undecodable", "non_text", "missing", "url", "outside")
CLAIM_SPAN_PARTS = ("quote", "span", "offset", "char_")
WORD_N = 5
CHAR_N = 8

FENCE = re.compile(r" {0,3}(`{3,}|~{3,})")
HEADING = re.compile(r" {0,3}#{1,6}(?:\s|$)")
SENTENCE_END = re.compile(r"[.!?](?=\s|\Z)|[。！？]")
ASCII_LETTER = re.compile(r"[A-Za-z]")
WORD = re.compile(r"\w+")
FIELD_NAME = re.compile(r"\s*([A-Za-z_][\w-]*)")


class FrontmatterError(ValueError):
    """The page opens a frontmatter block that does not parse to a mapping."""


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_frontmatter(text: str) -> tuple[dict, int]:
    """Return the frontmatter mapping and the offset where the body starts.

    A page whose first line is not `---` has no frontmatter. An opened block with no
    closing `---` line, a YAML error or a value that is not a mapping raises.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, 0
    offset = len(lines[0])
    for line in lines[1:]:
        if line.strip() == "---":
            block = text[len(lines[0]) : offset]
            try:
                meta = yaml.safe_load(block)
            except yaml.YAMLError as exc:
                raise FrontmatterError(f"frontmatter is not YAML: {exc}") from None
            if meta is None:
                meta = {}
            if not isinstance(meta, dict):
                raise FrontmatterError("frontmatter is not a mapping")
            return meta, offset + len(line)
        offset += len(line)
    raise FrontmatterError("frontmatter block is not closed")


def kept_runs(text: str, start: int) -> list[tuple[int, int]]:
    """Return the (start, end) spans of body lines that are not removed text."""
    runs: list[tuple[int, int]] = []
    run_start = None
    fence = None  # (character, length) of the open fence
    in_trail = False
    offset = start
    for line in text[start:].splitlines(keepends=True):
        content = line.rstrip("\r\n")
        opener = FENCE.match(content)
        if fence is not None:
            keep = False
            if opener and content.strip() == opener.group(1):
                mark = opener.group(1)
                if mark[0] == fence[0] and len(mark) >= fence[1]:
                    fence = None
        elif opener:
            fence = (opener.group(1)[0], len(opener.group(1)))
            keep = False
        elif in_trail and not content.startswith("## "):
            keep = False
        elif content.rstrip() == "## Evidence Trail":
            in_trail = True
            keep = False
        else:
            in_trail = False
            keep = not HEADING.match(content) and not content.lstrip().startswith("|")
        if keep and run_start is None:
            run_start = offset
        elif not keep and run_start is not None:
            runs.append((run_start, offset))
            run_start = None
        offset += len(line)
    if run_start is not None:
        runs.append((run_start, offset))
    return runs


def page_sentences(text: str) -> list[dict]:
    """Return the body sentences of a page file's text with offsets into that text."""
    _, body_start = split_frontmatter(text)
    sentences: list[dict] = []
    for run_start, run_end in kept_runs(text, body_start):
        run = text[run_start:run_end]
        cuts = [m.end() for m in SENTENCE_END.finditer(run)]
        piece_start = 0
        for cut in [*cuts, len(run)]:
            piece = run[piece_start:cut]
            stripped = piece.strip()
            if stripped:
                begin = run_start + piece_start + len(piece) - len(piece.lstrip())
                sentences.append(
                    {
                        "index": len(sentences),
                        "start": begin,
                        "end": begin + len(stripped),
                        "text": stripped,
                    }
                )
            piece_start = cut
    return sentences


def is_short(sentence: str) -> bool:
    return len(sentence) < (20 if ASCII_LETTER.search(sentence) else 8)


def word_grams(text: str) -> list[tuple[str, ...]]:
    words = WORD.findall(text.lower())
    return [tuple(words[i : i + WORD_N]) for i in range(len(words) - WORD_N + 1)]


class Source:
    """One text source: its text and, built on first use, its word 5-gram set."""

    def __init__(self, text: str) -> None:
        self.text = text
        self._grams: set[tuple[str, ...]] | None = None

    @property
    def grams(self) -> set[tuple[str, ...]]:
        if self._grams is None:
            self._grams = set(word_grams(self.text))
        return self._grams


def containment_in(sentence: str, sources: list[Source]) -> float | None:
    """Share of the sentence's n-grams found in one of the sources; None if it has none."""
    if ASCII_LETTER.search(sentence):
        grams = word_grams(sentence)
        found = sum(any(g in s.grams for s in sources) for g in grams)
    else:
        grams = [sentence[i : i + CHAR_N] for i in range(len(sentence) - CHAR_N + 1)]
        found = sum(any(g in s.text for s in sources) for g in grams)
    if not grams:
        return None
    return found / len(grams)


def containment(sentence: str, source_texts: list[str]) -> float | None:
    """Containment of a sentence in a list of source texts, each searched on its own."""
    return containment_in(sentence, [Source(t) for t in source_texts])


def band(value: float) -> str:
    if value >= 0.8:
        return "high"
    if value >= 0.2:
        return "mid"
    return "low"


def page_refs(meta: dict) -> list:
    value = meta.get("source")
    if value is None or value == "" or value == []:
        return []
    if isinstance(value, list):
        return value
    return [value]


def raw_path(ref: object, raw: Path) -> tuple[str, Path | None]:
    """Classify a ref by its form alone: ("url" | "outside", None) or ("raw", path)."""
    if not isinstance(ref, str):
        return "outside", None
    if ref.startswith(("http://", "https://")):
        return "url", None
    if not ref.startswith("raw/"):
        return "outside", None
    rest = ref[len("raw/") :]
    if any(c in rest for c in ("\\", ":", "\x00")):
        return "outside", None
    norm = posixpath.normpath(rest) if rest else "."
    if norm.startswith("/") or norm == ".." or norm.startswith("../"):
        return "outside", None
    return "raw", raw / norm


def read_source(path: Path) -> tuple[str, Source | None]:
    """Return the ref kind of a path under ctx.raw and its Source when it is text."""
    try:
        mode = path.stat().st_mode
    except OSError:
        return "missing", None
    if not stat.S_ISREG(mode):
        return "missing", None
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return "non_text", None
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError:
        return "missing", None
    try:
        return "text", Source(data.decode("utf-8"))
    except UnicodeDecodeError:
        return "undecodable", None


def list_pages(wiki: Path) -> list[tuple[str, Path]]:
    if not wiki.is_dir():
        return []
    pages = []
    for path in wiki.rglob("*.md"):
        rel = path.relative_to(wiki)
        if len(rel.parts) > 1 and path.is_file():
            pages.append((rel.with_suffix("").as_posix(), path))
    return sorted(pages)


def measure_containment(ctx) -> dict:
    out = Path(ctx.out)
    pages = list_pages(Path(ctx.wiki))
    if not pages:
        (out / SAMPLE).unlink(missing_ok=True)
        return {"status": "unmeasured", "reason": "no pages", "cases": 0, "metrics": {}}

    raw = Path(ctx.raw)
    m = dict.fromkeys(
        [
            "pages_unparsed",
            "pages_no_source_field",
            "pages_no_text_source",
            *(f"refs_{kind}" for kind in REF_KINDS),
            "refs_total",
            "sentences",
            "sentences_short",
            "sentences_no_text_source",
            "band_high",
            "band_mid",
            "band_low",
        ],
        0,
    )
    cache: dict[Path, tuple[str, Source | None]] = {}
    banded: dict[str, list[dict]] = {}

    for page_id, path in pages:
        try:
            with open(path, "rb") as handle:
                text = handle.read().decode("utf-8")
            meta, _ = split_frontmatter(text)
        except (UnicodeDecodeError, FrontmatterError):
            m["pages_unparsed"] += 1
            continue
        refs = page_refs(meta)
        if not refs:
            m["pages_no_source_field"] += 1
        sources: list[Source] = []
        text_refs: list[str] = []
        for ref in refs:
            kind, target = raw_path(ref, raw)
            if target is not None:
                if target not in cache:
                    cache[target] = read_source(target)
                kind, source = cache[target]
                if source is not None:
                    sources.append(source)
                    text_refs.append(ref)
            m[f"refs_{kind}"] += 1
            m["refs_total"] += 1
        if not sources:
            m["pages_no_text_source"] += 1

        rows = []
        for sentence in page_sentences(text):
            # With no source every n-gram is unfound, so None still means too short.
            value = (
                None if is_short(sentence["text"]) else containment_in(sentence["text"], sources)
            )
            if value is None:
                m["sentences_short"] += 1
                continue
            m["sentences"] += 1
            if not sources:
                m["sentences_no_text_source"] += 1
                continue
            m[f"band_{band(value)}"] += 1
            rows.append(
                {
                    "page": page_id,
                    "sentence_index": sentence["index"],
                    "start": sentence["start"],
                    "end": sentence["end"],
                    "sha256": sha(sentence["text"]),
                    "band": band(value),
                    "containment": value,
                    "sources": text_refs,
                    "text": sentence["text"],
                }
            )
        banded[page_id] = rows

    eligible = sorted((p for p, rows in banded.items() if len(rows) >= SAMPLE_PER_PAGE), key=sha)
    lines = []
    for page_id in eligible[:SAMPLE_PAGES]:
        rows = banded[page_id]
        chosen = sorted(rows, key=lambda r: sha(f"{page_id}:{r['sentence_index']}"))
        for row in sorted(chosen[:SAMPLE_PER_PAGE], key=lambda r: r["sentence_index"]):
            lines.append(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    out.mkdir(parents=True, exist_ok=True)
    (out / SAMPLE).write_bytes("".join(lines).encode("utf-8"))
    m["sample_pages"] = min(len(eligible), SAMPLE_PAGES)
    m["sample_sentences"] = len(lines)
    return {"status": "measured", "cases": len(pages), "metrics": m}


def field_names(extract: object) -> list[str]:
    """Names of the fields an `extract` value declares; `name (type): text` gives `name`."""
    items = extract if isinstance(extract, list) else [extract]
    names = []
    for item in items:
        if isinstance(item, dict):
            names += [str(key) for key in item]
        elif isinstance(item, str):
            match = FIELD_NAME.match(item)
            if match:
                names.append(match.group(1))
    return names


def measure_templates(ctx) -> dict:
    directory = getattr(ctx, "templates", None) or CHECKOUT / "templates"
    directory = Path(directory)
    if not directory.is_dir():
        return {
            "status": "unmeasured",
            "reason": "no templates directory",
            "cases": 0,
            "metrics": {},
        }
    files = sorted(p for p in directory.rglob("*.yaml") if p.is_file())
    with_span = 0
    for path in files:
        try:
            with open(path, encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            continue
        extract = data.get("extract") if isinstance(data, dict) else None
        names = [name.lower() for name in field_names(extract)]
        if any(part in name for name in names for part in CLAIM_SPAN_PARTS):
            with_span += 1
    return {
        "status": "measured",
        "cases": len(files),
        "metrics": {"templates_total": len(files), "templates_with_claim_span": with_span},
    }


def run(ctx) -> dict:
    return {
        "invariants": ["I1"],
        "arms": {"containment": measure_containment(ctx), "templates": measure_templates(ctx)},
    }
