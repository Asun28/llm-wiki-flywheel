"""Acceptance tests 1-9 of card T1-KBEVAL-HARNESS for `bench/knowledge/run.py`."""

from __future__ import annotations

import errno
import inspect
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import REPO, RUNNER

RECORD_KEYS = {"probe", "invariants", "commit", "dirty", "arms"}
GUARD = "guarded directory changed:"


def measured(metrics: dict, cases: int = 3) -> dict:
    return {"status": "measured", "cases": cases, "metrics": metrics}


def probe_returning(result: dict) -> str:
    return f"def run(ctx):\n    return {result!r}\n"


VALID = probe_returning({"invariants": ["I10"], "arms": {"main": measured({"recall": 0.5})}})


# -- acceptance 1: records [R1] [R2] -------------------------------------------


def test_each_probe_gets_one_record_with_the_five_keys(bench):
    alpha = {"invariants": ["I10"], "arms": {"main": measured({"precision": 1.0, "recall": 0.5})}}
    beta = {"invariants": ["I3", "I4"], "arms": {"x": measured({"n": 2}, cases=7)}}
    bench.probe("alpha", probe_returning(alpha))
    bench.probe("beta", probe_returning(beta))

    proc = bench.run()

    assert proc.returncode == 0, proc.output
    assert bench.records() == ["alpha.json", "beta.json"]
    for name, returned in (("alpha", alpha), ("beta", beta)):
        record = json.loads((bench.out / f"{name}.json").read_text(encoding="utf-8"))
        assert set(record) == RECORD_KEYS
        assert record["probe"] == name
        assert record["invariants"] == returned["invariants"]
        assert re.fullmatch(r"[0-9a-f]{40}", record["commit"])
        assert isinstance(record["dirty"], bool)
        assert record["arms"] == returned["arms"]


def test_record_is_sorted_two_space_json_with_lf_line_ends(bench):
    bench.probe("alpha", VALID)

    assert bench.run().returncode == 0
    raw = (bench.out / "alpha.json").read_bytes()
    expected = json.dumps(json.loads(raw), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    assert raw == expected.encode("utf-8")


def test_two_runs_write_byte_equal_records(bench):
    bench.probe("alpha", VALID)
    bench.probe("beta", probe_returning({"invariants": [], "arms": {"y": measured({"m": 3})}}))
    second = bench.root / "out2"

    assert bench.run().returncode == 0
    assert bench.run(out=second).returncode == 0
    for name in ("alpha.json", "beta.json"):
        assert (bench.out / name).read_bytes() == (second / name).read_bytes()


# -- acceptance 2: ctx [R3] ----------------------------------------------------


def test_ctx_gives_tmp_data_wiki_raw_out_and_unmeasured(bench):
    seen = bench.root / "seen.json"
    bench.probe(
        "looker",
        f"""
        import json, os

        def run(ctx):
            seen = {{
                "tmp": str(ctx.tmp),
                "tmp_is_empty_dir": os.path.isdir(ctx.tmp) and not os.listdir(ctx.tmp),
                "data": str(ctx.data),
                "wiki": str(ctx.wiki),
                "raw": str(ctx.raw),
                "out": str(ctx.out),
            }}
            with open({str(seen)!r}, "w", encoding="utf-8") as fh:
                json.dump(seen, fh)
            return {{"invariants": [], "arms": {{"skip": ctx.unmeasured("x")}}}}
        """,
    )

    assert bench.run().returncode == 0
    got = json.loads(seen.read_text(encoding="utf-8"))
    assert got["tmp_is_empty_dir"] is True
    assert not Path(got["tmp"]).exists()
    assert Path(got["data"]).parts[-2:] == ("data", "looker")
    assert Path(got["wiki"]).resolve() == bench.wiki.resolve()
    assert Path(got["raw"]).resolve() == bench.raw.resolve()
    assert Path(got["out"]).resolve() == bench.out.resolve()
    record = json.loads((bench.out / "looker.json").read_text(encoding="utf-8"))
    assert record["arms"]["skip"] == {
        "status": "unmeasured",
        "reason": "x",
        "cases": 0,
        "metrics": {},
    }


# -- acceptance 3: summary lines [R4] ------------------------------------------


def test_stdout_has_one_line_per_arm_with_metrics_in_name_order(bench):
    bench.probe(
        "alpha",
        """
        def run(ctx):
            return {
                "invariants": [],
                "arms": {
                    "first": {"status": "measured", "cases": 2,
                              "metrics": {"zeta": 0.25, "alpha": 3}},
                    "second": ctx.unmeasured("no model file"),
                },
            }
        """,
    )

    proc = bench.run()

    assert proc.returncode == 0, proc.output
    lines = proc.stdout.splitlines()
    assert "alpha first measured alpha=3 zeta=0.25" in lines
    assert "alpha second unmeasured no model file" in lines
    assert len([line for line in lines if line.startswith("alpha ")]) == 2


# -- acceptance 4: --probe [R5] -------------------------------------------------


def test_probe_option_runs_only_the_named_probe(bench):
    for name in ("a", "b", "c"):
        bench.probe(name, VALID)

    assert bench.run("--probe", "a").returncode == 0
    assert bench.records() == ["a.json"]


def test_probe_option_given_twice_runs_both(bench):
    for name in ("a", "b", "c"):
        bench.probe(name, VALID)

    assert bench.run("--probe", "a", "--probe", "b").returncode == 0
    assert bench.records() == ["a.json", "b.json"]


# -- acceptance 5: invalid probe results [R6] ----------------------------------

BROKEN = {
    "no_run": "X = 1\n",
    "run_raises": "def run(ctx):\n    raise RuntimeError('boom')\n",
    "not_a_mapping": "def run(ctx):\n    return [1, 2]\n",
    "bad_status": probe_returning(
        {"invariants": [], "arms": {"m": {"status": "done", "cases": 1, "metrics": {}}}}
    ),
    "cases_not_int": probe_returning(
        {"invariants": [], "arms": {"m": {"status": "measured", "cases": "1", "metrics": {}}}}
    ),
    "metric_is_string": probe_returning({"invariants": [], "arms": {"m": measured({"r": "0.5"})}}),
    "metric_is_nan": (
        "def run(ctx):\n"
        "    nan = float('nan')\n"
        "    return {'invariants': [], 'arms': {'m': {'status': 'measured', 'cases': 1,"
        " 'metrics': {'r': nan}}}}\n"
    ),
}


@pytest.mark.parametrize("cause", sorted(BROKEN))
def test_invalid_probe_fails_the_run_but_others_still_write(bench, cause):
    bench.probe("broken_probe", BROKEN[cause])
    bench.probe("good_probe", VALID)

    proc = bench.run()

    assert proc.returncode == 1, proc.output
    assert "broken_probe" in proc.output
    assert bench.records() == ["good_probe.json"]


# -- acceptance 6: usage errors [R7] -------------------------------------------


def test_unknown_probe_name_exits_2(bench):
    bench.probe("alpha", VALID)

    proc = bench.run("--probe", "nosuch")

    assert proc.returncode == 2, proc.output
    assert "nosuch" in proc.output
    assert bench.records() == []


@pytest.mark.parametrize("option", ["--wiki", "--raw", "--probes-dir"])
def test_file_given_as_directory_option_exits_2(bench, option):
    bench.probe("alpha", VALID)
    a_file = bench.root / "not_a_dir.txt"
    a_file.write_text("x", encoding="utf-8")

    proc = bench.run(option, str(a_file))

    assert proc.returncode == 2, proc.output
    assert option in proc.output
    assert bench.records() == []


# -- acceptance 7: guard [R8] --------------------------------------------------

WIKI_CHANGES = {
    "writes": "(ctx.wiki / 'new.md').write_text('new', encoding='utf-8')",
    "deletes": "(ctx.wiki / 'page.md').unlink()",
    "rewrites": "(ctx.wiki / 'page.md').write_text('a longer body than before', encoding='utf-8')",
}


@pytest.mark.parametrize("change", sorted(WIKI_CHANGES))
def test_probe_that_changes_wiki_fails_the_run(bench, change):
    (bench.wiki / "page.md").write_text("body", encoding="utf-8")
    (bench.raw / "source.md").write_text("source", encoding="utf-8")
    target = "new.md" if change == "writes" else "page.md"
    body = f"    {WIKI_CHANGES[change]}\n    return {{'invariants': [], 'arms': {{}}}}\n"
    bench.probe("leaky", "def run(ctx):\n" + body)

    proc = bench.run()

    assert proc.returncode == 1, proc.output
    guard_lines = [line for line in proc.output.splitlines() if GUARD in line]
    assert any(target in line and str(bench.wiki) in line for line in guard_lines), proc.output
    assert not any(str(bench.raw) in line for line in guard_lines)
    assert not any(".data" in line for line in guard_lines)


def test_unchanged_directories_give_no_guard_line(bench):
    (bench.wiki / "page.md").write_text("body", encoding="utf-8")
    (bench.raw / "source.md").write_text("source", encoding="utf-8")
    bench.probe(
        "reader",
        "def run(ctx):\n    (ctx.wiki / 'page.md').read_text(encoding='utf-8')\n"
        "    return {'invariants': [], 'arms': {}}\n",
    )

    proc = bench.run()

    assert proc.returncode == 0, proc.output
    assert bench.records() == ["reader.json"]
    assert GUARD not in proc.output


# -- acceptance 8: temporary project root [R9] ----------------------------------


def test_kb_config_sees_a_temporary_root_with_templates(bench):
    seen = bench.root / "seen.json"
    bench.probe(
        "rooted",
        f"""
        import json
        from pathlib import Path

        def run(ctx):
            import kb.config
            root = Path(kb.config.PROJECT_ROOT)
            with open({str(seen)!r}, "w", encoding="utf-8") as fh:
                json.dump({{"root": str(root), "templates": (root / "templates").is_dir()}}, fh)
            return {{"invariants": [], "arms": {{}}}}
        """,
    )

    proc = bench.run()

    assert proc.returncode == 0, proc.output
    got = json.loads(seen.read_text(encoding="utf-8"))
    root = Path(got["root"]).resolve()
    assert not root.is_relative_to(REPO.resolve())
    assert got["templates"] is True
    assert not root.exists()


# -- acceptance 9: invariants.json [R10] ---------------------------------------

PROBE_NAMES = {
    "contradiction",
    "retrieval",
    "linker",
    "citations",
    "trace",
    "rebuild",
    "provenance",
}


def test_invariants_json_lists_i1_to_i11_with_their_probes():
    path = REPO / "bench" / "knowledge" / "invariants.json"
    assert path.is_file()
    entries = json.loads(path.read_text(encoding="utf-8"))

    assert [entry["id"] for entry in entries] == [f"I{n}" for n in range(1, 12)]
    for entry in entries:
        assert set(entry) == {"id", "statement", "probes"}
        assert isinstance(entry["statement"], str) and entry["statement"].strip()
        assert set(entry["probes"]) <= PROBE_NAMES
    by_id = {entry["id"]: entry["probes"] for entry in entries}
    assert by_id["I5"] == [] and by_id["I7"] == []
    assert all(by_id[i] for i in by_id if i not in {"I5", "I7"})


# -- attempt 2 regressions (R3 review findings F1-F5) ----------------------------


def test_probes_run_in_file_name_order_not_stem_order(bench):
    """F1: "a.b.py" sorts before "a.py" by file name, after it by stem."""
    log = bench.root / "order.txt"
    for name in ("a", "a.b"):
        bench.probe(
            name,
            f"def run(ctx):\n"
            f"    with open({str(log)!r}, 'a', encoding='utf-8') as fh:\n"
            f"        fh.write({name!r} + '\\n')\n"
            f"    return {{'invariants': [], 'arms': {{}}}}\n",
        )

    assert bench.run().returncode == 0
    assert log.read_text(encoding="utf-8").splitlines() == ["a.b", "a"]
    log.unlink()
    assert bench.run("--probe", "a", "--probe", "a.b").returncode == 0
    assert log.read_text(encoding="utf-8").splitlines() == ["a.b", "a"]


def test_directory_named_like_a_probe_is_not_a_probe(bench):
    """F2: a probes dir holding only a `helper.py/` directory has no probe file."""
    (bench.probes / "helper.py").mkdir()

    proc = bench.run()

    assert proc.returncode == 0, proc.output
    assert proc.output == ""
    assert bench.records() == []


def test_directory_named_like_a_probe_is_unknown_to_probe_option(bench):
    (bench.probes / "helper.py").mkdir()

    proc = bench.run("--probe", "helper")

    assert proc.returncode == 2, proc.output
    assert "helper" in proc.output


def make_link(kind, target, link):
    import os

    if kind == "junction":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=kind == "dir_symlink")


def remove_link(kind, link):
    import os

    if kind != "file_symlink" and os.name == "nt":
        os.rmdir(link)
    else:
        os.unlink(link)


LINK_KINDS = ["file_symlink", "dir_symlink", "junction"]


def link_target(bench, kind: str) -> Path:
    if kind == "file_symlink":
        target = bench.root / "target.txt"
        target.write_text("target", encoding="utf-8")
    else:
        target = bench.root / "target_dir"
        target.mkdir(exist_ok=True)
    return target


def require_link_kind(bench, kind: str) -> None:
    """Skip when this platform cannot create the link kind (junctions: Windows only;
    symlinks on Windows without the privilege raise WinError 1314)."""
    if kind == "junction" and sys.platform != "win32":
        pytest.skip("junctions exist on Windows only")
    probe_link = bench.root / f"can_link_{kind}"
    try:
        make_link(kind, link_target(bench, kind), probe_link)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("symlink creation needs a privilege this Windows account lacks")
        raise
    remove_link(kind, probe_link)


@pytest.mark.parametrize("op", ["create", "remove"])
@pytest.mark.parametrize("kind", LINK_KINDS)
def test_adding_or_removing_a_link_under_wiki_fails_the_run(bench, kind, op):
    """F3: links, including links to directories and junctions, are guarded entries."""
    require_link_kind(bench, kind)
    target = link_target(bench, kind)
    link = bench.wiki / "link"
    if op == "create":
        call = f"make_link({kind!r}, {str(target)!r}, ctx.wiki / 'link')"
    else:
        make_link(kind, target, link)
        call = f"remove_link({kind!r}, ctx.wiki / 'link')"
    helpers = inspect.getsource(make_link) + "\n" + inspect.getsource(remove_link)
    bench.probe(
        "linker_probe",
        f"{helpers}\n\ndef run(ctx):\n    {call}\n    return {{'invariants': [], 'arms': {{}}}}\n",
    )

    proc = bench.run()

    assert proc.returncode == 1, proc.output
    guard_lines = [line for line in proc.output.splitlines() if GUARD in line]
    assert any(str(link) in line for line in guard_lines), proc.output


@pytest.mark.parametrize("code", [0, 3])
def test_probe_calling_sys_exit_fails_only_that_probe(bench, code):
    """F4: SystemExit from a probe is a probe failure; later probes and the guard still run."""
    write = "(ctx.wiki / 'leak.md').write_text('x', encoding='utf-8')\n    " if code == 0 else ""
    bench.probe("a_exiting", f"import sys\n\ndef run(ctx):\n    {write}sys.exit({code})\n")
    bench.probe("b_good", VALID)

    proc = bench.run()

    assert proc.returncode == 1, proc.output
    assert "a_exiting" in proc.output
    assert bench.records() == ["b_good.json"]
    if code == 0:
        assert any(GUARD in line and "leak.md" in line for line in proc.output.splitlines())


def scandir_denying(locked: Path, real_scandir):
    """An os.scandir that raises PermissionError for `locked` and passes everything else on.

    It replaces os.scandir process-wide, so it must accept every form the standard
    library uses: on POSIX, shutil.rmtree calls os.scandir with an int file descriptor.
    Only a str, bytes or PathLike argument is compared with `locked`.
    """

    def scandir(*args, **kwargs):
        path = args[0] if args else kwargs.get("path")
        if isinstance(path, (str, bytes, os.PathLike)):
            if os.path.normcase(os.fsdecode(path)) == os.path.normcase(str(locked)):
                raise PermissionError(13, "Permission denied", os.fsdecode(path))
        return real_scandir(*args, **kwargs)

    return scandir


def test_scandir_fake_passes_non_path_arguments_to_the_real_scandir(tmp_path):
    """The fake must not break callers that pass no path or a file descriptor."""
    (tmp_path / "entry.txt").write_text("x", encoding="utf-8")
    fake = scandir_denying(tmp_path / "locked", os.scandir)

    with fake() as found:  # default argument: the current directory
        assert isinstance(list(found), list)
    with fake(tmp_path) as found:
        assert [entry.name for entry in found] == ["entry.txt"]
    if os.scandir in os.supports_fd:  # POSIX: the form shutil.rmtree uses
        fd = os.open(tmp_path, os.O_RDONLY)
        try:
            with fake(fd) as found:
                assert [entry.name for entry in found] == ["entry.txt"]
        finally:
            os.close(fd)
    with pytest.raises(PermissionError):
        fake(tmp_path / "locked")


def test_unlistable_guarded_directory_fails_the_run(bench, runner, monkeypatch, capsys):
    """F5: a scan error under a guarded directory is reported, not read as an empty listing."""
    locked = bench.wiki / "locked"
    locked.mkdir()
    (locked / "page.md").write_text("body", encoding="utf-8")

    monkeypatch.setattr(os, "scandir", scandir_denying(locked, os.scandir))
    code = runner.main(
        [
            *("--probes-dir", str(bench.probes), "--wiki", str(bench.wiki)),
            *("--raw", str(bench.raw), "--out", str(bench.out)),
        ]
    )
    output = capsys.readouterr()

    assert code == 1, output
    assert "cannot list guarded directory:" in output.err
    assert str(locked) in output.out + output.err


# -- attempt 2 follow-up (coordinator items 1-3) ---------------------------------


def test_probe_raising_a_custom_base_exception_fails_only_that_probe(bench):
    """F4 class: any BaseException other than KeyboardInterrupt is a probe failure."""
    bench.probe(
        "a_stopping",
        "class Stop(BaseException):\n    pass\n\n"
        "def run(ctx):\n"
        "    (ctx.wiki / 'leak.md').write_text('x', encoding='utf-8')\n"
        "    raise Stop('halt')\n",
    )
    bench.probe("b_good", VALID)

    proc = bench.run()

    assert proc.returncode == 1, proc.output
    assert "a_stopping" in proc.output
    assert bench.records() == ["b_good.json"]
    assert any(GUARD in line and "leak.md" in line for line in proc.output.splitlines())


def test_failed_probe_leaves_no_record_from_an_earlier_run(bench):
    """R6: a reused --out must not show a record this run did not produce."""
    bench.out.mkdir()
    (bench.out / "a.json").write_text('{"probe": "a"}\n', encoding="utf-8")
    bench.probe("a", "def run(ctx):\n    raise RuntimeError('boom')\n")

    proc = bench.run()

    assert proc.returncode == 1, proc.output
    assert not (bench.out / "a.json").exists()


def test_underscore_file_is_not_a_probe(bench):
    log = bench.root / "ran.txt"
    bench.probe(
        "_helper",
        f"def run(ctx):\n    open({str(log)!r}, 'w').close()\n"
        "    return {'invariants': [], 'arms': {}}\n",
    )
    bench.probe("a", VALID)

    proc = bench.run()

    assert proc.returncode == 0, proc.output
    assert not log.exists()
    assert bench.records() == ["a.json"]
    assert bench.run("--probe", "_helper").returncode == 2


def test_keyboard_interrupt_propagates_and_restores_kb_project_root(bench, runner, monkeypatch):
    bench.probe("a", "def run(ctx):\n    raise KeyboardInterrupt\n")
    monkeypatch.setenv("KB_PROJECT_ROOT", "previous-root")
    argv = [
        *("--probes-dir", str(bench.probes), "--wiki", str(bench.wiki)),
        *("--raw", str(bench.raw), "--out", str(bench.out)),
    ]

    with pytest.raises(KeyboardInterrupt):
        runner.main(argv)

    assert os.environ["KB_PROJECT_ROOT"] == "previous-root"


# -- acceptance 11 and 12: record writing and console output [R13] [R14] ----------


def test_probe_returning_an_unencodable_string_fails_only_that_probe(bench):
    """Acceptance 11: a lone surrogate cannot be written as UTF-8, so the probe fails."""
    bench.probe(
        "a_surrogate",
        "def run(ctx):\n"
        "    (ctx.wiki / 'leak.md').write_text('x', encoding='utf-8')\n"
        "    return {'invariants': [], 'arms': {'main': ctx.unmeasured('bad \\ud800')}}\n",
    )
    bench.probe("b_good", VALID)

    proc = bench.run()

    assert proc.returncode == 1, proc.output
    assert "a_surrogate" in proc.output
    assert "Traceback" not in proc.output
    assert bench.records() == ["b_good.json"]
    assert any(GUARD in line and "leak.md" in line for line in proc.output.splitlines())


def test_console_that_cannot_show_a_character_gets_it_escaped(bench):
    """Acceptance 12: a cp1252 console gets an escape, the UTF-8 record the text itself."""
    bench.probe(
        "zh",
        "def run(ctx):\n"
        "    return {'invariants': [], 'arms': {'main': ctx.unmeasured('\\u4e2d\\u6587')}}\n",
    )

    proc = bench.run(io_encoding="cp1252")

    assert proc.returncode == 0, proc.output
    assert "Traceback" not in proc.output
    record = json.loads((bench.out / "zh.json").read_text(encoding="utf-8"))
    assert record["arms"]["main"]["reason"] == "\u4e2d\u6587"
    assert "zh main unmeasured \\u4e2d\\u6587" in proc.stdout.splitlines()


def test_record_write_failure_fails_only_that_probe(bench):
    """R13: a record that cannot be written is that probe's failure; later probes still run."""
    bench.probe(
        "a_blocked",
        "def run(ctx):\n"
        "    (ctx.out / 'a_blocked.json').mkdir()\n"
        "    return {'invariants': [], 'arms': {}}\n",
    )
    bench.probe("b_good", VALID)

    proc = bench.run()

    assert proc.returncode == 1, proc.output
    assert "a_blocked" in proc.output
    assert "Traceback" not in proc.output
    assert not (bench.out / "a_blocked.json").is_file()
    assert (bench.out / "b_good.json").is_file()


class BrokenStdout:
    """A stdout whose writes fail, as when the reading end of a pipe has closed."""

    def write(self, text):
        raise OSError(32, "Broken pipe")

    def flush(self):
        pass


def test_summary_print_failure_fails_the_probe_and_keeps_the_guard(
    bench, runner, monkeypatch, capsys
):
    """R13: when a summary line cannot be printed, the probe has no record and the guard runs."""
    bench.probe(
        "a_leaky",
        "def run(ctx):\n"
        "    (ctx.wiki / 'leak.md').write_text('x', encoding='utf-8')\n"
        "    return {'invariants': [], 'arms': {'main': ctx.unmeasured('r')}}\n",
    )
    monkeypatch.setattr(sys, "stdout", BrokenStdout())
    argv = [
        *("--probes-dir", str(bench.probes), "--wiki", str(bench.wiki)),
        *("--raw", str(bench.raw), "--out", str(bench.out)),
    ]

    code = runner.main(argv)
    err = capsys.readouterr().err

    assert code == 1
    assert "a_leaky" in err
    assert bench.records() == []
    assert any(GUARD in line and "leak.md" in line for line in err.splitlines())


# -- T1-KBEVAL-RUNNERERR: error paths of the runner (#148) ------------------------


def argv_for(bench, out: Path | None = None) -> list[str]:
    return [
        *("--probes-dir", str(bench.probes), "--wiki", str(bench.wiki)),
        *("--raw", str(bench.raw), "--out", str(out or bench.out)),
    ]


def marker_probe(bench, name: str) -> Path:
    """A valid probe that leaves a marker file when it runs; return the marker path."""
    marker = bench.root / f"ran-{name}.txt"
    bench.probe(
        name,
        f"def run(ctx):\n    open({str(marker)!r}, 'w').close()\n"
        "    return {'invariants': [], 'arms': {}}\n",
    )
    return marker


def read_only(path: Path) -> None:
    os.chmod(path, stat.S_IREAD)


# acceptance 1 [R1]


def test_unlistable_probes_directory_exits_2_naming_it(bench, runner, monkeypatch, capsys):
    marker = marker_probe(bench, "a")
    monkeypatch.setattr(os, "scandir", scandir_denying(bench.probes, os.scandir))

    code = runner.main(argv_for(bench))
    output = capsys.readouterr()

    assert code == 2, output
    assert str(bench.probes) in output.err
    assert "Traceback" not in output.err
    assert not marker.exists()
    assert bench.records() == []


def test_empty_readable_probes_directory_exits_0_with_no_output(bench):
    proc = bench.run()

    assert proc.returncode == 0, proc.output
    assert proc.output == ""
    assert bench.records() == []


# acceptance 2 [R2]


def test_stale_records_of_selected_probes_are_gone_before_the_first_probe(bench):
    """Read-only stale records of every selected probe are removed before any probe runs."""
    seen = bench.root / "seen.json"
    bench.probe(
        "a_looker",
        f"""
        import json

        def run(ctx):
            names = ("a_looker.json", "b_other.json", "c_unselected.json")
            with open({str(seen)!r}, "w", encoding="utf-8") as fh:
                json.dump({{n: (ctx.out / n).exists() for n in names}}, fh)
            return {{"invariants": [], "arms": {{}}}}
        """,
    )
    bench.probe("b_other", VALID)
    bench.probe("c_unselected", VALID)
    bench.out.mkdir()
    for name in ("a_looker", "b_other", "c_unselected"):
        stale = bench.out / f"{name}.json"
        stale.write_text('{"probe": "stale"}\n', encoding="utf-8")
        read_only(stale)

    proc = bench.run("--probe", "a_looker", "--probe", "b_other")

    assert proc.returncode == 0, proc.output
    observed = json.loads(seen.read_text(encoding="utf-8"))
    assert observed == {"a_looker.json": False, "b_other.json": False, "c_unselected.json": True}
    b_record = json.loads((bench.out / "b_other.json").read_text(encoding="utf-8"))
    assert b_record["probe"] == "b_other"
    unselected = bench.out / "c_unselected.json"
    assert unselected.read_text(encoding="utf-8") == '{"probe": "stale"}\n'


def test_stale_record_that_cannot_be_removed_exits_1_before_any_probe(bench):
    first = marker_probe(bench, "a")
    second = marker_probe(bench, "b")
    bench.out.mkdir()
    blocker = bench.out / "b.json"  # a directory: no unlink removes it
    blocker.mkdir()
    (blocker / "inside.txt").write_text("x", encoding="utf-8")

    proc = bench.run()

    assert proc.returncode == 1, proc.output
    assert any(str(blocker) in line for line in proc.stderr.splitlines()), proc.output
    assert "Traceback" not in proc.output
    assert not first.exists() and not second.exists()
    assert (blocker / "inside.txt").is_file()


# acceptance 3 [R3]


def test_failed_probe_leaves_no_read_only_record_of_its_own(bench):
    bench.probe(
        "a",
        "import os, stat\n\n"
        "def run(ctx):\n"
        "    record = ctx.out / 'a.json'\n"
        "    record.write_text('{}', encoding='utf-8')\n"
        "    os.chmod(record, stat.S_IREAD)\n"
        "    raise RuntimeError('boom')\n",
    )

    proc = bench.run()

    assert proc.returncode == 1, proc.output
    assert not (bench.out / "a.json").exists()
    assert "Traceback" not in proc.output


def test_failed_probe_record_that_cannot_be_removed_is_named_on_stderr(bench):
    bench.probe(
        "a",
        "def run(ctx):\n    (ctx.out / 'a.json').mkdir()\n    raise RuntimeError('boom')\n",
    )
    bench.probe("b_good", VALID)

    proc = bench.run()

    assert proc.returncode == 1, proc.output
    record = bench.out / "a.json"
    assert any(str(record) in line for line in proc.stderr.splitlines()), proc.output
    assert "Traceback" not in proc.output
    assert (bench.out / "b_good.json").is_file()


# acceptance 4 [R4] [R5]


def run_with_closed_pipe(bench) -> int:
    """Run the runner with stdout and stderr on one pipe whose reading end is already closed."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("KB_PROJECT_ROOT", None)
    proc = subprocess.Popen(
        [sys.executable, str(RUNNER), *argv_for(bench)],
        cwd=str(REPO),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    proc.stdout.close()
    return proc.wait(timeout=60)


def require_closed_pipe_write_error() -> None:
    """Skip where the OS reports no error for a write to a pipe whose reader has closed."""
    child = (
        # Writes past a full pipe buffer, so a write made before the parent closed
        # its end cannot pass for one made after; os._exit skips the shutdown flush.
        "import os, sys\n"
        "try:\n"
        "    for _ in range(64):\n"
        "        sys.stdout.write('x' * 65536); sys.stdout.flush()\n"
        "except OSError:\n"
        "    os._exit(7)\n"
        "os._exit(0)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", child], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    proc.stdout.close()
    if proc.wait(timeout=60) != 7:
        pytest.skip("this OS reports no error for a write to a closed pipe")


def test_closed_output_pipe_keeps_later_probes_and_exit_code_1(bench):
    require_closed_pipe_write_error()
    bench.probe("a_failing", "def run(ctx):\n    raise RuntimeError('boom')\n")
    bench.probe("b_quiet", "def run(ctx):\n    return {'invariants': [], 'arms': {}}\n")

    code = run_with_closed_pipe(bench)

    assert code == 1
    assert bench.records() == ["b_quiet.json"]


def test_closed_output_pipe_with_a_guard_change_exits_1_not_120(bench):
    require_closed_pipe_write_error()
    bench.probe(
        "a_leaky",
        "def run(ctx):\n"
        "    (ctx.wiki / 'leak.md').write_text('x', encoding='utf-8')\n"
        "    return {'invariants': [], 'arms': {}}\n",
    )

    assert run_with_closed_pipe(bench) == 1


def test_closed_output_pipe_with_summary_lines_exits_1_not_120(bench):
    require_closed_pipe_write_error()
    bench.probe("a", VALID)

    assert run_with_closed_pipe(bench) == 1


class UnavailableStream:
    """A stream whose every write and flush fails; it keeps what was attempted."""

    def __init__(self):
        self.attempts: list[str] = []

    def write(self, text):
        self.attempts.append(text)
        raise OSError(errno.EPIPE, "Broken pipe")

    def flush(self):
        raise OSError(errno.EPIPE, "Broken pipe")


def test_unwritable_diagnostic_stops_neither_later_probes_nor_the_guard(bench, runner, monkeypatch):
    bench.probe(
        "a_failing",
        "def run(ctx):\n"
        "    (ctx.wiki / 'leak.md').write_text('x', encoding='utf-8')\n"
        "    raise RuntimeError('boom')\n",
    )
    bench.probe("b_quiet", "def run(ctx):\n    return {'invariants': [], 'arms': {}}\n")
    err = UnavailableStream()
    monkeypatch.setattr(sys, "stdout", UnavailableStream())
    monkeypatch.setattr(sys, "stderr", err)

    code = runner.main(argv_for(bench))

    assert code == 1
    assert bench.records() == ["b_quiet.json"]
    assert any("a_failing" in text for text in err.attempts), err.attempts
    assert any(GUARD in text and "leak.md" in text for text in err.attempts), err.attempts


# acceptance 5 [R6]


def test_out_naming_an_existing_file_exits_2(bench):
    marker = marker_probe(bench, "a")
    a_file = bench.root / "out.txt"
    a_file.write_text("x", encoding="utf-8")

    proc = bench.run(out=a_file)

    assert proc.returncode == 2, proc.output
    assert str(a_file) in proc.stderr
    assert "Traceback" not in proc.output
    assert not marker.exists()
    assert a_file.read_text(encoding="utf-8") == "x"


def mkdir_denying(locked: Path, real_mkdir):
    """An os.mkdir that raises PermissionError for `locked` and passes everything else on.

    Like scandir_denying, it accepts every argument form (a dir_fd keyword included)
    and compares only a str, bytes or PathLike path with `locked`.
    """

    def mkdir(*args, **kwargs):
        path = args[0] if args else kwargs.get("path")
        if isinstance(path, (str, bytes, os.PathLike)):
            if os.path.normcase(os.path.abspath(os.fsdecode(path))) == os.path.normcase(
                str(locked)
            ):
                raise PermissionError(13, "Permission denied", os.fsdecode(path))
        return real_mkdir(*args, **kwargs)

    return mkdir


def test_out_that_cannot_be_created_exits_2(bench, runner, monkeypatch, capsys):
    marker = marker_probe(bench, "a")
    out = bench.root / "denied" / "out"
    monkeypatch.setattr(os, "mkdir", mkdir_denying(out, os.mkdir))

    code = runner.main(argv_for(bench, out))
    output = capsys.readouterr()

    assert code == 2, output
    assert str(out) in output.err
    assert "Traceback" not in output.err
    assert not marker.exists()
    assert not out.exists()


# acceptance 6 [R7]


def assert_overlap_refused(proc, out: Path, protected: Path, marker: Path) -> None:
    assert proc.returncode == 2, proc.output
    lines = proc.stderr.splitlines()
    assert any(str(out) in line and str(protected) in line for line in lines), proc.output
    assert "Traceback" not in proc.output
    assert not marker.exists()


def test_out_equal_to_wiki_exits_2_naming_both(bench):
    marker = marker_probe(bench, "a")
    (bench.wiki / "page.md").write_text("body", encoding="utf-8")

    proc = bench.run(out=bench.wiki)

    assert_overlap_refused(proc, bench.wiki, bench.wiki, marker)
    assert sorted(p.name for p in bench.wiki.iterdir()) == ["page.md"]


def test_out_inside_raw_exits_2_and_is_not_created(bench):
    marker = marker_probe(bench, "a")
    out = bench.raw / "sub" / "out"

    proc = bench.run(out=out)

    assert_overlap_refused(proc, out, bench.raw, marker)
    assert not (bench.raw / "sub").exists()


@pytest.mark.parametrize("name", ["wiki", "raw", ".data"])
def test_out_inside_a_checkout_input_directory_exits_2_and_is_not_created(bench, name):
    marker = marker_probe(bench, "a")
    protected = REPO / name
    # The top directory this test may cause to exist; it does not exist beforehand,
    # so removing it afterwards removes nothing the checkout already held.
    top = protected / f"kbeval-runnererr-{os.getpid()}" if protected.exists() else protected
    out = top / "nested" / "out"
    assert not top.exists()
    try:
        proc = bench.run(out=out)

        assert_overlap_refused(proc, out, protected, marker)
        assert not top.exists()
    finally:
        if top.exists():  # only a runner that ignored the overlap made it
            shutil.rmtree(top)


@pytest.mark.parametrize("kind", ["dir_symlink", "junction"])
def test_out_reaching_wiki_through_a_link_exits_2(bench, kind):
    require_link_kind(bench, kind)
    marker = marker_probe(bench, "a")
    link = bench.root / "wiki_link"
    make_link(kind, bench.wiki, link)
    out = link / "out"

    proc = bench.run(out=out)

    assert_overlap_refused(proc, out, bench.wiki, marker)
    assert not (bench.wiki / "out").exists()
