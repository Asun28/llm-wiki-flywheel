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
