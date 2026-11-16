"""Run the knowledge-layer probes and write one JSON record per probe.

Usage: python bench/knowledge/run.py [--probe NAME ...] [--probes-dir DIR]
       [--out DIR] [--wiki DIR] [--raw DIR]

Exit codes: 0 every probe returned a valid result and no guarded directory
changed; 1 a probe failed, a record could not be removed or a guarded directory
changed; 2 usage error (an unlistable probes directory and an `--out` that cannot
be created or lies inside an input directory included).
See bench/knowledge/README.md for the record shape and the probe entry.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import shutil
import stat
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
    a directory named `*.py` is not a probe. A directory that cannot be listed raises
    OSError (`Path.glob` would read it as empty).
    """
    with os.scandir(probes_dir) as entries:
        paths = [
            Path(entry.path)
            for entry in entries
            if os.path.normcase(entry.name).endswith(".py")
            and not entry.name.startswith("_")
            and entry.is_file()
        ]
    found = {p.stem: p for p in paths}
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
        warn(f"cannot list guarded directory: {where}: {exc.strerror or exc}")
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


def warn(text: str) -> None:
    """Write one diagnostic line to stderr; a stderr that cannot take it does not stop the run.

    The caller records the failure the line reports before calling, so the exit code
    holds even when nothing can be written.
    """
    try:
        say(text, sys.stderr)
    except (AttributeError, OSError, ValueError):
        pass  # no stream left to report on


def write_record(path: Path, record: dict) -> None:
    """Encode the whole record before writing, so an unencodable string writes nothing."""
    text = json.dumps(record, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    path.write_bytes((text + "\n").encode("utf-8"))


def remove_record(path: Path) -> str | None:
    """Remove `path`, a read-only file included; return the cause if it is still there.

    The read-only file attribute (Windows) makes unlink fail, so it is cleared and the
    unlink retried; a directory or link at the path is left as it is.
    """
    try:
        path.unlink(missing_ok=True)
        return None
    except OSError as exc:
        error = exc
    try:
        mode = os.lstat(path).st_mode
        if stat.S_ISREG(mode) and not mode & stat.S_IWRITE:
            os.chmod(path, stat.S_IMODE(mode) | stat.S_IWRITE)
            path.unlink()
            return None
    except FileNotFoundError:
        return None
    except OSError as exc:
        error = exc
    return error.strerror or str(error)


def overlap(args: argparse.Namespace, out: Path) -> str | None:
    """Name the input directory the resolved `out` equals or lies inside, or return None."""
    inputs = [
        ("--wiki", args.wiki),
        ("--raw", args.raw),
        ("the checkout's wiki/", CHECKOUT / "wiki"),
        ("the checkout's raw/", CHECKOUT / "raw"),
        ("the checkout's .data/", CHECKOUT / ".data"),
    ]
    for label, given in inputs:
        target = resolved(label, given)
        if out == target or out.is_relative_to(target):
            relation = "is" if out == target else "lies inside"
            return f"--out {shown(args.out, out)} {relation} {label} {shown(given, target)}"
    return None


def shown(given: Path, target: Path) -> str:
    return str(given) if given == target else f"{given} (resolves to {target})"


class UsageError(Exception):
    """A usage error; the message names the path and the cause, and the run exits 2."""


def stat_mode(label: str, path: Path) -> int | None:
    """Return the st_mode of `path`, or None when nothing is there.

    Any other error (permission denied on a parent, a link loop) is a UsageError, not
    a traceback and not "missing".
    """
    try:
        return os.stat(path).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as exc:
        raise UsageError(f"cannot inspect {label}: {path}: {exc.strerror or exc}") from exc


def resolved(label: str, path: Path) -> Path:
    try:
        return path.resolve()
    except (OSError, RuntimeError) as exc:  # RuntimeError: a link loop on Python 3.12
        cause = getattr(exc, "strerror", None) or exc
        raise UsageError(f"cannot resolve {label}: {path}: {cause}") from exc


def prepare_out(given: Path, out: Path) -> None:
    """Make sure `out` is a directory, creating it if nothing is there; raise UsageError."""
    mode = stat_mode("--out", given)
    if mode is not None and not stat.S_ISDIR(mode):
        raise UsageError(f"--out is not a directory: {given}")
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        where = f" ({exc.filename})" if exc.filename else ""
        raise UsageError(f"--out cannot be created: {given}: {exc.strerror or exc}{where}") from exc


def release_broken_streams() -> None:
    """Point the descriptor of a stdout or stderr that cannot be flushed at the null device.

    Otherwise interpreter shutdown flushes into the closed pipe again and exits 120
    instead of the run's exit code.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
            continue
        except (AttributeError, OSError, ValueError):
            pass
        try:
            null = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(null, stream.fileno())
            finally:
                os.close(null)
        except (AttributeError, OSError, ValueError):
            pass  # not backed by a descriptor; nothing to redirect


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
    """Run the probes with stdout and stderr escaping characters their encoding cannot show."""
    restore = []
    for stream in (sys.stdout, sys.stderr):
        try:
            errors = stream.errors
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, OSError, ValueError):
            continue  # not a reconfigurable text stream; leave it as it is
        restore.append((stream, errors))
    try:
        return run_all(argv)
    finally:
        for stream, errors in reversed(restore):
            try:
                stream.reconfigure(errors=errors)
            except (OSError, ValueError):
                pass  # reconfigure flushes; a broken stream is released below
        release_broken_streams()


def run_all(argv: list[str] | None) -> int:
    args = parse_args(argv)
    try:
        for option, path in (
            ("--wiki", args.wiki),
            ("--raw", args.raw),
            ("--probes-dir", args.probes_dir),
        ):
            mode = stat_mode(option, path)
            if mode is None or not stat.S_ISDIR(mode):
                raise UsageError(f"{option} is not a directory: {path}")
        wiki, raw, out = (
            resolved(option, path)
            for option, path in (("--wiki", args.wiki), ("--raw", args.raw), ("--out", args.out))
        )
        # Before any directory is made: a probe writing to ctx.out must not write an input.
        inside = overlap(args, out)
        if inside:
            raise UsageError(inside)
        try:
            probes = find_probes(args.probes_dir, args.probe)
        except OSError as exc:
            cause = exc.strerror or exc
            raise UsageError(f"cannot list --probes-dir: {args.probes_dir}: {cause}") from exc
        except ValueError as exc:
            raise UsageError(str(exc)) from exc
        try:
            commit, dirty = git_state()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise UsageError(str(exc)) from exc
        prepare_out(args.out, out)
    except UsageError as exc:
        warn(str(exc))
        return 2
    # A record left by an earlier run must not stand in for this one.
    stale = [(path, remove_record(path)) for path in (out / f"{p.stem}.json" for p in probes)]
    stale = [(path, cause) for path, cause in stale if cause]
    for path, cause in stale:
        warn(f"cannot remove record from an earlier run: {path}: {cause}")
    if stale:
        return 1
    guarded = [CHECKOUT / "wiki", CHECKOUT / "raw", CHECKOUT / ".data", wiki, raw]

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
            record_path = out / f"{probe}.json"
            tmp = Path(tempfile.mkdtemp(prefix=f"kbeval-{probe}-"))
            ctx = Context(tmp=tmp, data=BENCH / "data" / probe, wiki=wiki, raw=raw, out=out)
            try:
                invariants, arms = run_probe(path, ctx)
                record = {
                    "probe": probe,
                    "invariants": invariants,
                    "commit": commit,
                    "dirty": dirty,
                    "arms": arms,
                }
                # Writing and printing belong to the probe: a failure in either is
                # that probe's failure, not the end of the run.
                write_record(record_path, record)
                for line in summary_lines(probe, arms):
                    say(line, sys.stdout)
            except KeyboardInterrupt:
                raise
            except BaseException as exc:  # any other exception, sys.exit included
                exit_code = 1  # first: a diagnostic that cannot be written must not lose it
                left = remove_record(record_path)
                cause = "".join(traceback.format_exception_only(exc)).strip()
                warn(f"{probe} failed: {cause}")
                if left:
                    warn(f"cannot remove record of failed probe: {record_path}: {left}")
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
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
            exit_code = 1
            warn(f"guarded directory changed: {path}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
