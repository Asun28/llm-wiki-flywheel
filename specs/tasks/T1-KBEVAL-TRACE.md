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

## Attempt 3 evidence

R3 decision 2 blocked `3d88d14` with 4 findings. RED `cae6d84`, GREEN `5be80c9`. For this attempt, R3's literal text decides every rule it states. CommonMark is used only to recognise the blocks R3 excludes. Where the attempt-2 section above says container markers are trimmed or that a setext heading ends the trail, this section replaces it.

### Commits
- `cae6d84` RED: corrected and new block rows, run against `3d88d14`. 17 failed, all on `AssertionError`; 76 passed.
- `5be80c9` GREEN: 94 passed. It adds the row `fence-in-a-second-ordered-item` after mutation N18 survived the RED set. That row also fails on `3d88d14`.

### Findings
| Finding | Fix | Tests |
|---|---|---|
| 1 table-row-filter | A GFM table needs an unescaped `\|` in both the header and the delimiter row, plus equal cell counts | `no-pipe-in-either-row-is-prose` (the reviewer's input), `header-without-pipe-is-prose`, `delimiter-without-pipe-is-prose` |
| 2 fence-state-parsing | One column cursor `(pos, col, rem)` for every indent measurement (container continuation, list content, fence open and close, ATX, setext, table block starts, indented code). A tab advances to the next multiple of 4. The columns of a tab that `>` plus its optional space, or a list marker, consumes only in part count as indentation. | `tab-after-blockquote-marker-is-indent` (the reviewer's input), `tab-after-list-marker-is-indent`, `tab-indented-fence-in-list-item` (control) |
| 3 sentence-rule-overreach | `page_sentences` cuts at every R3 sentence end and strips white space, nothing else. Container tracking only decides excluded lines. | the corrected rows below |
| 4 evidence-trail-boundary-overreach | The trail starts only at a line equal to `## Evidence Trail` and ends only at the next level-2 ATX heading. A `## ` line inside a fenced block is not a heading (R3 says "heading"), so it ends nothing. | `trail-starts-only-at-the-exact-line`, `trail-ends-at-a-level-two-atx-heading-with-closing-hashes`, `trail-heading-inside-fence-does-not-end-it`, `trail-not-ended-by-setext-or-level-three` (setext and `### ` do not end the trail; the final sentence is excluded), `trail-line-inside-a-fence-starts-the-trail` |

### Corrected tests (each decided by R3's text)
- `ordered-list-markers`: was `["First item text.", "Second item text."]`, now `["1.", "First item text.", "2.", "Second item text."]`. R3: a `.` followed by white space is a sentence end, so `1.` is a piece; R4 counts it short.
- `list-marker-period-inside-a-sentence`: now `["1.", "First item\n2.", "Second item text."]`. Same clause.
- `quoted-sentence-over-two-lines`: now `["> This quoted sentence\n> spans two lines."]`. R3 strips white space only, so the `>` stays.
- `table-in-list-item`, `fence-in-list-item`: the item sentences now keep `- `. Same clause.
- `setext-in-blockquote`, `thematic-break-after-blockquote`, `atx-in-blockquote-and-list-item`: the quoted sentences now keep `> `. Same clause.
- `evidence-trail-with-closing-hashes`: replaced by `trail-starts-only-at-the-exact-line`. R3: the trail starts at "the line `## Evidence Trail`", so `## Evidence Trail ##` starts nothing and the entry under it is kept. The closing-hash end moved to `trail-ends-at-a-level-two-atx-heading-with-closing-hashes`.
- `evidence-trail-ended-by-setext-level-two`: replaced by `trail-not-ended-by-setext-or-level-three`. R3: the trail ends at "the next `## ` heading".
- `evidence-trail-heading-inside-fence-does-not-end-it`: renamed `trail-heading-inside-fence-does-not-end-it`; the expectation is unchanged.
- `setext-wins-over-one-cell-table`: renamed `dash-underline-under-a-pipe-line-is-setext`. A `---` line has no pipe, so under finding 1 it can no longer be a table delimiter and there is no precedence left to test. The expectation is unchanged.

### Rule-to-clause list (every rule the probe applies to page text)
- Page files: R1 says every `*.md` file in a subdirectory of `ctx.wiki`, id `<subdirectory>/<stem>`; the code reads files whose path relative to `ctx.wiki` has a directory part, id = that path without `.md`.
- Decoding: R1 says a file whose frontmatter does not parse is `pages_unparsed`; the code decodes the bytes as strict UTF-8 and counts a failure there.
- Frontmatter: R1 and R3 say "frontmatter"; the code reads the YAML block between a first line `---` and the next `---` line (the kb page convention). It counts as unparsed an unclosed block, any load error (`YAMLError`, `ValueError`, `TypeError`) and a non-mapping. A page whose first line is not `---` has no frontmatter.
- Refs: R1 says the `source` field is the list of refs; the code reads a list as the refs, any other non-empty value as one ref, and a missing, null, empty-string or empty-list field as no ref.
- Body: R3 says the text after the frontmatter; the code starts at the offset after the closing `---` line.
- Lines: CommonMark recognition of an R3 block: a line ends at `\n`, `\r\n` or `\r`. Lines are what the block rules classify.
- Fenced code blocks: CommonMark recognition of an R3 block: fenced code. Covers opening and closing fences, the info-string rule, closing length and character, and end at the container's end.
- ATX and setext headings: CommonMark recognition of an R3 block: heading lines.
- GFM tables: CommonMark (GFM) recognition of an R3 block: table rows, meaning the header, delimiter and rows, with a pipe in both header and delimiter and equal cell counts.
- Blockquotes, list items, lazy continuation, paragraph-interruption rules, indented code (4+ columns is not a fence or heading), thematic breaks (a `---` after a blank line is not a setext underline), tab columns: CommonMark recognition of the three R3 blocks inside and next to containers. These lines are classified, not removed.
- Evidence Trail start: R3 says "from the line `## Evidence Trail`"; the code starts at a line equal to `## Evidence Trail`. That includes such a line inside a fenced block: R3 names the line, not a heading.
- Evidence Trail end: R3 says "to the next `## ` heading or the end"; the code ends at the next line recognised as a level-2 ATX heading, which a line inside a fenced block is not.
- Removed text ends a piece: R8 says `start` and `end` cut the sentence out of the page file; the code cuts pieces only inside runs of consecutive kept lines, so no sentence spans removed text.
- Sentence ends: R3 says `.`, `!`, `?` followed by white space or the end of a line, and `。！？` anywhere; the code cuts after each match of `[.!?](?=\s|\Z)|[。！？]` in a run (a run's end is a line end).
- Strip and numbering: R3 says pieces are stripped and numbered from 0 in order; the code strips white space, numbers every non-empty piece from 0, and keeps container markers as text. A piece that is only white space holds no sentence and gets no number.
- Short: R4 says under 20 characters, or under 8 with no ASCII letter; the code does exactly that.
- Containment: R5 says the share of lower-cased `\w+` word 5-grams, or of character 8-grams with no ASCII letter, found in the page's text sources; the code does exactly that, each source searched on its own. A sentence with no n-gram is counted short.

I found no other rule on page text. Removed in this attempt: container-marker trimming, the list-marker exception to sentence ends, setext and top-level-only trail bounds, and the trail start by heading text.

### Construct matrix changes from attempt 2
- **Table:** a pipe is now required in the header and in the delimiter row (`no-pipe-in-either-row-is-prose`, `header-without-pipe-is-prose`, `delimiter-without-pipe-is-prose`).
- **Tabs:** column rule with partial tabs (`tab-after-blockquote-marker-is-indent`, `tab-after-list-marker-is-indent`, `tab-indented-fence-in-list-item`).
- **List items:** a fence in a second ordered item is a fence, not lazy paragraph text (`fence-in-a-second-ordered-item`).
- **Evidence Trail:** literal bounds (the five `trail-` rows).
- **Container markers:** kept as text.
- **Unchanged from attempt 2:** fence, ATX and setext rows. Not recognised, kept as prose because R3 does not exclude them: HTML blocks, link reference definitions, indented code and thematic breaks. Not implemented: the rule that a list item may begin with at most one blank line.

### Mutation checks (one at a time, not committed)
| Mutation | Caught by |
|---|---|
| P1 table needs no pipe | the three pipe rows |
| P2 pipe required only in the header | `delimiter-without-pipe-is-prose` |
| P3 pipe required only in the delimiter | `header-without-pipe-is-prose` |
| P4 a partly consumed tab consumed whole | both tab-after-marker rows |
| P5 a tab's remaining columns not counted as indent | both tab-after-marker rows |
| P6 trail starts at any heading with the text | `trail-starts-only-at-the-exact-line` |
| P7 trail ended by any ATX level | `trail-not-ended-by-setext-or-level-three` |
| P8 trail never ends | 5 tests |
| P9 trail also ended by a setext heading | `trail-not-ended-by-setext-or-level-three` |
| P10 `>` and `-` stripped from sentence starts | 11 rows |
| P11 a list-marker period does not end a piece | `ordered-list-markers`, `list-marker-period-inside-a-sentence` |
| P12 trail never entered | 7 tests |
| N1, N2, N3, N5, N6, N7, N8, N9, N21 (attempt-2 mutations still applicable) | each caught (1 to 9 tests) |
| N18 paragraph-interruption rule applied when the paragraph's container did not match | `fence-in-a-second-ordered-item` (survived before that row was added) |

### Demo run, before (`3d88d14`) and after (`5be80c9`)
```
before: band_high=1 band_mid=4 band_low=66 sentences=71 sentences_short=3  sample_pages=10 sample_sentences=20
after:  band_high=1 band_mid=5 band_low=67 sentences=73 sentences_short=19 sample_pages=10 sample_sentences=20
```
These equal the attempt-1 numbers. Refs and templates did not change. `sentences_short` rose by 16 because list markers (`1.`, `2.` and so on) are R3 sentence pieces again. The run exits 0 with no `guarded directory changed:` line.

## Attempt 4 evidence

R3 decision 3 blocked `196a022` with 2 findings. RED `c461d24`, GREEN `f32819e`. The attempt-3 rule stands: R3's text decides every rule it states, and CommonMark only recognises the blocks R3 excludes.

### Commits
- `c461d24` RED: 7 new tests run against `196a022`. 7 failed, all on `AssertionError`; 94 passed. The 7 are 5 block rows and 2 sample-level tests (the reviewer's empty-item input and an Arabic-Indic digit marker).
- `f32819e` GREEN: 102 passed. It adds the row `ideographic-space-line-is-not-blank` after mutation Q6 showed the space-and-tab blank rule untested. That row also fails on `196a022`.

### Findings
| Finding | Fix | Tests |
|---|---|---|
| 1 empty list item survives a blank line | A list item that began with a blank line and has no content yet ends at the next blank line (CommonMark 0.31.2, List items: "a list item can begin with at most one blank line") | `empty-item-ends-at-a-blank-line` (the reviewer's input), `test_sample_holds_the_sentences_commonmark_keeps[empty-item-then-blank-line]` |
| 2 `\d` matches Unicode digits | `ORDERED` uses `[0-9]{1,9}`. Every blank-line test uses space and tab only (`is_blank`, and the table cell trim). | `non-ascii-digit-is-not-a-list-marker`, `test_sample_holds_the_sentences_commonmark_keeps[arabic-indic-digit-marker]`, `ideographic-space-line-is-not-blank` |

Regex audit of the CommonMark patterns:
- `FENCE_OPEN`, `FENCE_CLOSE`, `ATX`, `SETEXT`, `THEMATIC`, `TABLE_DELIMITER`, `BULLET`: white space is `[ \t]` only.
- `ORDERED`: digits are `[0-9]`.
- `LINE`: CommonMark line ends `\n`, `\r\n` and `\r`.
- `FENCE_OPEN` keeps `re.DOTALL`; it only matters for an info string, and lines carry no line end. No pattern uses `\w`, `\s` or `\d`.
- Unicode classes remain only where R3 or R5 name them: `SENTENCE_END` (`\s` for R3's white space, `。！？`), `WORD` (R5's `\w+`), and the sentence strip (R3's white space).

### Differential check (scratch only; nothing of it is committed)
The probe imports neither markdown-it-py nor marko.
- **Method:** a scratch script parses each snippet with `MarkdownIt("commonmark").enable("table")`. It marks as excluded every line in the `map` of a `fence`, `heading_open` or `table_open` token at any depth, and compares line by line with `classify_lines` (the Evidence Trail switched off, since it is R3 text, not CommonMark).
- **Inputs:** all block snippets in `test_trace.py` (`BLOCK_CASES`, `EN_BODY`, `ZH_BODY`), plus generated combinations under fixed seeds. The generator covers:
  - containers: `>` with none, one or two spaces or a tab; `-`, `*`, `+`, `1.`, `1)`, `2.`, `10)` with 1 to 5 spaces or a tab; empty items with and without a following blank line; nesting both ways; lazy lines;
  - fences: backtick and tilde, 3 to 5 characters, info strings with and without a backtick, 0 to 4 columns of indent, unclosed fences;
  - ATX headings with 1 to 7 `#` and setext headings;
  - tables with and without outer pipes, and mismatched cell counts.
- **Tiebreaker:** for each disagreement, marko 2.2.2 (CommonMark 0.31.2 plus GFM), with block line ranges taken from its parser. marko is not the primary reference because it departs from the spec in two places the tests cover. It consumes a tab after `>` whole, so it reads `tab-after-blockquote-marker-is-indent` as a fence. It also treats a U+3000 line as blank.

Counts:
- **First run** (attempt-3 probe `196a022`, seed 20261114, 641 cases = 41 test snippets + 600 generated): 45 disagreements.
- **Final runs** (probe `f32819e`, seeds 20261114, 7 and 99, each 1547 cases = 47 test snippets + 1500 generated, 4641 cases in all): 58 disagreements (21, 16, 21).

| Class | Count | What |
|---|---|---|
| (a) probe bug | 0 left; 4 found and fixed in this attempt | empty item at a blank line (finding 1); a line indented 4+ columns ends a table; a lazy line is not a table header; a line indented 4+ columns is not a table header. Each has a committed row. Finding 2 (Unicode digits) was not generated and has its own rows. |
| (b) markdown-it-py differs from CommonMark/GFM | 52 (19, 14, 19) | On every disputed line the probe equals marko. Kinds listed below. |
| ruled by decision 2 | 6 (the same 2 test rows in each seed) | `delimiter-without-pipe-is-prose` and `dash-underline-under-a-pipe-line-is-setext`: markdown-it-py and marko both read a table there. The probe follows the decision-2 ruling that the header and the delimiter row each need an unescaped pipe. The GFM spec states no such rule (https://github.github.com/gfm/#tables-extension-). |
| (c) construct R3 does not exclude, both keep | 0 | Indented code, HTML blocks and thematic breaks are kept on both sides, so they produce no disagreement. |

(b) kinds:
- **Lazy continuation:** markdown-it-py builds a table from, or keeps a table going through, lines that CommonMark treats as lazy paragraph continuation inside a blockquote or list item (https://spec.commonmark.org/0.31.2/#lazy-continuation-line).
- **Cell-count mismatch in a container:** inside a list item or blockquote, markdown-it-py recognises a table whose header and delimiter cell counts differ. GFM: "The header row must match the delimiter row in the number of cells. If not, a table will not be recognized" (https://github.github.com/gfm/#tables-extension-).
- **Five or more spaces after a list marker:** the item starts with indented code (https://spec.commonmark.org/0.31.2/#list-items, rule 2). markdown-it-py reads a table from that line and the next.
- **Block-quote marker indented 4+ columns** relative to its container, after an empty list item: it is not a block-quote marker (https://spec.commonmark.org/0.31.2/#block-quote-marker, up to 3 spaces of indent). markdown-it-py opens a quote and a fence there.
- **Fence after a lazy line:** a fence inside an ordered item after a lazy `----` line. markdown-it-py ends the item; CommonMark keeps the fence in the item, and marko agrees.

### Mutation checks for the new rules (one at a time, not committed)
| Mutation | Caught by |
|---|---|
| Q1 list digits match any Unicode digit | `non-ascii-digit-is-not-a-list-marker`, sample `arabic-indic-digit-marker` |
| Q2 an empty item survives a blank line | `empty-item-ends-at-a-blank-line`, sample `empty-item-then-blank-line` |
| Q3 a line indented 4+ does not end a table | `line-indented-four-ends-a-table` |
| Q4 a lazy line may be a table header | `lazy-line-is-not-a-table-header` |
| Q5 a line indented 4+ may be a table header | `line-indented-four-is-not-a-table-header` |
| Q6 blank means any Unicode white space | `ideographic-space-line-is-not-blank` (survived before that row was added) |

The attempt-3 mutations P1 to P12, plus N1, N2, N3, N5, N6, N7, N8, N9, N18 and N21, were run again on `f32819e`. All are still caught.

### Demo run, before (`196a022`) and after (`f32819e`)
```
before: band_high=1 band_mid=5 band_low=67 sentences=73 sentences_short=19 sample_pages=10 sample_sentences=20
after:  band_high=1 band_mid=5 band_low=67 sentences=73 sentences_short=19 sample_pages=10 sample_sentences=20
```
No change: the demo pages contain none of the corrected constructs. Refs and templates did not change. The run exits 0 with no `guarded directory changed:` line.
