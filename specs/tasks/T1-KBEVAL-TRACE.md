---
id: T1-KBEVAL-TRACE
title: "The `trace` probe reports, for a wiki and its raw directory, the lexical containment of body sentences in their listed sources, the extraction templates that define a claim quote or offsets, and a fixed sample of sentences for labelling"
status: todo
branch: T1-KBEVAL-TRACE
worktree: D:\wt\llm-wiki-flywheel\T1-KBEVAL-TRACE
plan_ref: plans/kb-baseline.md#order-of-work
allow_paths:
  - bench/knowledge/probes/trace.py
  - bench/knowledge/tests/test_trace.py
  - specs/tasks/T1-KBEVAL-TRACE.md
dod_command: ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_trace.py -q
dod_exit: 0
requirements:
  - R1. The probe shall read every `*.md` file in a subdirectory of `ctx.wiki` as a page, with the page id `<subdirectory>/<stem>` and the `source` frontmatter field as its list of refs, and shall count a file whose frontmatter does not parse in `pages_unparsed` and a page with no ref in `pages_no_source_field`.
  - R2. The probe shall resolve a ref `raw/<rest>` to `ctx.raw/<rest>` and count every ref in `refs_total` and in exactly one of `refs_text` (a file with suffix `.md`, `.txt` or `.vtt` that decodes as UTF-8), `refs_undecodable`, `refs_non_text` (another suffix), `refs_missing` (no regular file), `refs_url` (starts with `http://` or `https://`) and `refs_outside` (any other ref, or one that resolves outside `ctx.raw`), without a file-system call on a `refs_outside` or `refs_url` ref.
  - R3. The body of a page shall be its text after the frontmatter, without fenced code blocks, heading lines, table rows and the text from the line `## Evidence Trail` to the next `## ` heading or the end, and its sentences shall be the pieces between sentence ends (`.`, `!`, `?` followed by white space or the end of a line; `。`, `！`, `？` anywhere), stripped, numbered from 0 in order.
  - R4. A sentence shorter than 20 characters, or shorter than 8 when it holds no ASCII letter, shall be counted in `sentences_short` and left out of every other count.
  - R5. The containment of a sentence shall be the share of its word 5-grams (lower-cased `\w+` words), or of its character 8-grams when it holds no ASCII letter, that occur in the `refs_text` sources of its page, and a sentence too short to form one n-gram shall be counted in `sentences_short`.
  - R6. The arm `containment` shall report `cases` (the pages read) and `pages_unparsed`, `pages_no_source_field`, `pages_no_text_source`, the six `refs_` counts with `refs_total`, `sentences`, `sentences_short`, `sentences_no_text_source`, and `band_high` (containment at least 0.8), `band_mid` (at least 0.2 and below 0.8) and `band_low` (below 0.2), where the three bands sum to `sentences` minus `sentences_no_text_source`.
  - R7. The arm `templates` shall report `templates_total` (the `*.yaml` files under the checkout's `templates/`) and `templates_with_claim_span` (those in which a field name holds `quote`, `span`, `offset` or `char_`).
  - R8. The probe shall write `trace-sample.jsonl` under `ctx.out` with two sentences from each of the first 30 pages, in ascending order of the sha256 of the page id, that have at least two banded sentences, taking in each page the two with the smallest sha256 of `<page id>:<sentence index>`, one JSON object per line with `page`, `sentence_index`, `start`, `end` (character offsets in the page file), `sha256` (of the sentence text), `band`, `containment`, `sources` and `text`, and shall report `sample_pages` and `sample_sentences` in the `containment` arm.
  - R9. IF `ctx.wiki` holds no page, THEN the `containment` arm shall be `unmeasured` with the reason `no pages` and no sample file shall be written.
  - R10. The probe shall return `invariants` equal to `["I1"]`.
acceptance:
  - 1. `test_trace.py`, a temporary wiki and raw directory: a root-level `index.md` is not a page; a page with broken frontmatter is in `pages_unparsed`; a page with no `source` is in `pages_no_source_field`; the page ids are `<subdirectory>/<stem>`. [R1] [dod arm 2]
  - 2. Same file, one ref of each of the six kinds, with `Path.stat`, `Path.exists` and `open` wrapped: each ref is counted once in its kind and in `refs_total`, and no wrapped call receives the `refs_outside` or `refs_url` ref. [R2] [dod arm 2]
  - 3. Same file: a body with a fenced block, a heading, a table row and an `## Evidence Trail` section followed by another `## ` section yields exactly the expected sentence list, in English and in Chinese, with the expected indexes. [R3] [dod arm 2]
  - 4. Same file: a 19-character sentence and a 7-character Chinese sentence are in `sentences_short`; a 20-character sentence of three words is in `sentences_short` under R5; none of them is in a band. [R4] [R5] [dod arm 2]
  - 5. Same file: a sentence copied from the source has containment 1.0, a sentence sharing no 5-gram has 0.0, a sentence with 2 of 4 word 5-grams in the source has 0.5, and a Chinese sentence copied from the source has 1.0; the band counts and their sum follow R6. [R5] [R6] [dod arm 2]
  - 6. Same file, a temporary templates directory given to the probe: a template with a `quote` field is counted in `templates_with_claim_span` and one with only `key_claims` is not. [R7] [dod arm 2]
  - 7. Same file, a wiki of 32 pages with three banded sentences each: the sample holds 60 rows from the 30 pages with the smallest sha256, the two rows of each page are the ones with the smallest sha256 of `<page id>:<index>`, `start` and `end` cut the sentence out of the page file, and a second run writes a byte-equal file; a wiki of 3 such pages gives 6 rows with `sample_pages` 3. [R8] [dod arm 2]
  - 8. Same file: an empty wiki gives `unmeasured` with `no pages` and no sample file; `demo/wiki` with `demo/raw` run through the runner exits 0 with `invariants` equal to `["I1"]`. [R9] [R10] [dod arm 2]
depends_on: [T1-KBEVAL-HARNESS-3]
parallelizable_with: [T1-KBEVAL-CONTRADICTION, T1-KBEVAL-RETRIEVAL, T1-KBEVAL-LINKER, T1-KBEVAL-CITATIONS, T1-KBEVAL-REBUILD, T1-KBEVAL-PROVENANCE]
budget: 500
forbid: [any change under src/kb/ templates/ or tests/, a write under `ctx.wiki` or `ctx.raw`, writing sentence text anywhere but `ctx.out`, a model call or network request, a new dependency such as rapidfuzz, a threshold or pass/fail judgement on a band]
non_goals: [entailment or support (the labels of T1-KBEVAL-BASELINE measure it; containment measures copied wording only), PDF and image sources (counted in `refs_non_text`, not read), fuzzy matching beyond n-gram membership, sentences inside tables and code, symbolic links under `ctx.raw` (a ref through one is read as its target and is not checked for containment in `ctx.raw` beyond the path), any fix]
hygiene: "The definitions of R3 to R5 fix the number; change one only by amending this card. `trace-sample.jsonl` holds text from the wiki that is read, so it is written only under `ctx.out`, which is gitignored by default. Run the DoD with the main checkout's `.venv` active."
---

# T1-KBEVAL-TRACE

## Deliverable
The first numbers for lead 5 of `intent/kb-baseline.md` and for invariant I1: how much of a page's wording is found in its listed sources, whether any extraction template can carry a quote or offsets, and the fixed sample that the baseline card labels.

## Why
`templates/*.yaml` define `key_claims` as plain strings and pages cite sources at file level, so no sentence of the wiki can be checked against a source by a program today. The containment bands show how many sentences a later claim layer could anchor to verbatim source text without a model, and the sample gives the only measure of support in Phase 0 once it is labelled.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check bench/knowledge && python -m pytest bench/knowledge/tests/test_trace.py -q
```
- Expected exit code: 0
- Assertion: every acceptance test above passes.

## Attempt evidence

Attempt 1. RED `ff7df45`, GREEN `a1f1089`. Tests in `bench/knowledge/tests/test_trace.py`.

### Commits
- `ff7df45` RED: the tests plus an importable stub `run(ctx)` that returns measured arms with every metric 0, no sentences, an empty sample file and `invariants: []`, reading nothing and calling no `kb` function. 47 failed, all on `AssertionError`; 1 passed (`containment[too-short]`, where the stub's `None` equals the expected `None`).
- `a1f1089` GREEN: the real probe. 48 passed. The same commit changes two test lines after RED: the 19-character sentence now holds five words (mutation M7 below survived the RED version, because a sentence of three words is also short under R5), and the URL test got plain parameter ids. Both tests still fail against the stub.

### Acceptance
| Item | Proving test | Result |
|---|---|---|
| 1 [R1] | `test_pages_are_md_files_in_subdirectories_with_id_subdirectory_slash_stem`, `test_page_whose_frontmatter_does_not_parse_is_in_pages_unparsed[4]`, `test_page_with_no_ref_is_in_pages_no_source_field[4]`, `test_source_given_as_one_string_is_one_ref` | pass |
| 2 [R2] | `test_one_ref_of_each_kind_is_counted_once_and_outside_and_url_are_never_touched` (Path.stat, Path.exists, open wrapped; asserts the wrappers did see the text and missing refs), `test_ref_outside_raw_is_counted_outside_without_a_file_system_call[8]`, `test_url_ref_is_counted_url_without_a_file_system_call[2]`, `test_utf8_file_with_a_text_suffix_is_a_text_ref[3]`, `test_regular_file_with_another_suffix_is_non_text_and_is_not_read[3]`, `test_ref_with_no_regular_file_is_missing[2]`, `test_text_suffix_that_does_not_decode_as_utf8_is_undecodable` | pass |
| 3 [R3] | `test_body_yields_the_expected_sentences_with_indexes_and_offsets[en,zh]`, `test_offsets_hold_for_a_page_with_crlf_line_ends` | pass |
| 4 [R4] [R5] | `test_short_sentences_are_counted_short_and_in_no_band` (19 chars of five words, 7-char Chinese, 20 chars of three words; 20-char five-word and 8-char Chinese controls are banded) | pass |
| 5 [R5] [R6] | `test_containment_is_the_share_of_ngrams_found_in_a_source[7]` (1.0, 0.0, 0.5, Chinese 1.0, any source, no gram across two files, too short), `test_band_counts_follow_containment_and_sum_to_sentences_with_a_text_source` (also pins the exact R6 metric names), `test_band_edges_are_high_from_0_8_and_mid_from_0_2_using_only_the_pages_sources` | pass |
| 6 [R7] | `test_templates_with_a_quote_span_offset_or_char_field_are_counted` (`ctx.templates`; a field description or YAML comment that mentions quote is not a field name; `.txt` not counted) | pass |
| 7 [R8] | `test_sample_takes_two_rows_from_each_of_the_30_pages_with_smallest_sha` (32 pages, expected pages and indexes computed with hashlib from the fixture ids, offsets cut the page file, byte-equal second run), `test_sample_of_a_small_wiki_takes_every_page_with_two_banded_sentences` (3 pages, one CRLF, plus a page with one banded sentence that is left out) | pass |
| 8 [R9] [R10] | `test_wiki_with_no_page_is_unmeasured_and_writes_no_sample` (a stale sample is removed), `test_runner_on_the_demo_corpus_exits_0_with_invariant_i1` | pass |

### Input forms and failure paths
- Unparsed page: YAML error, unclosed block, non-mapping YAML, non-UTF-8 bytes (one test each).
- No ref: no frontmatter, no `source` key, `source: []`, `source:` null; a single string is one ref.
- `refs_outside`: `raw/../x`, `raw/a/../../x`, `../x`, bare name, `wiki/x`, backslash, absolute path after `raw/`, a non-string ref; each asserts no wrapped call received the path.
- `refs_url`: `http://` and `https://`. `refs_text`: `.md`, `.txt`, `.vtt`. `refs_non_text`: `.pdf`, `.png`, no suffix (stat'd, never opened). `refs_missing`: absent file, a directory named `*.md`. `refs_undecodable`: Latin-1 `.txt`.

### Mutation checks (applied one at a time, not committed)
| Mutation | Caught by |
|---|---|
| M1 containment always 1.0 | 5 tests (containment none/half/no-cross-file-gram, bands, band edges) |
| M2 Evidence Trail kept | sentences en/zh, CRLF offsets |
| M3 sources joined into one text | containment `no-cross-file-gram` |
| M4 sample rows chosen by index, not sha256 | 32-page sample |
| M5 sample pages chosen by id, not sha256 | 32-page sample |
| M6 no lexical outside check | six-kinds test, outside `dotdot`, `nested-dotdot` |
| M7 R4 length rule removed | short-sentence test (survived before the five-word fixture) |
| M8 high band `> 0.8` | band edges |
| M9 stale sample kept on no pages | no-pages test |
| M10 headings kept, M11 fences kept | sentences en/zh, CRLF offsets |
| M12 template field name = whole item text | templates |
| M13 root-level `.md` read as a page | 11 tests |
| M14 sample takes pages with one banded sentence | small-wiki sample |

### Readings of the card fixed in the probe
- A sentence includes its end mark.
- Removed text (fence, heading, table row, Evidence Trail) ends the piece before it, so each sentence is one contiguous span of the page file and R8 offsets cut it out exactly; a piece never joins text across removed lines.
- A ref with `\`, `:` or NUL after `raw/` is `refs_outside` (a Windows drive or separator would otherwise escape `ctx.raw` with no file-system call to detect it).
- Field names of a template are the `extract` entries: the leading identifier of a string (`title (str): ...` gives `title`) or the keys of a mapping.
- `pages_no_text_source` includes pages with no ref.
- The Chinese half of R4 (under 8 characters) can never form an 8-gram, so R5 also makes such a sentence short; no test can separate the two rules for it.

### Demo run
`python bench/knowledge/run.py --probe trace` (demo/wiki, demo/raw): exit 0, no `guarded directory changed:` line.
```
trace containment measured band_high=1 band_low=67 band_mid=5 pages_no_source_field=0 pages_no_text_source=0 pages_unparsed=0 refs_missing=0 refs_non_text=0 refs_outside=0 refs_text=15 refs_total=15 refs_undecodable=0 refs_url=0 sample_pages=10 sample_sentences=20 sentences=73 sentences_no_text_source=0 sentences_short=19
trace templates measured templates_total=11 templates_with_claim_span=1
```
The one template is `book.yaml` (field `quotes`).

## Attempt 2 evidence

R3 (codex, decision 1/2) blocked `dcacd2e` with 6 findings. RED `2cd6322`, GREEN `31e6e55`. The attempt-1 rows above still hold, except that R3 now has the construct matrix below.

### Commits
- `2cd6322` RED: regression tests run against the attempt-1 probe. 27 failed, all on `AssertionError` (an unexpected exception is caught by the `outcome` helper and asserted on, so a crash also fails on an assertion); 57 passed (the 48 earlier tests and 9 control rows that attempt 1 already handled). Two earlier fixtures gained what GFM requires: `EN_BODY` a blank line after its table (otherwise the next prose line is a table row), `ZH_BODY` a delimiter row (otherwise its pipe line is not a table).
- `31e6e55` GREEN: 85 passed. It adds one block row, `list-marker-period-inside-a-sentence`, after mutation N13 survived; that row also fails on `dcacd2e`.

### Findings
| Finding | Fix | Tests |
|---|---|---|
| 1-3 R3 rules were line-based | `classify_lines`: a CommonMark block pass with blockquote and list-item containers, lazy continuation, fences, ATX and setext headings, thematic breaks, GFM tables, indented code | `test_block_constructs_are_recognised_by_commonmark_structure[31 rows]`, each run with LF and CRLF line ends, checking texts, indexes and offsets |
| 4 YAML constructor error | `yaml.YAMLError`, `ValueError` and `TypeError` from loading frontmatter count in `pages_unparsed`; the same for templates (counted, with no claim span) | `test_frontmatter_rejected_by_a_yaml_constructor_is_unparsed_and_other_pages_complete[2026-02-30, 2026-13-01]`, `test_template_rejected_by_a_yaml_constructor_is_counted_without_a_claim_span` |
| 5-6 unreadable counted as missing | Missing only on `FileNotFoundError` or `NotADirectoryError` from `stat` or `open`, or a stat that shows no regular file. Any other `OSError` propagates, so the runner fails the probe. `stat` follows symbolic links, as the card's non-goals require. | `test_permission_error_at_stat_propagates`, `test_permission_error_at_open_propagates`, `test_io_error_during_read_propagates` (EIO from `read`), `test_path_through_a_regular_file_is_missing`, and the attempt-1 missing tests (absent file, directory named `*.md`). The fakes pass every other call through with all its arguments. |

### Construct matrix (each row id is a `BLOCK_CASES` row)
- **GFM table:** header, delimiter and rows removed; rows run to a blank line or a fence, ATX heading or thematic break. Rows: `table-no-outer-pipes`, `table-in-blockquote`, `table-in-list-item`, `table-row-without-pipes-ends-at-heading`, `table-ends-at-blank-line`. Not a table: `pipe-line-without-delimiter-is-prose`, `cell-count-mismatch-is-prose`.
- **Setext heading:** text lines and underline removed. Rows: `setext-equals`, `setext-dash`, `setext-two-lines`, `setext-in-blockquote`. Precedence over a one-cell table delimiter: `setext-wins-over-one-cell-table`.
- **Thematic break:** after a blank line, or after a blockquote paragraph that it ends, `---` is kept text, because R3 does not exclude it. Rows: `thematic-break-after-blank-line`, `thematic-break-after-blockquote`.
- **Fenced code:** removed. Rows: `backtick-info-with-backtick-is-inline-code` (not a fence), `fence-in-blockquote`, `fence-in-list-item`, `unclosed-fence-ends-with-its-blockquote`, `unclosed-fence-ends-with-its-list-item`, `closing-fence-same-character-at-least-as-long`, `closing-fence-with-info-is-content`, `fence-indented-four-is-not-a-fence`.
- **ATX heading:** removed, inside containers too; four spaces of indent is text. Rows: `atx-in-blockquote-and-list-item`, `atx-indented-four-is-text`.
- **Evidence Trail:** a top-level ATX or setext level-2 heading whose text is `Evidence Trail` (closing hashes allowed), up to the next top-level level-2 heading. A heading inside a fence does not end it. Rows: `evidence-trail-with-closing-hashes`, `evidence-trail-heading-inside-fence-does-not-end-it`, `evidence-trail-ended-by-setext-level-two`, plus `EN_BODY` and `ZH_BODY`.
- **Container markers:** `>`, list markers and the indent a container consumes never end a sentence and are trimmed from both of its ends. Inside a multi-line sentence they stay, because a sentence is one contiguous span of the page file. Rows: `ordered-list-markers`, `list-marker-period-inside-a-sentence`, `quoted-sentence-over-two-lines`.

The probe does not recognise these, and keeps them as prose because R3 does not exclude them: HTML blocks, link reference definitions, indented code blocks, and thematic breaks. It also does not implement three rules that do not affect which lines are excluded in the tested cases: the rule that a list item may begin with at most one blank line, partial tab expansion after a container marker, and tables interrupted by a list item (rows continue, as in cmark-gfm). Tabs count to the next multiple of 4 columns.

### Mutation checks for the new rules (one at a time, not committed)
| Mutation | Caught by |
|---|---|
| N1 backtick info string may hold a backtick | `backtick-info-with-backtick-is-inline-code` |
| N2 unclosed fence runs past its container | `unclosed-fence-ends-with-its-blockquote`, `-list-item` |
| N3 setext headings not recognised | 6 rows |
| N4 table delimiter needs a leading pipe | `table-no-outer-pipes`, `table-row-without-pipes-ends-at-heading` |
| N5 no cell-count check | `cell-count-mismatch-is-prose` |
| N6 table rows not continued | 5 rows |
| N7 blockquote is not a container | 7 rows |
| N8 list item is not a container | 6 rows |
| N9 any closing fence length | `closing-fence-same-character-at-least-as-long` |
| N10 ATX closing hashes kept | `evidence-trail-with-closing-hashes` |
| N11 setext level 2 does not end the trail | `evidence-trail-ended-by-setext-level-two` |
| N12 container markers not trimmed | 8 rows |
| N13 a list-marker period ends a sentence | `list-marker-period-inside-a-sentence` (survived before that row was added) |
| N14 frontmatter ValueError not caught | both constructor rows |
| N15 any stat OSError is missing | `test_permission_error_at_stat_propagates` |
| N16 any read OSError is missing | `test_io_error_during_read_propagates` |
| N17 table delimiter checked before setext | 4 rows |
| N18 paragraph-interruption rule applied when the paragraph's container did not match | `ordered-list-markers`, `list-marker-period-inside-a-sentence` |
| N19 template ValueError not caught | template constructor test |
| N20 Evidence Trail never entered | 6 tests |
| N21 ATX heading kept | 7 tests |
| N22 any open OSError is missing | `test_permission_error_at_open_propagates` |

### Demo run, before (`dcacd2e`) and after (`31e6e55`)
```
before: band_high=1 band_mid=5 band_low=67 sentences=73 sentences_short=19 sample_pages=10 sample_sentences=20
after:  band_high=1 band_mid=4 band_low=66 sentences=71 sentences_short=3  sample_pages=10 sample_sentences=20
```
Refs and templates did not change (refs_text=15, refs_total=15, others 0; templates_total=11, templates_with_claim_span=1). The cause: list markers (`1.`, `2.`, ...) used to be cut as short sentences and to split items. They are now container markers. The run exits 0 with no `guarded directory changed:` line.
