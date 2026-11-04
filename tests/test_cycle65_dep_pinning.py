"""Test that dependency pinning is correctly applied (AC11).

Cycle 67 Step 15: floor bumped from 3.1.47 → 3.1.49 (CVE-2026-44244,
GitConfigParser.set_value newline injection). Updated assertion to use
a forward-compatible regex so future patch-level CVE bumps (e.g.,
cycle 68+ to 3.1.50) don't require lockstep test updates — only the
floor minor must stay at 3.1.x with patch ≥49 (cycle 67 baseline).
Ceiling <3.2 unchanged per cycle 65 AC11 contract.

2026-11-05 dependency sweep: range moved to >=3.2.1,<3.3 because six advisories
are fixed only in 3.2.0 / 3.2.1 (highest: CVE-2026-114145). The floor-plus-next-minor
ceiling shape from cycle 65 AC11 is unchanged.
"""

import re
from pathlib import Path


def test_gitpython_has_floor_and_ceiling():
    """Assert GitPython has a floor at or above 3.2.1 (2026-11-05 sweep baseline)
    and a next-minor ceiling (<3.3) in requirements.txt.
    """
    requirements_path = Path("requirements.txt")
    content = requirements_path.read_text(encoding="utf-8")

    # Find the GitPython line
    gitpython_line = None
    for line in content.splitlines():
        if line.startswith("GitPython"):
            gitpython_line = line
            break

    assert gitpython_line is not None, "GitPython not found in requirements.txt"

    # Floor must be >=3.2.X with X >= 1 (2026-11-05 sweep, CVE-2026-114145 patch).
    floor_match = re.search(r">=3\.2\.(\d+)", gitpython_line)
    assert floor_match is not None, (
        f"GitPython line missing forward-compatible floor `>=3.2.<patch>`: {gitpython_line}"
    )
    patch = int(floor_match.group(1))
    assert patch >= 1, (
        f"GitPython floor patch {patch} below 2026-11-05 CVE-2026-114145 baseline (3.2.1). "
        f"Line: {gitpython_line}"
    )
    # Next-minor ceiling, same shape as cycle 65 AC11.
    assert "<3.3" in gitpython_line, f"Ceiling version <3.3 not found in: {gitpython_line}"
