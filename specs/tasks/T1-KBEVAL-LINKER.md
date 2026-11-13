---
id: T1-KBEVAL-LINKER
title: "The `linker` probe reports precision and recall of `inject_wikilinks` on a committed labelled case set, in total and per category"
status: todo
branch: T1-KBEVAL-LINKER
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-LINKER
plan_ref: plans/kb-baseline.md#order-of-work
allow_paths:
  - bench/knowledge/probes/linker.py
  - bench/knowledge/data/linker/cases.jsonl
  - bench/knowledge/tests/test_linker.py
  - specs/tasks/T1-KBEVAL-LINKER.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_linker.py -q
dod_exit: 0
requirements:
  - R1. `cases.jsonl` shall hold one JSON object per line with `id` (unique), `category`, `title`, `target_id`, `body`, `should_link` and `why`, with at least 10 rows in each of six categories. `should_link` true, `proper-mention` (an English body names the titled thing) and `cjk-in-cjk` (a title in Chinese characters inside a Chinese sentence, with a Chinese character on each side of it). `should_link` false, `common-word` (the title is also an ordinary English word and the body uses the ordinary word), `case-variant` (the body holds the title's letters in another case with another meaning), `inside-code` (the title occurs only inside inline code or a fenced block), `already-linked` (the body already holds a wikilink to `target_id`).
  - R2. IF a line is not a JSON object, lacks a field, repeats an `id`, or holds a `category` outside the six or a `should_link` that is not its category's value, THEN the probe shall raise `ValueError` naming the file and the line number.
  - R3. For each row the probe shall make a wiki under `ctx.tmp` with one page of `target_id` and `title` and one page whose body is `body`, call `kb.compile.linker.inject_wikilinks(title, target_id, wiki_dir)`, and count the row as linked when the second page holds more wikilinks to `target_id` after the call than before it.
  - R4. The arm `inject` shall report `cases` and the metrics `tp`, `fp`, `fn`, `tn`, `precision`, `recall` and, for each category, `rows_<category>` and `linked_<category>`, where positive is `should_link` true and a ratio with a zero denominator is 0.
  - R5. The probe shall return `invariants` equal to `["I11"]`.
acceptance:
  - 1. `test_linker.py`: the committed `cases.jsonl` loads under R1 and R2, every category has at least 10 rows, and every `cjk-in-cjk` title has a Chinese character directly before and after it in the body. [R1] [dod arm 2]
  - 2. Same file, one test per cause of R2: `ValueError` whose message holds the file name and the line number. [R2] [dod arm 2]
  - 3. Same file, a four-row fixture with `inject_wikilinks` replaced by a stub that edits the page for chosen rows: the arm reports the hand-computed `tp`, `fp`, `fn`, `tn`, `precision`, `recall`, `rows_<category>` and `linked_<category>`; a row whose body already held one link and holds one after the call is not linked. [R3] [R4] [dod arm 2]
  - 4. Same file, the committed set run through the runner with the real function: exit 0, the arm `measured`, `cases` equal to the row count, `tp + fp + fn + tn` equal to `cases`, `invariants` equal to `["I11"]`. [R3] [R4] [R5] [dod arm 2]
  - 5. Each row's `why` names what the body text means, and each `common-word` and `case-variant` body uses the word in its other meaning (reviewer-verified against the diff). [R1]
depends_on: [T1-KBEVAL-HARNESS]
parallelizable_with: [T1-KBEVAL-CONTRADICTION, T1-KBEVAL-RETRIEVAL, T1-KBEVAL-CITATIONS, T1-KBEVAL-TRACE, T1-KBEVAL-REBUILD, T1-KBEVAL-PROVENANCE]
budget: 450
forbid: [any change under src/kb/ templates/ or tests/, a model call or network request, a threshold or pass/fail judgement on precision or recall, removing or relabelling a row because of what `inject_wikilinks` did with it]
non_goals: [`inject_wikilinks_batch` (same pattern builder, not measured here), the effect of a wrong link on PageRank or search ranking, links on the owner's real wiki (no labels exist for them), a Chinese title next to Latin letters or digits, any fix]
hygiene: "`inside-code` and `already-linked` are controls the current code is expected to pass; they stay in the set so a later change to the matcher is checked against them. Write the case set before the first run. Run the DoD with the main checkout's `.venv` active."
---

# T1-KBEVAL-LINKER

## Deliverable
The first number for lead 3 of `intent/kb-baseline.md` and for invariant I11: how often an inserted link is wrong, and how often a Chinese title is missed.

## Why
`_build_title_pattern` compiles `\b<title>\b` with `re.IGNORECASE` and no disambiguation. The lead says a title such as "Go" links from "we go ahead", and that `\b` does not separate a Chinese title from the Chinese characters around it. Wrong links become graph edges that ranking reads, so the precision of the linker bounds the quality of the graph.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_linker.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
