"""Run the knowledge-layer probes and write one JSON record per probe.

Usage: python bench/knowledge/run.py [--probe NAME ...] [--probes-dir DIR]
       [--out DIR] [--wiki DIR] [--raw DIR]

Exit codes: 0 every probe returned a valid result and no guarded directory
changed; 1 a probe failed or a guarded directory changed; 2 usage error.
See bench/knowledge/README.md for the record shape and the probe entry.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

BENCH = Path(__file__).resolve().parent
CHECKOUT = BENCH.parents[1]
STATUSES = ("measured", "unmeasured")


class ProbeError(Exception):
    """The probe module or its return value breaks the probe contract."""


@dataclass
class Context:
    """What a probe's `run(ctx)` receives."""

    tmp: Path
    data: Path
    wiki: Path
    raw: Path
    out: Path

    @staticmethod
    def unmeasured(reason: str) -> dict:
        return {"status": "unmeasured", "reason": reason, "cases": 0, "metrics": {}}


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the knowledge-layer probes.")
    parser.add_argument("--probe", action="append", default=[], help="run only this probe")
    parser.add_argument("--probes-dir", type=Path, default=BENCH / "probes")
    parser.add_argument("--out", type=Path, default=CHECKOUT / "_local" / "knowledge")
    parser.add_argument("--wiki", type=Path, default=CHECKOUT / "demo" / "wiki")
    parser.add_argument("--raw", type=Path, default=CHECKOUT / "demo" / "raw")
    return parser.parse_args(argv)


def find_probes(probes_dir: Path, wanted: list[str]) -> list[Path]:
    """Return the probe files to run, in file-name order; raise ValueError on an unknown name.

    A probe is a regular file (or a link to one) named `*.py` not starting with `_`;
    a directory named `*.py` is not a probe.
    """
    found = {
        p.stem: p for p in probes_dir.glob("*.py") if p.is_file() and not p.name.startswith("_")
    }
    unknown = sorted(set(wanted) - set(found))
    if unknown:
        raise ValueError(f"--probe names no file in {probes_dir}: {', '.join(unknown)}")
    selected = [found[name] for name in set(wanted)] if wanted else list(found.values())
    return sorted(selected, key=lambda p: p.name)


def git_state() -> tuple[str, bool]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(CHECKOUT), *args],
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    return git("rev-parse", "HEAD").strip(), bool(git("status", "--porcelain").strip())


def listing(directories: list[Path]) -> dict[str, tuple[int, int]]:
    """Map each entry path under the directories to (size, mtime in ns).

    Real directories are descended into. Every other entry, including a symbolic
    link to a directory and a Windows junction, is listed by its own lstat and not
    followed. A missing directory lists as empty; any OSError while scanning an
    existing one propagates so the caller can fail the run.
    """
    entries: dict[str, tuple[int, int]] = {}

    def scan(directory: str) -> None:
        with os.scandir(directory) as found:
            for entry in found:
                if entry.is_dir(follow_symlinks=False) and not entry.is_junction():
                    scan(entry.path)
                else:
                    stat = entry.stat(follow_symlinks=False)
                    entries[entry.path] = (stat.st_size, stat.st_mtime_ns)

    for directory in directories:
        if directory.is_dir():
            scan(str(directory))
    return entries


def guarded_listing(directories: list[Path]) -> dict[str, tuple[int, int]] | None:
    """Return the listing, or print which guarded path could not be listed and return None."""
    try:
        return listing(directories)
    except OSError as exc:
        where = exc.filename or ", ".join(str(d) for d in directories)
        say(f"cannot list guarded directory: {where}: {exc.strerror or exc}", sys.stderr)
        return None


def check_number(value: object, where: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProbeError(f"{where} is not a number: {value!r}")
    if not math.isfinite(value):
        raise ProbeError(f"{where} is not finite: {value!r}")


def check_arm(name: object, arm: object) -> dict:
    """Validate one arm and return it in record form."""
    if not isinstance(name, str):
        raise ProbeError(f"arm name is not a string: {name!r}")
    if not isinstance(arm, Mapping):
        raise ProbeError(f"arm {name} is not a mapping")
    status = arm.get("status")
    if status not in STATUSES:
        raise ProbeError(f"arm {name} status is not one of {STATUSES}: {status!r}")
    cases = arm.get("cases")
    if isinstance(cases, bool) or not isinstance(cases, int):
        raise ProbeError(f"arm {name} cases is not an integer: {cases!r}")
    metrics = arm.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ProbeError(f"arm {name} metrics is not a mapping")
    for metric, value in metrics.items():
        if not isinstance(metric, str):
            raise ProbeError(f"arm {name} metric name is not a string: {metric!r}")
        check_number(value, f"arm {name} metric {metric}")
    record = {"status": status, "cases": cases, "metrics": dict(metrics)}
    if status == "unmeasured":
        reason = arm.get("reason")
        if not isinstance(reason, str):
            raise ProbeError(f"arm {name} is unmeasured without a string reason")
        record["reason"] = reason
    return record


def check_result(result: object) -> tuple[list[str], dict]:
    if not isinstance(result, Mapping):
        raise ProbeError(f"run() returned {type(result).__name__}, not a mapping")
    invariants = result.get("invariants")
    if not isinstance(invariants, list) or not all(isinstance(i, str) for i in invariants):
        raise ProbeError("invariants is not a list of strings")
    arms = result.get("arms")
    if not isinstance(arms, Mapping):
        raise ProbeError("arms is not a mapping")
    return list(invariants), {name: check_arm(name, arm) for name, arm in arms.items()}


def run_probe(path: Path, ctx: Context) -> tuple[list[str], dict]:
    """Import one probe file, call its run(ctx) and return the checked invariants and arms."""
    module_name = f"kbeval_probe_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        run = getattr(module, "run", None)
        if not callable(run):
            raise ProbeError("module has no run(ctx)")
        return check_result(run(ctx))
    finally:
        sys.modules.pop(module_name, None)


def say(text: str, stream) -> None:
    """Write one output line; the runner's output is its interface, not debug text."""
    stream.write(text + "\n")
    stream.flush()


def write_record(out: Path, record: dict) -> None:
    text = json.dumps(record, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    (out / f"{record['probe']}.json").write_bytes((text + "\n").encode("utf-8"))


def summary_lines(probe: str, arms: dict) -> list[str]:
    lines = []
    for name in sorted(arms):
        arm = arms[name]
        if arm["status"] == "unmeasured":
            tail = [arm["reason"]]
        else:
            tail = [f"{key}={value}" for key, value in sorted(arm["metrics"].items())]
        lines.append(" ".join([probe, name, arm["status"], *tail]))
    return lines


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    for option, path in (
        ("--wiki", args.wiki),
        ("--raw", args.raw),
        ("--probes-dir", args.probes_dir),
    ):
        if not path.is_dir():
            say(f"{option} is not a directory: {path}", sys.stderr)
            return 2
    try:
        probes = find_probes(args.probes_dir, args.probe)
        commit, dirty = git_state()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        say(str(exc), sys.stderr)
        return 2

    wiki, raw, out = args.wiki.resolve(), args.raw.resolve(), args.out.resolve()
    guarded = [CHECKOUT / "wiki", CHECKOUT / "raw", CHECKOUT / ".data", wiki, raw]
    out.mkdir(parents=True, exist_ok=True)

    # kb.config binds its paths when first imported, so the temporary root must
    # be in the environment before any probe imports kb.
    root = Path(tempfile.mkdtemp(prefix="kbeval-root-"))
    previous_root = os.environ.get("KB_PROJECT_ROOT")
    exit_code = 0
    try:
        if (CHECKOUT / "templates").is_dir():
            shutil.copytree(CHECKOUT / "templates", root / "templates")
        os.environ["KB_PROJECT_ROOT"] = str(root)
        before = guarded_listing(guarded)
        if before is None:
            return 1
        for path in probes:
            probe = path.stem
            tmp = Path(tempfile.mkdtemp(prefix=f"kbeval-{probe}-"))
            ctx = Context(tmp=tmp, data=BENCH / "data" / probe, wiki=wiki, raw=raw, out=out)
            try:
                # A record left by an earlier run must not stand in for this one.
                (out / f"{probe}.json").unlink(missing_ok=True)
                invariants, arms = run_probe(path, ctx)
            except KeyboardInterrupt:
                raise
            except BaseException as exc:  # any other exception, sys.exit included
                cause = "".join(traceback.format_exception_only(exc)).strip()
                say(f"{probe} failed: {cause}", sys.stderr)
                exit_code = 1
                continue
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            record = {
                "probe": probe,
                "invariants": invariants,
                "commit": commit,
                "dirty": dirty,
                "arms": arms,
            }
            write_record(out, record)
            for line in summary_lines(probe, arms):
                say(line, sys.stdout)
        after = guarded_listing(guarded)
    finally:
        if previous_root is None:
            os.environ.pop("KB_PROJECT_ROOT", None)
        else:
            os.environ["KB_PROJECT_ROOT"] = previous_root
        shutil.rmtree(root, ignore_errors=True)

    if after is None:
        return 1
    for path in sorted(set(before) | set(after)):
        if before.get(path) != after.get(path):
            say(f"guarded directory changed: {path}", sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
