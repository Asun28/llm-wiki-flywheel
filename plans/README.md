# plans/ (Stage 3: Build, plan mode)

Work starts with a written plan produced in plan mode (read-only on the
codebase) and approved by an engineer before any implementation.

- T0 / T0-bugfix: the light form (Files that change, Order of work, Risks,
  Proof). One card.
- T1 / T2: the full form with sections 1-10 and the task split table
  `| Card | Priority | Output | depends_on | Parallel window | Freeze point |`.
  Cards are projected from that table (`aidlc cards project <plan>`), then a
  human signs off before they are written to `specs/tasks/`.
- `aidlc plan check <file>` runs Definition-of-Ready gates: files named,
  ordered steps, no open TBD/TODO markers, proof stated, existing files
  resolve, task split present. `needs-clarification` lists the questions.
- If implementation departs from the plan, update the plan in the same
  commit. Never delete a section; write "none this version".

Metrics: share of changes merging from the first implementation pass; time
from plan approval to merged PR (leading); rework cycles and how often the
merged diff matches the committed plan (lagging).
