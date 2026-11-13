# specs/ (Stage 2: Design) and specs/tasks/ (cards)

`specs/<slug>.md` is the requirements-and-design spec written once from an
accepted intent, with organisational skills loaded (security, UX, brand,
compliance) so policy is applied while writing, not discovered in review.

- Requirements use EARS, one `shall` per line, cited as `[R<n>]` by
  acceptance items: Ubiquitous / WHEN / WHILE / IF ... THEN / WHERE.
- Numbers need `[SOURCE: ...]` evidence or a closed `[TBD: question]`.
- Flagged concerns route to policy owners; the product owner signs off.
- `aidlc spec validate <file>` checks structure, EARS shape and citations.

`specs/tasks/<id>.md` are task cards: the machine-checkable projection of an
approved plan. The plan stays the single source of truth; a card is a thin
executable pointer (`dod_command`, `allow_paths`, `acceptance`). Ids are
immutable once a file exists. Validate with `aidlc cards validate`.

Metrics: time between intent and spec commits (leading); spec commits after
the first plan commit (lagging rework).
