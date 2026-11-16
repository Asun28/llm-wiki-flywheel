---
id: T0-KBFIX-CRREF
title: "Ingest refuses a source path whose reference holds a CR or LF (#179)"
status: todo
branch: T0-KBFIX-CRREF
worktree: D:\wt\llm-wiki-flywheel\T0-KBFIX-CRREF
allow_paths:
  - src/kb/ingest/pipeline.py
  - tests/test_kbfix_source_ref_line_break.py
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T0-KBFIX-CRREF.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_source_ref_line_break.py tests/test_kbfix_crlf_writers.py tests/test_kbfix_ingest_template_baseline.py tests/test_ingest.py -q
dod_exit: 0
requirements:
  - R1. WHEN the source reference that `ingest_source` builds holds a CR or an LF, `ingest_source` shall raise `ValueError` before it writes any file.
acceptance:
  - 1. `test_kbfix_source_ref_line_break.py`: with `kb.ingest.pipeline.make_source_ref` patched to return `raw/articles/b\r.md`, `raw/articles/b\r\n.md` and `raw/articles/b\n.md` for a real `raw/articles/b.md`, `ingest_source` raises `ValueError` matching `line break`, whose message holds the reference as its `repr` and no CR or LF character; every file under the test sandbox (wiki pages, `index.md`, `_sources.md`, `log.md`, the hash manifest, `.data/`) keeps its bytes and no file is added. [R1] [dod arm 2]
  - 2. Same file, POSIX only (skipped on Windows, whose file names cannot hold CR or LF): real files `raw/articles/b\r.md` and `raw/articles/b\r\n.md`, ingested with no patch, raise the same `ValueError` and leave the sandbox unchanged. [R1] [dod arm 2]
  - 3. Same file, control: the patched seam returning `raw/articles/b.md` ingests, and the sandbox snapshot then differs (a summary page is added), which shows the snapshot of acceptance 1 detects a write. [dod arm 2]
  - 4. In `_update_existing_page_body`, the comment after the body write says `append_evidence_trail` re-enters `page_lock` under the caller's lock (cycle 81), and the R5 comment (issue 175) above `ref_line` no longer says an ingested `source_ref` can hold a CR (reviewer-verified against the diff).
  - 5. Every DoD test file passes and no existing test is edited; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the counts in the `State` line of `CLAUDE.md` equal `scripts/verify_docs.py` output on the candidate (reviewer-verified).
depends_on: []
budget: 140
sweep: "Six paths: one src file, one new test file, three doc files, this card. `grep -n make_source_ref src/`: `ingest/pipeline.py:1556` (the one ingest call, where the check goes) and `lint/checks/consistency.py:88` (unchanged, see same_class). `grep -n 'acquires its own' src/kb/ingest/pipeline.py`: :1015 is the stale comment the issue names; :1371 and :1985 describe `_update_existing_page`'s own page lock and stay true. No doc under `docs/reference/` lists ingest's refusals, so none changes."
forbid:
  - "a change to `kb.utils.paths.make_source_ref`, `kb.utils.text.yaml_escape` / `yaml_sanitize`, `_update_sources_mapping` or `lint/checks/consistency.py`"
  - "any edit to an existing test"
  - "a model call or network request in tests"
non_goals:
  - "a source reference holding another character that `yaml_sanitize` strips (C0/C1 controls other than TAB/LF/CR, NEL, U+2028, U+2029, BOM, bidi marks): still accepted, and its frontmatter `source:` entry is written without that character (follow-up issue)"
  - "the `source_coverage` lint: a raw file whose name holds CR or LF is still listed as unreferenced, which is true, since it cannot be ingested until renamed"
  - "removing the `_to_lf(source_ref)` conversions in `_update_existing_page_body`: they stay for a direct caller of the helper"
  - "renaming or migrating raw files already on disk"
diagnosis:
  root_cause: "#179's stated symptom does not occur: `_CTRL_CHAR_RE` excludes `\\x0d` and `_BIDI_RE` holds no line-break character, so `yaml_sanitize` keeps the CR and `yaml_escape` writes it as `\\r`; on main abcdd4d, `raw/b\\r.md` and `raw/b\\r\\n.md` both parse back from the frontmatter unchanged. The defect is that `ingest_source` accepts a reference holding a line break at all, which the line-oriented writers cannot keep: `_update_existing_page_body` turns the CR into LF (`_to_lf`, #175 R5), splitting the References line into `- Mentioned in raw/b` and `.md`; `_update_sources_mapping` writes the raw CR into `_sources.md`, its next read (universal newlines) splits that entry, and a re-ingest appends a duplicate entry instead of merging. Owner ruling 2026-11-16: refuse at ingest."
  same_class: "`make_source_ref` has one other caller, `lint/checks/consistency.py:88`, which reads its `ValueError` as 'outside raw_dir'; the check therefore sits in `ingest_source`, right after `pipeline.py:1556` where the reference is built once for the whole ingest, and that caller is unchanged. Nothing is written before that line (the first write is the `stage=start` jsonl row after it)."
hygiene: "Run the DoD with the main checkout's `.venv` active. Write fixtures as bytes. RED: the three cases of acceptance 1 fail on the unfixed code (DID NOT RAISE); acceptance 3 passes on it as the control. Acceptance 2 is skipped on Windows and runs in CI (ubuntu-latest)."
---

# T0-KBFIX-CRREF

## Deliverable
`ingest_source` raises `ValueError` when the reference built from the source path holds a CR or an LF, before the duplicate check, the manifest reservation or any page write. The message shows the reference through `repr`, so no raw line break reaches a log line.

## Why
Issue #179. The issue reported the frontmatter `source:` entry losing its CR; that does not reproduce (see `diagnosis`). The same reference does break the References line and `wiki/_sources.md`, and the owner chose to refuse such a reference at ingest rather than escape it in every line-oriented writer.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_source_ref_line_break.py tests/test_kbfix_crlf_writers.py tests/test_kbfix_ingest_template_baseline.py tests/test_ingest.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.
