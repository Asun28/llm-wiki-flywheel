"""Advisory floors for pins in requirements.txt (T0-DEPS-ADVISORIES).

Each entry is a package whose Dependabot alerts this card closed. The floor is the
highest first-patched version among that package's advisories, as the GitHub advisory
records state it, so a pin below the floor reopens at least one of those alerts.
"""

import re
from pathlib import Path

import pytest
from packaging.utils import canonicalize_name
from packaging.version import Version

REQUIREMENTS = Path(__file__).resolve().parents[1] / "requirements.txt"

# package -> (highest first-patched version, advisories it closes)
ADVISORY_FLOORS = {
    "soupsieve": (
        "4.0.0",
        (
            "GHSA-6655-6qjp-jx7x",  # fixed 3.0.2
            "GHSA-7g44-g9rc-x53w",  # fixed 3.0.2
            "GHSA-mmhr-3c5m-f64f",  # fixed 4.0.0
            "GHSA-4j63-6c4x-wfg4",  # fixed 2.10.0
        ),
    ),
    "dnspython": ("2.9.2", ("GHSA-vvf4-9x63-8xvv",)),
    "opentelemetry-api": ("1.45.2", ("GHSA-mf5v-w3w3-f6cg",)),
}

_PIN = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([^\s;#]+)")


def pinned_versions(text: str) -> dict[str, Version]:
    """Map each `name==version` line of a requirements file to its version."""
    pins: dict[str, Version] = {}
    for line in text.splitlines():
        match = _PIN.match(line)
        if match:
            pins[canonicalize_name(match.group(1))] = Version(match.group(2))
    return pins


def floor_violation(text: str, name: str) -> str | None:
    """Return why `name`'s pin in `text` misses its advisory floor, or None if it meets it."""
    floor, advisories = ADVISORY_FLOORS[name]
    pinned = pinned_versions(text).get(canonicalize_name(name))
    if pinned is None:
        return f"{name}: no `{name}==<version>` pin in requirements.txt"
    if pinned < Version(floor):
        return f"{name}=={pinned} is below {floor}, which fixes {', '.join(advisories)}"
    return None


@pytest.mark.parametrize("name", sorted(ADVISORY_FLOORS))
def test_requirements_pin_meets_advisory_floor(name):
    assert floor_violation(REQUIREMENTS.read_text(encoding="utf-8"), name) is None


def test_floor_check_rejects_a_pin_below_the_floor():
    text = "soupsieve==3.0.2\ndnspython==2.9.2\nopentelemetry-api==1.45.2\n"
    assert floor_violation(text, "soupsieve") == (
        "soupsieve==3.0.2 is below 4.0.0, which fixes GHSA-6655-6qjp-jx7x, "
        "GHSA-7g44-g9rc-x53w, GHSA-mmhr-3c5m-f64f, GHSA-4j63-6c4x-wfg4"
    )


def test_floor_check_rejects_a_missing_pin():
    text = "soupsieve==4.1.1\nopentelemetry-api==1.45.2\n"
    assert floor_violation(text, "dnspython") == (
        "dnspython: no `dnspython==<version>` pin in requirements.txt"
    )
