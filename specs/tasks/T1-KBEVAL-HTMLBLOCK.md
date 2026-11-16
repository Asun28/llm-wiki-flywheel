---
id: T1-KBEVAL-HTMLBLOCK
title: "The trace probe recognises CommonMark HTML blocks, so a fence, heading or table line inside one no longer changes how later lines are classified (#157)"
status: todo
branch: T1-KBEVAL-HTMLBLOCK
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-HTMLBLOCK
plan_ref: plans/kb-fixes-2.md#order-of-work
allow_paths:
  - bench/knowledge/probes/trace.py
  - bench/knowledge/tests/test_trace.py
  - docs/knowledge-baseline.md
  - CHANGELOG.md
  - CHANGELOG-history.md
  - specs/tasks/T1-KBEVAL-HTMLBLOCK.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_trace.py bench/knowledge/tests/test_baseline.py -q
dod_exit: 0
requirements:
  - R1. The function `classify_lines` in `bench/knowledge/probes/trace.py` shall recognise an HTML block by the seven start conditions and their end conditions of CommonMark 0.31.2 section 4.6, on the line after its container markers with an indent of 3 columns or less, inside block quotes and list items too, where a type 7 start cannot interrupt a paragraph.
  - R2. WHILE a line is inside an HTML block, the function `classify_lines` shall keep it as text, never as a fence opener, an ATX heading, a setext underline or a table row.
  - R3. WHEN an HTML block ends (types 1-5 on the line holding the end string, which stays in the block; types 6-7 at a blank line; any type when its container ends), the function `classify_lines` shall classify the next line as it would after any other block.
  - R4. The baseline report `docs/knowledge-baseline.md` shall keep its Phase 0 numbers, with a dated note on each of its two lines naming issue 157 that the probe recognises HTML blocks since this card, the date and card id written as backticked spans.
acceptance:
  - 1. `test_trace.py`: the CommonMark example 161 page (`<div>`, a backtick fence line, `</div>`, a blank line, then two prose sentences of enough words) yields both sentences, and a wiki of that page with a text source gives a non-empty `trace-sample.jsonl`; both fail before the fix (RED receipt). [R1] [R2] [R3] [dod arm 2]
  - 2. Same file, one case per type (1 `<pre>`...`</pre>`, 2 `<!--`...`-->`, 3 `<?`...`?>`, 4 `<!DOCTYPE`...`>`, 5 `<![CDATA[`...`]]>`, 6 `<div>` to a blank line, 7 `<x-note class="a">` alone on its line to a blank line): a fence-marker line and a `# ` line inside the block are kept, and a fence opener after the block's end is excluded as a fence again. [R1] [R2] [R3] [dod arm 2]
  - 3. Same file: a type 7 line right after a paragraph line does not start a block (a following `# x` line is removed as a heading), and a type 6 line right after a paragraph line does (a following `# x` line is kept); a table header and delimiter inside a type 6 block are kept. [R1] [R2] [dod arm 2]
  - 4. Same file: `> <pre>` followed by an unquoted fence opener ends the block with the block quote, and the fence's content line is excluded; a list item holding `<div>` ends the block when the item ends. [R1] [R3] [dod arm 2]
  - 5. Every existing test in `test_trace.py` and `test_baseline.py` passes with no existing test edited, `test_every_number_in_the_report_comes_from_summary_or_labels` included. [R4] [dod arm 2]
  - 6. The two lines of `docs/knowledge-baseline.md` naming issue 157 each carry the dated note and no Phase 0 number changes; the module docstring of `trace.py` lists HTML blocks among the blocks `classify_lines` recognises; `git diff --numstat origin/main...HEAD -- bench/knowledge/summary.json bench/knowledge/labels.jsonl` is empty; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id (reviewer-verified). [R4]
depends_on: []
budget: 400
sweep: "Six paths: the probe, its test file, the baseline report, two changelogs and this card. `classify_lines` is called only by the trace probe's body extraction. The report names #157 on two lines (about lines 23 and 222). The R3 verdict that deferred this finding is `.review/T1-KBEVAL-TRACE.r3.4.83753aa7.json` (class `fence-state-parsing`)."
forbid: [excluding HTML block lines from the text (owner decision: they stay prose), rerunning or rewriting the Phase 0 numbers, editing an existing test, a model call or network request in tests]
non_goals: [HTML block lines removed from extraction, inline HTML inside paragraphs (not a block), link reference definitions, indented code blocks (unchanged: still kept as today)]
diagnosis:
  root_cause: "`classify_lines` tracks fences, headings, setext underlines, tables, block quotes and list items, but has no HTML block state, so the start lines of an HTML block fall through to the fence, heading and table checks (CommonMark example 161: a backtick line inside `<div>` belongs to the HTML block)."
  same_class: "Other block kinds the classifier does not track: indented code blocks and link reference definitions. Both are kept as text today and neither can open a fence or swallow later lines, so neither has this defect."
hygiene: "Run the DoD with the main checkout's `.venv` active. Deferred by owner ruling on R3 decision 4 of T1-KBEVAL-TRACE (candidate `f871514`). A scratch differential against markdown-it-py (block tokens `html_block`) is a useful self-check; it is not part of the DoD."
---

# T1-KBEVAL-HTMLBLOCK

## Deliverable
`classify_lines` gains an HTML block state with CommonMark's seven start and end conditions; lines inside stay prose, and the block's content can no longer open a fence or form a heading or table that changes later lines.

## Why
Issue #157: a fence marker inside an HTML block opens a false fence that never closes, so every later sentence of the page is dropped from extraction and the label sample. Owner decisions 2026-11-16: HTML block lines stay prose; the Phase 0 numbers stay as the before-reference with a dated note.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_trace.py bench/knowledge/tests/test_baseline.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 1, implementer, 2026-11-16. Base `origin/main` b07472d.

Commits: b6142b2 (RED tests), 6791345 (fix and docstrings), 85fe3b1 (report notes and changelogs), and the commit adding this section.

RED at b6142b2 (`python -m pytest bench/knowledge/tests/test_trace.py -q` against the unchanged probe): exit 1, 12 failed, 104 passed. Each failure is an assertion on the sentence list, for example `assert [] == ['<div>\n```\...o count too.']` (example 161 sample: empty) and `['<pre>', 'Fenced line after the block is excluded.'] != ['<pre>\n```\n# Kept heading line here.', '</pre>', 'After the block ends here.']`. Failing: both example 161 tests, all 7 type cases, `type-6-interrupts-a-paragraph`, `table-inside-a-type-6-block-is-kept`, `ends-with-its-list-item`. Passing at RED by design (guards against over-recognition): `type-7-cannot-interrupt-a-paragraph`, `ends-with-its-block-quote`. One correction in 6791345: the type 3 case starts with `<?php`, not `<?`, because a bare `<?` line ends in `?` before a line end and R3's sentence rule cuts it there (the probe's lines were right, the test's expected list was not); rechecked RED for that case on the base probe: fails on the fence assertion.

DoD (`ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_trace.py bench/knowledge/tests/test_baseline.py -q`, main checkout `.venv`): exit 0; `All checks passed!`, `147 passed`. Output sha256 32c0cc748737ca5eff028b6e9089b6c777a7317b8a09173af3a734bd20626197.

`python -m pytest bench/knowledge/tests -q`: 388 passed, 4 skipped.

`git diff --numstat origin/main...HEAD` before this section:

```
10	0	CHANGELOG-history.md
1	0	CHANGELOG.md
83	6	bench/knowledge/probes/trace.py
109	0	bench/knowledge/tests/test_trace.py
2	2	docs/knowledge-baseline.md
```

| Acceptance | Evidence |
|---|---|
| 1 | `test_example_161_fence_line_inside_an_html_block_keeps_the_later_sentences`, `test_example_161_page_gives_a_non_empty_label_sample`: both failed at RED, pass at HEAD. |
| 2 | `test_fence_and_heading_lines_inside_each_html_block_type_are_kept[type-1..7]`: 7 cases, LF and CRLF. |
| 3 | `test_html_block_start_after_a_paragraph_and_a_table_inside_one`: 3 cases. |
| 4 | `test_html_block_ends_with_its_container`: block quote and list item cases. |
| 5 | DoD green; `git diff origin/main...HEAD -- bench/knowledge/tests/test_trace.py` removes no line; `test_every_number_in_the_report_comes_from_summary_or_labels` passes. |
| 6 | Report lines 23 and 222 carry the note dated `2026-11-16` with the card id; module docstring of `trace.py` names HTML blocks; numstat of `summary.json` and `labels.jsonl` is empty; one entry each in `CHANGELOG.md` and `CHANGELOG-history.md`. |

Differential (self-check, not DoD; script `diff_html.py` in the session scratchpad, not the repo): `classify_lines` against markdown-it-py 4.0 (`commonmark` + `table`) on random documents of HTML, fence, heading, table and container lines. markdown-it-py's type 4 accepts only uppercase letters and its type 7 does not exclude `pre`, `script`, `style`, `textarea`; the run patched both to the spec text. Mismatches per 20,000 documents: seeds 1-3 give 19, 18, 22 at HEAD against 3883, 3949, 3935 for the base probe; seeds 4-5 with a larger vocabulary give 8 and 12. Every remaining mismatch was traced to one of three markdown-it-py behaviours outside CommonMark, each present with the base probe too: its table rule runs before list items (`- a | b` then a delimiter is a table), it accepts a `>` continuation marker indented 4 columns, and it reads a lazy line indented 4 columns inside a nested block quote as indented code.

### Attempt 2

Repair of R3 decision 1 on ecc1096 (`.review/T1-KBEVAL-HTMLBLOCK.r3.1.b19ef8d0.json`, block): F1 `html-closing-tag-exclusion`, F2 `html-trail-removal`. No card amendment.

Commits: 5e00473 (RED tests), 1bd51ff (fix), 59daca5 (changelog wording), and the commit adding this section.

- F1: the type 7 pattern leaves out only an OPEN tag named `pre`, `script`, `style` or `textarea` (`<pre/>` is no block); a closing tag of those names alone on its line starts a type 7 block, as in cmark and commonmark.js.
- F2: `classify_lines` records the lines of each HTML block (the start line, content lines and an explicit end line; not the blank line that ends type 6 or 7), and the Evidence Trail pass starts a trail only at a `## Evidence Trail` line outside them.

RED at 5e00473 (`python -m pytest bench/knowledge/tests/test_trace.py -q` against ecc1096's probe): exit 1, 7 failed, 116 passed. Failing: `test_closing_tag_of_a_type_1_name_alone_on_its_line_starts_a_type_7_block[</pre>, </script>, </style>, </textarea>]`, each `['</pre>', 'Fenced line after the block is excluded.'] != ['</pre>\n```', 'After the block ends here.']` (tag varies); `test_evidence_trail_line_inside_an_html_block_starts_no_trail[type-6-ends-at-blank-line, type-1-explicit-end, type-2-explicit-end]`, each with only the start line surviving, e.g. `['<div>'] != ['<div>\n## Evidence Trail\nHTML prose sentence has enough words.', 'Later prose sentence has enough words to count.']`. Output sha256 e4862b1df6ccf4b716adee5b67e3e2233926574c20305affe2ad54ea0a5c0131.

DoD (card command, main checkout `.venv`): exit 0; `All checks passed!`, `154 passed`. Output sha256 b63c5146295866328a257eed9066d954a6be8807bc72eecde03291d671ab9e74.

`python -m pytest bench/knowledge/tests -q`: 395 passed, 4 skipped.

`git diff --numstat origin/main...HEAD` before this section:

```
10	0	CHANGELOG-history.md
1	0	CHANGELOG.md
93	8	bench/knowledge/probes/trace.py
147	0	bench/knowledge/tests/test_trace.py
2	2	docs/knowledge-baseline.md
33	0	specs/tasks/T1-KBEVAL-HTMLBLOCK.md
```

| Acceptance | Evidence |
|---|---|
| 1 | Example 161 tests unchanged and passing. |
| 2 | 7 type cases unchanged and passing; new `test_closing_tag_of_a_type_1_name_alone_on_its_line_starts_a_type_7_block` (4 cases, F1). |
| 3 | Unchanged and passing. |
| 4 | Unchanged and passing. |
| 5 | DoD green; `git diff origin/main...HEAD -- bench/knowledge/tests/test_trace.py` removes 0 lines; the number scan passes. New `test_evidence_trail_line_inside_an_html_block_starts_no_trail` (3 cases, F2). |
| 6 | Unchanged from attempt 1; `summary.json` and `labels.jsonl` numstat empty; changelog entries reworded in place (still one each). |

Differential rerun, reference patched to leave out only open tags of the four names: seeds 1-3 give 19, 17, 20 mismatches per 20,000 documents at HEAD against 309, 331, 313 for ecc1096's probe under the same reference; seeds 4-5 (larger vocabulary) give 7 and 12. Every remaining mismatch falls in the three markdown-it-py classes named in attempt 1. The differential does not exercise F2: markdown-it-py has no Evidence Trail rule.
