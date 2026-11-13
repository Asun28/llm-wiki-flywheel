"""Fixtures for the knowledge-bench runner tests.

Every test runs `bench/knowledge/run.py` in a subprocess against probe files
written into a temporary probes directory, so `bench/knowledge/probes/` stays
untouched and each run starts with a fresh interpreter and environment.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
RUNNER = REPO / "bench" / "knowledge" / "run.py"


@dataclass
class Bench:
    """Temporary directories for one runner invocation and helpers to drive it."""

    root: Path
    probes: Path
    wiki: Path
    raw: Path
    out: Path

    def probe(self, name: str, source: str) -> Path:
        path = self.probes / f"{name}.py"
        path.write_text(textwrap.dedent(source), encoding="utf-8")
        return path

    def run(self, *args: str, out: Path | None = None, defaults: bool = True):
        argv = [sys.executable, str(RUNNER)]
        if defaults:
            argv += [
                "--probes-dir",
                str(self.probes),
                "--wiki",
                str(self.wiki),
                "--raw",
                str(self.raw),
                "--out",
                str(out or self.out),
            ]
        argv += list(args)
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        env.pop("KB_PROJECT_ROOT", None)
        proc = subprocess.run(
            argv,
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        proc.output = proc.stdout + proc.stderr
        return proc

    def records(self, out: Path | None = None) -> list[str]:
        directory = out or self.out
        if not directory.is_dir():
            return []
        return sorted(p.name for p in directory.glob("*.json"))


@pytest.fixture
def bench(tmp_path: Path) -> Bench:
    dirs = {name: tmp_path / name for name in ("probes", "wiki", "raw")}
    for path in dirs.values():
        path.mkdir()
    return Bench(root=tmp_path, out=tmp_path / "out", **dirs)
