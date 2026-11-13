# Knowledge-layer bench

`python bench/knowledge/run.py` runs the probes under `bench/knowledge/probes/`, writes one JSON record per probe and prints one line per probe arm. It makes no model call and no network request. Spec: `specs/kb-baseline.md`; invariants I1 to I11: `invariants.json`.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--probe NAME` | every probe | Run only this probe. Give it more than once to run several. |
| `--probes-dir DIR` | `bench/knowledge/probes/` | Directory searched for probe files. |
| `--out DIR` | `_local/knowledge/` | Directory the records are written to (gitignored). |
| `--wiki DIR` | `demo/wiki` | Wiki directory given to probes as `ctx.wiki`. |
| `--raw DIR` | `demo/raw` | Raw-source directory given to probes as `ctx.raw`. |

Default paths are relative to the checkout root. A probe is a regular file (or a link to one) named `<name>.py` whose name does not start with `_`; a directory named `*.py` is not a probe. Probes run one at a time, in full file-name order (`a.b.py` before `a.py`), with or without `--probe`.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Every probe returned a valid result and no guarded directory changed. |
| 1 | A probe failed (no `run`, an invalid return value, or any exception other than `KeyboardInterrupt` while it was imported or run, `sys.exit` with any code included), a guarded directory changed, or a guarded directory could not be listed. After a probe failure the other probes still run, write their records and the guard still runs. The failed probe has no record: `<out>/<probe>.json` from an earlier run is deleted before each probe runs. `KeyboardInterrupt` stops the run. |
| 2 | Usage error: `--probe` names no file in the probes directory, or `--wiki`, `--raw` or `--probes-dir` is not a directory. No probe runs. |

## Record

One file per probe, `<out>/<probe>.json`, UTF-8, sorted keys, two-space indent, `\n` line ends. It holds no timestamp or duration, so two runs on one commit write equal bytes.

```json
{
  "arms": {
    "<arm>": {
      "cases": 12,
      "metrics": {"precision": 0.75, "recall": 0.5},
      "status": "measured"
    },
    "<other arm>": {
      "cases": 0,
      "metrics": {},
      "reason": "embedding model not installed",
      "status": "unmeasured"
    }
  },
  "commit": "<40-hex HEAD of the checkout>",
  "dirty": false,
  "invariants": ["I10"],
  "probe": "<file stem of the probe>"
}
```

`reason` appears only on an unmeasured arm. Each summary line is `<probe> <arm> <status>` followed by `name=value` for each metric in name order, or by the reason for an unmeasured arm.

## Guard

Before the first probe and after the last, the runner lists every file (relative path, size, modification time in nanoseconds) under the checkout's `wiki/`, `raw/` and `.data/` and under the `--wiki` and `--raw` directories. For each entry that differs it prints `guarded directory changed: <path>` and exits 1.

- Real directories are descended into. Every other entry is listed by its own size and time and not followed: regular files, symbolic links to files or to directories, and Windows junctions. A junction is treated as a link, not a directory, so adding or removing one is a change and its target's contents are not listed.
- A missing guarded directory lists as empty.
- A guarded directory that exists but cannot be listed (for example, permission denied on a subdirectory) is not read as empty: the runner prints `cannot list guarded directory: <path>: <cause>` and exits 1. If this happens before the first probe, no probe runs.

While probes run, `KB_PROJECT_ROOT` points at a temporary directory that holds a copy of the checkout's `templates/`, so `kb.config` resolves its default `wiki/`, `raw/` and `.data/` paths there instead of in the checkout. The directory is removed when the run ends.

## Add a probe

1. Create `bench/knowledge/probes/<name>.py` (a name starting with `_` is skipped) with a function `run(ctx)`. `ctx` gives:
   - `ctx.tmp`: an empty directory for this probe, removed after it returns;
   - `ctx.data`: `bench/knowledge/data/<name>/`;
   - `ctx.wiki`, `ctx.raw`: the `--wiki` and `--raw` directories (read them, never write them);
   - `ctx.out`: the output directory;
   - `ctx.unmeasured(reason)`: returns an unmeasured arm with that reason.
2. Return `{"invariants": [<ids from invariants.json>], "arms": {<arm>: {"status": "measured", "cases": <int>, "metrics": {<name>: <finite number>}}}}`. Use `ctx.unmeasured(reason)` for an arm that cannot run because a model file or a corpus directory is absent.
3. Put the probe's committed case set or fixture corpus under `bench/knowledge/data/<name>/` and build any wiki it needs under `ctx.tmp`.
4. Add `bench/knowledge/tests/test_<name>.py`. Edit no other probe's files and not `run.py`: the runner finds probes by listing the directory.
5. Run `python bench/knowledge/run.py --probe <name>` and check the summary line and `_local/knowledge/<name>.json`.
