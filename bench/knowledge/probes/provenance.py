"""Probe `provenance`: what one `wrong` rating, a cut-down refine and capture sources do.

Arms:

- `trust`: for k of 1, 3 and 10, one call of
  `kb.feedback.store.add_feedback_entry("bench question", "wrong", pages,
  path=...)` with k page ids and a score file that does not exist yet under
  `ctx.tmp`. Reads that file as JSON and reports, for the i-th cited page,
  `trust_k<k>_p<i>` (its stored `trust`) and `wrong_k<k>_p<i>` (its stored
  `wrong` count). A page with no stored entry raises ValueError.
- `refine`: for a ratio of 50, 10, 1 and 0 percent, a wiki of its own under
  `ctx.tmp` with one page whose body is 20 different sentences (at least 2000
  characters), then `kb.review.refiner.refine_page(page_id, new_body, "bench",
  wiki_dir=..., history_path=...)` with `new_body` the first ratio percent of the
  body's characters. `accepted_<ratio>` is 1 when the page file's text after the
  closing frontmatter fence, outer white space removed, equals `new_body` with
  outer white space removed. `refused_<ratio>` is 1 when the call raised an
  Exception or returned a mapping with an `error` key. A failure of the probe's
  own page write is not caught.
- `captures`: reads every `*.md` file in a subdirectory of `ctx.wiki` and its
  `source` frontmatter in the form `kb` reads it
  (`kb.utils.pages.normalize_sources`: a list, or a single string as a list of
  one). A ref is a capture ref when it starts with `raw/captures/`. Frontmatter
  that fails to load for any reason, undecodable bytes included, leaves the page
  read with no sources. A file that is gone when read (`FileNotFoundError`,
  `NotADirectoryError`) is not read; any other OSError propagates. Unmeasured
  with the reason `no pages` when no page was read.

It makes no model call, writes nothing under `ctx.wiki` or `ctx.raw` and judges
no value.

Spec: specs/kb-baseline.md (R9); card specs/tasks/T1-KBEVAL-PROVENANCE.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

KS = (1, 3, 10)
RATIOS = (50, 10, 1, 0)
QUESTION = "bench question"
PAGE_ID = "concepts/bench-page"
CAPTURE_PREFIX = "raw/captures/"
FRONTMATTER = re.compile(r"\A---\r?\n.*?\r?\n---[ \t]*\r?\n", re.DOTALL)
SUBJECTS = (
    "ledger",
    "harbour",
    "orchard",
    "lantern",
    "bridge",
    "kettle",
    "meadow",
    "compass",
    "quarry",
    "violin",
    "glacier",
    "pigeon",
    "anvil",
    "tram",
    "walnut",
    "beacon",
    "canal",
    "saddle",
    "furnace",
    "mosaic",
)


def run(ctx) -> dict:
    tmp = Path(ctx.tmp)
    return {
        "invariants": ["I6", "I9"],
        "arms": {
            "trust": trust_arm(tmp),
            "refine": refine_arm(tmp),
            "captures": captures_arm(ctx, Path(ctx.wiki)),
        },
    }


# -- trust ----------------------------------------------------------------------------


def stored_score(path: Path, data: object, pid: str, key: str):
    entry = data.get("page_scores", {}).get(pid) if isinstance(data, dict) else None
    if not isinstance(entry, dict) or key not in entry:
        raise ValueError(f"{path.name}: no stored {key} for cited page {pid}")
    return entry[key]


def trust_arm(tmp: Path) -> dict:
    from kb.feedback import store

    metrics: dict[str, float] = {}
    for k in KS:
        pages = [f"concepts/bench-cited-{i:02d}" for i in range(1, k + 1)]
        path = tmp / f"trust-k{k}" / "feedback.json"
        path.parent.mkdir(parents=True)
        store.add_feedback_entry(QUESTION, "wrong", pages, path=path)
        data = json.loads(path.read_bytes().decode("utf-8"))
        for i, pid in enumerate(pages, start=1):
            metrics[f"trust_k{k}_p{i}"] = stored_score(path, data, pid, "trust")
            metrics[f"wrong_k{k}_p{i}"] = stored_score(path, data, pid, "wrong")
    return {"status": "measured", "cases": len(KS), "metrics": metrics}


# -- refine ---------------------------------------------------------------------------


def page_body() -> str:
    sentences = [
        f"Sentence {n:02d} of the bench page is about the {subject}, and it is written out "
        f"at this length so that the twenty sentences together pass two thousand characters."
        for n, subject in enumerate(SUBJECTS, start=1)
    ]
    return " ".join(sentences)


def write_refine_wiki(base: Path, body: str) -> Path:
    wiki = base / "wiki"
    page = wiki / f"{PAGE_ID}.md"
    page.parent.mkdir(parents=True)
    text = (
        "---\n"
        'title: "Bench Page"\n'
        "source:\n"
        '  - "raw/articles/bench-page.md"\n'
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "type: concept\n"
        "confidence: stated\n"
        "---\n"
        "\n"
        f"{body}\n"
    )
    page.write_bytes(text.encode("utf-8"))
    return wiki


def body_after(page: Path) -> str:
    text = page.read_bytes().decode("utf-8")
    match = FRONTMATTER.match(text)
    return text[match.end() :] if match else text


def refine_arm(tmp: Path) -> dict:
    from kb.review import refiner

    body = page_body()
    metrics: dict[str, int] = {}
    for ratio in RATIOS:
        base = tmp / f"refine-{ratio}"
        wiki = write_refine_wiki(base, body)
        new_body = body[: len(body) * ratio // 100]
        refused = 0
        try:
            result = refiner.refine_page(
                PAGE_ID,
                new_body,
                "bench",
                wiki_dir=wiki,
                history_path=base / ".data" / "review_history.json",
            )
        except Exception:
            refused = 1
        else:
            refused = int(isinstance(result, dict) and "error" in result)
        accepted = body_after(wiki / f"{PAGE_ID}.md").strip() == new_body.strip()
        metrics[f"accepted_{ratio}"] = int(accepted)
        metrics[f"refused_{ratio}"] = refused
    return {"status": "measured", "cases": len(RATIOS), "metrics": metrics}


# -- captures -------------------------------------------------------------------------


def read_sources(path: Path) -> tuple[bool, list[str], dict]:
    """Return (read, refs, metadata); read is False when the file is gone."""
    import frontmatter

    from kb.utils.pages import normalize_sources

    try:
        data = path.read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        return False, [], {}
    try:
        text = data.decode("utf-8").lstrip("﻿")
        metadata = frontmatter.loads(text).metadata
    except Exception:  # frontmatter that fails to load for any reason
        return True, [], {}
    if not isinstance(metadata, dict):
        return True, [], {}
    return True, normalize_sources(metadata.get("source")), metadata


def captures_arm(ctx, wiki: Path) -> dict:
    files = sorted(
        p for p in wiki.rglob("*.md") if len(p.relative_to(wiki).parts) > 1 and not p.is_dir()
    )
    counts = dict.fromkeys(
        (
            "pages_with_sources",
            "pages_any_capture_source",
            "pages_all_capture_sources",
            "refs_total",
            "refs_captures",
            "stated_all_capture",
            "confirmed_all_capture",
        ),
        0,
    )
    cases = 0
    for path in files:
        read, refs, metadata = read_sources(path)
        if not read:
            continue
        cases += 1
        captures = [ref.startswith(CAPTURE_PREFIX) for ref in refs]
        counts["refs_total"] += len(refs)
        counts["refs_captures"] += sum(captures)
        if not refs:
            continue
        counts["pages_with_sources"] += 1
        counts["pages_any_capture_source"] += any(captures)
        if all(captures):
            counts["pages_all_capture_sources"] += 1
            counts["stated_all_capture"] += metadata.get("confidence") == "stated"
            counts["confirmed_all_capture"] += metadata.get("belief_state") == "confirmed"
    if cases == 0:
        return ctx.unmeasured("no pages")
    return {"status": "measured", "cases": cases, "metrics": counts}
