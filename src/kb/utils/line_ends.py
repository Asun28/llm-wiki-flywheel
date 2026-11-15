"""Read a page as LF text plus its own line ends, and write an edit of it back with them.

Page patterns (frontmatter, headings, code masks) are written for LF text, so a
page writer matches on the LF text `read_page_text` returns and puts the page's
line ends back only when it writes, through `restore_line_ends` (#168, #175).
Leaf module: no ``kb`` imports.
"""

import difflib
import re
from pathlib import Path

_CRLF = "\r\n"
_LF = "\n"
_LINE_END_RE = re.compile(r"\r\n|\r|\n")


def read_page_text(path: Path) -> tuple[str, list[str]]:
    """Return a page's text with every line end turned into LF, and its line ends.

    One read of the file's bytes. The text equals ``Path.read_text(encoding="utf-8")``;
    the ends list holds one entry per line end in order, ``"\\r\\n"`` for a CRLF and
    ``"\\n"`` for an LF or a lone CR.
    """
    raw = Path(path).read_bytes().decode("utf-8")
    ends = [_CRLF if m.group() == _CRLF else _LF for m in _LINE_END_RE.finditer(raw)]
    return _LINE_END_RE.sub(_LF, raw), ends


def restore_line_ends(text: str, original: str, ends: list[str]) -> str:
    """Return ``text``, an edit of ``original``, with the page's own line ends.

    ``original`` and ``ends`` come from `read_page_text`: one entry of ``ends`` per
    LF of ``original``. If ``ends`` holds no CRLF, ``text`` is returned unchanged.
    Otherwise the common leading and trailing lines of ``original`` and ``text`` keep
    their ends, and a line diff (`difflib.SequenceMatcher`) of the lines between
    them decides the rest: a line equal to an original line keeps that line's end;
    the lines of one replaced run pair from the end of the run and each keeps the
    end of the line it replaced, so a line joined from two keeps the second one's
    end; every other line that has an end (an added line, a leading extra line of a
    replaced run, or an original last line that had none) gets the page's most-used
    end, LF on a tie. The last line of ``text`` gets no end, so a text with no final
    line end keeps none.
    """
    if _CRLF not in ends:
        return text
    crlf_count = ends.count(_CRLF)
    most_used = _CRLF if crlf_count > len(ends) - crlf_count else _LF

    old_lines = original.split(_LF)
    new_lines = text.split(_LF)
    shorter = min(len(old_lines), len(new_lines))
    lead = 0
    while lead < shorter and old_lines[lead] == new_lines[lead]:
        lead += 1
    trail = 0
    while trail < shorter - lead and old_lines[-1 - trail] == new_lines[-1 - trail]:
        trail += 1
    # (old index, new index) of every line that keeps an original line's end.
    pairs = [(i, i) for i in range(lead)]
    pairs += [(len(old_lines) - 1 - k, len(new_lines) - 1 - k) for k in range(trail)]
    matcher = difflib.SequenceMatcher(
        None,
        old_lines[lead : len(old_lines) - trail],
        new_lines[lead : len(new_lines) - trail],
        autojunk=False,
    )
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("equal", "replace"):
            for k in range(min(i2 - i1, j2 - j1)):
                pairs.append((lead + i2 - 1 - k, lead + j2 - 1 - k))

    new_ends = [most_used] * (len(new_lines) - 1)
    for old_i, new_j in pairs:
        # The last line of either side has no end.
        if old_i < len(ends) and new_j < len(new_ends):
            new_ends[new_j] = ends[old_i]
    body = "".join(line + end for line, end in zip(new_lines, new_ends, strict=False))
    return body + new_lines[-1]
