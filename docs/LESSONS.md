# Lessons

Durable rules this repository learned from its own review blocks and
incidents. Append-only: one dated line per lesson, written at CLOSE of the
card that learned it, only when a review block or an incident taught a
rule the playbook did not already state. Past lines are never rewritten;
a superseded lesson gets a new line that names it. PREPARE reads this
file once per card.

Format: `- YYYY-MM-DD <card or incident>: NEVER|ALWAYS|NOTE <rule> (source: <verdict, PR or incident ref>)`

## Lessons
- (none yet)
- 2026-11-14 T1-KBEVAL-HARNESS-3: ALWAYS make a process-wide monkeypatch of an os function pass every argument form it does not test (no argument, an int file descriptor) to the real function: POSIX shutil.rmtree calls os.scandir(fd), so a path-only fake passes on Windows and fails on Linux CI (source: PR #147, CI run 43568859972)
- 2026-11-14 T1-KBEVAL-CONTRADICTION: ALWAYS record a card's RED against an importable stub that returns a well-formed wrong result, so every test fails on an assertion: a RED made only of missing-file errors runs no assertion and R3 blocks it as missing-behavioral-red (source: T1-KBEVAL-CONTRADICTION R3 decision 1, PR #150)
- 2026-11-14 T1-KBEVAL-RETRIEVAL: ALWAYS write a data-loader rule that says each or every with all(), never any(), and test it with a list holding one non-matching item: R3 found an any() that accepted a query whose words were split across relevant pages (source: T1-KBEVAL-RETRIEVAL R3 decision 1, PR #151)
- 2026-11-14 T1-KBEVAL-LINKER: ALWAYS count a probe's measured effect on the raw output, not through a helper that strips code or markup first: extract_wikilinks hid links written inside code, so the inside-code control could not fail (source: T1-KBEVAL-LINKER R3 decision 1, PR #152)
