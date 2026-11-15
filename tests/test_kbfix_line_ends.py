"""T1-KBFIX-LINEENDS (#175): `kb.utils.line_ends` reads a page as LF text plus its
own line ends and writes an edit of it back with those ends, after any number of
edits; an added line takes the page's most-used end (LF on a tie)."""

from __future__ import annotations

import os
import random
import time

import pytest

from kb.utils.line_ends import read_page_text, restore_line_ends

CRLF = "\r\n"
LF = "\n"


def _restore(raw_original: str, text: str) -> str:
    """Restore `text`, an edit of the LF form of `raw_original` (CRLF and LF ends only)."""
    ends = [CRLF if seg.endswith("\r") else LF for seg in raw_original.split(LF)[:-1]]
    return restore_line_ends(text, raw_original.replace(CRLF, LF), ends)


# --- Acceptance 1 [R1] -----------------------------------------------------


def test_read_page_text_gives_read_text_and_the_line_ends(tmp_path):
    path = tmp_path / "page.md"
    # Bytes, not text: write_text on Windows would turn every "\n" into "\r\n".
    path.write_bytes(b"one\r\ntwo\nthree\rfour")
    text, ends = read_page_text(path)
    assert (text, ends) == (path.read_text(encoding="utf-8"), [CRLF, LF, LF])


def test_read_page_text_without_a_line_end_gives_no_ends(tmp_path):
    path = tmp_path / "page.md"
    path.write_bytes("only line é".encode())
    assert read_page_text(path) == ("only line é", [])


# --- Acceptance 2 [R2] -----------------------------------------------------


def test_lf_page_returns_text_unchanged():
    original = "a\nb\nc\nd\ne\n"
    text = "a\nadded\nB2\nd\ne\nmore\n"  # adds lines, removes "c", replaces "b"
    result = restore_line_ends(text, original, [LF] * 5)
    assert result is text or result == text


# --- Acceptance 3 [R3] -----------------------------------------------------


def test_two_separate_edits_keep_crlf_on_every_line_between_them():
    lines = [f"line {n}" for n in range(1, 11)]
    edited = [*lines[:1], "line 2 edited", *lines[2:8], "line 9 edited", lines[9]]
    result = _restore(CRLF.join(lines) + CRLF, LF.join(edited) + LF)
    assert result == CRLF.join(edited) + CRLF


def test_replaced_lines_keep_their_own_end_on_a_mixed_page():
    raw = "head\r\nlf line\ncrlf line\r\ntail\n"
    text = "head\nLF LINE\nCRLF LINE\ntail\n"
    assert _restore(raw, text) == "head\r\nLF LINE\nCRLF LINE\r\ntail\n"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a\nfirst\r\nsecond\nz\n", "a\nfirst second\nz\n"),
        ("a\r\nfirst\nsecond\r\nz\r\n", "a\r\nfirst second\r\nz\r\n"),
    ],
    ids=["crlf-then-lf", "lf-then-crlf"],
)
def test_a_merged_line_keeps_the_second_lines_end(raw, expected):
    # Joining two lines removes the first line's end; the second line's end survives.
    assert _restore(raw, "a\nfirst second\nz\n") == expected


@pytest.mark.parametrize(
    ("raw", "text", "expected"),
    [
        # 3 CRLF and 1 LF: the split LF line's first part takes the most-used CRLF.
        (
            "a\r\nfirst second\nz\r\nw\r\n",
            "a\nfirst\nsecond\nz\nw\n",
            "a\r\nfirst\r\nsecond\nz\r\nw\r\n",
        ),
        # 1 CRLF and 3 LF: the split CRLF line's first part takes the most-used LF.
        ("a\nfirst second\r\nz\nw\n", "a\nfirst\nsecond\nz\nw\n", "a\nfirst\nsecond\r\nz\nw\n"),
    ],
    ids=["lf-line-on-crlf-page", "crlf-line-on-lf-page"],
)
def test_a_split_line_gives_the_first_part_the_most_used_end_and_the_second_its_own(
    raw, text, expected
):
    assert _restore(raw, text) == expected


def test_an_edited_line_whose_old_text_recurs_later_keeps_its_own_end():
    original = "matters\n\n\n\nx Hydration\n x \nmatters\nmatters"
    ends = [LF, LF, LF, LF, CRLF, LF, CRLF]
    text = "matters\n\n\n\nx Hydration\n x \n[[t|T]]ters\nmatters"  # seventh line edited
    expected = "matters\n\n\n\nx Hydration\r\n x \n[[t|T]]ters\r\nmatters"
    assert restore_line_ends(text, original, ends) == expected


# --- Acceptance 4 [R4] -----------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("l1\r\nl2\r\nl3\r\nl4\r\n", "l1\r\nl2\r\nadded\r\nl3\r\nl4\r\n"),
        ("l1\r\nl2\nl3\r\nl4\r\n", "l1\r\nl2\nadded\r\nl3\r\nl4\r\n"),
        ("l1\nl2\r\nl3\nl4\n", "l1\nl2\r\nadded\nl3\nl4\n"),
        ("l1\r\nl2\nl3\nl4\r\n", "l1\r\nl2\nadded\nl3\nl4\r\n"),
    ],
    ids=["all-crlf", "3-crlf-1-lf", "1-crlf-3-lf", "2-2-tie"],
)
def test_an_added_line_gets_the_most_used_end(raw, expected):
    assert _restore(raw, "l1\nl2\nadded\nl3\nl4\n") == expected


@pytest.mark.parametrize(
    ("raw", "text", "expected"),
    [
        ("a\r\nb\r\nc", "a\nb\nc\nd", "a\r\nb\r\nc\r\nd"),
        ("a\nb\r\nc\nd", "a\nb\nc\nd\ne", "a\nb\r\nc\nd\ne"),
    ],
    ids=["most-used-crlf", "most-used-lf"],
)
def test_an_original_last_line_that_gains_an_end_gets_the_most_used_end(raw, text, expected):
    assert _restore(raw, text) == expected


def test_a_text_without_a_final_line_end_gets_none():
    assert _restore("a\r\nb\r\n", "a\nb\nc") == "a\r\nb\r\nc"


# --- Acceptance 5 [R2] [R3] [R4] -------------------------------------------

_VOCAB = ["", "", "## Heading", "- item", "Same line.", "See [[a/b]].", "---"]


def _random_line(rng: random.Random) -> str:
    # Repeated lines and blank lines make the line diff's alignment ambiguous.
    return rng.choice(_VOCAB) if rng.random() < 0.5 else f"line {rng.randrange(10_000)}"


def _random_edit(rng: random.Random, segments: list[str]) -> None:
    """Add, remove or replace one line of `segments` (the LF-split text) in place."""
    kind = rng.choice(["add", "remove", "replace"])
    if kind == "add":
        segments.insert(rng.randrange(len(segments) + 1), _random_line(rng))
    elif kind == "remove" and len(segments) > 1:
        del segments[rng.randrange(len(segments))]
    else:
        segments[rng.randrange(len(segments))] = _random_line(rng)


def test_random_multi_edits_keep_the_text_and_the_page_ends():
    rng = random.Random(175)
    kinds = ["all-crlf", "all-lf", "mixed"]
    for case in range(3000):
        kind = kinds[case % 3]
        n = rng.randint(2, 30)
        lines = [_random_line(rng) for _ in range(n)]
        n_ends = n if rng.random() < 0.7 else n - 1
        if kind == "all-crlf":
            ends = [CRLF] * n_ends
        elif kind == "all-lf":
            ends = [LF] * n_ends
        else:
            ends = [rng.choice([CRLF, LF]) for _ in range(n_ends)]
        raw = "".join(line + end for line, end in zip(lines, ends, strict=False))
        raw += "".join(lines[n_ends:])
        segments = raw.replace(CRLF, LF).split(LF)
        for _ in range(rng.randint(1, 5)):
            _random_edit(rng, segments)
        text = LF.join(segments)

        result = _restore(raw, text)

        assert result.replace(CRLF, LF) == text, (case, raw, text, result)
        if kind == "all-crlf":
            assert LF not in result.replace(CRLF, ""), (case, raw, text, result)
        if kind == "all-lf":
            assert result == text, (case, raw, text, result)


def _one_splice_restore(text: str, original: str, ends: list[str]) -> str:
    """Oracle: PR 174's restore (`kb.compile.linker._restore_line_ends` at 4408d78).

    Right for one splice: each LF before and after the splice keeps its end, and
    an LF inside the inserted text gets LF. Copied verbatim.
    """
    if "\r\n" not in ends:
        return text
    head = len(os.path.commonprefix([original, text]))
    tail = len(os.path.commonprefix([original[head:][::-1], text[head:][::-1]]))
    n_head = original[:head].count("\n")
    n_tail = original[len(original) - tail :].count("\n")
    n_mid = text[head : len(text) - tail].count("\n")
    new_ends = ends[:n_head] + ["\n"] * n_mid + ends[len(ends) - n_tail :]
    parts = text.split("\n")
    return "".join(part + end for part, end in zip(parts, new_ends, strict=False)) + parts[-1]


_INSERTS = ["[[t|T]]", "", "x", "Same line.", "line 7", "## Heading", "]] "]


def test_single_splices_on_mixed_pages_give_the_one_splice_restores_bytes():
    rng = random.Random(174)
    cases = 0
    while cases < 3000:
        n = rng.randint(2, 12)
        lines = [_random_line(rng) for _ in range(n)]
        n_ends = n if rng.random() < 0.7 else n - 1
        ends = [rng.choice([CRLF, LF]) for _ in range(n_ends)]
        if n_ends < 2:
            continue
        ends[0], ends[-1] = rng.sample([CRLF, LF], 2)  # mixed: both ends present
        original = LF.join(lines[: n_ends + 1]) + (LF if n_ends == n else "")
        if not original:
            continue
        start = rng.randrange(len(original) + 1)
        stop = min(len(original), start + rng.randint(0, 20))
        text = original[:start] + rng.choice(_INSERTS) + original[stop:]
        expected = _one_splice_restore(text, original, ends)
        assert restore_line_ends(text, original, ends) == expected, (original, ends, text)
        cases += 1


def test_a_5000_line_crlf_page_with_50_edits_restores_in_under_5_seconds():
    rng = random.Random(5000)
    lines = []
    for n in range(5000):
        if n % 4 == 3:
            lines.append("")  # blank lines repeat, as in a real page
        elif n % 50 == 0:
            lines.append(f"## Section {n // 50}")
        else:
            lines.append(f"Sentence {n} mentions [[concepts/topic-{n % 37}]].")
    segments = [*lines, ""]
    for _ in range(50):
        _random_edit(rng, segments)
    text = LF.join(segments)

    start = time.perf_counter()
    result = _restore(CRLF.join(lines) + CRLF, text)
    elapsed = time.perf_counter() - start

    expected = text.replace(LF, CRLF)
    # A plain `==` assert makes pytest diff two 250 KB strings, which outlasts the
    # suite timeout; report the first differing offset instead.
    same = result == expected
    first = next((i for i, pair in enumerate(zip(result, expected)) if pair[0] != pair[1]), None)
    assert same, f"first difference at offset {first}: {result[first or 0 :][:60]!r}"
    assert elapsed < 5.0, elapsed
