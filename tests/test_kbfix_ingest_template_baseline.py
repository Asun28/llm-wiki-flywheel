"""T1-KBFIX-TPLBASE (#160): `ingest_source` records the `_template/<type>` baseline.

Only `compile_wiki` used to write `_template/<type>` manifest keys, and
`find_changed_sources` reads a missing key as a template change. A wiki built by
`ingest_source` alone therefore had no baseline, and the scan listed every source
of every ingested type as changed even when nothing had changed.

`ingest_source` now writes `_template/<source_type>` when the key is absent, in
the same `file_lock(HASH_MANIFEST)` span and save as the source hash, using the
template hash captured when the ingest began. An existing value is never changed.
"""

from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path

from kb.compile import compiler as compiler_mod
from kb.ingest import pipeline as pipeline_mod
from kb.utils.hashing import hash_bytes

_TEMPLATE_KEY = "_template/article"


def _extraction(slug: str) -> dict:
    return {
        "title": f"Template Baseline Source {slug}",
        "summary": f"Test source {slug} for the ingest template baseline.",
        "entities_mentioned": [],
        "concepts_mentioned": [],
        "key_points": [f"Point from {slug}."],
    }


def _seed_raw(root: Path, slug: str) -> Path:
    raw = root / "raw" / "articles" / f"{slug}.md"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(f"# {slug}\n\nDistinct body for {slug}.\n".encode())
    return raw


def _ingest(root: Path, raw: Path) -> dict:
    return pipeline_mod.ingest_source(
        raw,
        source_type="article",
        extraction=_extraction(raw.stem),
        wiki_dir=root / "wiki",
        raw_dir=root / "raw",
        _skip_vector_rebuild=True,
    )


def _scan(root: Path) -> tuple[list[Path], list[Path]]:
    return compiler_mod.find_changed_sources(
        root / "raw", compiler_mod.HASH_MANIFEST, save_hashes=False
    )


def _template_keys(manifest: dict) -> dict:
    return {k: v for k, v in manifest.items() if k.startswith("_template/")}


def _copy_templates(src: Path, dest: Path, *, drop: tuple[str, ...] = ()) -> Path:
    dest.mkdir(parents=True)
    for tpl in src.glob("*.yaml"):
        if tpl.name not in drop:
            shutil.copyfile(tpl, dest / tpl.name)
    return dest


def test_ingest_only_wiki_scan_lists_nothing(tmp_kb_env: Path) -> None:
    """Acceptance 1 [R1][R2][R3]."""
    raws = [_seed_raw(tmp_kb_env, f"tpl-base-{i}") for i in range(3)]
    for raw in raws:
        result = _ingest(tmp_kb_env, raw)
        assert not result.get("duplicate")

    assert _scan(tmp_kb_env) == ([], [])

    manifest = compiler_mod.load_manifest()
    expected = compiler_mod._template_hashes()[_TEMPLATE_KEY]
    assert _template_keys(manifest) == {_TEMPLATE_KEY: expected}


def test_existing_unequal_template_value_is_kept_and_scan_flags_type(
    tmp_kb_env: Path,
) -> None:
    """Acceptance 2 [R2][R4]."""
    stale = "0" * 32
    assert stale != compiler_mod._template_hashes()[_TEMPLATE_KEY]
    compiler_mod.save_manifest({_TEMPLATE_KEY: stale})

    raws = [_seed_raw(tmp_kb_env, f"tpl-stale-{i}") for i in range(2)]
    for raw in raws:
        _ingest(tmp_kb_env, raw)

    manifest = compiler_mod.load_manifest()
    assert manifest[_TEMPLATE_KEY] == stale

    new_sources, changed_sources = _scan(tmp_kb_env)
    listed = {p.resolve() for p in new_sources + changed_sources}
    assert listed == {r.resolve() for r in raws}


# Manifest-lock acquisitions made by ONE successful first ingest of a source, all
# through `kb.ingest.pipeline.file_lock(HASH_MANIFEST)`:
#   1. `_is_duplicate_content_locked` - the read-only duplicate check;
#   2. `_clear_ingest_manifest_entry` - the pre-body entry clear (the lock is
#      taken even when the key is absent; it saves only when the key exists);
#   3. `_commit_ingest_manifest` - the commit, which writes the source hash and
#      the template baseline in one save.
# Writing the baseline must not add an acquisition.
_MANIFEST_LOCKS_PER_INGEST = 3


class _ManifestSpy:
    """Record each `file_lock(HASH_MANIFEST)` acquisition and the saves inside it."""

    def __init__(self, monkeypatch) -> None:
        self.acquisitions = 0
        self.active: int | None = None  # 1-based index of the held acquisition
        self.saves: list[tuple[dict, int | None]] = []  # (snapshot, acquisition)
        real_file_lock = pipeline_mod.file_lock
        real_save = compiler_mod.save_manifest
        manifest_path = Path(compiler_mod.HASH_MANIFEST)

        @contextmanager
        def spy_lock(path, *args, **kwargs):
            is_manifest = Path(path) == manifest_path
            with real_file_lock(path, *args, **kwargs):
                if not is_manifest:
                    yield
                    return
                self.acquisitions += 1
                outer, self.active = self.active, self.acquisitions
                try:
                    yield
                finally:
                    self.active = outer

        def spy_save(manifest, *args, **kwargs):
            self.saves.append((dict(manifest), self.active))
            return real_save(manifest, *args, **kwargs)

        monkeypatch.setattr(pipeline_mod, "file_lock", spy_lock)
        monkeypatch.setattr(compiler_mod, "save_manifest", spy_save)

    def reset(self) -> None:
        self.acquisitions = 0
        self.saves = []


def test_source_hash_and_template_key_land_in_one_locked_save(
    tmp_kb_env: Path, monkeypatch
) -> None:
    """Acceptance 3 [R1]: one save, inside the commit acquisition, no extra lock."""
    raw = _seed_raw(tmp_kb_env, "tpl-one-save")
    source_ref = "raw/articles/tpl-one-save.md"
    source_hash = hash_bytes(raw.read_bytes())
    expected_tpl = compiler_mod._template_hashes()[_TEMPLATE_KEY]

    spy = _ManifestSpy(monkeypatch)
    _ingest(tmp_kb_env, raw)

    assert spy.acquisitions == _MANIFEST_LOCKS_PER_INGEST
    with_source = [(m, a) for m, a in spy.saves if m.get(source_ref) == source_hash]
    with_template = [(m, a) for m, a in spy.saves if _TEMPLATE_KEY in m]
    assert len(with_source) == 1
    assert with_template == with_source
    snapshot, acquisition = with_source[0]
    assert snapshot[_TEMPLATE_KEY] == expected_tpl
    # The commit is the last acquisition; it holds exactly this one save.
    assert acquisition == _MANIFEST_LOCKS_PER_INGEST
    assert [a for _, a in spy.saves] == [_MANIFEST_LOCKS_PER_INGEST]


def test_baseline_write_adds_no_manifest_lock_acquisition(tmp_kb_env: Path, monkeypatch) -> None:
    """Acceptance 3 [R1]: an ingest that writes the baseline and one that finds it
    present make the same number of manifest-lock acquisitions."""
    first = _seed_raw(tmp_kb_env, "tpl-lock-writes")
    second = _seed_raw(tmp_kb_env, "tpl-lock-present")
    spy = _ManifestSpy(monkeypatch)

    _ingest(tmp_kb_env, first)
    writes_baseline = spy.acquisitions
    assert _TEMPLATE_KEY in compiler_mod.load_manifest()

    spy.reset()
    _ingest(tmp_kb_env, second)
    baseline_present = spy.acquisitions

    assert (writes_baseline, baseline_present) == (
        _MANIFEST_LOCKS_PER_INGEST,
        _MANIFEST_LOCKS_PER_INGEST,
    )


def test_absent_template_file_writes_no_template_key(
    tmp_kb_env: Path, tmp_path: Path, monkeypatch
) -> None:
    """Acceptance 4 [R1]."""
    tpl_dir = _copy_templates(
        compiler_mod.TEMPLATES_DIR, tmp_path / "templates", drop=("article.yaml",)
    )
    monkeypatch.setattr(compiler_mod, "TEMPLATES_DIR", tpl_dir)
    assert _TEMPLATE_KEY not in compiler_mod._template_hashes()

    raw = _seed_raw(tmp_kb_env, "tpl-absent")
    _ingest(tmp_kb_env, raw)

    manifest = compiler_mod.load_manifest()
    assert manifest["raw/articles/tpl-absent.md"] == hash_bytes(raw.read_bytes())
    assert _template_keys(manifest) == {}


def test_template_edited_mid_ingest_records_pre_edit_hash(
    tmp_kb_env: Path, tmp_path: Path, monkeypatch
) -> None:
    """Lead design: the baseline is the template hash captured when the ingest began.

    An edit to the template while the ingest body runs must stay visible to the
    scan, so the manifest holds the pre-edit hash and the article sources are
    listed as changed.
    """
    tpl_dir = _copy_templates(compiler_mod.TEMPLATES_DIR, tmp_path / "templates")
    monkeypatch.setattr(compiler_mod, "TEMPLATES_DIR", tpl_dir)
    pre_edit = compiler_mod._template_hashes()[_TEMPLATE_KEY]

    real_body = pipeline_mod._run_ingest_body

    def body_with_template_edit(*args, **kwargs):
        article = tpl_dir / "article.yaml"
        article.write_bytes(article.read_bytes() + b"\n# edited during ingest\n")
        return real_body(*args, **kwargs)

    monkeypatch.setattr(pipeline_mod, "_run_ingest_body", body_with_template_edit)

    raw = _seed_raw(tmp_kb_env, "tpl-mid-edit")
    _ingest(tmp_kb_env, raw)

    assert compiler_mod._template_hashes()[_TEMPLATE_KEY] != pre_edit
    manifest = compiler_mod.load_manifest()
    assert manifest.get(_TEMPLATE_KEY) == pre_edit

    new_sources, changed_sources = _scan(tmp_kb_env)
    assert {p.resolve() for p in new_sources + changed_sources} == {raw.resolve()}
