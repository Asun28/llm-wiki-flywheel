---
id: T0-DEPS-ADVISORIES
title: "`requirements.txt` pins soupsieve 4.1.1, dnspython 2.9.2 and opentelemetry-api 1.45.2, closing the six open Dependabot alerts, and a test holds each pin at or above its advisory's first patched version"
status: todo
branch: T0-DEPS-ADVISORIES
worktree: D:\wt\llm-wiki-flywheel\T0-DEPS-ADVISORIES
allow_paths:
  - requirements.txt
  - tests/test_dep_advisory_floors.py
  - SECURITY.md
  - CHANGELOG.md
  - CHANGELOG-history.md
  - CLAUDE.md
  - specs/tasks/T0-DEPS-ADVISORIES.md
dod_command: ruff check tests/test_dep_advisory_floors.py && python -m pytest tests/test_dep_advisory_floors.py tests/test_cycle65_dep_pinning.py -q && python -m pip install --dry-run --ignore-installed --quiet -r requirements.txt
dod_exit: 0
requirements:
  - R1. `requirements.txt` shall pin `soupsieve==4.1.1`, `dnspython==2.9.2` and `opentelemetry-api==1.45.2`, and no other line of the file shall change.
  - R2. `tests/test_dep_advisory_floors.py` shall fail when the pinned version of soupsieve, dnspython or opentelemetry-api in `requirements.txt` is below the first patched version of its advisories (4.0.0, 2.9.2, 1.45.2), and when a package's pin line is missing.
  - R3. `SECURITY.md` (`Last reviewed`), `CHANGELOG.md` (Unreleased) and `CHANGELOG-history.md` shall each record this sweep under this card id, naming the alerts and GHSA ids, and the `State` line of `CLAUDE.md` shall match the collected test count and test-file count.
acceptance:
  - 1. `test_dep_advisory_floors.py` passes on the candidate and fails on `origin/main` for all three packages (RED receipt). A test feeds the checker a pin line below the floor and one with the package absent, and both fail. [R2] [dod arm 2]
  - 2. `git diff origin/main...HEAD -- requirements.txt` changes exactly the three lines of R1. [R1] (reviewer-verified against the diff)
  - 3. `pip install --dry-run --ignore-installed -r requirements.txt` resolves the full pin set with no conflict (soupsieve 4 against `beautifulsoup4==4.14.3`, which declares `soupsieve>=1.6.1`; dnspython against `email-validator`). [R1] [dod arm 3]
  - 4. The doc entries of R3 are present; `scripts/verify_docs.py` reports docs in sync on the candidate. [R3] (reviewer-verified against the diff)
depends_on: []
budget: 120
sweep: "Seven paths, one new test file and this card. `grep -rn` over src/ and tests/ for bs4, BeautifulSoup, soupsieve, dns, opentelemetry, markdownify and markitdown imports finds none: the three packages are transitive (soupsieve via beautifulsoup4 under crawl4ai, markdownify, markitdown and obsidiantools; dnspython via email-validator) or an unused pin (opentelemetry-api has no dependent in the venv). Alert #105 (nltk, GHSA-qx2g-xrx7-vfh8, fixed in 3.10.1) is already fixed by the `nltk==3.10.4` pin; the API reports it `fixed`. Code scanning has no analysis configured and secret scanning has no open alert, so neither has work here."
forbid: [a change to any requirements.txt line other than the three of R1, a change to pyproject.toml, a change under src/, an accepted-advisory exception or pip-audit ignore flag, an edit to an existing test]
non_goals: [setting up code scanning (the untracked `.github/workflows/security-scanners.yml` belongs to the owner and stays untouched), a general dependency upgrade, bumping beautifulsoup4]
hygiene: "Run the DoD with the main checkout's `.venv` active. The dry-run resolver arm needs network access to PyPI and installs nothing."
doc_sync: SECURITY.md
---

# T0-DEPS-ADVISORIES

## Deliverable
Three pin bumps in `requirements.txt` that close the six open Dependabot alerts on the repository's Security page, plus a regression test that keeps each pin at or above its advisory floor.

| Alert | Severity | Package | Advisory | First patched |
|---|---|---|---|---|
| #243 | high | dnspython | GHSA-vvf4-9x63-8xvv | 2.9.2 |
| #242 | medium | opentelemetry-api | GHSA-mf5v-w3w3-f6cg | 1.45.2 |
| #241 | high | soupsieve | GHSA-6655-6qjp-jx7x | 3.0.2 |
| #240 | medium | soupsieve | GHSA-7g44-g9rc-x53w | 3.0.2 |
| #239 | high | soupsieve | GHSA-mmhr-3c5m-f64f | 4.0.0 |
| #238 | medium | soupsieve | GHSA-4j63-6c4x-wfg4 | 2.10.0 |

soupsieve goes to 4.1.1 rather than 4.0.0: 4.1 and 4.1.1 fix further quadratic-time selector paths (`nth ... of S`, `:has(~ ...)`, `:placeholder-shown`, `:lang()`) that are in the same class as #238 and #239.

## Acceptance (DoD = command + exit code + assertion; paired with the closed `acceptance:` list)
```powershell
ruff check tests/test_dep_advisory_floors.py && python -m pytest tests/test_dep_advisory_floors.py tests/test_cycle65_dep_pinning.py -q && python -m pip install --dry-run --ignore-installed --quiet -r requirements.txt
```
- Expected exit code: 0
- Assertion: the floor tests pass and the full pin set resolves with no conflict.

## Attempt evidence
| Item | Proof | Result |
|---|---|---|
| 1 | `pytest tests/test_dep_advisory_floors.py`: RED at 8948f12 (old pins) 3 failed on the floor assertion, 2 checker tests passed; on the candidate 5 passed | pass |
| 2 | `git diff origin/main...HEAD -- requirements.txt`: exactly `soupsieve` 2.9 → 4.1.1, `dnspython` 2.9.0 → 2.9.2, `opentelemetry-api` 1.45.1 → 1.45.2 | pass |
| 3 | DoD arm 3, `pip install --dry-run --ignore-installed --quiet -r requirements.txt`: exit 0; `.venv` on the new pins: `pip check` clean, `pip-audit` no known vulnerabilities | pass |
| 4 | CHANGELOG.md, CHANGELOG-history.md, SECURITY.md entries; CLAUDE.md 3855 tests / 220 files; `python scripts/verify_docs.py`: docs in sync | pass |
