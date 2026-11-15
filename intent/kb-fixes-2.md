---
slug: kb-fixes-2
title: "Fix the four open issues #175, #163, #157 and #148"
author: asun28 (engineer)
status: accepted
created: 2026-11-15T18:52:00Z
source: human
---

# Intent: Fix the four open issues #175, #163, #157 and #148
Author: asun28 (engineer). Status: accepted.

## Problem
Four GitHub issues are open. One is a product defect in `src/kb/`; three are
defects in the knowledge bench (`bench/knowledge/`).

1. #175: three wiki page writers read a page with `Path.read_text` and write it
   back with `atomic_text_write`, so a page saved with CRLF is written back with
   LF: `kb.ingest.pipeline._update_existing_page_body` (re-ingest References and
   Context editing), `kb.ingest.evidence.append_evidence_trail`, and
   `kb.lint.checks.dead_links.fix_dead_links` (`kb lint --fix`). `wiki/` holds
   124 CRLF pages. #168 fixed the same pattern in the linker (PR #174) with a
   one-splice restore, which these writers cannot reuse: they make several
   separate edits per write and add new lines.
2. #163: `bench/knowledge/tests/test_baseline.py::plain()` takes an image
   token's raw `content` as its alt text, so a figure name in alt text with
   markup (`![Rows with an **owner** ruling: 2](x.png)`) is not matched and the
   figure is not counted.
3. #157: the trace probe's block classifier does not track HTML blocks, so a
   fence marker inside an HTML block opens a false fence and drops the prose
   after the block.
4. #148: six error paths of the bench runner `bench/knowledge/run.py`: an
   unreadable probes directory reads as empty; a read-only stale record
   survives a failed probe on Windows; a failure diagnostic can stop the run
   when stdout and stderr share a closed pipe; restoring a broken stdout exits
   120; an `--out` that cannot be created raises a traceback; an `--out` equal
   to or inside `--wiki`, `--raw` or the checkout's `wiki/`, `raw/` or `.data/`
   is accepted and a probe writes into that input directory.

## Proposed outcome
- A CRLF page edited by re-ingest, an evidence append, `kb lint --fix` or the
  linker is written back with its own line ends; added lines take the page's
  most-used line end; LF pages are unchanged byte for byte.
- `test_baseline.py` counts a figure whose name in image alt text holds markup.
- The trace probe keeps the prose after an HTML block that holds a fence
  marker, heading or table line.
- The bench runner reports each of the six error paths with a defined exit code
  and no traceback, and never lets a probe write inside an input directory.
- Each issue is closed with a comment naming the merged PR and the evidence.

## Affected users and systems
- `src/kb/ingest/pipeline.py`, `src/kb/ingest/evidence.py`,
  `src/kb/lint/checks/dead_links.py`, `src/kb/compile/linker.py`, plus a new
  shared helper in `src/kb/utils/`.
- `bench/knowledge/tests/test_baseline.py`, `bench/knowledge/probes/trace.py`,
  `bench/knowledge/run.py`, `docs/knowledge-baseline.md`.
- Users: anyone who re-ingests a source, runs `kb lint --fix` or `kb compile`
  on a wiki with CRLF pages; operators of `python bench/knowledge/run.py`.

## Constraints
- Development target only. No release, no data migration of existing wikis.
- Existing tests must not be weakened; the 27 linker CRLF tests from #168
  must pass unchanged.
- Match on LF-normalised text and restore line ends only at write
  (docs/LESSONS.md, 2026-11-15 T0-KBFIX-CRLF).
- `kb.review.refiner.refine_page` converts CRLF to LF on purpose and is out of
  scope.

## Decisions (owner, 2026-11-16)
The owner took the recommended answer to each of the four intake questions.
- #175 added lines: a line the edit adds takes the page's most-used line end
  (a tie takes LF); every unchanged line keeps its own end.
- #175 helper scope: one shared helper in `kb.utils` restores line ends after
  any number of edits, and all four writers use it, the linker included.
- #157 HTML block lines: lines inside an HTML block stay prose, as today; the
  fix only stops them changing how later lines are classified.
- #157 baseline: the committed Phase 0 numbers (`bench/knowledge/summary.json`,
  `docs/knowledge-baseline.md`) stay as the before-reference; the report's two
  #157 lines get a dated note that it was fixed after Phase 0. Rerun numbers go
  in the arc evidence and the issue comment.
- Dependabot: the owner asked to include open Dependabot alerts. At intake all
  238 alerts are `fixed` and `pip-audit -r requirements.txt` reports no known
  vulnerability, so no card is added. (Alert #105, nltk, is returned by the
  API's `state=open` filter while its own record says `fixed`; `nltk==3.10.4`
  is above the fix version 3.10.1.)

## Open questions
- (none)
