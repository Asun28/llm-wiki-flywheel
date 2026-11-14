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
- CommonMark block structure (GFM for tables) only recognises the blocks R3
  removes: fenced code, heading lines and table rows; see `classify_lines`.
  Everything else follows R3's text: the Evidence Trail bounds, the sentence ends
  and the white-space strip. A kept line keeps its `>` or list marker as text.
- A sentence includes its end mark.
- Removed text ends the piece before it, so every sentence is one contiguous span
  of the page file and `start`/`end` in the sample cut it out exactly (R8).
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
ATX = re.compile(r"(#{1,6})(?=[ \t]|\Z)")
SETEXT = re.compile(r"(?:=+|-+)[ \t]*\Z")
THEMATIC = re.compile(r"([-*_])(?:[ \t]*\1){2,}[ \t]*\Z")
TABLE_DELIMITER = re.compile(r"\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*\Z")
BULLET = re.compile(r"[-+*](?=[ \t]|\Z)")
ORDERED = re.compile(r"([0-9]{1,9})[.)](?=[ \t]|\Z)")
TRAIL_LINE = "## Evidence Trail"
# CommonMark block syntax treats only space and tab as white space, and only ASCII
# digits as list-marker digits; the patterns above say so explicitly.
SPACE_TAB = " \t"


def leading(s: str, pos: int, col: int, rem: int) -> tuple[int, int, int]:
    """Indent at a cursor in columns, and the position and column after it.

    `rem` is the number of columns left of a tab that a container marker consumed only
    in part; they count as indentation. A tab advances to the next multiple of 4.
    """
    width, col = rem, col + rem
    while pos < len(s) and s[pos] in " \t":
        step = 1 if s[pos] == " " else 4 - col % 4
        width, col, pos = width + step, col + step, pos + 1
    return width, pos, col


def advance(s: str, pos: int, col: int, rem: int, columns: int) -> tuple[int, int, int]:
    """Consume up to `columns` columns of indent; return the new (pos, col, rem)."""
    take = min(rem, columns)
    col, rem, columns = col + take, rem - take, columns - take
    while columns > 0 and pos < len(s) and s[pos] in " \t":
        step = 1 if s[pos] == " " else 4 - col % 4
        if step <= columns:
            col, columns = col + step, columns - step
        else:  # part of a tab: the rest stays as indentation
            col, rem, columns = col + columns, step - columns, 0
        pos += 1
    return pos, col, rem


def fence_opener(after: str) -> tuple[str, int] | None:
    """(character, length) when `after` (indent removed) opens a fenced code block."""
    match = FENCE_OPEN.match(after)
    if not match or (match.group(1)[0] == "`" and "`" in match.group(2)):
        return None
    return match.group(1)[0], len(match.group(1))


def unescaped_pipes(row: str) -> int:
    return row.replace("\\|", "").count("|")


def is_blank(text: str) -> bool:
    return not text.strip(SPACE_TAB)


def cell_count(row: str) -> int:
    row = row.strip(SPACE_TAB).replace("\\|", "")
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return row.count("|") + 1


def classify_lines(lines: list[str]) -> list[bool]:
    """Return, per body line, whether it is kept text.

    CommonMark 0.31.2 block structure (GFM for tables) is used only to recognise the
    blocks R3 excludes: fenced code blocks, heading lines (ATX and setext) and table
    rows. Blockquotes and list items are tracked as containers so those blocks are
    found inside them too; tabs count by CommonMark's column rule. The Evidence Trail
    follows R3's text: from the line `## Evidence Trail` to the next `## ` ATX heading.
    """
    kept = [True] * len(lines)
    content = [0] * len(lines)  # offset after the container markers, for table cells
    level_two_atx: set[int] = set()
    # Each container is [kind, content indent, has content]: ("quote", 0, True) or
    # ("item", indent, False while an item that began with a blank line is empty).
    stack: list[list] = []
    leaf: dict | None = None  # the open leaf block of the innermost container

    for i, s in enumerate(lines):
        pos = col = rem = matched = 0
        for entry in stack:
            kind, indent = entry[0], entry[1]
            width, q, qcol = leading(s, pos, col, rem)
            if kind == "quote":
                if width > 3 or s[q : q + 1] != ">":
                    break
                pos, col, rem = advance(s, q + 1, qcol + 1, 0, 1)
            elif not is_blank(s[pos:]):
                if width < indent:
                    break
                pos, col, rem = advance(s, pos, col, rem, indent)
                entry[2] = True
            elif not entry[2]:
                break  # a list item can begin with at most one blank line
            matched += 1
        all_matched = matched == len(stack)

        if leaf is not None and leaf["kind"] == "fence":
            if all_matched:
                kept[i] = False
                width, q, _ = leading(s, pos, col, rem)
                close = FENCE_CLOSE.match(s[q:])
                if width <= 3 and close:
                    mark = close.group(1)
                    if mark[0] == leaf["char"] and len(mark) >= leaf["length"]:
                        leaf = None
                continue
            leaf = None  # an unclosed fence ends with its container

        para = leaf if leaf is not None and leaf["kind"] == "para" else None
        new: list[list] = []
        cursor = (pos, col, rem)
        while True:
            width, q, qcol = leading(s, *cursor)
            if width >= 4:
                break
            after = s[q:]
            if after.startswith(">"):
                cursor = advance(s, q + 1, qcol + 1, 0, 1)
                new.append(["quote", 0, True])
                continue
            if THEMATIC.match(after):
                break
            marker = BULLET.match(after) or ORDERED.match(after)
            if not marker:
                break
            body = after[marker.end() :]
            if para is not None and not new and all_matched:
                if is_blank(body):
                    break  # an empty item cannot interrupt a paragraph
                if marker.re is ORDERED and int(marker.group(1)) != 1:
                    break  # an ordered list interrupting a paragraph starts at 1
            marker_col = qcol + marker.end()
            spaces, r, rcol = leading(s, q + marker.end(), marker_col, 0)
            if is_blank(body) or spaces >= 5:
                new.append(["item", width + marker.end() + 1, not is_blank(body)])
                cursor = advance(s, q + marker.end(), marker_col, 0, 1)
            else:
                new.append(["item", width + marker.end() + spaces, True])
                cursor = (r, rcol, 0)

        if not new and not all_matched and para is not None and not is_blank(s[pos:]):
            width, q, _ = leading(s, pos, col, rem)
            after = s[q:]
            starts_block = width <= 3 and (
                fence_opener(after) or ATX.match(after) or THEMATIC.match(after)
            )
            if not starts_block:  # lazy continuation of the paragraph
                para["lines"].append(i)
                para["lazy"].add(i)
                content[i] = pos
                continue

        if not all_matched or new:
            leaf = None
            para = None
        stack = stack[:matched] + new
        pos, col, rem = cursor
        content[i] = pos
        width, q, _ = leading(s, pos, col, rem)
        after = s[q:]

        if is_blank(after):
            if leaf is not None and leaf["kind"] in ("para", "table"):
                leaf = None
            continue
        if leaf is not None and leaf["kind"] == "table":
            # A row ends at a blank line, a block start or a line indented 4+ columns.
            if width >= 4 or fence_opener(after) or ATX.match(after) or THEMATIC.match(after):
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
            heading = ATX.match(after)
            if heading:
                leaf = None
                kept[i] = False
                if len(heading.group(1)) == 2:
                    level_two_atx.add(i)
                continue
            if para is not None and SETEXT.match(after):
                for j in [*para["lines"], i]:
                    kept[j] = False
                leaf = None
                continue
            if para is not None and TABLE_DELIMITER.match(after):
                last = para["lines"][-1]
                header = lines[last][content[last] :]
                if (
                    last not in para["lazy"]  # a lazy line is not in the table's container
                    and last not in para["indented"]  # a header is indented 3 columns or less
                    and unescaped_pipes(header)
                    and unescaped_pipes(after)
                    and cell_count(header) == cell_count(after)
                ):
                    kept[last] = kept[i] = False
                    leaf = {"kind": "table"}
                    continue
            if THEMATIC.match(after):
                leaf = None
                continue
        if para is not None:
            para["lines"].append(i)
            if width >= 4:
                para["indented"].add(i)
        elif width >= 4:
            leaf = {"kind": "code"}
        else:
            leaf = {"kind": "para", "lines": [i], "lazy": set(), "indented": set()}

    in_trail = False
    for i, s in enumerate(lines):
        if s == TRAIL_LINE:
            in_trail = True
        elif i in level_two_atx:
            in_trail = False
        if in_trail:
            kept[i] = False
    return kept


def page_sentences(text: str) -> list[dict]:
    """Return the body sentences of a page file's text with offsets into that text.

    R3: the pieces between sentence ends (`.`, `!`, `?` followed by white space or the
    end of a line; `。！？` anywhere), stripped of white space, numbered from 0. Pieces
    are cut from runs of consecutive kept lines, so removed text ends the piece before
    it and each sentence is one contiguous span of the page file (R8 `start`/`end`).
    """
    _, body_start = split_frontmatter(text)
    starts: list[int] = []
    lines: list[str] = []
    for match in LINE.finditer(text, body_start):
        if match.start() == len(text):
            break
        starts.append(match.start())
        lines.append(match.group(1))
    kept = classify_lines(lines)
    ends = [*starts[1:], len(text)]

    runs: list[tuple[int, int]] = []
    for i, keep in enumerate(kept):
        if not keep:
            continue
        if runs and runs[-1][1] == starts[i]:
            runs[-1] = (runs[-1][0], ends[i])
        else:
            runs.append((starts[i], ends[i]))

    sentences: list[dict] = []
    for run_start, run_end in runs:
        run = text[run_start:run_end]
        cuts = [run_start + m.end() for m in SENTENCE_END.finditer(run)]
        piece_start = run_start
        for cut in [*cuts, run_end]:
            begin, end = piece_start, cut
            while begin < end and text[begin].isspace():
                begin += 1
            while end > begin and text[end - 1].isspace():
                end -= 1
            if begin < end:  # a piece of white space only holds no sentence
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
