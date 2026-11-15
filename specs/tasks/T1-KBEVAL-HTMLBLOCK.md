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
