---
slug: kb-fixes-2
title: "Fix the four open issues #175, #163, #157 and #148"
intent: intent/kb-fixes-2.md
status: accepted
created: 2026-11-15T19:05:00Z
skills_applied: [grilling]
---

# Spec: Fix the four open issues #175, #163, #157 and #148
From intent: intent/kb-fixes-2.md. Status: accepted. Skills applied: grilling (one round, four owner decisions).

## Requirements (EARS)
Shared line-end helper (#175)
- R1. The function `kb.utils.line_ends.read_page_text(path)` shall return, from one read of the file, the page text with every CRLF and lone CR turned into LF (equal to what `Path.read_text(encoding="utf-8")` returns) and the page's line ends in order, `"\r\n"` for a CRLF and `"\n"` for an LF or a lone CR.
- R2. IF `ends` holds no CRLF, THEN the function `kb.utils.line_ends.restore_line_ends(text, original, ends)` shall return `text` unchanged.
- R3. WHEN `ends` holds a CRLF, the function `restore_line_ends` shall give each line of `text` that a line diff aligns with an equal line of `original` that line's own end, and each line that replaces a line of `original` (paired in order within one replaced run) the replaced line's end.
- R4. WHEN `ends` holds a CRLF, the function `restore_line_ends` shall give every other line of `text` that has a line end (an added line, or an original last line that had no end) the page's most-used end, and LF on a tie [SOURCE: owner decision 2026-11-16].
- R5. The linker (`inject_wikilinks`, `inject_wikilinks_batch`) shall read and write pages through `read_page_text` and `restore_line_ends` and keep no copy of either in `kb.compile.linker` [SOURCE: owner decision 2026-11-16].

Page writers (#175)
- R6. The function `kb.ingest.pipeline._update_existing_page_body` shall read the page once through `read_page_text`, run every pattern on the LF text and write `restore_line_ends` of its result.
- R7. The function `kb.ingest.evidence.append_evidence_trail` shall read the page through `read_page_text` and write `restore_line_ends` of its result.
- R8. The function `kb.lint.checks.dead_links.fix_dead_links` shall read each page through `read_page_text` and write `restore_line_ends` of its result.
- R9. WHEN a page holds no CRLF, the writers of R5-R8 shall write the same bytes they wrote before this change.

Image alt text in the baseline test (#163)
- R10. The helper `bench/knowledge/tests/test_baseline.py::plain()` shall render an `image` child as the rendered text of its alt (its children, by `plain`'s own rules), not as the token's raw `content`.

HTML blocks in the trace probe (#157)
- R11. The function `bench/knowledge/probes/trace.py::classify_lines` shall recognise an HTML block by the start and end conditions of CommonMark 0.31.2 section 4.6 (types 1-7), inside block quotes and list items too, where a type 7 block cannot interrupt a paragraph.
- R12. WHILE a line is inside an HTML block, the function `classify_lines` shall keep it as text, never as a fence opener, an ATX heading, a setext underline or a table row [SOURCE: owner decision 2026-11-16: HTML block lines stay prose].
- R13. WHEN an HTML block ends (its end condition, or the end of its container), the function `classify_lines` shall classify the next line as it would after any other block.
- R14. The baseline report `docs/knowledge-baseline.md` shall keep its Phase 0 numbers and `bench/knowledge/summary.json`, with a dated note on each of its two lines naming #157 that the probe recognises HTML blocks since card T1-KBEVAL-HTMLBLOCK [SOURCE: owner decision 2026-11-16].

Bench runner error paths (#148)
- R15. IF the probes directory cannot be listed, THEN the runner `run.py` shall name the directory and the cause and exit 2 before any probe runs, while an empty readable directory keeps today's behaviour.
- R16. WHEN a run starts, the runner `run.py` shall remove `<out>/<probe>.json` of every selected probe before the first probe runs, a read-only one included, or name the path and the cause and exit 1 before any probe runs.
- R17. WHEN a probe fails, the runner `run.py` shall remove that probe's record, a read-only one included, or name the path of a record it cannot remove.
- R18. WHEN a probe fails, the runner `run.py` shall set the exit code to 1 before writing any diagnostic, so that a diagnostic that cannot be written stops neither the later probes nor the guard comparison.
- R19. WHEN stdout's pipe is closed during a run, the process shall exit with the run's exit code, not 120.
- R20. IF `--out` cannot be created or is not a directory, THEN the runner `run.py` shall name it and the cause and exit 2 before any probe runs.
- R21. IF the resolved `--out` equals or lies inside the resolved `--wiki`, `--raw`, or the checkout's `wiki/`, `raw/` or `.data/`, THEN the runner `run.py` shall exit 2 naming both paths, before any probe runs and before any directory is created.

## Design
- `kb.utils.line_ends` (new leaf module, no `kb` imports): `read_page_text` and `restore_line_ends` move here from `kb.compile.linker` (`_read_page`, `_restore_line_ends`). The new restore aligns lines with `difflib.SequenceMatcher(None, original.split("\n"), text.split("\n"), autojunk=False)`: `equal` keeps ends, `replace` pairs lines in order and gives extra lines the most-used end, `insert` gives the most-used end. On the cases the 27 tests of `tests/test_kbfix_linker_crlf.py` pin it gives the same bytes as the current restore; it differs only where the owner decision changes the rule (an LF inside inserted text now takes the page's most-used end instead of LF).
- The three writers keep matching on LF text (docs/LESSONS.md 2026-11-15 T0-KBFIX-CRLF) and change only their read and their write argument. `_update_existing_page` holds one page lock across the body write and the evidence append; the evidence append reads the page the body write just restored, so both must change in the same card.
- `test_baseline.py::plain()`: an `image` child appends `plain(child)`.
- `trace.py`: an `html` leaf kind in `classify_lines`, opened by the seven start conditions (checked on the line after container markers, indent 3 or less) before the fence, heading, setext and table checks, closed by its end condition (types 1-5: the line holding the end string; types 6-7: a blank line) or by its container ending. Lines in it stay `kept`.
- `run.py`: `find_probes` enumerates with `os.scandir` (raises) instead of `Path.glob`; `--out` checks join the usage checks before `mkdir`; record removal clears the read-only bit before `unlink`; the per-probe handler sets `exit_code = 1` first and wraps the diagnostic; `main()` guards the stream restore and, when stdout is broken, points it at `os.devnull` so interpreter shutdown cannot flush the broken pipe.

## Interfaces and contracts
- New: `kb.utils.line_ends.read_page_text(path: Path) -> tuple[str, list[str]]`, `kb.utils.line_ends.restore_line_ends(text: str, original: str, ends: list[str]) -> str`.
- Removed: `kb.compile.linker._read_page`, `kb.compile.linker._restore_line_ends` (private; no test or caller outside the linker imports them).
- `bench/knowledge/run.py` exit codes keep their meaning (0 clean, 1 probe failure or guard change, 2 usage); R15, R20 and R21 are usage errors (2), R16 is a run failure (1).
- No frozen contract changes.

## Data model and migration impact
None. Pages already rewritten to LF stay LF; a CRLF page keeps CRLF from its next edit on.

## Flagged concerns (route to policy owners)
- (none)

## Non-goals
- `kb.review.refiner.refine_page`, which converts CRLF to LF on purpose.
- `_update_sources_mapping` (`wiki/_sources.md`), `_update_index_batch` (`wiki/index.md`) and the contradictions writer: files kb writes itself with LF (0 CRs in this wiki); they keep LF output.
- `save_page_frontmatter` (augment persister): reserializes the whole page through `frontmatter.dumps`, so it has no original line ends to keep.
- Lone CR line ends: still written as LF (patterns see LF only).
- Rerunning or rewriting the committed Phase 0 baseline numbers.
- HTML block lines as excluded text (owner decision: they stay prose).
- Dependabot: no open alert at intake (see intent).

## Acceptance
- 1. Unit tests of `kb.utils.line_ends`: an LF page returns `text` unchanged; a CRLF page with edits at two separate places keeps CRLF on every line between them; an added line on a CRLF page gets CRLF, on a mixed page the most-used end, on a tie LF; a replaced line keeps its end; and all 27 tests of `tests/test_kbfix_linker_crlf.py` pass unchanged. [R1-R5]
- 2. Re-ingest into a CRLF page (References append and `### From` Context subsection), an evidence append, and `kb lint --fix` on a CRLF page each leave every line end CRLF; the same calls on an LF page write the same bytes as before; the existing ingest, evidence and dead-links tests pass. [R6-R9]
- 3. `test_baseline.py` counts a formatted owner figure and a formatted null-final figure in image alt text. [R10]
- 4. `test_trace.py`: the CommonMark example 161 page keeps both prose sentences; a heading-like and a table-like line inside an HTML block are kept; each of the seven start conditions and its end condition is covered, and a type 7 line does not interrupt a paragraph. The baseline report carries the two dated notes and `summary.json` is unchanged. [R11-R14]
- 5. `bench/knowledge/tests`: each of R15-R21 has a regression (closed pipe in a real subprocess for R18-R19; both overlaps and a symlinked path for R21). [R15-R21]
- 6. Integrated: the full test suite and `bench/knowledge/tests` pass on the final SHA; `python bench/knowledge/run.py --out <scratch>` exits 0; a CRLF copy of a demo page goes through re-ingest, an evidence append and `kb lint --fix` and keeps CRLF on every line.
