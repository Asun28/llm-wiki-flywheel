---
id: T0-KBFIX-QUERYDIR
title: "kb query and kb_query(use_api=true) use the default wiki directory when wiki_dir is omitted (#188)"
status: todo
branch: T0-KBFIX-QUERYDIR
worktree: D:\wt\llm-wiki-flywheel\T0-KBFIX-QUERYDIR
allow_paths:
  - src/kb/query/engine.py
  - tests/test_kbfix_query_default_wiki_dir.py
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T0-KBFIX-QUERYDIR.md
dod_command: ruff check src/ tests/ && python -m pytest tests/test_kbfix_query_default_wiki_dir.py tests/test_query.py tests/test_mcp_core.py tests/test_cli.py tests/test_cycle70_prompt_safety.py tests/test_v4_11_query_integration.py tests/test_utils.py -q
dod_exit: 0
requirements:
  - R1. WHEN `query_wiki` is called without `wiki_dir` and at least one page matches, it shall load `purpose.md` from the default wiki directory (`kb.query.engine.WIKI_DIR`, read at call time) and reach the model call, not raise `QueryError`.
  - R2. WHEN `kb query "<question>"` is run without a wiki directory argument and a page matches, it shall print the answer and exit 0.
  - R3. WHEN `kb_query(question, use_api=True)` is called and a page matches, it shall return the answer text, not an `Error:` string.
acceptance:
  - 1. `test_kbfix_query_default_wiki_dir.py`: in the `tmp_kb_env` sandbox with one concept page and a `purpose.md` written as bytes, `KB_DISABLE_VECTORS=1`, and `kb.query.engine.call_llm` replaced by a recorder that returns a fixed answer, `query_wiki("What is hydration?")` with no `wiki_dir` returns that answer, and the recorded prompt contains the `purpose.md` text. [R1] [dod arm 2]
  - 2. Same file: in the same sandbox with the same stub, `CliRunner().invoke(cli, ["query", "What is hydration?"])` exits 0 and its output contains the fixed answer. [R2] [dod arm 2]
  - 3. Same file: in the same sandbox with the same stub, `kb_query("What is hydration?", use_api=True)` returns text that contains the fixed answer and does not start with `Error`. [R3] [dod arm 2]
  - 4. Every DoD test file passes and no existing test is edited; `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` each carry one entry under this card id; the counts in the `State` line of `CLAUDE.md` equal `scripts/verify_docs.py` output on the candidate (reviewer-verified).
depends_on: []
budget: 80
sweep: "`load_purpose` callers: `ingest/extractors.py:357` guards `None`; `lint/augment/orchestrator.py:98` receives a `wiki_dir` already resolved at line 126; `query/engine.py:1093` is the only unguarded caller. Other `wiki_dir` uses inside `query_wiki`'s body handle `None`: `engine.py:146,586,990` use `wiki_dir or WIKI_DIR`, `engine.py:264` guards `wiki_dir.parent`, `engine.py:925` derives `raw_dir` only when `wiki_dir` is set (unchanged here). Production callers that omit `wiki_dir`: `cli.py:271`, `mcp/core.py:338`. Tests that call `query_wiki` or `kb_query` in the DoD: `test_query.py`, `test_mcp_core.py`, `test_cli.py`, `test_cycle70_prompt_safety.py`, `test_v4_11_query_integration.py`, `test_utils.py` (`load_purpose`)."
forbid:
  - "a change to `load_purpose` or its signature"
  - "resolving `wiki_dir` at the top of `query_wiki`: it would change the `raw_dir` derivation at `engine.py:925` for the default call"
  - "any edit to an existing test"
  - "a model call or network request in tests"
non_goals:
  - "#189 (citations outside the prompt context): separate issue"
  - "making `load_purpose` accept `None`: its callers own the default, as `extractors.py:357` does"
diagnosis:
  root_cause: "`_query_wiki_body` passes its `wiki_dir` argument unchanged to `load_purpose(wiki_dir)` at `src/kb/query/engine.py:1093`. For the default `wiki_dir=None`, `load_purpose` evaluates `None / \"purpose.md\"` (`src/kb/utils/pages.py:210`) and raises `TypeError`, re-raised as `QueryError` (`engine.py:909`) before the model call. Reproduced on main 36dab28 in the `tmp_kb_env` sandbox with one concept page, `KB_DISABLE_VECTORS=1` and no API key: `query_wiki(\"What is hydration?\")` raises `QueryError: unsupported operand type(s) for /: 'NoneType' and 'str'` with a `TypeError` cause. Fix: guard the call as `extractors.py:357` does, `load_purpose(wiki_dir if wiki_dir is not None else WIKI_DIR)`, using the module-level `WIKI_DIR` that `engine.py:146,586,990` already use and the sandbox rebinds."
  same_class: "#187 (`kb_stats` -> `get_graph(None)`), fixed in T0-KBFIX-STATSDIR. No other `load_purpose` caller can receive `None` (see sweep)."
hygiene: "Run the DoD with the main checkout's `.venv` active. Write fixtures as bytes. Every call runs inside `tmp_kb_env`. Stub `kb.query.engine.call_llm`, not the Anthropic client. RED: acceptance 1, 2 and 3 fail on the unfixed code (`QueryError`, CLI exit 1, `Error:` string)."
---

# T0-KBFIX-QUERYDIR

## Deliverable
`kb query "<question>"` and `kb_query(..., use_api=True)` with no wiki directory argument load `purpose.md` from the default wiki directory and reach the model call instead of failing with `unsupported operand type(s) for /: 'NoneType' and 'str'`.

## Why
Issue #188. The default invocation of `kb query` fails for every user whenever a page matches the question.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check src/ tests/ && python -m pytest tests/test_kbfix_query_default_wiki_dir.py tests/test_query.py tests/test_mcp_core.py tests/test_cli.py tests/test_cycle70_prompt_safety.py tests/test_v4_11_query_integration.py tests/test_utils.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 1. RED at 5c639f6: `test_query_wiki_without_wiki_dir_reads_the_default_purpose`, `test_cli_query_without_wiki_dir_exits_zero` and `test_kb_query_use_api_without_wiki_dir_returns_the_answer` 3 failed (`QueryError: unsupported operand type(s) for /: 'NoneType' and 'str'` from `kb/query/engine.py:909`).

| Acceptance item | Proving test or command | Result |
|---|---|---|
| 1. `query_wiki()` with no `wiki_dir`: answer returned, default `purpose.md` in the prompt | `test_query_wiki_without_wiki_dir_reads_the_default_purpose` | pass |
| 2. `kb query` exits 0 with the answer | `test_cli_query_without_wiki_dir_exits_zero` | pass |
| 3. `kb_query(use_api=True)` returns the answer, not `Error:` | `test_kb_query_use_api_without_wiki_dir_returns_the_answer` | pass |
| 4. DoD green, no existing test edited, CHANGELOG / CHANGELOG-history entries, CLAUDE.md counts | DoD below; `git diff main --stat -- tests/` lists only the new file; `python scripts/verify_docs.py`: 3991 tests, 229 files, docs in sync | pass (reviewer-verified) |
