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

Readings of the card fixed here:
- Removed text is found by CommonMark block structure (GFM for tables), inside
  blockquotes and list items too; see `classify_lines`.
- A sentence includes its end mark.
- Removed text ends the piece before it, so every sentence is one contiguous span
  of the page file and `start`/`end` in the sample cut it out exactly.
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
            except (yaml.YAMLError, ValueError, TypeError) as exc:
                # A constructor (an impossible date, for one) raises ValueError or
                # TypeError rather than YAMLError; each means the block does not load.
                raise FrontmatterError(f"frontmatter is not YAML: {exc}") from None
            if meta is None:
                meta = {}
            if not isinstance(meta, dict):
                raise FrontmatterError("frontmatter is not a mapping")
            return meta, offset + len(line)
        offset += len(line)
    raise FrontmatterError("frontmatter block is not closed")


LINE = re.compile(r"([^\r\n]*)(\r\n|\r|\n|\Z)")
FENCE_OPEN = re.compile(r"(`{3,}|~{3,})(.*)\Z", re.DOTALL)
FENCE_CLOSE = re.compile(r"(`{3,}|~{3,})[ \t]*\Z")
ATX = re.compile(r"(#{1,6})(?=[ \t]|\Z)(.*)\Z", re.DOTALL)
ATX_CLOSING = re.compile(r"(?:^|[ \t]+)#+[ \t]*\Z")
SETEXT = re.compile(r"(?:=+|-+)[ \t]*\Z")
THEMATIC = re.compile(r"([-*_])(?:[ \t]*\1){2,}[ \t]*\Z")
TABLE_DELIMITER = re.compile(r"\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*\Z")
BULLET = re.compile(r"[-+*](?=[ \t]|\Z)")
ORDERED = re.compile(r"(\d{1,9})[.)](?=[ \t]|\Z)")


def leading(s: str, pos: int, col: int) -> tuple[int, int]:
    """Columns of spaces and tabs at s[pos:] starting at column col, and the end position."""
    start = col
    while pos < len(s) and s[pos] in " \t":
        col = col + 1 if s[pos] == " " else col + 4 - col % 4
        pos += 1
    return col - start, pos


def advance(s: str, pos: int, col: int, columns: int) -> tuple[int, int]:
    """Consume up to `columns` columns of spaces and tabs; return the new (pos, col)."""
    target = col + columns
    while pos < len(s) and col < target and s[pos] in " \t":
        col = col + 1 if s[pos] == " " else col + 4 - col % 4
        pos += 1
    return pos, col


def fence_opener(after: str) -> tuple[str, int] | None:
    """(character, length) when `after` (indent removed) opens a fenced code block."""
    match = FENCE_OPEN.match(after)
    if not match or (match.group(1)[0] == "`" and "`" in match.group(2)):
        return None
    return match.group(1)[0], len(match.group(1))


def atx_heading(after: str) -> tuple[int, str] | None:
    """(level, text) when `after` (indent removed) is an ATX heading."""
    match = ATX.match(after)
    if not match:
        return None
    return len(match.group(1)), ATX_CLOSING.sub("", match.group(2).strip()).strip()


def cell_count(row: str) -> int:
    row = row.strip().replace("\\|", "")
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return row.count("|") + 1


def classify_lines(lines: list[str]) -> tuple[list[bool], list[int]]:
    """Return, per body line, whether it is kept text and where its content starts.

    A line is removed when it belongs to a fenced code block, an ATX or setext heading,
    a GFM table (header, delimiter, rows) or the Evidence Trail section. Blockquotes and
    list items are containers, so these blocks are found inside them too. The content
    start is the offset after the line's container markers. Follows CommonMark 0.31
    block structure without HTML blocks, link reference definitions or the rule that a
    list item may start with only one blank line.
    """
    kept = [True] * len(lines)
    content = [0] * len(lines)
    level_two: dict[int, str] = {}  # line index -> text of a top-level level-2 heading
    stack: list[tuple[str, int]] = []  # ("quote", 0) or ("item", content indent)
    leaf: dict | None = None  # the open leaf block of the innermost container

    for i, s in enumerate(lines):
        pos = col = matched = 0
        for kind, indent in stack:
            width, p = leading(s, pos, col)
            if kind == "quote":
                if width > 3 or s[p : p + 1] != ">":
                    break
                pos, col = advance(s, p + 1, col + width + 1, 1)
            elif s[pos:].strip():
                if width < indent:
                    break
                pos, col = advance(s, pos, col, indent)
            matched += 1
        all_matched = matched == len(stack)

        if leaf is not None and leaf["kind"] == "fence":
            if all_matched:
                kept[i] = False
                content[i] = pos
                width, p = leading(s, pos, col)
                close = FENCE_CLOSE.match(s[p:])
                if width <= 3 and close:
                    mark = close.group(1)
                    if mark[0] == leaf["char"] and len(mark) >= leaf["length"]:
                        leaf = None
                continue
            leaf = None  # an unclosed fence ends with its container

        para = leaf if leaf is not None and leaf["kind"] == "para" else None
        new: list[tuple[str, int]] = []
        p_new, c_new = pos, col
        while True:
            width, q = leading(s, p_new, c_new)
            if width >= 4:
                break
            after = s[q:]
            if after.startswith(">"):
                p_new, c_new = advance(s, q + 1, c_new + width + 1, 1)
                new.append(("quote", 0))
                continue
            if THEMATIC.match(after):
                break
            marker = BULLET.match(after) or ORDERED.match(after)
            if not marker:
                break
            body = after[marker.end() :]
            if para is not None and not new and all_matched:
                if not body.strip():
                    break  # an empty item cannot interrupt a paragraph
                if marker.re is ORDERED and int(marker.group(1)) != 1:
                    break  # an ordered list interrupting a paragraph starts at 1
            marker_col = c_new + width + marker.end()
            spaces, r = leading(s, q + marker.end(), marker_col)
            if not body.strip() or spaces >= 5:
                new.append(("item", width + marker.end() + 1))
                p_new, c_new = advance(s, q + marker.end(), marker_col, 1)
            else:
                new.append(("item", width + marker.end() + spaces))
                p_new, c_new = r, marker_col + spaces

        if not new and not all_matched and para is not None and s[pos:].strip():
            width, q = leading(s, pos, col)
            after = s[q:]
            starts_block = width <= 3 and (
                fence_opener(after) or atx_heading(after) or THEMATIC.match(after)
            )
            if not starts_block:  # lazy continuation of the paragraph
                para["lines"].append(i)
                content[i] = pos
                continue

        if not all_matched or new:
            leaf = None
            para = None
        stack = stack[:matched] + new
        pos, col = p_new, c_new
        content[i] = pos
        top_level = not stack
        width, q = leading(s, pos, col)
        after = s[q:]

        if not after.strip():
            if leaf is not None and leaf["kind"] in ("para", "table"):
                leaf = None
            continue
        if leaf is not None and leaf["kind"] == "table":
            if width <= 3 and (fence_opener(after) or atx_heading(after) or THEMATIC.match(after)):
                leaf = None
            else:
                kept[i] = False
                continue
        if width <= 3:
            fence = fence_opener(after)
            if fence:
                leaf = {"kind": "fence", "char": fence[0], "length": fence[1]}
                kept[i] = False
                continue
            heading = atx_heading(after)
            if heading:
                leaf = None
                kept[i] = False
                if top_level and heading[0] == 2:
                    level_two[i] = heading[1]
                continue
            if para is not None and SETEXT.match(after):
                for j in [*para["lines"], i]:
                    kept[j] = False
                if top_level and after[0] == "-":
                    text = " ".join(lines[j][content[j] :].strip() for j in para["lines"])
                    level_two[para["lines"][0]] = text
                leaf = None
                continue
            if para is not None and TABLE_DELIMITER.match(after):
                header = para["lines"][-1]
                if cell_count(lines[header][content[header] :]) == cell_count(after):
                    kept[header] = kept[i] = False
                    leaf = {"kind": "table"}
                    continue
            if THEMATIC.match(after):
                leaf = None
                continue
        if para is not None:
            para["lines"].append(i)
        elif width >= 4:
            leaf = {"kind": "code"}
        else:
            leaf = {"kind": "para", "lines": [i]}

    in_trail = False
    for i in range(len(lines)):
        if i in level_two:
            in_trail = level_two[i] == "Evidence Trail"
        if in_trail:
            kept[i] = False
    return kept, content


def page_sentences(text: str) -> list[dict]:
    """Return the body sentences of a page file's text with offsets into that text.

    Sentences are cut from runs of consecutive kept lines. Container markers (`>`, a
    list marker and the indent a container consumes) never end a sentence and are
    trimmed from its two ends; inside a sentence that spans lines they stay, because
    a sentence is one contiguous span of the page file.
    """
    _, body_start = split_frontmatter(text)
    starts: list[int] = []
    lines: list[str] = []
    for match in LINE.finditer(text, body_start):
        if match.start() == len(text):
            break
        starts.append(match.start())
        lines.append(match.group(1))
    kept, content = classify_lines(lines)
    ends = [*starts[1:], len(text)]

    runs: list[tuple[int, int]] = []
    marker = [False] * len(text)
    for i, keep in enumerate(kept):
        if not keep:
            continue
        for offset in range(starts[i], starts[i] + content[i]):
            marker[offset] = True
        if runs and runs[-1][1] == starts[i]:
            runs[-1] = (runs[-1][0], ends[i])
        else:
            runs.append((starts[i], ends[i]))

    def skip(offset: int) -> bool:
        return text[offset].isspace() or marker[offset]

    sentences: list[dict] = []
    for run_start, run_end in runs:
        run = text[run_start:run_end]
        cuts = [
            run_start + m.end()
            for m in SENTENCE_END.finditer(run)
            if not marker[run_start + m.start()]
        ]
        piece_start = run_start
        for cut in [*cuts, run_end]:
            begin, end = piece_start, cut
            while begin < end and skip(begin):
                begin += 1
            while end > begin and skip(end - 1):
                end -= 1
            if begin < end:
                sentences.append(
                    {"index": len(sentences), "start": begin, "end": end, "text": text[begin:end]}
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
    """Return the ref kind of a path under ctx.raw and its Source when it is text.

    Only an absence error or a stat that shows no regular file makes a ref missing.
    Any other OSError (permission, I/O) fits none of the six kinds and propagates, so
    the runner reports the probe as failed instead of recording a false absence. The
    stat follows a symbolic link: a ref through one is read as its target.
    """
    try:
        mode = path.stat().st_mode
    except (FileNotFoundError, NotADirectoryError):
        return "missing", None
    if not stat.S_ISREG(mode):
        return "missing", None
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return "non_text", None
    try:
        handle = open(path, "rb")
    except (FileNotFoundError, NotADirectoryError):
        return "missing", None
    with handle:
        data = handle.read()
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
        except (yaml.YAMLError, ValueError, TypeError):
            continue  # counted, with no claim span; UnicodeDecodeError is a ValueError
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
