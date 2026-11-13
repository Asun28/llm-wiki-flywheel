"""Acceptance tests 1-9 of card T1-KBEVAL-HARNESS for `bench/knowledge/run.py`."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from conftest import REPO

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
