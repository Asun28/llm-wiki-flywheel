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

    def run(
        self,
        *args: str,
        out: Path | None = None,
        defaults: bool = True,
        io_encoding: str = "utf-8",
    ):
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
        env = dict(os.environ, PYTHONIOENCODING=io_encoding)
        env.pop("KB_PROJECT_ROOT", None)
        proc = subprocess.run(
            argv,
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            encoding=io_encoding,
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


@pytest.fixture
def runner():
    """The runner module loaded in-process, for tests that inject a filesystem error."""
    import importlib.util

    name = "kbeval_run_under_test"
    spec = importlib.util.spec_from_file_location(name, RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses look the module up while the class is built
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(name, None)
