---
# id naming (machine-checked): T<stage>-<UPPER-KEBAB>, regex ^T\d+-[A-Z0-9]+(-[A-Z0-9]+)*$
#   OK: T0-SCAFFOLD / T2-API / T3-REVIEW-GATE   NOT: t1-foo / T1_FOO / my-task
#   id == file name == branch == worktree leaf. The T?-EXAMPLE below is a deliberate placeholder
#   violation; validators skip files starting with "_". Required fields first, optional block after.
id: T?-EXAMPLE
title: one-sentence deliverable
status: todo            # todo | in-progress | in-review | merged
branch: T?-EXAMPLE
worktree: C:\wt\<repository>\T?-EXAMPLE   # = <WorktreeRoot>\<id>; empty worktreeRoot = <platform root>\<main checkout name>, see aidlc.config.json
allow_paths:            # the paths this card may change; the ship scope gate blocks anything outside them
  - path/to/...
dod_command: npm test -- --run <tests>   # the card's own tests and fast static checks; the full suite runs in CI; only tools CI already has, or that the card installs
dod_exit: 0
review_gate: codex {verdict:pass}   # optional; declaring it invokes the independent reviewer
acceptance:            # CLOSED numbered list the reviewer judges against; required once review_gate is set
  # A change of 30 src lines or fewer gets a card of about 400 words or fewer.
  # Doc text is proved with `(reviewer-verified against the diff)` unless a program reads that exact text.
  # A card that reads input or adds I/O names in these items each input form and failure path it handles; non_goals names each form it leaves out and what the code does with it (refuse, ignore or fail closed).
  - 1. <one fact that means done, naming the assertion that covers it>. [dod arm 1]
  - 2. <the next one; a gap outside this list is [FOLLOW-UP], not a block>. [dod arm 2]
# ------- Optional below. Absent is silent; no gate asks for any of these.
# requirements:        # optional `R<n>.` items, one EARS line each, exactly one `shall`; cite `[R<n>]` in acceptance
#   - R1. The <system> shall <observable response>.
# depends_on: []       # prerequisite card ids (topological order decides what may run in parallel)
# parallelizable_with: []   # parallel card ids; their allow_paths must not overlap (machine-checked)
# plan_ref: plans/<slug>.md#section   # this card's plan section
# budget: 400          # declared net changed lines (added+deleted); a merge gate only on the scaffold ship path, advisory on github and dry-run
# size_exception: "<who approved, why>"   # [CARD-SIZE] blocks a card that changes src/ with a budget over 250 unless this records the approval; split the card instead where you can
# tier: S              # acceptance tier; computed from allow_paths, may only be RAISED, never lowered
# sweep: "<the grep you ran and the faces it found>"   # REQUIRED above five allow_paths
# forbid: [<hard boundaries this card may not cross: network, credentials, frozen contracts>]
# non_goals: [<a capability this card deliberately does not build>]
# diagnosis:           # bugfix cards only: repair the root cause, not the symptom
#   root_cause: <why it broke, not how it showed>
#   same_class: <sibling call sites checked too?>
# dod_assert: <the machine-checkable assertion the command produces, in prose>
# hygiene: <mutation/test hygiene note>
# doc_sync: <docs to bring back in step after merge>
# superseded_by: <the later card that deliberately deleted what this card asserted>
# ------- aidlc extensions (optional)
# tdd: false           # explicit non-TDD exemption (pure docs/config); default true requires a RED receipt
# freeze: true         # shared interface/contract card: runs alone before its dependents
# migration_phase: expand   # expand | deploy | backfill | verify | contract; contract never runs first
# resources: [db:main, port:8080]   # shared resources beyond paths; two cards sharing one never run in parallel
---

# T?-EXAMPLE

## Deliverable
(The single deliverable, matching this card's section of the plan.)

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
<dod_command>
```
- Expected exit code: 0
- Assertion: <...>
