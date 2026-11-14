"""Probe `linker`: precision and recall of `kb.compile.linker.inject_wikilinks`.

Arm `inject`: for each row, a fresh wiki under `ctx.tmp` holds the target page
(`target_id`, `title`) and one other page whose body is `body`; the probe calls
`inject_wikilinks(title, target_id, wiki_dir)` once and counts the row as linked
when the other page holds more wikilinks to `target_id` after the call than before.

Positive is `should_link` true. Case set: `ctx.data / "cases.jsonl"`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

CATEGORY_LINK = {
    "proper-mention": True,
    "cjk-in-cjk": True,
    "common-word": False,
    "case-variant": False,
    "inside-code": False,
    "already-linked": False,
}
FIELDS = ("id", "category", "title", "target_id", "body", "should_link", "why")
STRING_FIELDS = ("id", "category", "title", "target_id", "body", "why")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
# The page that holds `body`; a row may not use its id as the target.
BODY_PAGE = "summaries/linker-probe-body"


def load_cases(path: Path) -> list[dict]:
    """Read and check the case set; raise ValueError naming the file and line on a bad line."""
    from kb.utils.pages import WIKI_SUBDIRS

    rows: list[dict] = []
    seen: set[str] = set()
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):

            def bad(cause: str, number: int = number) -> ValueError:
                return ValueError(f"{path} line {number}: {cause}")

            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise bad(f"not JSON ({exc.msg})") from None
            if not isinstance(row, dict):
                raise bad("not a JSON object")
            for field in FIELDS:
                if field not in row:
                    raise bad(f"missing field {field!r}")
            for field in STRING_FIELDS:
                if not isinstance(row[field], str):
                    raise bad(f"field {field!r} is not a string")
            if row["id"] in seen:
                raise bad(f"repeated id {row['id']!r}")
            if row["category"] not in CATEGORY_LINK:
                raise bad(f"unknown category {row['category']!r}")
            expected = CATEGORY_LINK[row["category"]]
            if row["should_link"] is not expected:
                raise bad(
                    f"should_link {row['should_link']!r} is not {expected!r} "
                    f"for category {row['category']!r}"
                )
            subdir, _, slug = row["target_id"].partition("/")
            if (
                subdir not in WIKI_SUBDIRS
                or not SLUG.fullmatch(slug)
                or row["target_id"] == BODY_PAGE
            ):
                raise bad(f"target_id {row['target_id']!r} is not a page id <subdir>/<slug>")
            seen.add(row["id"])
            rows.append(row)
    return rows


def links_to(path: Path, target_id: str) -> int:
    from kb.utils.markdown import extract_wikilinks

    return extract_wikilinks(path.read_text(encoding="utf-8")).count(target_id)


def link_row(row: dict, wiki_dir: Path) -> bool:
    """Build the two-page wiki for one row, call inject_wikilinks once, report a new link."""
    # Looked up at call time so a test can replace the function on the module.
    from kb.compile import linker

    target = wiki_dir / f"{row['target_id']}.md"
    page = wiki_dir / f"{BODY_PAGE}.md"
    for path in (target, page):
        path.parent.mkdir(parents=True, exist_ok=True)
    title = json.dumps(row["title"], ensure_ascii=False)
    target.write_bytes(f"---\ntitle: {title}\n---\n# {row['title']}\n".encode())
    page.write_bytes(f'---\ntitle: "Linker probe body"\n---\n{row["body"]}\n'.encode())

    before = links_to(page, row["target_id"])
    linker.inject_wikilinks(row["title"], row["target_id"], wiki_dir)
    return links_to(page, row["target_id"]) > before


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0


def measure(rows: list[dict], linked: list[bool]) -> dict:
    """Return the arm for rows and whether each row was linked."""
    metrics = {}
    for category in CATEGORY_LINK:
        metrics[f"rows_{category}"] = 0
        metrics[f"linked_{category}"] = 0
    tp = fp = fn = tn = 0
    for row, link in zip(rows, linked, strict=True):
        metrics[f"rows_{row['category']}"] += 1
        metrics[f"linked_{row['category']}"] += int(link)
        if row["should_link"] and link:
            tp += 1
        elif row["should_link"]:
            fn += 1
        elif link:
            fp += 1
        else:
            tn += 1
    metrics.update(
        tp=tp, fp=fp, fn=fn, tn=tn, precision=ratio(tp, tp + fp), recall=ratio(tp, tp + fn)
    )
    return {"status": "measured", "cases": len(rows), "metrics": metrics}


def run(ctx) -> dict:
    rows = load_cases(Path(ctx.data) / "cases.jsonl")
    linked = [
        link_row(row, Path(ctx.tmp) / f"row-{index:03d}" / "wiki")
        for index, row in enumerate(rows, start=1)
    ]
    return {"invariants": ["I11"], "arms": {"inject": measure(rows, linked)}}
