---
id: T0-KBFIX-MASKREDOS
title: "`_CODE_MASK_RE` scans an unclosed markdown link or image opener in linear time and matches the same spans as before (#167)"
status: merged
branch: T0-KBFIX-MASKREDOS
worktree: D:\wt\llm-wiki-flywheel\T0-KBFIX-MASKREDOS
allow_paths:
  - src/kb/compile/linker.py
  - tests/test_kbfix_code_mask_redos.py
  - tests/test_kbfix_linker_headings.py
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T0-KBFIX-MASKREDOS.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_code_mask_redos.py tests/test_kbfix_linker_headings.py tests/test_compile.py tests/test_ingest.py tests/test_lint.py tests/test_cycle19_inject_wikilinks_batch.py -q
dod_exit: 0
requirements:
  - R1. WHEN a text holds a link or image opener (`[...](` or `![...](`) with no closing `)`, followed by 5,000 characters, `_CODE_MASK_RE` shall finish scanning it in under 1 second.
  - R2. `_CODE_MASK_RE` shall match the same spans as the pre-fix pattern on every input, so `_mask_code_blocks` and `_mask_for_injection` return the same results as before.
  - R3. WHEN a wiki page body holds such an unclosed opener, `inject_wikilinks` and `fix_dead_links` shall each return their normal result for that page instead of stalling.
acceptance:
  - 1. `test_kbfix_code_mask_redos.py`: `_mask_code_blocks` on `see [x](` and on `see ![x](`, each followed by 5,000 characters holding spaces and newlines, runs in a subprocess that finishes within 30 s, reports a masking time under 1 s and returns an empty masked list. [R1] [dod arm 2]
  - 2. Same file: `inject_wikilinks("Hydration", "concepts/hydration", wiki_dir=...)` on a page whose body is `Hydration matters. See [x](` plus 5,000 characters returns `["entities/bread"]`, and the page then holds `[[concepts/hydration|Hydration]]`; run in a subprocess that finishes within 30 s. [R3] [dod arm 2]
  - 3. Same file: `fix_dead_links(wiki_dir)` on a page holding `[[missing/page]]` and the same unclosed opener returns one fix and the page no longer holds `[[missing/page]]`; run in a subprocess that finishes within 30 s. [R3] [dod arm 2]
  - 4. Same file: the `finditer` spans of `_CODE_MASK_RE` equal those of the pre-fix pattern (copied verbatim into the test) on every length-5 product of a 12-token alphabet (248,832 inputs; the count is asserted) and on the literal inputs of the existing `_CODE_MASK_RE` / `_mask_code_blocks` tests in `test_compile.py` and the 512 generated cases of `test_kbfix_linker_headings.py`; the list of disagreeing inputs is empty. [R2] [dod arm 2]
  - 5. Every existing test in the DoD passes. The only edit to an existing test file is the comment at `tests/test_kbfix_linker_headings.py:316-317`, which stops saying the pattern backtracks exponentially (reviewer-verified against the diff). [R2] [dod arm 2]
  - 6. `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the counts in the `State` line of `CLAUDE.md` equal `scripts/verify_docs.py` output on the candidate (reviewer-verified).
depends_on: []
budget: 200
sweep: "Seven paths: one src file, one new and one existing test file, three doc files, this card. `_CODE_MASK_RE` is used at linker.py:68 (`_mask_code_blocks`) and :94 (`_mask_for_injection`). `_mask_code_blocks` callers: ingest/pipeline.py:918 and :960 (References / Context editing) and lint/checks/dead_links.py:82 (`fix_dead_links`). `_mask_for_injection` callers: linker.py:270, :307 (`inject_wikilinks` peek + locked) and :519, :551 (`inject_wikilinks_batch` chunk peek + locked). A grep of src/ for a quantified group inside a repeated group (`\\)\\)[*+]`, `[*+]\\)[*+]`, `[*+]\\|...\\)[*+]`) finds only linker.py:48-49."
forbid:
  - "a change to the fence, inline-code or bracket alternatives of `_CODE_MASK_RE`"
  - "a change to `_mask_code_blocks`, `_mask_for_injection` or their callers"
  - "any other edit to an existing test"
  - "a model call or network request in tests"
non_goals:
  - 'the quadratic scan of many unclosed `[` openers by `\[(?:[^\]]*)\]` (0.42 s for 20,000 `[`; unchanged by this card)'
  - "CommonMark-correct link parsing (parentheses nested deeper than one level stay unmatched, as before)"
  - "the CRLF read defect of issue 168 (its own goal)"
diagnosis:
  root_cause: "The link and image alternatives end in `\\((?:[^()]*|\\([^()]*\\))*\\)`: the repeated group's first branch is itself `[^()]*`, so a run of non-parenthesis characters can be split between the inner and outer repetition in 2^n ways, and the engine tries all of them before the missing `)` fails the match. Measured on main: 0.0007 s at 14 trailing characters, 0.21 s at 22, doubling per character."
  same_class: "No other regex in src/ repeats a group whose branch is itself quantified (sweep grep). Every caller reaches the pattern through `_mask_code_blocks` or `_mask_for_injection`, so the one pattern change fixes ingest, both injectors and `fix_dead_links`."
hygiene: "Run the DoD with the main checkout's `.venv` active. RED: acceptance 1-3 fail on the unfixed code with an AssertionError naming the 30 s subprocess timeout, not with an import or collection error; acceptance 4 passes on both (its oracle is the pre-fix pattern) and is shown to fail under a mutation that changes a span. Run the full suite locally before SHIP (shared helper; lesson T1-KBFIX-SHRINK-2)."
---

# T0-KBFIX-MASKREDOS

## Deliverable
One pattern change in `src/kb/compile/linker.py`: the link and image alternatives of `_CODE_MASK_RE` consume one character or one parenthesised group per repetition (`\((?:[^()]|\([^()]*\))*\)`), so an unclosed `](` is rejected in linear time and every matched span stays the same.

## Why
Issue #167. One malformed link in a wiki page stalls ingest, wikilink injection and `kb lint --fix`.

The span set cannot change: after `(`, a valid end is a `)` preceded by text whose parentheses are all paired at depth one; a second such `)` would have no `(` to pair with, so each start has at most one match under either form. A pre-card differential found 0 disagreements over 269,568 generated inputs.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_code_mask_redos.py tests/test_kbfix_linker_headings.py tests/test_compile.py tests/test_ingest.py tests/test_lint.py tests/test_cycle19_inject_wikilinks_batch.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
