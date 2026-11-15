"""T0-KBFIX-MASKREDOS (#167): `_CODE_MASK_RE` scans an unclosed markdown link or
image opener in linear time and matches the same spans as before."""

from __future__ import annotations

import itertools
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from kb.compile.linker import _CODE_MASK_RE

_REPO_SRC = (Path(__file__).resolve().parent.parent / "src").resolve()
_TIMEOUT_S = 30
# 5,000 characters after the opener: words, spaces and newlines, no parenthesis.
_TAIL = "word word\n" * 500
_FM = (
    '---\ntitle: "Bread"\nsource:\n  - "raw/articles/a.md"\ntype: entity\n'
    "confidence: stated\ncreated: 2026-04-01\nupdated: 2026-04-01\n---\n\n"
)


def _run_bounded(script: str, *args: str) -> dict:
    """Run ``script`` in a fresh interpreter that imports ``kb`` from this checkout.

    A regex scan holds the GIL and the pre-fix pattern never finishes on these
    inputs, so the time limit is enforced from outside the process. The script
    prints one JSON object as its last stdout line.
    """
    env = {
        **os.environ,
        "PYTHONPATH": str(_REPO_SRC) + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script, *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            env=env,
        )
    except subprocess.TimeoutExpired:
        proc = None
    assert proc is not None, f"did not finish within the {_TIMEOUT_S} s subprocess timeout"
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    # The subprocess must exercise this checkout's linker, not another install.
    assert Path(result["linker"]).resolve().is_relative_to(_REPO_SRC), result["linker"]
    return result


def _write_page(wiki: Path, body: str) -> Path:
    path = wiki / "entities" / "bread.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((_FM + body).encode("utf-8"))
    return path


# --- Acceptance 1 [R1] -----------------------------------------------------

_MASK_SCRIPT = """
import json, sys, time
from pathlib import Path
from kb.compile import linker
text = Path(sys.argv[1]).read_bytes().decode("utf-8")
start = time.perf_counter()
_masked_text, masked, _prefix = linker._mask_code_blocks(text)
seconds = time.perf_counter() - start
print(json.dumps({"linker": linker.__file__, "seconds": seconds, "masked": masked}))
"""


@pytest.mark.parametrize("opener", ["see [x](", "see ![x]("], ids=["link", "image"])
def test_unclosed_opener_is_masked_in_under_a_second(tmp_path, opener):
    text_file = tmp_path / "text.md"
    text_file.write_bytes((opener + _TAIL).encode("utf-8"))
    result = _run_bounded(_MASK_SCRIPT, str(text_file))
    assert (result["masked"], result["seconds"] < 1.0) == ([], True), result["seconds"]


# --- Acceptance 2 [R3] -----------------------------------------------------

_INJECT_SCRIPT = """
import json, sys
from pathlib import Path
from kb.compile import linker
updated = linker.inject_wikilinks("Hydration", "concepts/hydration", wiki_dir=Path(sys.argv[1]))
print(json.dumps({"linker": linker.__file__, "updated": updated}))
"""


def test_inject_wikilinks_links_a_page_holding_an_unclosed_opener(tmp_path):
    wiki = tmp_path / "wiki"
    page = _write_page(wiki, "Hydration matters. See [x](" + _TAIL)
    result = _run_bounded(_INJECT_SCRIPT, str(wiki))
    assert result["updated"] == ["entities/bread"]
    assert page.read_bytes().decode("utf-8") == (
        _FM + "[[concepts/hydration|Hydration]] matters. See [x](" + _TAIL
    )


# --- Acceptance 3 [R3] -----------------------------------------------------

_FIX_DEAD_LINKS_SCRIPT = """
import json, sys
from pathlib import Path
from kb.compile import linker
from kb.lint.checks.dead_links import fix_dead_links
fixes = fix_dead_links(Path(sys.argv[1]))
print(json.dumps({"linker": linker.__file__, "targets": [f["target"] for f in fixes]}))
"""


def test_fix_dead_links_fixes_a_page_holding_an_unclosed_opener(tmp_path):
    wiki = tmp_path / "wiki"
    page = _write_page(wiki, "Links to [[missing/page]]. See [x](" + _TAIL)
    result = _run_bounded(_FIX_DEAD_LINKS_SCRIPT, str(wiki))
    assert result["targets"] == ["missing/page"]
    assert page.read_bytes().decode("utf-8") == _FM + "Links to page. See [x](" + _TAIL


# --- Acceptance 4 [R2] -----------------------------------------------------

# `_CODE_MASK_RE` on main before this card, copied verbatim: the oracle for R2.
_PRE_FIX_RE = re.compile(
    r"```.*?```|~~~.*?~~~|`[^`\n]+`"
    r"|!\[(?:[^\]]*)\]\((?:[^()]*|\([^()]*\))*\)"
    r"|\[(?:[^\]]*)\]\((?:[^()]*|\([^()]*\))*\)",
    re.DOTALL,
)

# At most four 3-character tokens follow any "](" in a length-5 product, so the
# pre-fix pattern stays fast on every generated case.
_TOKENS = ["[", "]", "(", ")", "!", "`", "```", "~~~", "a", "\n", "](", "x y"]

# Literal inputs of the existing `_CODE_MASK_RE` / `_mask_code_blocks` /
# `_mask_for_injection` tests (tests/test_compile.py, tests/test_kbfix_linker_headings.py).
_EXISTING_INPUTS = [
    "~~~python\nfoo_entity()\n~~~",
    "See [OpenAI](https://openai.com) for details.",
    "Here is ![diagram](./img/arch.png) inline.",
    "```python\nprint('hello')\n```",
    "Use `compile_wiki()` to compile.",
    "Visit [OpenAI](https://openai.com) for more.",
    "hello `world`",
    "`a`",
    "`b`",
    "Here is `inline code` and ```block code``` in text.",
    "Use `foo()` here.",
    "Normal text.\n```\ncode block\n```\nMore text.",
    "Before `inline code` after.",
    "Start ```\nblock1\n``` middle ```\nblock2\n``` end",
    "Inline `code1` text ```\nblock\n``` and `code2` end",
    "# Hydration\nUse `water` and [docs](http://x/y) and ![pic](a.png).\n\n"
    "```py\n# not a heading\n```\n\n### From `raw/articles/high-hydration.md`\n",
    "See [docs\n## link](url) Hydration\n\nHydration matters.\n",
    "## [docs](\nurl) Hydration matters.\n",
    "",
    "plain text, no markup\n",
    "## Hydration from `raw/a.md`\nbody `x` [l](u)\n",
    "```\n# not a heading\n```\n## after fence\n",
    "![pic\n## alt](a.png) Hydration\n",
    "# Title\r\n\r\nSee [docs\r\n## link](url) Hydration\r\n`c` text\r\n",
    "Use `water` and [docs](http://x/y) and ![pic](a.png).\n\n```py\n# c\n```\n",
    "`a``b` [x](\ny) `c`\n",
    "#tag only\n",
]

# The 512 generated cases of `test_every_commonmark_heading_line_is_protected`.
_DIFF_PIECES = [
    "Hydration text.",
    "## Hydration head",
    "See [docs",
    "## link](url) Hydration",
    "## [docs](",
    "url) Hydration tail.",
    "```\n# Hydration in fence\n```",
    "`code` Hydration and ![i](p.png)",
]
_DIFF_TAIL = "\n)\n)\n)\n"


def _spans(pattern: re.Pattern[str], text: str) -> list[tuple[int, int]]:
    return [m.span() for m in pattern.finditer(text)]


def _disagreements(cases: list[str]) -> list[str]:
    return [c for c in cases if _spans(_CODE_MASK_RE, c) != _spans(_PRE_FIX_RE, c)]


def test_generated_inputs_match_the_pre_fix_spans():
    cases = ["".join(p) for p in itertools.product(_TOKENS, repeat=5)]
    assert len(cases) == 248_832
    assert _disagreements(cases) == []


def test_existing_test_inputs_match_the_pre_fix_spans():
    cases = _EXISTING_INPUTS + [
        "\n".join(p) + _DIFF_TAIL for p in itertools.product(_DIFF_PIECES, repeat=3)
    ]
    assert len(cases) == len(_EXISTING_INPUTS) + 512
    assert _disagreements(cases) == []
