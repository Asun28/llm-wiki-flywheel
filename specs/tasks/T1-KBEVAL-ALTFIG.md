---
id: T1-KBEVAL-ALTFIG
title: "The baseline report test reads a figure in image alt text by its rendered text, so a formatted second figure is counted (#163)"
status: todo
branch: T1-KBEVAL-ALTFIG
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-ALTFIG
plan_ref: plans/kb-fixes-2.md#order-of-work
allow_paths:
  - bench/knowledge/tests/test_baseline.py
  - CHANGELOG.md
  - CHANGELOG-history.md
  - specs/tasks/T1-KBEVAL-ALTFIG.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_baseline.py -q
dod_exit: 0
requirements:
  - R1. The helper `plain()` in `bench/knowledge/tests/test_baseline.py` shall render an `image` child as `plain(child)` (the rendered text of its alt children, by `plain`'s own rules), not as the token's raw `content`.
acceptance:
  - 1. `test_baseline.py`: inserting `![Rows with an **owner** ruling: 2](x.png)` after the report's owner-ruling figure makes `figure_errors` non-empty, and so does `![Rows with a *null* final: 2](x.png)` after the null-final figure; both cases fail before the fix (RED receipt). [R1] [dod arm 2]
  - 2. Same file: `plain()` of an inline holding `![a **b** `c`](x.png)` returns `a b c`, and an image whose alt holds raw HTML (`![a <b>x</b>](x.png)`) leaves the HTML out as for other inline runs. [R1] [dod arm 2]
  - 3. Every existing test in `test_baseline.py` passes, the existing image-alt case of `test_label_checks_find_figures_by_name_and_label_rows_in_any_table` included; no existing test is edited; `git diff --numstat origin/main...HEAD -- docs/knowledge-baseline.md bench/knowledge/summary.json bench/knowledge/labels.jsonl` is empty. [dod arm 2]
  - 4. `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id (reviewer-verified).
depends_on: []
budget: 60
forbid: [a change to the report, `summary.json` or `labels.jsonl`, weakening an existing check]
non_goals: [markup inside link text other than image alt (already rendered by markdown-it children), reference-style images resolved from a definition elsewhere (rendered the same way, not tested separately)]
diagnosis:
  root_cause: "`plain()` (test_baseline.py:316-325) appends `child.content` for `image` children; markdown-it-py keeps the image's alt as raw source in `content` and its parsed text in `children`, so `**owner**` stays in the text the name pattern searches."
  same_class: "`rendered()` collects text through `plain()` for every inline run, table cells included, so fixing `plain()` covers alt text in tables too. No other helper in the file reads `child.content` of an image."
hygiene: "Run the DoD with the main checkout's `.venv` active. Finding of R3 decision 4/4 on T0-KBEVAL-RULINGS (candidate `10a12d9`), deferred by the owner."
---

# T1-KBEVAL-ALTFIG

## Deliverable
`plain()` renders an image's alt text from its parsed children, so the Labels figure checks find a figure name written with markup in alt text.

## Why
Issue #163: a second figure hidden in formatted alt text shows as "Rows with an owner ruling: 2" when the image does not load, but the check misses it. The report itself is correct; the gap is in the test helper.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_baseline.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
